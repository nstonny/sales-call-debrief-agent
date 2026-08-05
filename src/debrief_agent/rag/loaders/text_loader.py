from pathlib import Path

from langchain_community.document_loaders import TextLoader
from langchain_core.documents import Document

class TextLoaderService:
    """Loads text files and enriches each chunk with consistent metadata."""

    def load(self, text_path: Path) -> list[Document]:
        """Load one text file and attach source/category metadata to each returned document."""
        loader = TextLoader(str(text_path), encoding="utf-8")
        documents = loader.load()

        for docs in documents:
            docs.metadata.update(
                {
                    "source": text_path.name,
                    "category": text_path.parent.name,
                    "document_type": "txt",
                }
            )
        return documents

def load_text(text_path: Path) -> list[Document]:
    """Compatibility helper for call sites that still use function-style loading."""
    return TextLoaderService().load(text_path)
