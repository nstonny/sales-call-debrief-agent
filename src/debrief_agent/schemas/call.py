import uuid
from datetime import datetime
from typing import Optional

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
    rep_name: Optional[str] = None
    contact_name: Optional[str] = None
    contact_title: Optional[str] = None
    deal_stage: Optional[str] = None

    # Manually supplied at upload time
    company: Optional[str] = None
    deal_value: Optional[float] = None

    # Nested analysis debrief (null until analysis pass runs)
    analysis: Optional[AnalysisResult] = None

    model_config = {"from_attributes": True}  # allows building from ORM object

