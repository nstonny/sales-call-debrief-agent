# ---------------------------------------------------------------------------
# Prompts for the metadata extraction pass.
#
# Goal: extract structured call metadata from a raw transcript so that
# downstream LLM prompts can be personalised (e.g. "You're speaking to a CTO
# at a company in the proposal stage — focus on ROI and risk reduction").
#
# Editing guide:
#   - Adjust EXTRACTION_SYSTEM_PROMPT to change what the LLM is asked to do.
#   - Adjust the field descriptions inside the prompt to refine extraction.
#   - build_extraction_user_message() wraps the transcript for the user turn.
# ---------------------------------------------------------------------------

EXTRACTION_SYSTEM_PROMPT = """
You are a sales intelligence assistant. Your job is to extract structured
metadata from a raw sales call transcript.

Return ONLY a valid JSON object that matches the provided CallMetadataExtraction schema exactly.

Rules:
- include only schema-defined keys
- If a field cannot be determined from the transcript, set it to null.
- For deal_stage, infer from context clues (e.g. reviewing a proposal → "proposal",
  first call with no prior context → "discovery", discussing pricing/discounts → "negotiation").
- Do not add any extra keys or commentary outside the JSON object.
- Do not wrap the JSON in markdown code fences.
""".strip()


def build_extraction_user_message(transcript: str) -> str:
    """Build the extraction user-turn payload.

    Keeps the transcript in the user message while the system prompt enforces
    the `CallMetadataExtraction` JSON schema contract.
    """
    return f"Extract metadata from the following sales call transcript and return it as JSON:\n\n{transcript}"
