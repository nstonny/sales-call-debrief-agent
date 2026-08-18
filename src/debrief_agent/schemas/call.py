import uuid
from datetime import datetime

from pydantic import BaseModel

from debrief_agent.schemas.analysis import AnalysisResult


class CallResponse(BaseModel):
    """
    Shape of the JSON response returned after a transcript is uploaded.
    Includes the fully populated call metadata and the nested analysis debrief.
    """

    id: uuid.UUID
    filename: str
    created_at: datetime

    # LLM-extracted (null until extraction pass runs)
    rep_name: str | None = None
    contact_name: str | None = None
    contact_title: str | None = None
    deal_stage: str | None = None

    # Manually supplied at upload time
    company: str | None = None
    deal_value: float | None = None

    # Nested analysis debrief (null until analysis pass runs)
    analysis: AnalysisResult | None = None

    model_config = {"from_attributes": True}  # allows building from ORM object
