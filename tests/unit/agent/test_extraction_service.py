"""Unit tests for MetadataExtractor.extract.

Exercises the full failure contract without touching the network: the fake
OpenAI client is injected via the constructor, and small stand-in response
objects drive the success / refusal / API-error / validation paths.
"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from openai import OpenAIError

from debrief_agent.rag.agent.services.extraction import MetadataExtractor
from debrief_agent.schemas.extraction import CallMetadataExtraction, DealStage


# ---------------------------------------------------------------------------
# Fake Responses-API response builders
# ---------------------------------------------------------------------------


def _refusal_response(reason: str = "policy violation"):
    """A response whose output contains a refusal content part."""
    refusal_part = SimpleNamespace(type="refusal", refusal=reason)
    item = SimpleNamespace(content=[refusal_part])
    return SimpleNamespace(output=[item], output_parsed=None)


def _parsed_response(parsed):
    """A response exposing `output_parsed` directly and an empty output list."""
    return SimpleNamespace(output=[], output_parsed=parsed)


def _empty_response():
    """A response with no parsed payload anywhere."""
    return SimpleNamespace(output=[], output_parsed=None)


# ---------------------------------------------------------------------------
# Success paths
# ---------------------------------------------------------------------------


async def test_extract_returns_dump_for_parsed_model(make_openai_client):
    parsed = CallMetadataExtraction(rep_name="Dana", deal_stage="proposal")
    client = make_openai_client(result=_parsed_response(parsed))
    extractor = MetadataExtractor(client=client)

    result = await extractor.extract(transcript="some transcript")

    assert isinstance(result, dict)
    assert result["rep_name"] == "Dana"
    assert result["deal_stage"] == DealStage.PROPOSAL


async def test_extract_validates_dict_payload(make_openai_client):
    client = make_openai_client(
        result=_parsed_response({"rep_name": "Sam", "deal_stage": "discovery"})
    )
    extractor = MetadataExtractor(client=client)

    result = await extractor.extract(transcript="t")

    assert result["rep_name"] == "Sam"
    assert result["deal_stage"] == DealStage.DISCOVERY


async def test_extract_normalizes_blank_fields(make_openai_client):
    # The schema validator turns blank strings into None.
    client = make_openai_client(
        result=_parsed_response({"rep_name": "   ", "contact_name": "Lee"})
    )
    extractor = MetadataExtractor(client=client)

    result = await extractor.extract(transcript="t")

    assert result["rep_name"] is None
    assert result["contact_name"] == "Lee"


async def test_extract_passes_session_id_without_error(make_openai_client):
    parsed = CallMetadataExtraction(rep_name="Dana")
    client = make_openai_client(result=_parsed_response(parsed))
    extractor = MetadataExtractor(client=client)

    result = await extractor.extract(transcript="t", session_id="call-123")
    assert result["rep_name"] == "Dana"


# ---------------------------------------------------------------------------
# OpenAI API error -> 502
# ---------------------------------------------------------------------------


async def test_extract_raises_502_on_openai_error(make_openai_client):
    client = make_openai_client(exc=OpenAIError("rate limited"))
    extractor = MetadataExtractor(client=client)

    with pytest.raises(HTTPException) as exc_info:
        await extractor.extract(transcript="t")

    assert exc_info.value.status_code == 502
    assert "OpenAI API error" in exc_info.value.detail


# ---------------------------------------------------------------------------
# LLM refusal -> 502
# ---------------------------------------------------------------------------


async def test_extract_raises_502_on_refusal(make_openai_client):
    client = make_openai_client(result=_refusal_response("cannot comply"))
    extractor = MetadataExtractor(client=client)

    with pytest.raises(HTTPException) as exc_info:
        await extractor.extract(transcript="t")

    assert exc_info.value.status_code == 502
    assert "refused" in exc_info.value.detail
    assert "cannot comply" in exc_info.value.detail


# ---------------------------------------------------------------------------
# Missing / invalid parsed payload -> 502
# ---------------------------------------------------------------------------


async def test_extract_raises_502_when_no_parsed_payload(make_openai_client):
    client = make_openai_client(result=_empty_response())
    extractor = MetadataExtractor(client=client)

    with pytest.raises(HTTPException) as exc_info:
        await extractor.extract(transcript="t")

    assert exc_info.value.status_code == 502
    assert "did not match expected schema" in exc_info.value.detail


async def test_extract_raises_502_on_validation_error(make_openai_client):
    # An invalid deal_stage fails Pydantic validation.
    client = make_openai_client(
        result=_parsed_response({"deal_stage": "not_a_real_stage"})
    )
    extractor = MetadataExtractor(client=client)

    with pytest.raises(HTTPException) as exc_info:
        await extractor.extract(transcript="t")

    assert exc_info.value.status_code == 502
    assert "did not match expected schema" in exc_info.value.detail


# ---------------------------------------------------------------------------
# Constructor wiring
# ---------------------------------------------------------------------------


async def test_injected_client_is_used(make_openai_client):
    parsed = CallMetadataExtraction(rep_name="Dana")
    client = make_openai_client(result=_parsed_response(parsed))
    extractor = MetadataExtractor(client=client)

    assert extractor._client is client
    await extractor.extract(transcript="t")  # exercises the injected client end-to-end
