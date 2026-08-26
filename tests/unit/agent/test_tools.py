"""Unit tests for the RAG retrieval tools.

Covers the shared `_retrieve_by_knowledge_type` serialization logic, the
chunk-logging env toggle, and the three `@tool` entrypoints. The hybrid
retriever is patched so no OpenAI/Qdrant calls are made.
"""

import pytest

from debrief_agent.rag.agent import tools
from debrief_agent.rag.agent.tools import (
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
    result = RetrievalResult(
        query="q",
        chunks=[_chunk("first chunk"), _chunk("second chunk")],
    )
    retrieve = mocker.patch.object(tools.hybrid_retriever, "retrieve", return_value=result)

    output = _retrieve_by_knowledge_type("q", KnowledgeType.SALES_FRAMEWORKS)

    assert output == "first chunk\n\nsecond chunk"
    retrieve.assert_called_once_with(
        query="q",
        limit=10,
        knowledge_type=KnowledgeType.SALES_FRAMEWORKS,
    )


def test_retrieve_skips_empty_chunk_text(mocker):
    result = RetrievalResult(query="q", chunks=[_chunk("real"), _chunk("")])
    mocker.patch.object(tools.hybrid_retriever, "retrieve", return_value=result)

    output = _retrieve_by_knowledge_type("q", KnowledgeType.COACHING_GUIDES)
    assert output == "real"


def test_retrieve_returns_sentinel_when_no_chunks(mocker):
    result = RetrievalResult(query="q", chunks=[])
    mocker.patch.object(tools.hybrid_retriever, "retrieve", return_value=result)

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
    result = RetrievalResult(query="q", chunks=[_chunk("body", expected_type)])
    retrieve = mocker.patch.object(tools.hybrid_retriever, "retrieve", return_value=result)

    output = tool_obj.invoke({"query": "objection handling"})

    assert output == "body"
    assert retrieve.call_args.kwargs["knowledge_type"] is expected_type
    assert retrieve.call_args.kwargs["query"] == "objection handling"
