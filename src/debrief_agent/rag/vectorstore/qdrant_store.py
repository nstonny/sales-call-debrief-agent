from typing import Any, cast

from langchain_qdrant import QdrantVectorStore
from qdrant_client.http.models import Filter, Record, ScoredPoint

from debrief_agent.core.qdrant import (
    get_sync_qdrant_client,
    get_sync_qdrant_collection_name,
)
from debrief_agent.rag.embeddings.embedding_service import embeddings


class QdrantStoreService:
    """Service wrapper that lazily creates and reuses a QdrantVectorStore."""

    def __init__(self) -> None:
        self._vector_store: QdrantVectorStore | None = None

    def get_store(self) -> QdrantVectorStore:
        """Return the lazily initialized QdrantVectorStore instance."""
        if self._vector_store is None:
            self._vector_store = QdrantVectorStore(
                client=get_sync_qdrant_client(),
                collection_name=get_sync_qdrant_collection_name(),
                embedding=embeddings,
            )
        return self._vector_store

    def similarity_search(
        self,
        query_vector: list[float],
        limit: int = 5,
        query_filter: Filter | None = None,
    ) -> list[ScoredPoint]:
        """Run vector similarity search directly against Qdrant and return points.
        Example:
        results = similarity_search(query_vector=[0.1, 0.2, 0.3], limit=3)
        """
        response = get_sync_qdrant_client().query_points(
            collection_name=get_sync_qdrant_collection_name(),
            query=cast(Any, query_vector),
            limit=limit,
            query_filter=query_filter,
            with_payload=True,
        )
        return response.points

    def scroll_all(self, query_filter: Filter | None = None, page_size: int = 256) -> list[Record]:
        """Fetch every point matching a filter, paging through the full collection.

        Used to build an in-memory BM25 corpus per knowledge type; the knowledge
        base is small enough (a few dozen chunks per category) that loading it
        whole is cheap.
        """
        client = get_sync_qdrant_client()
        collection_name = get_sync_qdrant_collection_name()
        records: list[Record] = []
        offset = None
        while True:
            points, offset = client.scroll(
                collection_name=collection_name,
                scroll_filter=query_filter,
                limit=page_size,
                with_payload=True,
                with_vectors=False,
                offset=offset,
            )
            records.extend(points)
            if offset is None:
                break
        return records


qdrant_store_service = QdrantStoreService()


def get_vector_store() -> QdrantVectorStore:
    """Compatibility helper for call sites expecting a function getter."""
    return qdrant_store_service.get_store()


def similarity_search(
    query_vector: list[float],
    limit: int = 5,
    query_filter: Filter | None = None,
) -> list[ScoredPoint]:
    """Compatibility helper for call sites expecting function-style similarity search.

    Example:
        results = similarity_search(query_vector=[0.1, 0.2, 0.3], limit=3)
    """
    return qdrant_store_service.similarity_search(
        query_vector=query_vector,
        limit=limit,
        query_filter=query_filter,
    )
