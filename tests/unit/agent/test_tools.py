"""Unit tests for the RAG retrieval tools.

Covers the shared `_retrieve_by_knowledge_type` serialization logic, the
chunk-logging env toggle, and the three `@tool` entrypoints. The hybrid
retriever and the LLM reranker are both patched so no OpenAI/Qdrant calls
are made; the reranker patch defaults to an identity pass-through (truncated
to `top_n`) so these tests exercise the join/serialize logic, not reranking
itself -- that's covered in `test_rerank_service.py`.
"""

import pytest

from debrief_agent.rag.agent import tools
from debrief_agent.rag.agent.tools import (
    FINAL_RESULT_COUNT,
    RERANK_CANDIDATE_POOL,
    _is_chunk_logging_enabled,
    _retrieve_by_knowledge_type,
    retrieve_call_examples,
    retrieve_coaching_guides,
    retrieve_sales_frameworks,
)
from debrief_agent.rag.retrieval.retrieval_models import (
    KnowledgeType,
    RetrievalResult,
    RetrievedChunk,
)


def _chunk(text: str, knowledge_type=KnowledgeType.SALES_FRAMEWORKS) -> RetrievedChunk:
    return RetrievedChunk(
        text=text,
        score=0.9,
        source="doc.md",
        knowledge_type=knowledge_type,
    )


def _patch_retrieval(mocker, chunks):
    """Patch hybrid retrieval to return `chunks`, and the reranker to pass them through."""
    retrieve = mocker.patch.object(
        tools.hybrid_retriever,
        "retrieve",
        return_value=RetrievalResult(query="q", chunks=chunks),
    )
    rerank = mocker.patch.object(
        tools.chunk_reranker,
        "rerank",
        side_effect=lambda query, chunks, top_n: chunks[:top_n],
    )
    return retrieve, rerank


# ---------------------------------------------------------------------------
# _is_chunk_logging_enabled
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["true", "TRUE", "True"])
def test_chunk_logging_enabled_when_true(monkeypatch, value):
    monkeypatch.setenv("DEBRIEF_AGENT_LOG_RAG_CHUNKS", value)
    assert _is_chunk_logging_enabled() is True


@pytest.mark.parametrize("value", ["false", "0", "yes", ""])
def test_chunk_logging_disabled_for_other_values(monkeypatch, value):
    monkeypatch.setenv("DEBRIEF_AGENT_LOG_RAG_CHUNKS", value)
    assert _is_chunk_logging_enabled() is False


def test_chunk_logging_disabled_by_default(monkeypatch):
    monkeypatch.delenv("DEBRIEF_AGENT_LOG_RAG_CHUNKS", raising=False)
    assert _is_chunk_logging_enabled() is False


# ---------------------------------------------------------------------------
# _retrieve_by_knowledge_type
# ---------------------------------------------------------------------------


def test_retrieve_joins_chunk_texts(mocker):
    retrieve, rerank = _patch_retrieval(mocker, [_chunk("first chunk"), _chunk("second chunk")])

    output = _retrieve_by_knowledge_type("q", KnowledgeType.SALES_FRAMEWORKS)

    assert output == "first chunk\n\nsecond chunk"
    retrieve.assert_called_once_with(
        query="q",
        limit=RERANK_CANDIDATE_POOL,
        knowledge_type=KnowledgeType.SALES_FRAMEWORKS,
    )
    assert rerank.call_args.kwargs["top_n"] == FINAL_RESULT_COUNT


def test_retrieve_skips_empty_chunk_text(mocker):
    _patch_retrieval(mocker, [_chunk("real"), _chunk("")])

    output = _retrieve_by_knowledge_type("q", KnowledgeType.COACHING_GUIDES)
    assert output == "real"


def test_retrieve_returns_sentinel_when_no_chunks(mocker):
    _patch_retrieval(mocker, [])

    output = _retrieve_by_knowledge_type("q", KnowledgeType.CALL_EXAMPLES)
    assert output == "No relevant context found in the selected knowledge base section."


# ---------------------------------------------------------------------------
# @tool entrypoints route to the correct knowledge type
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "tool_obj,expected_type",
    [
        (retrieve_sales_frameworks, KnowledgeType.SALES_FRAMEWORKS),
        (retrieve_coaching_guides, KnowledgeType.COACHING_GUIDES),
        (retrieve_call_examples, KnowledgeType.CALL_EXAMPLES),
    ],
)
def test_tool_routes_to_expected_knowledge_type(mocker, tool_obj, expected_type):
    retrieve, _rerank = _patch_retrieval(mocker, [_chunk("body", expected_type)])

    output = tool_obj.invoke({"query": "objection handling"})

    assert output == "body"
    assert retrieve.call_args.kwargs["knowledge_type"] is expected_type
    assert retrieve.call_args.kwargs["query"] == "objection handling"
