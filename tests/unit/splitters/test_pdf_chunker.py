"""Unit tests for PDFChunker.

Covers markdown-heading section splitting, long-section (paragraph then
sentence) splitting, chunk metadata, directory loading of markdown files,
and the JSONL trace artifact. No external services are involved.
"""

import json

import pytest

from debrief_agent.rag.splitters.pdf_chunker import PDFChunker

# ---------------------------------------------------------------------------
# __init__ validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_value", [0, -1, -1200])
def test_init_rejects_non_positive_max_chars(bad_value):
    with pytest.raises(ValueError, match="max_chars must be > 0"):
        PDFChunker(max_chars=bad_value)


def test_init_accepts_positive_max_chars():
    assert PDFChunker(max_chars=500)._max_chars == 500


# ---------------------------------------------------------------------------
# Markdown-heading section splitting
# ---------------------------------------------------------------------------


def test_chunk_document_splits_by_markdown_headings(pdf_markdown_document):
    chunks = PDFChunker().chunk_document(pdf_markdown_document)
    titles = [c.metadata["section_title"] for c in chunks]
    assert titles == ["Overview", "MEDDIC", "Qualification"]


def test_text_before_first_heading_is_overview(make_doc):
    doc = make_doc("Intro paragraph.\n\n# Heading\nBody text.")
    chunks = PDFChunker().chunk_document(doc)
    assert chunks[0].metadata["section_title"] == "Overview"
    assert "Intro paragraph" in chunks[0].page_content


@pytest.mark.parametrize(
    "heading_line,expected_title",
    [
        ("# H1", "H1"),
        ("## H2", "H2"),
        ("###### H6", "H6"),
    ],
)
def test_heading_levels_one_through_six(make_doc, heading_line, expected_title):
    doc = make_doc(f"{heading_line}\nBody under the heading.")
    chunks = PDFChunker().chunk_document(doc)
    assert chunks[0].metadata["section_title"] == expected_title


def test_seven_hashes_is_not_a_heading(make_doc):
    # Markdown headings only go up to level 6; 7 hashes stays body text.
    doc = make_doc("####### NotAHeading\nBody.")
    chunks = PDFChunker().chunk_document(doc)
    assert chunks[0].metadata["section_title"] == "Overview"
    assert "####### NotAHeading" in chunks[0].page_content


def test_no_headings_yields_single_overview_chunk(make_doc):
    doc = make_doc("plain body text with no markdown headings at all")
    chunks = PDFChunker().chunk_document(doc)
    assert len(chunks) == 1
    assert chunks[0].metadata["section_title"] == "Overview"


@pytest.mark.parametrize("content", ["", "   ", "\n\n\t\n"])
def test_empty_or_whitespace_document_yields_no_chunks(make_doc, content):
    assert PDFChunker().chunk_document(make_doc(content)) == []


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


def test_chunk_index_is_monotonic_across_sections(pdf_markdown_document):
    chunks = PDFChunker().chunk_document(pdf_markdown_document)
    assert [c.metadata["chunk_index"] for c in chunks] == list(range(len(chunks)))


def test_source_metadata_is_preserved(pdf_markdown_document):
    chunks = PDFChunker().chunk_document(pdf_markdown_document)
    for chunk in chunks:
        assert chunk.metadata["source"] == "frameworks.md"
        assert chunk.metadata["category"] == "sales_frameworks"


# ---------------------------------------------------------------------------
# Long-section splitting
# ---------------------------------------------------------------------------


def test_long_section_splits_on_paragraph_boundaries(make_doc):
    para_a = "First paragraph is here and it is reasonably sized text."
    para_b = "Second paragraph follows after a blank line here as well."
    doc = make_doc(f"# Heading One\n{para_a}\n\n{para_b}")

    chunks = PDFChunker(max_chars=60).chunk_document(doc)

    assert len(chunks) == 2
    assert [c.metadata["section_chunk_index"] for c in chunks] == [0, 1]
    assert all(c.metadata["section_title"] == "Heading One" for c in chunks)
    assert all(len(c.page_content) <= 60 for c in chunks)


def test_oversized_paragraph_falls_back_to_sentence_split(make_doc):
    body = "Sentence one here. Sentence two here. Sentence three here."
    doc = make_doc(f"# Heading\n{body}")

    chunks = PDFChunker(max_chars=25).chunk_document(doc)

    assert all(len(c.page_content) <= 25 for c in chunks)
    joined = " ".join(c.page_content for c in chunks)
    for sentence in ("Sentence one", "Sentence two", "Sentence three"):
        assert sentence in joined


def test_short_section_stays_single_chunk(make_doc):
    doc = make_doc("# Heading\nShort body under the limit.")
    chunks = PDFChunker(max_chars=1200).chunk_document(doc)
    assert len(chunks) == 1
    assert chunks[0].metadata["section_chunk_index"] == 0


# ---------------------------------------------------------------------------
# Directory loading via chunk_markdown_directory
# ---------------------------------------------------------------------------


def test_chunk_markdown_directory_loads_and_chunks_files(tmp_path):
    category_dir = tmp_path / "sales_frameworks"
    category_dir.mkdir()
    (category_dir / "meddic.md").write_text("# MEDDIC\nQualify well.", encoding="utf-8")
    (category_dir / "spin.md").write_text("# SPIN\nAsk questions.", encoding="utf-8")

    chunks = PDFChunker().chunk_markdown_directory(tmp_path)

    sources = {c.metadata["source"] for c in chunks}
    assert sources == {"meddic.md", "spin.md"}
    # category is taken from the parent directory name
    assert all(c.metadata["category"] == "sales_frameworks" for c in chunks)
    assert all(c.metadata["document_type"] == "md" for c in chunks)


def test_chunk_markdown_directory_rejects_missing_directory(tmp_path):
    missing = tmp_path / "does_not_exist"
    with pytest.raises(ValueError, match="must be an existing directory"):
        PDFChunker().chunk_markdown_directory(missing)


def test_chunk_markdown_directory_rejects_file_path(tmp_path):
    file_path = tmp_path / "a_file.md"
    file_path.write_text("# H\nbody", encoding="utf-8")
    with pytest.raises(ValueError, match="must be an existing directory"):
        PDFChunker().chunk_markdown_directory(file_path)


def test_chunk_markdown_directory_ignores_non_markdown(tmp_path):
    (tmp_path / "keep.md").write_text("# Keep\nbody", encoding="utf-8")
    (tmp_path / "ignore.txt").write_text("not markdown", encoding="utf-8")

    chunks = PDFChunker().chunk_markdown_directory(tmp_path)
    assert {c.metadata["source"] for c in chunks} == {"keep.md"}


# ---------------------------------------------------------------------------
# Trace artifact
# ---------------------------------------------------------------------------


def test_chunk_documents_writes_trace_jsonl(tmp_path, pdf_markdown_document):
    trace_path = tmp_path / "nested" / "trace.jsonl"
    chunker = PDFChunker()

    chunks = chunker.chunk_documents([pdf_markdown_document], trace_output_path=trace_path)

    assert trace_path.exists()
    rows = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["source"] == "frameworks.md"
    assert rows[0]["total_chunks"] == len(chunks)
    assert len(rows[0]["chunks"]) == len(chunks)


def test_chunk_documents_without_trace_path_writes_nothing(tmp_path, pdf_markdown_document):
    PDFChunker().chunk_documents([pdf_markdown_document])
    assert list(tmp_path.iterdir()) == []
