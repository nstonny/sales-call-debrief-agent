"""
services/analysis.py

Runs the LLM analysis (debrief) pass on a sales call transcript.
Generates: summary, strengths, areas_for_improvement, action_items,
           objections_raised, competitor_mentioned, next_steps, sentiment, score.

Uses the OpenAI Responses API (client.responses.create).
Uses Pydantic (AnalysisResult) for JSON parsing, validation, and normalisation.

Behaviour on failure:
  - If the OpenAI call fails (network error, API error, rate limit) → raises HTTPException 502.
  - If the LLM returns a refusal → raises HTTPException 502.
  - If the response cannot be parsed / validated by Pydantic → raises HTTPException 502.
  In all failure cases the caller (upload route) will roll back the transaction.
"""

import logging

from fastapi import HTTPException
from openai import AsyncOpenAI, OpenAIError
from pydantic import ValidationError

from debrief_agent.core.config import OPENAI_API_KEY
from debrief_agent.prompts.analysis import (
    ANALYSIS_SYSTEM_PROMPT,
    build_analysis_user_message,
)
from debrief_agent.schemas.analysis import AnalysisResult

logger = logging.getLogger(__name__)

# Reusable async client — one instance for the lifetime of the process
_client = AsyncOpenAI(api_key=OPENAI_API_KEY)


async def generate_call_analysis(transcript: str, metadata: dict) -> dict:
    """
    Send the transcript and call metadata to the OpenAI Responses API
    and return a structured debrief.

    Args:
        transcript: The raw transcript text.
        metadata:   Dict with keys rep_name, contact_name, contact_title, deal_stage.
                    Used to personalise the coaching prompt.

    Returns a dict with all AnalysisResult fields. Each value is a string,
    list, float, or None.

    Raises HTTPException(502) on any failure so the upload transaction is
    rolled back and the caller receives a clear error message.
    """
    # --- Call the LLM via Responses API ---
    try:
        response = await _client.responses.create(
            model="gpt-4.1-mini",          # fast and cheap for structured generation
            instructions=ANALYSIS_SYSTEM_PROMPT,
            input=build_analysis_user_message(transcript, metadata),
            temperature=0.3,              # slight creativity for narrative fields
            text={"format": {"type": "json_object"}},  # guarantees valid JSON output
        )
    except OpenAIError as exc:
        logger.error("OpenAI API call failed during analysis generation: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"LLM analysis failed — OpenAI API error: {exc}",
        )

    # --- Check for LLM refusal before parsing ---
    # next() scans all output items and their content parts, returning the first
    # refusal it finds, or None if there is no refusal in the response.
    refusal_part = next(
        (
            content_part
            for item in response.output
            if hasattr(item, "content")
            for content_part in item.content
            if getattr(content_part, "type", None) == "refusal"
        ),
        None,  # default: no refusal found
    )

    if refusal_part:
        refusal_text = getattr(refusal_part, "refusal", "No reason given.")
        logger.warning("LLM refused analysis generation request. Reason: %s", refusal_text)
        raise HTTPException(
            status_code=502,
            detail=f"LLM refused to analyse the transcript: {refusal_text}",
        )

    # --- Parse + validate + normalise via Pydantic ---
    # model_validate_json handles JSON parsing, field validation (incl. score range 0–10),
    # and empty-string → None normalisation in one step.
    raw_content = response.output_text or ""

    try:
        result = AnalysisResult.model_validate_json(raw_content)
    except ValidationError as exc:
        logger.error(
            "LLM analysis response failed Pydantic validation. Raw content: %r — Errors: %s",
            raw_content,
            exc,
        )
        raise HTTPException(
            status_code=502,
            detail="LLM analysis failed — response did not match expected schema.",
        )

    return result.model_dump()

