"""
services/extraction.py

Runs the LLM metadata extraction pass on a raw transcript.
Extracts: rep_name, contact_name, contact_title, deal_stage.

Uses the OpenAI Responses API (client.responses.create).
Uses Pydantic (CallMetadataExtraction) for JSON parsing, validation, and normalisation.

Primary API:
  - `MetadataExtractor.extract(...)` is the preferred class-based entrypoint.
  - `extract_call_metadata(...)` is kept as a compatibility wrapper for older callers.

Behaviour on failure:
  - If the OpenAI call fails (network error, API error, rate limit) → raises HTTPException 502.
  - If the LLM returns a refusal → raises HTTPException 502.
  - If the response cannot be parsed / validated by Pydantic → raises HTTPException 502.
  In all failure cases the caller (upload route) will roll back the transaction.

Langfuse metadata (current span):
- service: "extraction"
- model: "gpt-4.1-mini"
- had_refusal: bool
- validation_ok: bool
- error_type: "none" | "openai_error" | "llm_refusal" | "validation_error"
"""

import logging
from typing import Any, cast

from fastapi import HTTPException
from langfuse import observe
from langfuse.openai import AsyncOpenAI
from openai import OpenAIError
from pydantic import ValidationError

from debrief_agent.core.config import OPENAI_API_KEY
from debrief_agent.core.observability import update_current_span_metadata
from debrief_agent.prompts.extraction import (
    EXTRACTION_SYSTEM_PROMPT,
    build_extraction_user_message,
)
from debrief_agent.schemas.extraction import CallMetadataExtraction

logger = logging.getLogger(__name__)

# Reusable async client — one instance for the lifetime of the process
_client = AsyncOpenAI(api_key=OPENAI_API_KEY)


class MetadataExtractor:
    """Service class that extracts structured call metadata from transcript text."""

    def __init__(self, client: AsyncOpenAI | None = None) -> None:
        self._client = client or _client

    @observe(name="metadata.extract", as_type="span", capture_input=False, capture_output=False)
    async def extract(self, transcript: str) -> dict:
        """Return rep/contact/deal-stage metadata parsed and validated with Pydantic."""

        trace_metadata: dict[str, Any] = {
            "service": "extraction",
            "model": "gpt-4.1-mini",
            "had_refusal": False,
            "validation_ok": False,
            "error_type": "none",
        }
        update_current_span_metadata(trace_metadata)

        # --- Call the LLM via Responses API ---
        try:
            response = await self._client.responses.create(
                model="gpt-4.1-mini",          # fast and cheap — ideal for structured extraction
                instructions=EXTRACTION_SYSTEM_PROMPT,
                input=build_extraction_user_message(transcript),
                temperature=0,                # deterministic — extraction should not be creative
                text=cast(Any, {"format": {"type": "json_object"}}),  # guarantees valid JSON output
            )
        except OpenAIError as exc:
            trace_metadata["error_type"] = "openai_error"
            update_current_span_metadata(trace_metadata)
            logger.error("OpenAI API call failed during metadata extraction: %s", exc)
            raise HTTPException(
                status_code=502,
                detail=f"LLM extraction failed — OpenAI API error: {exc}",
            )

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
            logger.warning("LLM refused metadata extraction request. Reason: %s", refusal_text)
            raise HTTPException(
                status_code=502,
                detail=f"LLM refused to process the transcript: {refusal_text}",
            )

        # --- Parse + validate + normalise via Pydantic ---
        # model_validate_json handles JSON parsing, key validation, and empty-string -> None
        # normalisation in one step via CallMetadataExtraction.
        raw_content = response.output_text or ""

        try:
            metadata = CallMetadataExtraction.model_validate_json(raw_content)
        except ValidationError as exc:
            trace_metadata["validation_ok"] = False
            trace_metadata["error_type"] = "validation_error"
            update_current_span_metadata(trace_metadata)
            logger.error(
                "LLM response failed Pydantic validation. Raw content: %r — Errors: %s",
                raw_content,
                exc,
            )
            raise HTTPException(
                status_code=502,
                detail="LLM extraction failed — response did not match expected schema.",
            )

        trace_metadata["validation_ok"] = True
        update_current_span_metadata(trace_metadata)
        return metadata.model_dump()


_default_metadata_extractor = MetadataExtractor()


async def extract_call_metadata(transcript: str) -> dict:
    """Compatibility wrapper for legacy callers; new code should use MetadataExtractor."""
    return await _default_metadata_extractor.extract(transcript)
