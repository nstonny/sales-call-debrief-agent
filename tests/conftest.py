"""Shared pytest fixtures for the debrief-agent test suite.

Fixtures here are intentionally dependency-light: they build plain in-memory
objects (LangChain `Document`s, fake Qdrant points, a stub OpenAI client) so
unit tests never touch Qdrant, OpenAI, Langfuse, or the database.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from langchain_core.documents import Document

# ---------------------------------------------------------------------------
# LangChain Document fixtures (chunker / loader tests)
# ---------------------------------------------------------------------------


def make_document(page_content: str, **metadata: Any) -> Document:
    """Build a LangChain Document with arbitrary metadata."""
    return Document(page_content=page_content, metadata=dict(metadata))


@pytest.fixture
def make_doc():
    """Factory fixture for building `Document`s inside a test."""
    return make_document


@pytest.fixture
def coaching_guide_document() -> Document:
    """A small heading-structured document for the coaching-guide chunker."""
    content = (
        "Overview text before any heading.\n"
        "\n"
        "Discovery Best Practices\n"
        "Ask open questions to surface pain.\n"
        "Confirm the impact before proposing a solution.\n"
        "\n"
        "Objection Handling\n"
        "Acknowledge the concern, then reframe with value.\n"
    )
    return make_document(
        content,
        source="coaching_guide.docx",
        category="coaching_guides",
    )


@pytest.fixture
def pdf_markdown_document() -> Document:
    """A markdown-heading document for the PDF chunker."""
    content = (
        "Intro paragraph with no heading yet.\n"
        "\n"
        "# MEDDIC\n"
        "Metrics, Economic buyer, Decision criteria.\n"
        "\n"
        "## Qualification\n"
        "Qualify early and often.\n"
    )
    return make_document(
        content,
        source="frameworks.md",
        category="sales_frameworks",
    )


@pytest.fixture
def call_examples_document() -> Document:
    """A dashed-header call-examples document.

    Section titles are wrapped in dashed separators; body lines are not, so
    they are never mistaken for headers.
    """
    content = (
        "Some preamble before the sections.\n"
        "\n"
        "----------\n"
        "Successful Discovery Call\n"
        "----------\n"
        "Rep asked strong discovery questions.\n"
        "Rep confirmed the impact clearly.\n"
        "----------\n"
        "Failed Pricing Call\n"
        "----------\n"
        "Rep discounted too early.\n"
    )
    return make_document(
        content,
        source="call_examples.txt",
        category="call_examples",
    )


# ---------------------------------------------------------------------------
# Fake Qdrant point (VectorRetriever tests)
# ---------------------------------------------------------------------------


@dataclass
class FakeScoredPoint:
    """Minimal stand-in for qdrant_client ScoredPoint used by VectorRetriever."""

    score: float
    payload: dict[str, Any] | None = None


@pytest.fixture
def make_point():
    """Factory for building fake Qdrant scored points."""

    def _make(score: float = 0.9, payload: dict[str, Any] | None = None) -> FakeScoredPoint:
        return FakeScoredPoint(score=score, payload=payload)

    return _make


@dataclass
class FakeRecord:
    """Minimal stand-in for a qdrant_client Record returned by `scroll`."""

    payload: dict[str, Any] | None = None


@pytest.fixture
def make_record():
    """Factory for building fake Qdrant scroll records (used by BM25Retriever tests)."""

    def _make(payload: dict[str, Any] | None = None) -> FakeRecord:
        return FakeRecord(payload=payload)

    return _make


# ---------------------------------------------------------------------------
# Fake OpenAI Responses client (MetadataExtractor tests)
# ---------------------------------------------------------------------------


@dataclass
class FakeResponsesAPI:
    """Stub for `client.responses` exposing an async `parse`."""

    result: Any = None
    exc: Exception | None = None

    async def parse(self, **_kwargs: Any) -> Any:
        if self.exc is not None:
            raise self.exc
        return self.result


@dataclass
class FakeOpenAIClient:
    """Stub AsyncOpenAI client injectable into `MetadataExtractor(client=...)`."""

    responses: FakeResponsesAPI = field(default_factory=FakeResponsesAPI)


@pytest.fixture
def make_openai_client():
    """Factory that builds a fake OpenAI client returning `result` or raising `exc`."""

    def _make(result: Any = None, exc: Exception | None = None) -> FakeOpenAIClient:
        return FakeOpenAIClient(responses=FakeResponsesAPI(result=result, exc=exc))

    return _make
