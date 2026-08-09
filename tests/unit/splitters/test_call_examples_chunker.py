"""Unit tests for CallExamplesChunker.

Covers dashed-line header detection (`_is_dashed_line`, `_find_section_headers`),
one-chunk-per-section splitting, the "Overview" fallback for preamble text,
metadata stability, and the JSONL trace artifact. No external services involved.
"""

import json

import pytest

from debrief_agent.rag.splitters.call_examples_chunker import CallExamplesChunker


# ---------------------------------------------------------------------------
# _is_dashed_line
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["----------", "-" * 10, "-" * 40])
def test_is_dashed_line_true(value):
    assert CallExamplesChunker._is_dashed_line(value) is True


@pytest.mark.parametrize(
    "value",
    [
        "-" * 9,          # too short (must be >= 10)
        "",               # empty
        "---- ----",      # contains a space
        "----------x",    # contains a non-dash char
        "==========",     # wrong char
        "—" * 10,         # em dashes, not hyphens
    ],
)
def test_is_dashed_line_false(value):
    assert CallExamplesChunker._is_dashed_line(value) is False


# ---------------------------------------------------------------------------
# _find_section_headers
# ---------------------------------------------------------------------------


def test_find_section_headers_detects_wrapped_titles():
    lines = [
        "----------",
        "First Section",
        "----------",
        "body line",
        "another body line",
        "----------",
        "Second Section",
        "----------",
    ]
    headers = CallExamplesChunker._find_section_headers(lines)
    assert headers == [(0, "First Section"), (5, "Second Section")]


def test_find_section_headers_ignores_blank_title():
    lines = ["----------", "", "----------"]
    assert CallExamplesChunker._find_section_headers(lines) == []


def test_find_section_headers_empty_when_no_dashes():
    lines = ["just", "some", "plain", "lines"]
    assert CallExamplesChunker._find_section_headers(lines) == []


# ---------------------------------------------------------------------------
# chunk_document
# ---------------------------------------------------------------------------


def test_chunk_document_produces_one_chunk_per_section(call_examples_document):
    chunks = CallExamplesChunker().chunk_document(call_examples_document)
    titles = [c.metadata["section_title"] for c in chunks]
    assert titles == ["Overview", "Successful Discovery Call", "Failed Pricing Call"]


def test_preamble_becomes_overview_chunk(call_examples_document):
    chunks = CallExamplesChunker().chunk_document(call_examples_document)
    overview = chunks[0]
    assert overview.metadata["section_title"] == "Overview"
    assert overview.page_content == "Some preamble before the sections."


def test_section_bodies_are_captured(call_examples_document):
    chunks = CallExamplesChunker().chunk_document(call_examples_document)
    by_title = {c.metadata["section_title"]: c.page_content for c in chunks}
    assert by_title["Successful Discovery Call"] == (
        "Rep asked strong discovery questions.\nRep confirmed the impact clearly."
    )
    assert by_title["Failed Pricing Call"] == "Rep discounted too early."


def test_no_preamble_means_no_overview(make_doc):
    content = (
        "----------\n"
        "Only Section\n"
        "----------\n"
        "The body of the only section.\n"
    )
    chunks = CallExamplesChunker().chunk_document(make_doc(content))
    titles = [c.metadata["section_title"] for c in chunks]
    assert titles == ["Only Section"]


def test_document_without_headers_is_single_overview(make_doc):
    doc = make_doc("no dashed headers here\njust two lines of text")
    chunks = CallExamplesChunker().chunk_document(doc)
    assert len(chunks) == 1
    assert chunks[0].metadata["section_title"] == "Overview"
    assert chunks[0].page_content == "no dashed headers here\njust two lines of text"


def test_empty_section_body_is_skipped(make_doc):
    # "Empty Section" header immediately followed by the next header -> no body.
    content = (
        "----------\n"
        "Empty Section\n"
        "----------\n"
        "----------\n"
        "Real Section\n"
        "----------\n"
        "Has content.\n"
    )
    chunks = CallExamplesChunker().chunk_document(make_doc(content))
    titles = [c.metadata["section_title"] for c in chunks]
    assert "Empty Section" not in titles
    assert titles == ["Real Section"]


@pytest.mark.parametrize("content", ["", "   ", "\n\n\n"])
def test_empty_document_yields_no_chunks(make_doc, content):
    assert CallExamplesChunker().chunk_document(make_doc(content)) == []


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


def test_chunk_index_is_monotonic(call_examples_document):
    chunks = CallExamplesChunker().chunk_document(call_examples_document)
    assert [c.metadata["chunk_index"] for c in chunks] == list(range(len(chunks)))


def test_source_metadata_is_preserved(call_examples_document):
    chunks = CallExamplesChunker().chunk_document(call_examples_document)
    for chunk in chunks:
        assert chunk.metadata["source"] == "call_examples.txt"
        assert chunk.metadata["category"] == "call_examples"


# ---------------------------------------------------------------------------
# chunk_documents (batch) + trace artifact
# ---------------------------------------------------------------------------


def test_chunk_documents_concatenates_all_chunks(call_examples_document, make_doc):
    other = make_doc(
        "----------\nExtra\n----------\nExtra body.\n",
        source="other.txt",
        category="call_examples",
    )
    chunker = CallExamplesChunker()
    combined = chunker.chunk_documents([call_examples_document, other])
    expected = (
        chunker.chunk_document(call_examples_document)
        + chunker.chunk_document(other)
    )
    assert len(combined) == len(expected)


def test_chunk_documents_writes_trace_jsonl(tmp_path, call_examples_document):
    trace_path = tmp_path / "nested" / "trace.jsonl"
    chunker = CallExamplesChunker()

    chunks = chunker.chunk_documents([call_examples_document], trace_output_path=trace_path)

    assert trace_path.exists()
    rows = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["source"] == "call_examples.txt"
    assert rows[0]["total_chunks"] == len(chunks)
    assert len(rows[0]["chunks"]) == len(chunks)


def test_chunk_documents_without_trace_path_writes_nothing(tmp_path, call_examples_document):
    CallExamplesChunker().chunk_documents([call_examples_document])
    assert list(tmp_path.iterdir()) == []
