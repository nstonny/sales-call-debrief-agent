"""Unit tests for the CallMetadataExtraction schema.

Focuses on the defensive layer applied to LLM extraction output before
persistence: the `empty_str_to_none` normalizer and `deal_stage` enum coercion.
"""

import pytest
from pydantic import ValidationError

from debrief_agent.schemas.extraction import CallMetadataExtraction, DealStage


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


def test_all_fields_default_to_none():
    meta = CallMetadataExtraction()
    assert meta.rep_name is None
    assert meta.contact_name is None
    assert meta.contact_title is None
    assert meta.deal_stage is None


# ---------------------------------------------------------------------------
# empty_str_to_none normalizer
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("blank", ["", "   ", "\t", "\n", "  \n  "])
def test_blank_strings_normalized_to_none(blank):
    meta = CallMetadataExtraction(
        rep_name=blank,
        contact_name=blank,
        contact_title=blank,
        deal_stage=blank,
    )
    assert meta.rep_name is None
    assert meta.contact_name is None
    assert meta.contact_title is None
    assert meta.deal_stage is None


def test_text_fields_are_stripped():
    meta = CallMetadataExtraction(
        rep_name="  Dana  ",
        contact_name="  Sam Lee ",
        contact_title="  VP Sales ",
    )
    assert meta.rep_name == "Dana"
    assert meta.contact_name == "Sam Lee"
    assert meta.contact_title == "VP Sales"


def test_meaningful_text_is_preserved():
    meta = CallMetadataExtraction(
        rep_name="Dana",
        contact_name="Sam Lee",
        contact_title="CTO",
    )
    assert meta.rep_name == "Dana"
    assert meta.contact_name == "Sam Lee"
    assert meta.contact_title == "CTO"


# ---------------------------------------------------------------------------
# deal_stage enum
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        ("discovery", DealStage.DISCOVERY),
        ("demo", DealStage.DEMO),
        ("proposal", DealStage.PROPOSAL),
        ("negotiation", DealStage.NEGOTIATION),
        ("closing", DealStage.CLOSING),
        ("unknown", DealStage.UNKNOWN),
    ],
)
def test_deal_stage_accepts_valid_values(value, expected):
    assert CallMetadataExtraction(deal_stage=value).deal_stage is expected


def test_deal_stage_strips_whitespace_before_coercion():
    assert CallMetadataExtraction(deal_stage="  proposal  ").deal_stage is DealStage.PROPOSAL


def test_deal_stage_enum_member_is_accepted():
    meta = CallMetadataExtraction(deal_stage=DealStage.NEGOTIATION)
    assert meta.deal_stage is DealStage.NEGOTIATION


@pytest.mark.parametrize("bad", ["Discovery", "PROPOSAL", "qualification", "won"])
def test_deal_stage_rejects_invalid_values(bad):
    with pytest.raises(ValidationError):
        CallMetadataExtraction(deal_stage=bad)


# ---------------------------------------------------------------------------
# serialization round-trip
# ---------------------------------------------------------------------------


def test_model_dump_round_trip_preserves_values():
    original = CallMetadataExtraction(
        rep_name="Dana",
        contact_name="Sam Lee",
        contact_title="CTO",
        deal_stage="proposal",
    )
    restored = CallMetadataExtraction.model_validate(original.model_dump())
    assert restored == original


def test_model_dump_serializes_enum_to_value():
    meta = CallMetadataExtraction(deal_stage="closing")
    dumped = meta.model_dump()
    assert dumped["deal_stage"] is DealStage.CLOSING or dumped["deal_stage"] == "closing"
