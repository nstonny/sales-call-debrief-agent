"""
services/extraction.py

Runs the LLM metadata extraction pass on a raw transcript.
Extracts: rep_name, contact_name, contact_title, deal_stage.

Uses the OpenAI Responses API (client.responses.create).

Behaviour on failure:
  - If the OpenAI call fails (network error, API error, rate limit) → raises HTTPException 502.
  - If the response cannot be parsed as valid JSON → raises HTTPException 502.
  - If required keys are missing from the JSON → raises HTTPException 502.
  In all failure cases the caller (upload route) will roll back the transaction.
"""

import json
import logging

from fastapi import HTTPException
from openai import AsyncOpenAI, OpenAIError

from debrief_agent.core.config import OPENAI_API_KEY
from debrief_agent.prompts.extraction import (
    EXTRACTION_SYSTEM_PROMPT,
    build_extraction_user_message,
)

logger = logging.getLogger(__name__)

# Reusable async client — one instance for the lifetime of the process
_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Keys we expect the LLM to return
_EXPECTED_KEYS = {"rep_name", "contact_name", "contact_title", "deal_stage"}


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
            model="gpt-4o-mini",          # fast and cheap — ideal for structured extraction
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

    # --- Parse the response ---
    raw_content = response.output_text or ""

    try:
        extracted: dict = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        logger.error(
            "LLM returned non-JSON content during extraction: %r — %s",
            raw_content,
            exc,
        )
        raise HTTPException(
            status_code=502,
            detail="LLM extraction failed — response was not valid JSON.",
        )

    # --- Validate expected keys are present ---
    missing = _EXPECTED_KEYS - extracted.keys()
    if missing:
        logger.error(
            "LLM extraction response missing keys %s. Full response: %r",
            missing,
            extracted,
        )
        raise HTTPException(
            status_code=502,
            detail=f"LLM extraction failed — missing keys in response: {missing}",
        )

    # --- Normalise: ensure values are str or None (no empty strings) ---
    return {
        key: (extracted[key].strip() if isinstance(extracted[key], str) and extracted[key].strip() else None)
        for key in _EXPECTED_KEYS
    }