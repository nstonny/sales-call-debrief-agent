from enum import Enum
from typing import Optional

from pydantic import BaseModel, field_validator, Field


class DealStage(str, Enum):
    """Canonical deal stages accepted by CallMetadataExtraction.deal_stage."""

    DISCOVERY = "discovery"
    DEMO = "demo"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    CLOSING = "closing"
    UNKNOWN = "unknown"


class CallMetadataExtraction(BaseModel):
    """
    Structured extraction payload returned by the metadata LLM step.

    The model is used directly with OpenAI structured parsing and then validated
    by Pydantic before persistence. All fields are optional: missing values should
    be returned as null.

    `deal_stage` is enum-constrained to `DealStage` to keep downstream analytics
    consistent and prevent free-form stage labels.
    """
    rep_name: Optional[str] = Field(default=None, alias="First name (or full name) of the sales representative on the call")
    contact_name: Optional[str] = Field(default=None, alias="First name (or full name) of the prospect/customer on the call")
    contact_title: Optional[str] = Field(default=None, alias="Job title of the prospect (e.g. 'CTO', 'VP Sales')")
    deal_stage: Optional[DealStage] = Field(default=None, alias="One of: 'discovery', 'demo', 'proposal', 'negotiation', 'closing', 'unknown'")

    @field_validator("rep_name", "contact_name", "contact_title", "deal_stage", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: object) -> object:
        """
        Normalise empty/whitespace strings to None before type validation.

        This keeps DB values clean and allows enum coercion for `deal_stage`
        after stripping user/model whitespace.
        """
        # If the value is a string, strip whitespace and return None if it's empty
        if isinstance(v, str):
            return v.strip() or None

        # If the value is not a string (e.g. already None), pass it through unchanged
        return v  # type: ignore[return-value]
