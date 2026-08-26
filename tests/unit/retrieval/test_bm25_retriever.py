"""Unit tests for BM25Retriever.

Qdrant is stubbed via `scroll_all`, so no live database is touched. BM25Okapi
itself runs for real -- it's pure Python/numpy, not a heavy ML dependency.
"""

import pytest

from debrief_agent.rag.retrieval.bm25_retriever import BM25Retriever
from debrief_agent.rag.retrieval.retrieval_models import KnowledgeType, RetrievalResult
from debrief_agent.rag.vectorstore.qdrant_store import qdrant_store_service


@pytest.fixture
def retriever() -> BM25Retriever:
    return BM25Retriever()


def test_retrieve_rejects_empty_query(retriever):
    with pytest.raises(ValueError, match="query must not be empty"):
        retriever.retrieve(query="   ", knowledge_type=KnowledgeType.SALES_FRAMEWORKS, limit=5)


def test_retrieve_ranks_exact_term_match_first(retriever, mocker, make_record):
    records = [
        make_record(payload={"page_content": "generic sales advice", "metadata": {}}),
        make_record(payload={"page_content": "MEDDIC qualification framework", "metadata": {}}),
    ]
    mocker.patch.object(qdrant_store_service, "scroll_all", return_value=records)

    result = retriever.retrieve(
        query="MEDDIC", knowledge_type=KnowledgeType.SALES_FRAMEWORKS, limit=5
    )

    assert isinstance(result, RetrievalResult)
    assert result.chunks[0].text == "MEDDIC qualification framework"


def test_retrieve_excludes_zero_score_chunks(retriever, mocker, make_record):
    records = [make_record(payload={"page_content": "totally unrelated text", "metadata": {}})]
    mocker.patch.object(qdrant_store_service, "scroll_all", return_value=records)

    result = retriever.retrieve(
        query="objection handling", knowledge_type=KnowledgeType.SALES_FRAMEWORKS, limit=5
    )

    assert result.chunks == []


def test_retrieve_truncates_to_limit(retriever, mocker, make_record):
    records = [
        make_record(payload={"page_content": f"discovery call example {i}", "metadata": {}})
        for i in range(5)
    ]
    mocker.patch.object(qdrant_store_service, "scroll_all", return_value=records)

    result = retriever.retrieve(
        query="discovery call", knowledge_type=KnowledgeType.CALL_EXAMPLES, limit=2
    )

    assert len(result.chunks) == 2


def test_retrieve_on_empty_corpus_returns_no_chunks(retriever, mocker):
    mocker.patch.object(qdrant_store_service, "scroll_all", return_value=[])

    result = retriever.retrieve(
        query="anything", knowledge_type=KnowledgeType.COMPANY_PLAYBOOKS, limit=5
    )

    assert result.chunks == []


def test_index_is_built_once_and_cached_per_knowledge_type(retriever, mocker, make_record):
    records = [make_record(payload={"page_content": "MEDDIC framework", "metadata": {}})]
    scroll = mocker.patch.object(qdrant_store_service, "scroll_all", return_value=records)

    retriever.retrieve(query="MEDDIC", knowledge_type=KnowledgeType.SALES_FRAMEWORKS, limit=5)
    retriever.retrieve(query="framework", knowledge_type=KnowledgeType.SALES_FRAMEWORKS, limit=5)

    scroll.assert_called_once()
