from pathlib import Path

from langchain_community.document_loaders import Docx2txtLoader
from langchain_core.documents import Document


class DOCXLoaderService:
    """Loads DOCX files and enriches each chunk with consistent metadata."""

    def load(self, docx_path: Path) -> list[Document]:
        """Load one DOCX and attach source/category metadata to each returned document."""
        loader = Docx2txtLoader(str(docx_path))
        documents = loader.load()

        for document in documents:
            document.metadata.update(
                {
                    "source": docx_path.name,
                    "category": docx_path.parent.name,
                    "document_type": "docx",
                }
            )
        return documents


def load_docx(docx_path: Path) -> list[Document]:
    """Compatibility helper for call sites that still use function-style loading."""
    return DOCXLoaderService().load(docx_path)
