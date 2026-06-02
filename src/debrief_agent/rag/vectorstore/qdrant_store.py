from langchain_qdrant import QdrantVectorStore

from debrief_agent.core.qdrant import (
    get_sync_qdrant_client,
    get_sync_qdrant_collection_name,
)
from debrief_agent.rag.embeddings.embedding_service import embeddings


vector_store = QdrantVectorStore(
    client=get_sync_qdrant_client(),
    collection_name=get_sync_qdrant_collection_name(),
    embedding=embeddings,
)
