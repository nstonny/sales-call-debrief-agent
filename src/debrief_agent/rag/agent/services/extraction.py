"""
services/extraction.py

Runs the LLM metadata extraction pass on a raw transcript.
Extracts: rep_name, contact_name, contact_title, deal_stage.

Uses the OpenAI Responses API structured parser (`client.responses.parse`).
Uses Pydantic (`CallMetadataExtraction`) directly as the response format model.

Primary API:
  - `MetadataExtractor.extract(...)` is the class-based entrypoint.

Behaviour on failure:
  - If the OpenAI call fails (network error, API error, rate limit) -> raises HTTPException 502.
  - If the LLM returns a refusal -> raises HTTPException 502.
  - If the response cannot be parsed / validated by Pydantic -> raises HTTPException 502.
  In all failure cases the caller (upload route) will roll back the transaction.

Langfuse metadata (current span):
- service: "extraction"
- model: str (DEBRIEF_EXTRACTION_MODEL, default "gpt-4.1-mini")
- trace_id: str | None
- session_id: str | None (`call.id` in upload flow; unset in some non-API flows)
- had_refusal: bool
- validation_ok: bool
- error_type: "none" | "openai_error" | "llm_refusal" | "validation_error"
"""

import logging
import os
from typing import Any, cast

from fastapi import HTTPException
from langfuse.openai import AsyncOpenAI
from openai import OpenAIError
from pydantic import ValidationError

from debrief_agent.core.config import OPENAI_API_KEY
from debrief_agent.core.observability import (
    get_current_trace_id,
    observe,
    update_current_span_metadata,
)
from debrief_agent.rag.agent.prompts.extraction import (
    EXTRACTION_SYSTEM_PROMPT,
    build_extraction_user_message,
)
from debrief_agent.schemas.extraction import CallMetadataExtraction

logger = logging.getLogger(__name__)

# Extraction is a single structured parse, so it defaults to a cheaper, faster
# model than the tool-calling analysis agent. Mirrors DEFAULT_MODEL_NAME in
# services/analysis.py.
DEFAULT_MODEL_NAME = os.getenv("DEBRIEF_EXTRACTION_MODEL", "gpt-4.1-mini")

# Reusable async client — one instance for the lifetime of the process
_client = AsyncOpenAI(api_key=OPENAI_API_KEY)


class MetadataExtractor:
    """Service class that extracts structured call metadata from transcript text."""

    def __init__(
        self,
        client: AsyncOpenAI | None = None,
        model_name: str | None = None,
    ) -> None:
        self._client = client or _client
        self._model_name = model_name or DEFAULT_MODEL_NAME

    @observe(name="metadata.extract", as_type="span", capture_input=False, capture_output=False)
    async def extract(self, transcript: str, session_id: str | None = None) -> dict:
        """Return rep/contact/deal-stage metadata parsed and validated with Pydantic.

        `session_id` is optional and is used only for tracing correlation.
        """

        trace_id = get_current_trace_id()
        trace_metadata: dict[str, Any] = {
            "service": "extraction",
            "model": self._model_name,
            "trace_id": trace_id,
            "session_id": session_id,
            "had_refusal": False,
            "validation_ok": False,
            "error_type": "none",
        }
        update_current_span_metadata(trace_metadata)

        # --- Call the LLM via Responses API with structured Pydantic parsing ---
        try:
            response = await cast(Any, self._client.responses).parse(
                model=self._model_name,  # fast and cheap — ideal for structured extraction
                instructions=EXTRACTION_SYSTEM_PROMPT,
                input=build_extraction_user_message(transcript),
                temperature=0,  # deterministic — extraction should not be creative
                text_format=CallMetadataExtraction,
            )
        except OpenAIError as exc:
            trace_metadata["error_type"] = "openai_error"
            update_current_span_metadata(trace_metadata)
            logger.error(
                "OpenAI API call failed during metadata extraction (trace_id=%s): %s",
                trace_id,
                exc,
            )
            raise HTTPException(
                status_code=502,
                detail=f"LLM extraction failed — OpenAI API error: {exc}",
            ) from exc

        # --- Check for LLM refusal before parsing ---
        # next() scans all output items and their content parts, returning the first
        # refusal it finds, or None if there is no refusal in the response.
        refusal_part = next(
            (
                content_part
                for item in (response.output or [])
                for content_part in (getattr(item, "content", None) or [])
                if getattr(content_part, "type", None) == "refusal"
            ),
            None,  # default: no refusal found
        )

        if refusal_part:
            trace_metadata["had_refusal"] = True
            trace_metadata["error_type"] = "llm_refusal"
            update_current_span_metadata(trace_metadata)
            refusal_text = getattr(refusal_part, "refusal", "No reason given.")
            logger.warning(
                "LLM refused metadata extraction request (trace_id=%s). Reason: %s",
                trace_id,
                refusal_text,
            )
            raise HTTPException(
                status_code=502,
                detail=f"LLM refused to process the transcript: {refusal_text}",
            )

        # --- Read parsed model and validate fallback payloads when needed ---
        try:
            parsed_payload = getattr(response, "output_parsed", None)
            if parsed_payload is None:
                parsed_payload = next(
                    (
                        getattr(content_part, "parsed", None)
                        for item in (response.output or [])
                        for content_part in (getattr(item, "content", None) or [])
                        if getattr(content_part, "type", None) in {"output_text", "text"}
                    ),
                    None,
                )

            if parsed_payload is None:
                raise ValueError("No parsed payload returned by Responses API")

            metadata = (
                parsed_payload
                if isinstance(parsed_payload, CallMetadataExtraction)
                else CallMetadataExtraction.model_validate(parsed_payload)
            )
        except (ValidationError, ValueError, TypeError) as exc:
            trace_metadata["validation_ok"] = False
            trace_metadata["error_type"] = "validation_error"
            update_current_span_metadata(trace_metadata)
            logger.error(
                "LLM response failed Pydantic validation (trace_id=%s). Parsed payload: %r — Errors: %s",
                trace_id,
                getattr(response, "output_parsed", None),
                exc,
            )
            raise HTTPException(
                status_code=502,
                detail="LLM extraction failed — response did not match expected schema.",
            ) from exc

        trace_metadata["validation_ok"] = True
        update_current_span_metadata(trace_metadata)
        return metadata.model_dump()
