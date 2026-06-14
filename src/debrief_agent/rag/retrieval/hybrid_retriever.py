import logging
from typing import Any

from qdrant_client.http.models import Filter, ScoredPoint

from debrief_agent.rag.embeddings.embedding_service import embeddings
from debrief_agent.rag.retrieval.retrieval_models import (
    KnowledgeType,
    RetrievedChunk,
    RetrievalResult,
)
from debrief_agent.rag.vectorstore.qdrant_store import qdrant_store_service

logger = logging.getLogger(__name__)


# Keep mapping permissive for payloads produced by different ingestion paths.
_CATEGORY_TO_KNOWLEDGE_TYPE: dict[str, KnowledgeType] = {
    "call_examples": KnowledgeType.CALL_EXAMPLES,
    "coaching_guides": KnowledgeType.COACHING_GUIDES,
    "sales_frameworks": KnowledgeType.SALES_FRAMEWORKS,
    "company_playbooks": KnowledgeType.COMPANY_PLAYBOOKS,
    "processed_markdown": KnowledgeType.PROCESSED_MARKDOWN,
}


class HybridRetriever:
    """Embed a user query, retrieve Qdrant points, and map them to typed models."""

    def retrieve(
        self,
        query: str,
        limit: int = 5,
        query_filter: Filter | None = None,
    ) -> RetrievalResult:
        """Run similarity retrieval and return normalized retrieval models.

        Example:
            result = hybrid_retriever.retrieve(query="objection handling", limit=5)
        """
        cleaned_query = query.strip()
        if not cleaned_query:
            raise ValueError("query must not be empty")
        try:
            query_vector = self._embed_query(cleaned_query)
            results = self._similarity_search(
                query_vector=query_vector,
                limit=limit,
                query_filter=query_filter,
            )
            chunks = [self._point_to_chunk(point) for point in results]
            return RetrievalResult(query=cleaned_query, chunks=chunks)
        except Exception:
            logger.exception("Hybrid retrieval failed")
            raise


    def _embed_query(self, query: str) -> list[float]:
        """Create a vector embedding for the user query."""
        return embeddings.embed_query(query)

    def _similarity_search(
        self,
        query_vector: list[float],
        limit: int,
        query_filter: Filter | None,
    ) -> list[ScoredPoint]:
        """Search Qdrant for nearest-neighbor chunks."""
        return qdrant_store_service.similarity_search(
            query_vector=query_vector,
            limit=limit,
            query_filter=query_filter,
        )

    def _point_to_chunk(self, point: ScoredPoint) -> RetrievedChunk:
        payload = point.payload if isinstance(point.payload, dict) else {}
        metadata_raw = payload.get("metadata")
        metadata = metadata_raw if isinstance(metadata_raw, dict) else {}

        text = self._resolve_text(payload=payload, metadata=metadata)
        source = self._resolve_source(payload=payload, metadata=metadata)
        knowledge_type = self._resolve_knowledge_type(payload=payload, metadata=metadata)

        enriched_metadata = dict(metadata)
        for key, value in payload.items():
            if key not in {"metadata", "page_content", "text"} and key not in enriched_metadata:
                enriched_metadata[key] = value

        return RetrievedChunk(
            text=text,
            score=float(point.score),
            source=source,
            knowledge_type=knowledge_type,
            metadata=enriched_metadata,
        )

    @staticmethod
    def _resolve_text(payload: dict[str, Any], metadata: dict[str, Any]) -> str:
        for candidate in (
            payload.get("page_content"),
            payload.get("text"),
            metadata.get("page_content"),
            metadata.get("text"),
        ):
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        return ""

    @staticmethod
    def _resolve_source(payload: dict[str, Any], metadata: dict[str, Any]) -> str:
        for candidate in (metadata.get("source"), payload.get("source")):
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        return "unknown"

    @staticmethod
    def _resolve_knowledge_type(
        payload: dict[str, Any],
        metadata: dict[str, Any],
    ) -> KnowledgeType:
        for candidate in (
            metadata.get("category"),
            payload.get("category"),
            metadata.get("knowledge_type"),
            payload.get("knowledge_type"),
        ):
            if isinstance(candidate, KnowledgeType):
                return candidate
            if isinstance(candidate, str):
                normalized = candidate.strip().lower()
                if normalized in _CATEGORY_TO_KNOWLEDGE_TYPE:
                    return _CATEGORY_TO_KNOWLEDGE_TYPE[normalized]
        return KnowledgeType.SALES_FRAMEWORKS


hybrid_retriever = HybridRetriever()


def retrieve(
    query: str,
    limit: int = 5,
    query_filter: Filter | None = None,
) -> RetrievalResult:
    """Compatibility helper for call sites expecting function-style retrieval."""
    return hybrid_retriever.retrieve(query=query, limit=limit, query_filter=query_filter)

