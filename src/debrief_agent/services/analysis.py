"""
services/analysis.py

Runs the LLM analysis (debrief) pass on a sales call transcript.
Generates: summary, strengths, areas_for_improvement, action_items,
           objections_raised, competitor_mentioned, next_steps, sentiment, score.

Runtime behavior:
- Loads analysis rubrics from backend configuration (DEFAULT_ANALYSIS_RUBRICS)
  unless an internal override list is explicitly provided.
- Injects rubric guidance into the analysis system prompt.
- Calls the OpenAI Responses API and validates output with AnalysisResult.

Failure behavior:
- OpenAI/API errors -> HTTPException 502
- LLM refusal -> HTTPException 502
- Invalid schema -> HTTPException 502
- Invalid/missing rubric file -> HTTPException 422
"""

import logging
from typing import Any, cast

from fastapi import HTTPException
from openai import AsyncOpenAI, OpenAIError
from pydantic import ValidationError

from debrief_agent.core.config import DEFAULT_ANALYSIS_RUBRICS, OPENAI_API_KEY
from debrief_agent.prompts.analysis import (
    build_analysis_system_prompt,
    build_analysis_user_message,
)
from debrief_agent.prompts.rubrics import load_rubric_text
from debrief_agent.schemas.analysis import AnalysisResult

logger = logging.getLogger(__name__)

# Reusable async client — one instance for the lifetime of the process
_client = AsyncOpenAI(api_key=OPENAI_API_KEY)


async def generate_call_analysis(
    transcript: str,
    metadata: dict,
    rubric_names: list[str] | None = None,
) -> dict:
    """
    Generate a structured sales call debrief from transcript + call metadata.

    Rubrics:
    - If ``rubric_names`` is provided, those rubric files are used.
    - Otherwise the backend default rubric set (DEFAULT_ANALYSIS_RUBRICS) is used.
    - Rubric text is appended to the system prompt and treated as strict guidance.

    Args:
        transcript: Raw transcript text.
        metadata: Dict containing rep_name, contact_name, contact_title, deal_stage.
        rubric_names: Optional internal override list of rubric file names
            (with or without ".txt"). Not user-facing.

    Returns:
        A dict matching ``AnalysisResult``.

    Raises:
        HTTPException(422): Rubric names are invalid or rubric files are missing.
        HTTPException(502): OpenAI error, model refusal, or schema validation failure.
    """
    # Resolve rubric set: caller override or backend default.
    effective_rubrics = rubric_names if rubric_names is not None else DEFAULT_ANALYSIS_RUBRICS
    try:
        rubric_text = load_rubric_text(effective_rubrics)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    system_prompt = build_analysis_system_prompt(rubric_text or None)

    # --- Call the LLM via Responses API ---
    try:
        response = await _client.responses.create(
            model="gpt-5-mini",
            instructions=system_prompt,
            input=build_analysis_user_message(transcript, metadata),
            text=cast(Any, {"format": {"type": "json_object"}}),  # guarantees valid JSON output
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
            for item in (response.output or [])
            for content_part in (getattr(item, "content", None) or [])
            if getattr(content_part, "type", None) == "refusal"
        ),
        None,  # default: no refusal found
    )

    if refusal_part:
        refusal_text = getattr(refusal_part, "refusal", "No reason given.")
        logger.warning(
            "LLM refused analysis generation request. Reason: %s",
            refusal_text,
        )
        raise HTTPException(
            status_code=502,
            detail=f"LLM refused to analyse the transcript: {refusal_text}",
        )

    # --- Parse + validate + normalise via Pydantic ---
    # model_validate_json handles JSON parsing, field validation (incl. score range 0–10),
    # and empty-string -> None normalisation in one step.
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
