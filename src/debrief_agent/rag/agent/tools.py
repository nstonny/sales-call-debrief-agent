import logging
import os

from langchain.tools import tool

from debrief_agent.rag.retrieval.vector_retriever import (
    vector_retriever,
)
from debrief_agent.rag.retrieval.retrieval_models import (
    KnowledgeType,
)

logger = logging.getLogger(__name__)


def _is_chunk_logging_enabled() -> bool:
    return os.getenv("DEBRIEF_AGENT_LOG_RAG_CHUNKS", "false").lower() == "true"


def _log_retrieved_chunks(knowledge_type: KnowledgeType, query: str, chunks: list) -> None:
    if not _is_chunk_logging_enabled():
        return

    logger.info(
        "RAG retrieval | type=%s | query=%r | chunks=%d",
        knowledge_type.value,
        query,
        len(chunks),
    )

    for index, chunk in enumerate(chunks, start=1):
        preview = chunk.text.replace("\n", " ").strip() if isinstance(chunk.text, str) else ""
        if len(preview) > 240:
            preview = f"{preview[:240]}..."

        logger.info(
            "RAG chunk %d | type=%s | score=%.4f | source=%s | preview=%r",
            index,
            chunk.knowledge_type.value,
            chunk.score,
            chunk.source,
            preview,
        )


def _retrieve_by_knowledge_type(query: str, knowledge_type: KnowledgeType) -> str:
    """Retrieve top chunks for a specific knowledge category and serialize them."""
    result = vector_retriever.retrieve(
        query=query,
        limit=10,
        knowledge_type=knowledge_type,
    )

    _log_retrieved_chunks(
        knowledge_type=knowledge_type,
        query=query,
        chunks=result.chunks,
    )

    if not result.chunks:
        return "No relevant context found in the selected knowledge base section."

    return "\n\n".join(chunk.text for chunk in result.chunks if chunk.text)

@tool
def retrieve_sales_frameworks(query: str) -> str:
    """
    Retrieve MEDDIC, SPIN, Challenger, discovery,
    qualification and objection handling guidance.
    """
    print("TOOL CALLED: retrieve_sales_frameworks")
    return _retrieve_by_knowledge_type(
        query=query,
        knowledge_type=KnowledgeType.SALES_FRAMEWORKS,
    )

@tool
def retrieve_coaching_guides(query: str) -> str:
    """
    Retrieve sales coaching best practices and
    performance improvement guidance.
    """
    print("TOOL CALLED: retrieve_coaching_guides")
    return _retrieve_by_knowledge_type(
        query=query,
        knowledge_type=KnowledgeType.COACHING_GUIDES,
    )

@tool
def retrieve_call_examples(query: str) -> str:
    """
    Retrieve examples of successful and unsuccessful
    sales conversations.
    """
    print("TOOL CALLED: retrieve_call_examples")
    return _retrieve_by_knowledge_type(
        query=query,
        knowledge_type=KnowledgeType.CALL_EXAMPLES,
    )

