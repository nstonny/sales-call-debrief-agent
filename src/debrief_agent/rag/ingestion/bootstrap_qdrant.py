from qdrant_client.models import Distance, VectorParams

from debrief_agent.core.qdrant import (
    get_sync_qdrant_client,
    get_sync_qdrant_collection_name,
)

# text-embedding-3-small outputs 1536-dimensional vectors.
EMBEDDING_DIMENSION = 1536


def ensure_collection() -> None:
    """Ensure the configured Qdrant collection exists before ingestion."""
    client = get_sync_qdrant_client()
    collection_name = get_sync_qdrant_collection_name()

    if client.collection_exists(collection_name=collection_name):
        return

    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=EMBEDDING_DIMENSION,
            distance=Distance.COSINE,
        ),
    )
