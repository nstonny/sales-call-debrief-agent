import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, Numeric, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from debrief_agent.models.call import Call

from debrief_agent.core.database import Base


class Analysis(Base):
    """
    Stores the LLM-generated debrief output for a single sales call.

    Each Analysis belongs to exactly one Call (one-to-one for MVP).
    raw_llm_output preserves the full LLM response so new fields can be
    parsed later without re-calling the API.
    """
    __tablename__ = "analyses"

    # --- Primary key ---
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # --- Foreign key to calls ---
    call_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("calls.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # --- LLM narrative output ---
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_steps: Mapped[str | None] = mapped_column(Text, nullable=True)
    competitor_mentioned: Mapped[str | None] = mapped_column(String(150), nullable=True)

    # --- LLM structured list output (stored as JSONB arrays) ---
    strengths: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    areas_for_improvement: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    action_items: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    objections_raised: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # --- LLM scoring ---
    sentiment: Mapped[str | None] = mapped_column(String(20), nullable=True)   # positive / neutral / negative
    score: Mapped[float | None] = mapped_column(Numeric(4, 1), nullable=True)  # 0.0 – 10.0

    # --- Full LLM response preserved for reuse / debugging ---
    raw_llm_output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # --- Timestamp ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # --- Relationship back to Call ---
    call: Mapped["Call"] = relationship(
        "Call",
        back_populates="analysis",
    )



