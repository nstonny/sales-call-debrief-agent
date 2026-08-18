from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document


class PDFLoaderService:
    """Loads PDF files and enriches each page chunk with consistent metadata."""

    def load(self, pdf_path: Path) -> list[Document]:
        """Load one PDF and attach source/category metadata to each returned document."""
        loader = PyPDFLoader(str(pdf_path))
        documents = loader.load()

        for doc in documents:
            doc.metadata.update(
                {
                    "source": pdf_path.name,
                    "category": pdf_path.parent.name,
                    "document_type": "pdf",
                }
            )
        return documents


def load_pdf(pdf_path: Path) -> list[Document]:
    """Compatibility helper for call sites that still use function-style loading."""
    return PDFLoaderService().load(pdf_path)
