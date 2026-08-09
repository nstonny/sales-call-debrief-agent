"""Unit tests for LoaderFactory.

Covers extension-based loader resolution (including case-insensitivity and
unsupported types) and the recursive `load_documents` walk. Only real .txt
files are read; PDF/DOCX routing is asserted at the resolver level so no
binary parsers are exercised.
"""

from pathlib import Path

import pytest

from debrief_agent.rag.loaders.loader_factory import LoaderFactory


@pytest.fixture
def factory():
    return LoaderFactory()


# ---------------------------------------------------------------------------
# _resolve_loader
# ---------------------------------------------------------------------------


def test_resolve_loader_maps_pdf(factory):
    assert factory._resolve_loader(Path("doc.pdf")) == factory._pdf_loader.load


def test_resolve_loader_maps_docx(factory):
    assert factory._resolve_loader(Path("doc.docx")) == factory._docx_loader.load


def test_resolve_loader_maps_txt(factory):
    assert factory._resolve_loader(Path("doc.txt")) == factory._text_loader.load


@pytest.mark.parametrize("name", ["DOC.PDF", "Doc.Docx", "notes.TXT"])
def test_resolve_loader_is_case_insensitive(factory, name):
    assert factory._resolve_loader(Path(name)) is not None


@pytest.mark.parametrize("name", ["image.png", "data.csv", "archive.zip", "noext"])
def test_resolve_loader_returns_none_for_unsupported(factory, name):
    assert factory._resolve_loader(Path(name)) is None


# ---------------------------------------------------------------------------
# load_documents
# ---------------------------------------------------------------------------


def test_load_documents_reads_supported_files(factory, tmp_path):
    category_dir = tmp_path / "coaching_guides"
    category_dir.mkdir()
    (category_dir / "guide.txt").write_text("Coaching content.", encoding="utf-8")

    documents = factory.load_documents(tmp_path)

    assert len(documents) == 1
    doc = documents[0]
    assert "Coaching content." in doc.page_content
    assert doc.metadata["source"] == "guide.txt"
    assert doc.metadata["category"] == "coaching_guides"
    assert doc.metadata["document_type"] == "txt"


def test_load_documents_skips_unsupported_files(factory, tmp_path):
    (tmp_path / "keep.txt").write_text("keep me", encoding="utf-8")
    (tmp_path / "ignore.md").write_text("ignore me", encoding="utf-8")
    (tmp_path / "photo.png").write_bytes(b"\x89PNG\r\n")

    documents = factory.load_documents(tmp_path)

    assert {d.metadata["source"] for d in documents} == {"keep.txt"}


def test_load_documents_recurses_into_subdirectories(factory, tmp_path):
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    (nested / "deep.txt").write_text("deep content", encoding="utf-8")

    documents = factory.load_documents(tmp_path)

    assert len(documents) == 1
    assert documents[0].metadata["source"] == "deep.txt"


def test_load_documents_empty_directory_returns_empty(factory, tmp_path):
    assert factory.load_documents(tmp_path) == []
