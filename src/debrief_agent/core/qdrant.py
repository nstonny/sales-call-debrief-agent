from qdrant_client import AsyncQdrantClient

from debrief_agent.core.config import (
    QDRANT_API_KEY,
    QDRANT_COLLECTION_NAME,
    QDRANT_TIMEOUT_SECONDS,
    QDRANT_URL,
)

# Reuse one async client for the process lifetime.
_qdrant_client: AsyncQdrantClient | None = None


def get_qdrant_client() -> AsyncQdrantClient:
    """Return a lazily-initialized AsyncQdrantClient singleton."""
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = AsyncQdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY,
            timeout=QDRANT_TIMEOUT_SECONDS,
        )
    return _qdrant_client


def get_qdrant_collection_name() -> str:
    """Return the configured Qdrant collection name."""
    return QDRANT_COLLECTION_NAME


async def close_qdrant_client() -> None:
    """Close and clear the shared Qdrant client if it was initialized."""
    global _qdrant_client
    if _qdrant_client is not None:
        await _qdrant_client.close()
        _qdrant_client = None

