"""
services/extraction.py

Runs the LLM metadata extraction pass on a raw transcript.
Extracts: rep_name, contact_name, contact_title, deal_stage.

Uses the OpenAI Responses API (client.responses.create).
Uses Pydantic (CallMetadataExtraction) for JSON parsing, validation, and normalisation.

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
from debrief_agent.prompts.extraction import (
    EXTRACTION_SYSTEM_PROMPT,
    build_extraction_user_message,
)
from debrief_agent.schemas.extraction import CallMetadataExtraction

logger = logging.getLogger(__name__)

# Reusable async client — one instance for the lifetime of the process
_client = AsyncOpenAI(api_key=OPENAI_API_KEY)


async def extract_call_metadata(transcript: str) -> dict:
    """
    Send the transcript to the OpenAI Responses API and return extracted metadata.

    Returns a dict with keys: rep_name, contact_name, contact_title, deal_stage.
    Each value is either a string or None.

    Raises HTTPException(502) on any failure so the upload transaction is
    rolled back and the caller receives a clear error message.
    """
    # --- Call the LLM via Responses API ---
    try:
        response = await _client.responses.create(
            model="gpt-4.1-mini",          # fast and cheap — ideal for structured extraction
            instructions=EXTRACTION_SYSTEM_PROMPT,
            input=build_extraction_user_message(transcript),
            temperature=0,                # deterministic — extraction should not be creative
            text={"format": {"type": "json_object"}},  # guarantees valid JSON output
        )
    except OpenAIError as exc:
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
            for item in response.output
            if hasattr(item, "content")
            for content_part in item.content
            if getattr(content_part, "type", None) == "refusal"
        ),
        None,  # default: no refusal found
    )

    if refusal_part:
        refusal_text = getattr(refusal_part, "refusal", "No reason given.")
        logger.warning("LLM refused metadata extraction request. Reason: %s", refusal_text)
        raise HTTPException(
            status_code=502,
            detail=f"LLM refused to process the transcript: {refusal_text}",
        )

    # --- Parse + validate + normalise via Pydantic ---
    # model_validate_json handles JSON parsing, key validation, and empty-string → None
    # normalisation in one step via CallMetadataExtraction.
    raw_content = response.output_text or ""

    try:
        metadata = CallMetadataExtraction.model_validate_json(raw_content)
    except ValidationError as exc:
        logger.error(
            "LLM response failed Pydantic validation. Raw content: %r — Errors: %s",
            raw_content,
            exc,
        )
        raise HTTPException(
            status_code=502,
            detail="LLM extraction failed — response did not match expected schema.",
        )

    return metadata.model_dump()
