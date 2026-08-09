"""Unit tests for CoachingGuideChunker.

These tests exercise the pure chunking logic: heading detection, section
splitting, long-section (paragraph then sentence) splitting, chunk metadata,
and the JSONL trace artifact. No external services are involved.
"""

import json

import pytest

from debrief_agent.rag.splitters.coaching_guide_chunker import CoachingGuideChunker


# ---------------------------------------------------------------------------
# __init__ validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_value", [0, -1, -1200])
def test_init_rejects_non_positive_max_chars(bad_value):
    with pytest.raises(ValueError, match="max_chars must be > 0"):
        CoachingGuideChunker(max_chars=bad_value)


def test_init_accepts_positive_max_chars():
    chunker = CoachingGuideChunker(max_chars=500)
    assert chunker._max_chars == 500


# ---------------------------------------------------------------------------
# _looks_like_heading heuristics
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Discovery Best Practices",       # title-case phrase
        "Objection Handling",             # two title-case words
        "OVERVIEW",                       # all caps
        "1. Introduction",                # numbered with dot
        "2) Steps To Follow",             # numbered with paren
    ],
)
def test_looks_like_heading_true(text):
    assert CoachingGuideChunker._looks_like_heading(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "This is a sentence that ends with a period.",  # ends with '.'
        "ask open questions to surface the customer pain",  # lowercase body
        "x" * 91,                                        # too long (> 90 chars)
        "One Two Three Four Five Six Seven Eight Nine Ten Eleven",  # > 10 words
        "",                                              # empty
        "123 456",                                       # no letters
    ],
)
def test_looks_like_heading_false(text):
    assert CoachingGuideChunker._looks_like_heading(text) is False


# ---------------------------------------------------------------------------
# Section splitting via chunk_document
# ---------------------------------------------------------------------------


def test_chunk_document_splits_by_headings(coaching_guide_document):
    chunker = CoachingGuideChunker()
    chunks = chunker.chunk_document(coaching_guide_document)

    titles = [c.metadata["section_title"] for c in chunks]
    assert titles == ["Overview", "Discovery Best Practices", "Objection Handling"]


def test_chunk_document_text_before_first_heading_is_overview(make_doc):
    doc = make_doc("Intro line here without a heading.\n\nActual Heading\nBody text.")
    chunks = CoachingGuideChunker().chunk_document(doc)

    assert chunks[0].metadata["section_title"] == "Overview"
    assert "Intro line here" in chunks[0].page_content


def test_chunk_index_is_monotonic_across_sections(coaching_guide_document):
    chunks = CoachingGuideChunker().chunk_document(coaching_guide_document)
    assert [c.metadata["chunk_index"] for c in chunks] == list(range(len(chunks)))


def test_source_metadata_is_preserved(coaching_guide_document):
    chunks = CoachingGuideChunker().chunk_document(coaching_guide_document)
    for chunk in chunks:
        assert chunk.metadata["source"] == "coaching_guide.docx"
        assert chunk.metadata["category"] == "coaching_guides"


def test_heading_trailing_colon_is_stripped(make_doc):
    doc = make_doc("Summary:\nThe rep closed strongly.")
    chunks = CoachingGuideChunker().chunk_document(doc)
    assert chunks[0].metadata["section_title"] == "Summary"


def test_numbered_heading_starts_new_section(make_doc):
    doc = make_doc("1. Discovery\nAsk questions.\n2. Demo\nShow value.")
    chunks = CoachingGuideChunker().chunk_document(doc)
    titles = [c.metadata["section_title"] for c in chunks]
    assert titles == ["1. Discovery", "2. Demo"]


def test_no_headings_yields_single_overview_chunk(make_doc):
    doc = make_doc("just one line of body text without any heading structure")
    chunks = CoachingGuideChunker().chunk_document(doc)
    assert len(chunks) == 1
    assert chunks[0].metadata["section_title"] == "Overview"


@pytest.mark.parametrize("content", ["", "   ", "\n\n\t\n"])
def test_empty_or_whitespace_document_yields_no_chunks(make_doc, content):
    chunks = CoachingGuideChunker().chunk_document(make_doc(content))
    assert chunks == []


# ---------------------------------------------------------------------------
# Long-section splitting
# ---------------------------------------------------------------------------


def test_long_section_splits_on_paragraph_boundaries(make_doc):
    para_a = "First paragraph is here and it is reasonably sized text."
    para_b = "Second paragraph follows after a blank line here as well."
    doc = make_doc(f"Heading One\n{para_a}\n\n{para_b}")

    chunks = CoachingGuideChunker(max_chars=60).chunk_document(doc)

    assert len(chunks) == 2
    assert [c.metadata["section_chunk_index"] for c in chunks] == [0, 1]
    assert all(c.metadata["section_title"] == "Heading One" for c in chunks)
    assert all(len(c.page_content) <= 60 for c in chunks)


def test_oversized_paragraph_falls_back_to_sentence_split(make_doc):
    body = "Sentence one here. Sentence two here. Sentence three here."
    doc = make_doc(f"Heading\n{body}")

    chunks = CoachingGuideChunker(max_chars=25).chunk_document(doc)

    # Every chunk stays within the bound...
    assert all(len(c.page_content) <= 25 for c in chunks)
    # ...and no sentence content is lost.
    joined = " ".join(c.page_content for c in chunks)
    for sentence in ("Sentence one", "Sentence two", "Sentence three"):
        assert sentence in joined


def test_short_section_stays_single_chunk(make_doc):
    doc = make_doc("Heading\nShort body under the limit.")
    chunks = CoachingGuideChunker(max_chars=1200).chunk_document(doc)
    assert len(chunks) == 1
    assert chunks[0].metadata["section_chunk_index"] == 0


# ---------------------------------------------------------------------------
# chunk_documents (batch) + trace artifact
# ---------------------------------------------------------------------------


def test_chunk_documents_concatenates_all_chunks(coaching_guide_document, make_doc):
    other = make_doc("Heading A\nBody A.", source="other.docx", category="coaching_guides")
    chunker = CoachingGuideChunker()

    combined = chunker.chunk_documents([coaching_guide_document, other])
    expected = chunker.chunk_document(coaching_guide_document) + chunker.chunk_document(other)

    assert len(combined) == len(expected)


def test_chunk_documents_writes_trace_jsonl(tmp_path, coaching_guide_document):
    trace_path = tmp_path / "nested" / "trace.jsonl"
    chunker = CoachingGuideChunker()

    chunks = chunker.chunk_documents([coaching_guide_document], trace_output_path=trace_path)

    assert trace_path.exists()
    rows = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    row = rows[0]
    assert row["source"] == "coaching_guide.docx"
    assert row["category"] == "coaching_guides"
    assert row["total_chunks"] == len(chunks)
    assert len(row["chunks"]) == len(chunks)


def test_chunk_documents_without_trace_path_writes_nothing(tmp_path, coaching_guide_document):
    chunker = CoachingGuideChunker()
    chunker.chunk_documents([coaching_guide_document])  # no trace_output_path
    assert list(tmp_path.iterdir()) == []
