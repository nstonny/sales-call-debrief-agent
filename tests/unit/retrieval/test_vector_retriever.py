"""Unit tests for VectorRetriever.

The static resolvers (`_resolve_text`, `_resolve_source`,
`_resolve_knowledge_type`) and `_point_to_chunk` are pure and tested directly
against fake Qdrant points. `retrieve` is tested with `_embed_query` and
`_similarity_search` patched so no OpenAI/Qdrant calls are made.
"""

import pytest
from qdrant_client.http.models import Filter, FieldCondition, MatchValue

from debrief_agent.rag.retrieval.retrieval_models import KnowledgeType, RetrievalResult
from debrief_agent.rag.retrieval.vector_retriever import VectorRetriever


@pytest.fixture
def retriever():
    return VectorRetriever()


# ---------------------------------------------------------------------------
# _resolve_text
# ---------------------------------------------------------------------------


def test_resolve_text_prefers_payload_page_content():
    text = VectorRetriever._resolve_text(
        payload={"page_content": "from payload", "text": "ignored"},
        metadata={"page_content": "from metadata"},
    )
    assert text == "from payload"


def test_resolve_text_falls_back_to_payload_text():
    text = VectorRetriever._resolve_text(payload={"text": "payload text"}, metadata={})
    assert text == "payload text"


def test_resolve_text_falls_back_to_metadata():
    text = VectorRetriever._resolve_text(payload={}, metadata={"text": "meta text"})
    assert text == "meta text"


def test_resolve_text_strips_whitespace():
    text = VectorRetriever._resolve_text(payload={"page_content": "  padded  "}, metadata={})
    assert text == "padded"


@pytest.mark.parametrize("blank", ["", "   ", "\n"])
def test_resolve_text_skips_blank_candidates(blank):
    text = VectorRetriever._resolve_text(
        payload={"page_content": blank, "text": "real text"},
        metadata={},
    )
    assert text == "real text"


def test_resolve_text_returns_empty_when_nothing_found():
    assert VectorRetriever._resolve_text(payload={}, metadata={}) == ""


# ---------------------------------------------------------------------------
# _resolve_source
# ---------------------------------------------------------------------------


def test_resolve_source_prefers_metadata():
    source = VectorRetriever._resolve_source(
        payload={"source": "payload.txt"},
        metadata={"source": "meta.txt"},
    )
    assert source == "meta.txt"


def test_resolve_source_falls_back_to_payload():
    source = VectorRetriever._resolve_source(payload={"source": "payload.txt"}, metadata={})
    assert source == "payload.txt"


def test_resolve_source_defaults_to_unknown():
    assert VectorRetriever._resolve_source(payload={}, metadata={}) == "unknown"


# ---------------------------------------------------------------------------
# _resolve_knowledge_type
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "category,expected",
    [
        ("call_examples", KnowledgeType.CALL_EXAMPLES),
        ("coaching_guides", KnowledgeType.COACHING_GUIDES),
        ("sales_frameworks", KnowledgeType.SALES_FRAMEWORKS),
    ],
)
def test_resolve_knowledge_type_maps_known_categories(category, expected):
    kt = VectorRetriever._resolve_knowledge_type(
        payload={},
        metadata={"category": category},
    )
    assert kt is expected


def test_resolve_knowledge_type_is_case_insensitive():
    kt = VectorRetriever._resolve_knowledge_type(
        payload={},
        metadata={"category": "  Coaching_Guides  "},
    )
    assert kt is KnowledgeType.COACHING_GUIDES


def test_resolve_knowledge_type_accepts_enum_member():
    kt = VectorRetriever._resolve_knowledge_type(
        payload={},
        metadata={"category": KnowledgeType.CALL_EXAMPLES},
    )
    assert kt is KnowledgeType.CALL_EXAMPLES


def test_resolve_knowledge_type_falls_back_to_payload_category():
    kt = VectorRetriever._resolve_knowledge_type(
        payload={"category": "call_examples"},
        metadata={},
    )
    assert kt is KnowledgeType.CALL_EXAMPLES


def test_resolve_knowledge_type_defaults_to_sales_frameworks():
    # Unknown / missing category falls back to SALES_FRAMEWORKS.
    kt = VectorRetriever._resolve_knowledge_type(
        payload={},
        metadata={"category": "company_playbooks"},
    )
    assert kt is KnowledgeType.SALES_FRAMEWORKS


def test_resolve_knowledge_type_defaults_when_absent():
    assert (
        VectorRetriever._resolve_knowledge_type(payload={}, metadata={})
        is KnowledgeType.SALES_FRAMEWORKS
    )


# ---------------------------------------------------------------------------
# _point_to_chunk
# ---------------------------------------------------------------------------


def test_point_to_chunk_maps_nested_metadata(retriever, make_point):
    point = make_point(
        score=0.87,
        payload={
            "page_content": "chunk body",
            "metadata": {"source": "guide.md", "category": "coaching_guides"},
        },
    )
    chunk = retriever._point_to_chunk(point)

    assert chunk.text == "chunk body"
    assert chunk.score == pytest.approx(0.87)
    assert chunk.source == "guide.md"
    assert chunk.knowledge_type is KnowledgeType.COACHING_GUIDES


def test_point_to_chunk_enriches_metadata_with_extra_payload_keys(retriever, make_point):
    point = make_point(
        payload={
            "page_content": "body",
            "metadata": {"source": "a.md", "category": "call_examples"},
            "chunk_index": 3,
            "custom_key": "value",
        },
    )
    chunk = retriever._point_to_chunk(point)

    # extra top-level payload keys are merged into metadata...
    assert chunk.metadata["chunk_index"] == 3
    assert chunk.metadata["custom_key"] == "value"
    # ...but reserved keys are not copied in as metadata entries.
    assert "page_content" not in chunk.metadata


def test_point_to_chunk_handles_missing_payload(retriever, make_point):
    chunk = retriever._point_to_chunk(make_point(score=0.5, payload=None))
    assert chunk.text == ""
    assert chunk.source == "unknown"
    assert chunk.knowledge_type is KnowledgeType.SALES_FRAMEWORKS
    assert chunk.score == pytest.approx(0.5)


def test_point_to_chunk_existing_metadata_not_overwritten_by_payload(retriever, make_point):
    # metadata.source should win; a top-level payload "source" must not clobber it.
    point = make_point(
        payload={
            "page_content": "body",
            "metadata": {"source": "correct.md", "category": "call_examples"},
            "source": "wrong.md",
        },
    )
    chunk = retriever._point_to_chunk(point)
    assert chunk.source == "correct.md"
    assert chunk.metadata["source"] == "correct.md"


# ---------------------------------------------------------------------------
# _build_knowledge_filter
# ---------------------------------------------------------------------------


def test_build_knowledge_filter_targets_category(retriever):
    knowledge_filter = retriever._build_knowledge_filter(KnowledgeType.COACHING_GUIDES)
    assert isinstance(knowledge_filter, Filter)
    condition = knowledge_filter.must[0]
    assert isinstance(condition, FieldCondition)
    assert condition.key == "metadata.category"
    assert isinstance(condition.match, MatchValue)
    assert condition.match.value == "coaching_guides"


# ---------------------------------------------------------------------------
# retrieve (with embedding + search patched)
# ---------------------------------------------------------------------------


def _patch_pipeline(retriever, mocker, points):
    """Stub out the embedding + Qdrant search boundary, capturing the search filter."""
    mocker.patch.object(retriever, "_embed_query", return_value=[0.1, 0.2, 0.3])
    return mocker.patch.object(retriever, "_similarity_search", return_value=points)


def test_retrieve_rejects_empty_query(retriever):
    with pytest.raises(ValueError, match="query must not be empty"):
        retriever.retrieve(query="   ")


def test_retrieve_returns_normalized_result(retriever, mocker, make_point):
    points = [
        make_point(
            score=0.9,
            payload={
                "page_content": "body one",
                "metadata": {"source": "a.md", "category": "call_examples"},
            },
        )
    ]
    _patch_pipeline(retriever, mocker, points)

    result = retriever.retrieve(query="  objection handling  ")

    assert isinstance(result, RetrievalResult)
    assert result.query == "objection handling"  # cleaned
    assert len(result.chunks) == 1
    assert result.chunks[0].text == "body one"


def test_retrieve_without_knowledge_type_passes_no_filter(retriever, mocker):
    search = _patch_pipeline(retriever, mocker, [])
    retriever.retrieve(query="anything")
    assert search.call_args.kwargs["query_filter"] is None


def test_retrieve_builds_filter_for_knowledge_type(retriever, mocker):
    search = _patch_pipeline(retriever, mocker, [])
    retriever.retrieve(query="q", knowledge_type=KnowledgeType.CALL_EXAMPLES)

    used_filter = search.call_args.kwargs["query_filter"]
    assert isinstance(used_filter, Filter)
    assert used_filter.must[0].match.value == "call_examples"


def test_retrieve_merges_knowledge_filter_into_existing_must(retriever, mocker):
    search = _patch_pipeline(retriever, mocker, [])
    caller_condition = FieldCondition(key="metadata.source", match=MatchValue(value="a.md"))
    caller_filter = Filter(must=[caller_condition])

    retriever.retrieve(
        query="q",
        knowledge_type=KnowledgeType.COACHING_GUIDES,
        query_filter=caller_filter,
    )

    used_filter = search.call_args.kwargs["query_filter"]
    keys = {c.key for c in used_filter.must}
    assert keys == {"metadata.source", "metadata.category"}


def test_retrieve_populates_must_when_caller_filter_is_bare(retriever, mocker):
    search = _patch_pipeline(retriever, mocker, [])
    bare_filter = Filter()  # must is None

    retriever.retrieve(
        query="q",
        knowledge_type=KnowledgeType.SALES_FRAMEWORKS,
        query_filter=bare_filter,
    )

    used_filter = search.call_args.kwargs["query_filter"]
    assert used_filter.must is not None
    assert used_filter.must[0].match.value == "sales_frameworks"


def test_retrieve_forwards_limit(retriever, mocker):
    search = _patch_pipeline(retriever, mocker, [])
    retriever.retrieve(query="q", limit=3)
    assert search.call_args.kwargs["limit"] == 3


def test_retrieve_reraises_on_search_failure(retriever, mocker):
    mocker.patch.object(retriever, "_embed_query", return_value=[0.1])
    mocker.patch.object(
        retriever, "_similarity_search", side_effect=RuntimeError("qdrant down")
    )
    with pytest.raises(RuntimeError, match="qdrant down"):
        retriever.retrieve(query="q")
