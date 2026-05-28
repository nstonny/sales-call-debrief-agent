from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class Sentiment(str, Enum):
    """Canonical sentiment labels accepted by AnalysisResult.sentiment."""

    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class AnalysisResult(BaseModel):
    """
    Structured analysis payload returned by the debrief LLM step.

    The model mirrors persisted analysis fields and is used as the Pydantic
    response format contract for structured parsing. All fields are optional;
    unknown values should be returned as null.

    `sentiment` is enum-constrained to `Sentiment` to prevent drift in
    downstream reporting and filters.
    """

    # --- Narrative fields ---
    summary: Optional[str] = Field(None, description="2–4 sentence narrative summary of the call")
    next_steps: Optional[str] = Field(None, description="What was agreed as the next step at the end of the call")
    competitor_mentioned: Optional[str] = Field(None, description="Name of any competitor mentioned, or null")

    # --- Structured list fields (LLM returns JSON arrays) ---
    strengths: Optional[list[str]] = Field(None, description="What the rep did well (each item one concise sentence)")
    areas_for_improvement: Optional[list[str]] = Field(None, description="Specific coaching points for the rep")
    action_items: Optional[list[str]] = Field(None, description="Concrete follow-up actions agreed or recommended")
    objections_raised: Optional[list[str]] = Field(None, description="Objections the prospect raised (e.g. 'pricing too high')")

    # --- Scoring ---
    sentiment: Optional[Sentiment] = Field(None, description="Overall call sentiment: 'positive', 'neutral', or 'negative'")   # "positive" | "neutral" | "negative"
    score: Optional[float] = Field(None, ge=0.0, le=5.0, description="Overall rep performance score from 0.0 to 5.0")  # 0.0 – 5.0

    model_config = {"from_attributes": True}  # allows building from ORM Analysis object

    @field_validator(
        "summary", "next_steps", "competitor_mentioned", "sentiment",
        mode="before",
    )
    @classmethod
    def empty_str_to_none(cls, v: object) -> object:
        """
        Normalise empty/whitespace strings to None before field validation.

        This keeps optional text fields and enum-backed `sentiment` clean when
        LLM output includes blank strings.
        """
        # If the value is a string, strip whitespace and return None if it's empty
        if isinstance(v, str):
            return v.strip() or None

        # If the value is not a string (e.g. already None), pass it through unchanged
        return v  # type: ignore[return-value]
