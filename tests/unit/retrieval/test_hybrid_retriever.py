"""Unit tests for HybridRetriever's Reciprocal Rank Fusion logic.

Both underlying retrievers are patched, so no OpenAI/Qdrant calls are made.
"""

from debrief_agent.rag.retrieval.hybrid_retriever import HybridRetriever
from debrief_agent.rag.retrieval.retrieval_models import (
    KnowledgeType,
    RetrievalResult,
    RetrievedChunk,
)


def _chunk(text: str) -> RetrievedChunk:
    return RetrievedChunk(
        text=text,
        score=0.0,
        source="doc.md",
        knowledge_type=KnowledgeType.SALES_FRAMEWORKS,
    )


def _patch(mocker, vector_chunks, bm25_chunks):
    mocker.patch(
        "debrief_agent.rag.retrieval.hybrid_retriever.vector_retriever.retrieve",
        return_value=RetrievalResult(query="q", chunks=vector_chunks),
    )
    mocker.patch(
        "debrief_agent.rag.retrieval.hybrid_retriever.bm25_retriever.retrieve",
        return_value=RetrievalResult(query="q", chunks=bm25_chunks),
    )


def test_chunk_found_by_both_channels_ranks_above_single_channel_hits(mocker):
    shared = _chunk("shared chunk")
    vector_only = _chunk("vector only")
    bm25_only = _chunk("bm25 only")
    _patch(mocker, vector_chunks=[vector_only, shared], bm25_chunks=[bm25_only, shared])

    result = HybridRetriever().retrieve(
        query="q", knowledge_type=KnowledgeType.SALES_FRAMEWORKS, limit=10
    )

    assert result.chunks[0].text == "shared chunk"
    assert {c.text for c in result.chunks} == {"shared chunk", "vector only", "bm25 only"}


def test_retrieve_truncates_to_limit(mocker):
    chunks = [_chunk(f"chunk {i}") for i in range(5)]
    _patch(mocker, vector_chunks=chunks, bm25_chunks=[])

    result = HybridRetriever().retrieve(
        query="q", knowledge_type=KnowledgeType.SALES_FRAMEWORKS, limit=2
    )

    assert len(result.chunks) == 2


def test_retrieve_handles_no_results_from_either_channel(mocker):
    _patch(mocker, vector_chunks=[], bm25_chunks=[])

    result = HybridRetriever().retrieve(
        query="q", knowledge_type=KnowledgeType.SALES_FRAMEWORKS, limit=10
    )

    assert result.chunks == []


def test_retrieve_forwards_candidate_pool_to_both_channels(mocker):
    vector_retrieve = mocker.patch(
        "debrief_agent.rag.retrieval.hybrid_retriever.vector_retriever.retrieve",
        return_value=RetrievalResult(query="q", chunks=[]),
    )
    bm25_retrieve = mocker.patch(
        "debrief_agent.rag.retrieval.hybrid_retriever.bm25_retriever.retrieve",
        return_value=RetrievalResult(query="q", chunks=[]),
    )

    HybridRetriever().retrieve(
        query="q", knowledge_type=KnowledgeType.SALES_FRAMEWORKS, limit=10, candidate_pool=25
    )

    assert vector_retrieve.call_args.kwargs["limit"] == 25
    assert bm25_retrieve.call_args.kwargs["limit"] == 25
