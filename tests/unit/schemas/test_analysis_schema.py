"""Unit tests for the AnalysisResult schema.

Focuses on the defensive layer that guards messy LLM output before it reaches
the DB/UI: the `empty_str_to_none` normalizer, the `score` bounds, and the
`sentiment` enum coercion.
"""

import pytest
from pydantic import ValidationError

from debrief_agent.schemas.analysis import AnalysisResult, Sentiment


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


def test_all_fields_default_to_none():
    result = AnalysisResult()
    assert result.summary is None
    assert result.next_steps is None
    assert result.competitor_mentioned is None
    assert result.strengths is None
    assert result.areas_for_improvement is None
    assert result.action_items is None
    assert result.objections_raised is None
    assert result.sentiment is None
    assert result.score is None


# ---------------------------------------------------------------------------
# empty_str_to_none normalizer (text + sentiment fields)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("blank", ["", "   ", "\t", "\n", "  \n  "])
def test_blank_strings_normalized_to_none(blank):
    result = AnalysisResult(
        summary=blank,
        next_steps=blank,
        competitor_mentioned=blank,
        sentiment=blank,
    )
    assert result.summary is None
    assert result.next_steps is None
    assert result.competitor_mentioned is None
    assert result.sentiment is None


def test_text_fields_are_stripped():
    result = AnalysisResult(summary="  Strong discovery call.  ")
    assert result.summary == "Strong discovery call."


def test_meaningful_text_is_preserved():
    result = AnalysisResult(
        summary="The rep ran a solid call.",
        next_steps="Send the proposal by Friday.",
        competitor_mentioned="Acme Corp",
    )
    assert result.summary == "The rep ran a solid call."
    assert result.next_steps == "Send the proposal by Friday."
    assert result.competitor_mentioned == "Acme Corp"


# ---------------------------------------------------------------------------
# sentiment enum
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        ("positive", Sentiment.POSITIVE),
        ("neutral", Sentiment.NEUTRAL),
        ("negative", Sentiment.NEGATIVE),
    ],
)
def test_sentiment_accepts_valid_values(value, expected):
    assert AnalysisResult(sentiment=value).sentiment is expected


def test_sentiment_enum_member_is_accepted():
    assert AnalysisResult(sentiment=Sentiment.POSITIVE).sentiment is Sentiment.POSITIVE


@pytest.mark.parametrize("bad", ["happy", "POSITIVE", "mixed", "1"])
def test_sentiment_rejects_invalid_values(bad):
    with pytest.raises(ValidationError):
        AnalysisResult(sentiment=bad)


# ---------------------------------------------------------------------------
# score bounds (0.0 - 5.0)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("score", [0.0, 2.5, 3.5, 5.0])
def test_score_within_bounds_is_accepted(score):
    assert AnalysisResult(score=score).score == score


@pytest.mark.parametrize("score", [-0.1, 5.1, 6.0, 100.0])
def test_score_out_of_bounds_is_rejected(score):
    with pytest.raises(ValidationError):
        AnalysisResult(score=score)


# ---------------------------------------------------------------------------
# list fields
# ---------------------------------------------------------------------------


def test_list_fields_accept_string_lists():
    result = AnalysisResult(
        strengths=["Built rapport", "Handled pricing objection"],
        areas_for_improvement=["Ask more discovery questions"],
        action_items=["Send follow-up email"],
        objections_raised=["pricing too high"],
    )
    assert result.strengths == ["Built rapport", "Handled pricing objection"]
    assert result.areas_for_improvement == ["Ask more discovery questions"]
    assert result.action_items == ["Send follow-up email"]
    assert result.objections_raised == ["pricing too high"]


# ---------------------------------------------------------------------------
# serialization round-trip
# ---------------------------------------------------------------------------


def test_model_dump_round_trip_preserves_values():
    original = AnalysisResult(
        summary="Solid call.",
        sentiment="positive",
        score=4.0,
        strengths=["Good rapport"],
    )
    restored = AnalysisResult.model_validate(original.model_dump())
    assert restored == original


def test_model_validate_from_attributes():
    class ORMLike:
        summary = "From ORM."
        next_steps = None
        competitor_mentioned = None
        strengths = None
        areas_for_improvement = None
        action_items = None
        objections_raised = None
        sentiment = "neutral"
        score = 3.0

    result = AnalysisResult.model_validate(ORMLike())
    assert result.summary == "From ORM."
    assert result.sentiment is Sentiment.NEUTRAL
    assert result.score == 3.0
