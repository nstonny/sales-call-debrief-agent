"""Route-level tests for the transcript-library endpoints.

This repo has no FastAPI TestClient-based tests yet — only tests/unit/*
service/schema tests built on conftest.py's stub-object pattern. This file
establishes that pattern one layer up: a fake AsyncSession stands in for the
database (no real DB touched), and the module-level extractor/analyzer
singletons in routes/upload.py are monkeypatched, mirroring how conftest.py
already stubs the OpenAI client underneath them.
"""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from debrief_agent.api.routes import transcripts as transcripts_route
from debrief_agent.api.routes import upload as upload_route
from debrief_agent.app.main import app
from debrief_agent.core.database import get_db


class FakeAsyncSession:
    """Stands in for AsyncSession: no real DB, just enough for the route to run."""

    def add(self, obj: object) -> None:
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        if hasattr(obj, "created_at") and obj.created_at is None:
            obj.created_at = datetime.now(UTC)

    async def flush(self) -> None:
        pass

    async def refresh(self, _obj: object) -> None:
        pass

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass


@pytest.fixture
def client():
    async def _override_get_db():
        yield FakeAsyncSession()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def sample_transcripts_dir(tmp_path, monkeypatch):
    """Three sample files named so a lexicographic sort would misorder them."""
    (tmp_path / "transcript_2.txt").write_text("Second call transcript.")
    (tmp_path / "transcript_10.txt").write_text("Tenth call transcript.")
    (tmp_path / "transcript_1.txt").write_text("First call transcript.")
    monkeypatch.setattr(transcripts_route, "TRANSCRIPTS_DIR", tmp_path)
    return tmp_path


def test_list_transcripts_sorts_numerically(client, sample_transcripts_dir):
    response = client.get("/api/transcripts")

    assert response.status_code == 200
    assert response.json() == ["transcript_1.txt", "transcript_2.txt", "transcript_10.txt"]


def test_get_transcript_content(client, sample_transcripts_dir):
    response = client.get("/api/transcripts/transcript_1.txt")

    assert response.status_code == 200
    assert response.json() == {
        "filename": "transcript_1.txt",
        "content": "First call transcript.",
    }


def test_get_transcript_content_unknown_filename_404(client, sample_transcripts_dir):
    response = client.get("/api/transcripts/does_not_exist.txt")

    assert response.status_code == 404


def test_analyze_transcript_unknown_filename_404(client, sample_transcripts_dir):
    response = client.post("/api/transcripts/does_not_exist.txt/analyze", json={})

    assert response.status_code == 404


def test_analyze_transcript_success(client, sample_transcripts_dir, monkeypatch):
    fake_extractor = SimpleNamespace(
        extract=AsyncMock(
            return_value={
                "rep_name": "Natalie",
                "contact_name": "Brian",
                "contact_title": "VP Sales",
                "deal_stage": "discovery",
            }
        )
    )
    fake_analyzer = SimpleNamespace(
        analyze=AsyncMock(
            return_value={
                "summary": "Productive discovery call.",
                "next_steps": "Send proposal.",
                "competitor_mentioned": None,
                "strengths": ["Asked open questions"],
                "areas_for_improvement": [],
                "action_items": ["Follow up next week"],
                "objections_raised": [],
                "sentiment": "positive",
                "score": 4.5,
            }
        )
    )
    monkeypatch.setattr(upload_route, "metadata_extractor", fake_extractor)
    monkeypatch.setattr(upload_route, "call_analyzer", fake_analyzer)

    response = client.post(
        "/api/transcripts/transcript_1.txt/analyze",
        json={"company": "Acme Corp", "deal_value": 25000},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "transcript_1.txt"
    assert body["rep_name"] == "Natalie"
    assert body["company"] == "Acme Corp"
    assert body["analysis"]["sentiment"] == "positive"
    fake_extractor.extract.assert_awaited_once()
    fake_analyzer.analyze.assert_awaited_once()


def test_analyze_transcript_empty_body_defaults_to_no_metadata(
    client, sample_transcripts_dir, monkeypatch
):
    fake_extractor = SimpleNamespace(
        extract=AsyncMock(
            return_value={
                "rep_name": None,
                "contact_name": None,
                "contact_title": None,
                "deal_stage": None,
            }
        )
    )
    fake_analyzer = SimpleNamespace(
        analyze=AsyncMock(
            return_value={
                "summary": None,
                "next_steps": None,
                "competitor_mentioned": None,
                "strengths": [],
                "areas_for_improvement": [],
                "action_items": [],
                "objections_raised": [],
                "sentiment": None,
                "score": None,
            }
        )
    )
    monkeypatch.setattr(upload_route, "metadata_extractor", fake_extractor)
    monkeypatch.setattr(upload_route, "call_analyzer", fake_analyzer)

    response = client.post("/api/transcripts/transcript_2.txt/analyze")

    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "transcript_2.txt"
    assert body["company"] is None
