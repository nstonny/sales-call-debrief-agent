from typing import Optional

from pydantic import BaseModel, Field, field_validator


class AnalysisResult(BaseModel):
    """
    Pydantic model for the structured JSON output of the LLM analysis pass.
    Used to parse, validate, and normalise the LLM response in one step.

    Mirrors the columns of the analyses table. All fields are optional —
    if the LLM cannot determine a value it returns null.
    """

    # --- Narrative fields ---
    summary: Optional[str] = None
    next_steps: Optional[str] = None
    competitor_mentioned: Optional[str] = None

    # --- Structured list fields (LLM returns JSON arrays) ---
    strengths: Optional[list[str]] = None
    areas_for_improvement: Optional[list[str]] = None
    action_items: Optional[list[str]] = None
    objections_raised: Optional[list[str]] = None

    # --- Scoring ---
    sentiment: Optional[str] = None   # "positive" | "neutral" | "negative"
    score: Optional[float] = Field(None, ge=0.0, le=10.0)  # 0.0 – 10.0

    model_config = {"from_attributes": True}  # allows building from ORM Analysis object

    @field_validator(
        "summary", "next_steps", "competitor_mentioned", "sentiment",
        mode="before",
    )
    @classmethod
    def empty_str_to_none(cls, v: object) -> Optional[str]:
        """
        Strips whitespace and converts empty strings to None.

        Examples:
            "Good discovery"  → "Good discovery"
            "  "              → None
            ""                → None
            None              → None  (passed through unchanged)
        """
        # If the value is a string, strip whitespace and return None if it's empty
        if isinstance(v, str):
            return v.strip() or None

        # If the value is not a string (e.g. already None), pass it through unchanged
        return v  # type: ignore[return-value]
