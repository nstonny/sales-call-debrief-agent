from typing import Optional

from pydantic import BaseModel, field_validator


class CallMetadataExtraction(BaseModel):
    """
    Pydantic model for the structured JSON output of the LLM metadata extraction pass.
    Used to parse, validate, and normalise the LLM response in one step.

    All fields are optional — if the LLM cannot determine a value it returns null,
    which maps cleanly to None here.
    """
    rep_name: Optional[str] = None
    contact_name: Optional[str] = None
    contact_title: Optional[str] = None
    deal_stage: Optional[str] = None

    @field_validator("rep_name", "contact_name", "contact_title", "deal_stage", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: object) -> Optional[str]:
        """
        Runs on each of the four fields before Pydantic checks the type.

        Problem it solves: the LLM sometimes returns an empty string ""
        instead of null when it can't find a value. We want to store None
        in the database, not an empty string.

        Examples:
            "Alex"   → "Alex"    (normal value, returned as-is after stripping)
            "  Alex" → "Alex"    (trims accidental whitespace)
            ""       → None      (empty string becomes None)
            "   "    → None      (whitespace-only string becomes None)
            None     → None      (LLM returned null, passed through unchanged)
        """
        # If the value is a string, strip whitespace and return None if it's empty
        if isinstance(v, str):
            return v.strip() or None

        # If the value is not a string (e.g. already None), pass it through unchanged
        return v  # type: ignore[return-value]
