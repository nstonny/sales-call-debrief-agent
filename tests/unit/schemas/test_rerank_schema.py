"""Unit tests for the RerankResult schema."""

import pytest
from pydantic import ValidationError

from debrief_agent.schemas.rerank import RerankedChunkRef, RerankResult


def test_rankings_default_to_empty_list():
    result = RerankResult(rankings=[])
    assert result.rankings == []


def test_valid_ranking_round_trip():
    result = RerankResult(
        rankings=[
            RerankedChunkRef(index=2, relevance_score=0.9),
            RerankedChunkRef(index=0, relevance_score=0.4),
        ]
    )
    restored = RerankResult.model_validate(result.model_dump())
    assert restored == result


def test_rankings_preserve_given_order():
    result = RerankResult(
        rankings=[
            RerankedChunkRef(index=5, relevance_score=0.8),
            RerankedChunkRef(index=1, relevance_score=0.6),
            RerankedChunkRef(index=3, relevance_score=0.2),
        ]
    )
    assert [ref.index for ref in result.rankings] == [5, 1, 3]


@pytest.mark.parametrize("bad_index", ["not-an-int", None, 1.5])
def test_index_rejects_non_integer(bad_index):
    with pytest.raises(ValidationError):
        RerankedChunkRef(index=bad_index, relevance_score=0.5)


@pytest.mark.parametrize("bad_score", ["not-a-float", None])
def test_relevance_score_rejects_non_numeric(bad_score):
    with pytest.raises(ValidationError):
        RerankedChunkRef(index=0, relevance_score=bad_score)


def test_missing_rankings_is_invalid():
    with pytest.raises(ValidationError):
        RerankResult()
