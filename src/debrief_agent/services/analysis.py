"""
services/analysis.py

Runs the LLM analysis (debrief) pass on a sales call transcript and returns
structured coaching output.

Generated fields:
- summary
- strengths
- areas_for_improvement
- action_items
- objections_raised
- competitor_mentioned
- next_steps
- sentiment
- score

Runtime behavior:
- Resolves rubric files from backend defaults (`DEFAULT_ANALYSIS_RUBRICS`)
  unless an internal override list is provided.
- Injects all resolved rubric text into the system prompt as strict guidance.
- Calls the OpenAI Responses API structured parser (`client.responses.parse`).
- Uses Pydantic (`AnalysisResult`) directly as the response format model.

Primary API:
- `CallAnalyzer.analyze(...)` is the class-based entrypoint.

Failure behavior:
- OpenAI/API errors -> HTTPException 502
- LLM refusal -> HTTPException 502
- Invalid schema -> HTTPException 502
- Invalid/missing rubric file -> HTTPException 422

Langfuse metadata (current span):
- service: "analysis"
- model: "gpt-5-mini"
- trace_id: str | None
- session_id: str | None (`call.id` in upload flow; unset in some non-API flows)
- had_refusal: bool
- validation_ok: bool
- error_type: "none" | "rubric_error" | "openai_error" | "llm_refusal" | "validation_error"
"""

import logging
from typing import Any, cast

from fastapi import HTTPException
from langfuse.openai import AsyncOpenAI
from openai import OpenAIError
from pydantic import ValidationError

from debrief_agent.core.config import DEFAULT_ANALYSIS_RUBRICS, OPENAI_API_KEY
from debrief_agent.core.observability import (
    get_current_trace_id,
    observe,
    update_current_span_metadata,
)
from debrief_agent.prompts.analysis import (
    build_analysis_system_prompt,
    build_analysis_user_message,
)
from debrief_agent.prompts.rubrics import load_rubric_text
from debrief_agent.schemas.analysis import AnalysisResult

logger = logging.getLogger(__name__)

# Reusable async client -- one instance for the lifetime of the process
_client = AsyncOpenAI(api_key=OPENAI_API_KEY)


class CallAnalyzer:
    """Service class that generates structured debrief analysis for one call."""

    def __init__(self, client: AsyncOpenAI | None = None) -> None:
        self._client = client or _client

    @observe(name="analysis.generate", as_type="span", capture_input=False, capture_output=False)
    async def analyze(
        self,
        transcript: str,
        metadata: dict,
        rubric_names: list[str] | None = None,
        session_id: str | None = None,
    ) -> dict:
        """Generate one validated analysis object from transcript, metadata, and rubrics.

        `session_id` is optional and is used only for tracing correlation.
        """
        trace_id = get_current_trace_id()
        trace_metadata: dict[str, Any] = {
            "service": "analysis",
            "model": "gpt-5-mini",
            "trace_id": trace_id,
            "session_id": session_id,
            "had_refusal": False,
            "validation_ok": False,
            "error_type": "none",
        }
        update_current_span_metadata(trace_metadata)

        # Resolve rubric set: caller override or backend default.
        effective_rubrics = rubric_names if rubric_names is not None else DEFAULT_ANALYSIS_RUBRICS
        try:
            rubric_text = load_rubric_text(effective_rubrics)
        except (FileNotFoundError, ValueError) as exc:
            trace_metadata["error_type"] = "rubric_error"
            update_current_span_metadata(trace_metadata)
            raise HTTPException(status_code=422, detail=str(exc))

        system_prompt = build_analysis_system_prompt(rubric_text or None)

        # --- Call the LLM via Responses API with structured Pydantic parsing ---
        try:
            response = await cast(Any, self._client.responses).parse(
                model="gpt-5-mini",
                instructions=system_prompt,
                input=build_analysis_user_message(transcript, metadata),
                reasoning=cast(Any, {"effort": "medium"}),
                text_format=AnalysisResult,
            )
        except OpenAIError as exc:
            trace_metadata["error_type"] = "openai_error"
            update_current_span_metadata(trace_metadata)
            logger.error(
                "OpenAI API call failed during analysis generation (trace_id=%s): %s",
                trace_id,
                exc,
            )
            raise HTTPException(
                status_code=502,
                detail=f"LLM analysis failed -- OpenAI API error: {exc}",
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
            logger.warning(
                "LLM refused analysis generation request (trace_id=%s). Reason: %s",
                trace_id,
                refusal_text,
            )
            raise HTTPException(
                status_code=502,
                detail=f"LLM refused to analyse the transcript: {refusal_text}",
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

            result = (
                parsed_payload
                if isinstance(parsed_payload, AnalysisResult)
                else AnalysisResult.model_validate(parsed_payload)
            )
        except (ValidationError, ValueError, TypeError) as exc:
            trace_metadata["validation_ok"] = False
            trace_metadata["error_type"] = "validation_error"
            update_current_span_metadata(trace_metadata)
            logger.error(
                "LLM analysis response failed Pydantic validation (trace_id=%s). Parsed payload: %r -- Errors: %s",
                trace_id,
                getattr(response, "output_parsed", None),
                exc,
            )
            raise HTTPException(
                status_code=502,
                detail="LLM analysis failed -- response did not match expected schema.",
            )

        trace_metadata["validation_ok"] = True
        update_current_span_metadata(trace_metadata)
        return result.model_dump()
