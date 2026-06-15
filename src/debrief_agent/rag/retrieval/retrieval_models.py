from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class KnowledgeType(str, Enum):
    """Canonical knowledge-base categories used in chunk metadata."""

    CALL_EXAMPLES = "call_examples"
    COACHING_GUIDES = "coaching_guides"
    SALES_FRAMEWORKS = "sales_frameworks"
    COMPANY_PLAYBOOKS = "company_playbooks"


class RetrievedChunk(BaseModel):
    """One retrieved chunk with ranking score and source metadata."""

    text: str = Field(description="Chunk text returned by retrieval")
    score: float = Field(description="Retrieval score for ranking")
    source: str = Field(description="Origin document identifier")
    knowledge_type: KnowledgeType = Field(description="Knowledge-base category")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional retrieval metadata associated with the chunk",
    )

    model_config = {"from_attributes": True}


class RetrievalResult(BaseModel):
    """Retrieval output payload for a single query."""

    query: str = Field(description="Original retrieval query")
    chunks: list[RetrievedChunk] = Field(
        default_factory=list,
        description="Ranked chunks returned for the query",
    )

    model_config = {"from_attributes": True}
