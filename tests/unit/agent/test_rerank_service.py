"""Unit tests for ChunkReranker.rerank.

Exercises the full failure contract without touching the network: the fake
sync OpenAI client is injected via the constructor, and small stand-in
response objects drive the success / refusal / API-error / validation paths.
Every failure path falls back to `chunks[:top_n]` rather than raising.
"""

from types import SimpleNamespace

from openai import OpenAIError

from debrief_agent.rag.agent.services.rerank import ChunkReranker
from debrief_agent.rag.retrieval.retrieval_models import KnowledgeType, RetrievedChunk
from debrief_agent.schemas.rerank import RerankedChunkRef, RerankResult


def _chunk(text: str, score: float = 0.5) -> RetrievedChunk:
    return RetrievedChunk(
        text=text,
        score=score,
        source="doc.md",
        knowledge_type=KnowledgeType.SALES_FRAMEWORKS,
    )


def _refusal_response(reason: str = "policy violation"):
    refusal_part = SimpleNamespace(type="refusal", refusal=reason)
    item = SimpleNamespace(content=[refusal_part])
    return SimpleNamespace(output=[item], output_parsed=None)


def _parsed_response(parsed):
    return SimpleNamespace(output=[], output_parsed=parsed)


def _empty_response():
    return SimpleNamespace(output=[], output_parsed=None)


# ---------------------------------------------------------------------------
# No-op passthrough
# ---------------------------------------------------------------------------


def test_rerank_noops_on_empty_chunks(make_sync_openai_client):
    reranker = ChunkReranker(client=make_sync_openai_client())
    assert reranker.rerank(query="q", chunks=[], top_n=5) == []


def test_rerank_noops_on_single_chunk(make_sync_openai_client):
    chunk = _chunk("only one")
    reranker = ChunkReranker(client=make_sync_openai_client())
    assert reranker.rerank(query="q", chunks=[chunk], top_n=5) == [chunk]


# ---------------------------------------------------------------------------
# Success paths
# ---------------------------------------------------------------------------


def test_rerank_reorders_by_returned_ranking(make_sync_openai_client):
    chunks = [_chunk("first"), _chunk("second"), _chunk("third")]
    parsed = RerankResult(
        rankings=[
            RerankedChunkRef(index=2, relevance_score=0.9),
            RerankedChunkRef(index=0, relevance_score=0.5),
        ]
    )
    client = make_sync_openai_client(result=_parsed_response(parsed))
    reranker = ChunkReranker(client=client)

    result = reranker.rerank(query="q", chunks=chunks, top_n=5)

    assert [c.text for c in result] == ["third", "first"]
    assert result[0].score == 0.9
    assert result[0].metadata["fusion_score"] == chunks[2].score


def test_rerank_truncates_to_top_n(make_sync_openai_client):
    chunks = [_chunk(f"chunk {i}") for i in range(5)]
    parsed = RerankResult(
        rankings=[RerankedChunkRef(index=i, relevance_score=1.0 - i * 0.1) for i in range(5)]
    )
    client = make_sync_openai_client(result=_parsed_response(parsed))
    reranker = ChunkReranker(client=client)

    result = reranker.rerank(query="q", chunks=chunks, top_n=2)

    assert len(result) == 2


def test_rerank_validates_dict_payload(make_sync_openai_client):
    chunks = [_chunk("a"), _chunk("b")]
    payload = {"rankings": [{"index": 1, "relevance_score": 0.7}]}
    client = make_sync_openai_client(result=_parsed_response(payload))
    reranker = ChunkReranker(client=client)

    result = reranker.rerank(query="q", chunks=chunks, top_n=5)

    assert [c.text for c in result] == ["b"]


def test_rerank_drops_out_of_range_and_duplicate_indices(make_sync_openai_client):
    chunks = [_chunk("a"), _chunk("b")]
    parsed = RerankResult(
        rankings=[
            RerankedChunkRef(index=5, relevance_score=0.9),  # out of range
            RerankedChunkRef(index=1, relevance_score=0.8),
            RerankedChunkRef(index=1, relevance_score=0.7),  # duplicate
            RerankedChunkRef(index=0, relevance_score=0.6),
        ]
    )
    client = make_sync_openai_client(result=_parsed_response(parsed))
    reranker = ChunkReranker(client=client)

    result = reranker.rerank(query="q", chunks=chunks, top_n=5)

    assert [c.text for c in result] == ["b", "a"]


# ---------------------------------------------------------------------------
# Failure paths -> graceful fallback, never raise
# ---------------------------------------------------------------------------


def test_rerank_falls_back_on_openai_error(make_sync_openai_client):
    chunks = [_chunk("a"), _chunk("b"), _chunk("c")]
    client = make_sync_openai_client(exc=OpenAIError("rate limited"))
    reranker = ChunkReranker(client=client)

    result = reranker.rerank(query="q", chunks=chunks, top_n=2)

    assert result == chunks[:2]


def test_rerank_falls_back_on_refusal(make_sync_openai_client):
    chunks = [_chunk("a"), _chunk("b")]
    client = make_sync_openai_client(result=_refusal_response("cannot comply"))
    reranker = ChunkReranker(client=client)

    result = reranker.rerank(query="q", chunks=chunks, top_n=5)

    assert result == chunks


def test_rerank_falls_back_when_no_parsed_payload(make_sync_openai_client):
    chunks = [_chunk("a"), _chunk("b")]
    client = make_sync_openai_client(result=_empty_response())
    reranker = ChunkReranker(client=client)

    result = reranker.rerank(query="q", chunks=chunks, top_n=5)

    assert result == chunks


def test_rerank_falls_back_on_validation_error(make_sync_openai_client):
    chunks = [_chunk("a"), _chunk("b")]
    # Missing required "rankings" key fails RerankResult validation.
    client = make_sync_openai_client(result=_parsed_response({}))
    reranker = ChunkReranker(client=client)

    result = reranker.rerank(query="q", chunks=chunks, top_n=5)

    assert result == chunks


# ---------------------------------------------------------------------------
# Constructor wiring
# ---------------------------------------------------------------------------


def test_injected_client_is_used(make_sync_openai_client):
    chunks = [_chunk("a"), _chunk("b")]
    parsed = RerankResult(rankings=[RerankedChunkRef(index=0, relevance_score=0.5)])
    client = make_sync_openai_client(result=_parsed_response(parsed))
    reranker = ChunkReranker(client=client)

    assert reranker._client is client
    reranker.rerank(query="q", chunks=chunks, top_n=5)  # exercises the injected client
