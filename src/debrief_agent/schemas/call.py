import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CallResponse(BaseModel):
    """
    Shape of the JSON response returned after a transcript is uploaded.
    All metadata fields are optional because they are populated later
    by the LLM extraction pass (except company / deal_value which come
    from the upload form).
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

    model_config = {"from_attributes": True}  # allows building from ORM object

