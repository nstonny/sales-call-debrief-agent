from qdrant_client import AsyncQdrantClient, QdrantClient

from debrief_agent.core.config import (
    QDRANT_API_KEY,
    QDRANT_COLLECTION_NAME,
    QDRANT_TIMEOUT_SECONDS,
    QDRANT_URL,
)

# Reuse clients for the process lifetime.
_async_qdrant_client: AsyncQdrantClient | None = None
_sync_qdrant_client: QdrantClient | None = None


def get_async_qdrant_client() -> AsyncQdrantClient:
    """Return a lazily-initialized AsyncQdrantClient singleton."""
    global _async_qdrant_client
    if _async_qdrant_client is None:
        _async_qdrant_client = AsyncQdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY,
            timeout=QDRANT_TIMEOUT_SECONDS,
        )
    return _async_qdrant_client


def get_sync_qdrant_client() -> QdrantClient:
    """Return a lazily-initialized synchronous QdrantClient singleton."""
    global _sync_qdrant_client
    if _sync_qdrant_client is None:
        _sync_qdrant_client = QdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY,
            timeout=QDRANT_TIMEOUT_SECONDS,
        )
    return _sync_qdrant_client


def get_async_qdrant_collection_name() -> str:
    """Return the configured Qdrant collection name for async call paths."""
    return QDRANT_COLLECTION_NAME


def get_sync_qdrant_collection_name() -> str:
    """Return the configured Qdrant collection name for sync call paths."""
    return QDRANT_COLLECTION_NAME


async def close_async_qdrant_client() -> None:
    """Close and clear the shared async Qdrant client if it was initialized."""
    global _async_qdrant_client
    if _async_qdrant_client is not None:
        await _async_qdrant_client.close()
        _async_qdrant_client = None


def close_sync_qdrant_client() -> None:
    """Close and clear the shared sync Qdrant client if it was initialized."""
    global _sync_qdrant_client
    if _sync_qdrant_client is not None:
        _sync_qdrant_client.close()
        _sync_qdrant_client = None


# Compatibility aliases for existing imports.
get_qdrant_client = get_async_qdrant_client
get_qdrant_collection_name = get_async_qdrant_collection_name
close_qdrant_client = close_async_qdrant_client
