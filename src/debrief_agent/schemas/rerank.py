from pydantic import BaseModel, Field


class RerankedChunkRef(BaseModel):
    """One ranked reference back into the candidate list the LLM was shown."""

    index: int = Field(description="0-based index into the candidate passage list")
    relevance_score: float = Field(
        description="Relevance of this passage to the query, from 0.0 (irrelevant) to 1.0 (highly relevant)"
    )


class RerankResult(BaseModel):
    """Structured output payload returned by the reranking LLM step."""

    rankings: list[RerankedChunkRef] = Field(
        description="Candidate passages ordered most to least relevant to the query"
    )
