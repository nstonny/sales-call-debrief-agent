# ---------------------------------------------------------------------------
# Prompts for the analysis (debrief) pass.
#
# Goal: generate a full structured debrief of a sales call, personalised
# using the metadata extracted in the first pass (rep name, contact title,
# deal stage, etc.) so the LLM can tailor its coaching accordingly.
#
# Editing guide:
#   - Adjust ANALYSIS_SYSTEM_PROMPT to change the debrief structure or
#     the coaching focus areas.
#   - build_analysis_user_message() injects both the metadata context and
#     the raw transcript into the user turn.
# ---------------------------------------------------------------------------

ANALYSIS_SYSTEM_PROMPT = """
You are an expert sales coach. You will be given a sales call transcript
along with context about the call (rep name, contact name and title, deal stage).

Your job is to produce a structured debrief of the call as a JSON object.

Return ONLY a valid JSON object with exactly these keys:

{
  "summary":                string or null,   // 2–4 sentence narrative summary of the call
  "strengths":              array of strings, // What the rep did well (each item one concise sentence)
  "areas_for_improvement":  array of strings, // Specific coaching points for the rep
  "action_items":           array of strings, // Concrete follow-up actions agreed or recommended
  "objections_raised":      array of strings, // Objections the prospect raised (e.g. "pricing too high")
  "competitor_mentioned":   string or null,   // Name of any competitor mentioned, or null
  "next_steps":             string or null,   // What was agreed as the next step at the end of the call
  "sentiment":              string,           // Overall call sentiment: "positive", "neutral", or "negative"
  "score":                  number            // Overall rep performance score from 0.0 to 10.0
}

Scoring guide for "score":
  9–10 : Excellent — strong discovery, clear value articulation, objections handled, next step secured
  7–8  : Good — mostly effective, minor gaps
  5–6  : Average — some positives but notable missed opportunities
  3–4  : Below average — multiple weaknesses, deal at risk
  0–2  : Poor — significant rep errors, relationship or deal likely damaged

Rules:
- Use the call context (contact title, deal stage) to calibrate your coaching.
  e.g. if the contact is a CTO, assess technical credibility; if deal stage is
  "negotiation", focus on how well the rep handled pricing pressure.
- For array fields, return an empty array [] if there are none, not null.
- Do not add extra keys or commentary outside the JSON object.
- Do not wrap the JSON in markdown code fences.
""".strip()


def build_analysis_system_prompt(rubric_text: str | None = None) -> str:
    """
    Builds the system prompt for analysis, optionally appending rubric guidance.

    If rubric text is provided, it is treated as strict additional evaluation criteria.
    """
    if not rubric_text:
        return ANALYSIS_SYSTEM_PROMPT

    return (
        f"{ANALYSIS_SYSTEM_PROMPT}\n\n"
        "Additional evaluation rubrics (apply strictly):\n"
        f"{rubric_text}\n\n"
        "If rubric guidance conflicts with default coaching preferences, prioritize the rubric.\n"
        "Still return ONLY the required JSON schema."
    )


def build_analysis_user_message(transcript: str, metadata: dict) -> str:
    """
    Builds the user-turn message for the analysis prompt.

    Injects the extracted call metadata as context so the LLM can personalise
    its coaching (e.g. tailor advice based on the contact's title or deal stage).

    Args:
        transcript: The raw transcript text.
        metadata:   Dict with keys rep_name, contact_name, contact_title, deal_stage.
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
