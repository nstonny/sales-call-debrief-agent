from langchain_qdrant import QdrantVectorStore

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


qdrant_store_service = QdrantStoreService()


def get_vector_store() -> QdrantVectorStore:
    """Compatibility helper for call sites expecting a function getter."""
    return qdrant_store_service.get_store()
