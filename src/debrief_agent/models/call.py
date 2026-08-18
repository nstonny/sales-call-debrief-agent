import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from debrief_agent.models.analysis import Analysis

from debrief_agent.core.database import Base


class Call(Base):
    """
    Represents an uploaded sales call transcript and its extracted metadata.

    Metadata columns (rep_name, contact_name, etc.) are populated by the LLM
    extraction pass after upload. company and deal_value are nullable because
    they are not present in transcripts and must be supplied manually.
    """

    __tablename__ = "calls"

    # --- Primary key ---
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # --- File info ---
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    transcript_text: Mapped[str] = mapped_column(Text, nullable=False)

    # --- LLM-extracted metadata ---
    rep_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    contact_title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    deal_stage: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # --- Manually provided metadata (not present in transcripts) ---
    company: Mapped[str | None] = mapped_column(String(150), nullable=True)
    deal_value: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)

    # --- Timestamp ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # --- Relationship (back-populated from Analysis, optional until LLM runs) ---
    analysis: Mapped[Optional["Analysis"]] = relationship(
        "Analysis",
        back_populates="call",
        uselist=False,  # one-to-one
        cascade="all, delete-orphan",
    )
