# ---------------------------------------------------------------------------
# Prompts for the analysis (debrief) pass.
#
# Goal: generate a full structured debrief of a sales call, personalised
# using the metadata extracted in the first pass (rep name, contact title,
# deal stage, etc.) so the LLM can tailor its coaching accordingly.
#
# This module exposes two prompt builders:
#   - build_analysis_system_prompt(): returns the base system prompt and,
#     when provided, appends rubric text as strict additional guidance.
#   - build_analysis_user_message(): injects metadata context and transcript
#     into the user turn.
# ---------------------------------------------------------------------------

ANALYSIS_SYSTEM_PROMPT = """
You are an expert sales coach. You will be given a sales call transcript
along with context about the call (rep name, contact name and title, deal stage).

Your job is to produce a structured debrief of the call as a JSON object.

Return ONLY a valid JSON object that matches the provided AnalysisResult schema exactly.

Scoring guide for "score":

  5 : Excellent — strong discovery, clear value articulation, objections handled, next step secured
  3 : Average — some positives but notable missed opportunities
  1 : Poor — significant rep errors, relationship or deal likely damaged

Rules:
- include only schema-defined keys
- Use the call context (contact title, deal stage) to calibrate your coaching.
  e.g. if the contact is a CTO, assess technical credibility; if deal stage is
  "negotiation", focus on how well the rep handled pricing pressure.
- For array fields, return an empty array [] if there are none, not null.
- Do not add extra keys or commentary outside the JSON object.
- Do not wrap the JSON in markdown code fences.
""".strip()


def build_analysis_system_prompt(rubric_text: str | None = None) -> str:
    """Build the system prompt used for structured analysis generation.

    When `rubric_text` is provided, it is appended as strict evaluation
    guidance. In rubric-enabled runs, rubric scoring instructions override
    the default score examples embedded in `ANALYSIS_SYSTEM_PROMPT`.
    """
    if not rubric_text:
        return ANALYSIS_SYSTEM_PROMPT

    return (
        f"{ANALYSIS_SYSTEM_PROMPT}\n\n"
        "Additional evaluation rubrics (apply strictly):\n"
        f"{rubric_text}\n\n"
        "If rubric guidance conflicts with default coaching preferences, prioritize the rubric.\n"
        "Follow the scoring guide in the 'HOW TO SCORE' section of the rubric text files and not the 'score' field above.\n"
        "Still return ONLY the required JSON schema."
    )


def build_analysis_user_message(transcript: str, metadata: dict) -> str:
    """Build the analysis user-turn payload with call context + transcript.

    The context block is derived from extracted metadata so the model can adapt
    coaching to persona and deal stage while still returning `AnalysisResult`
    JSON only.
    """
    rep = metadata.get("rep_name") or "Unknown rep"
    contact = metadata.get("contact_name") or "Unknown contact"
    title = metadata.get("contact_title") or "Unknown title"
    stage = metadata.get("deal_stage") or "Unknown stage"

    context_block = (
        f"Call context:\n"
        f"- Sales rep: {rep}\n"
        f"- Contact: {contact} ({title})\n"
        f"- Deal stage: {stage}\n"
    )

    return (
        f"{context_block}\n"
        f"Analyse the following sales call transcript and return a structured debrief as JSON:\n\n"
        f"{transcript}"
    )
