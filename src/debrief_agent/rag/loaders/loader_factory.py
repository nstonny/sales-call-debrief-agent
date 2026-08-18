from collections.abc import Callable
from pathlib import Path
from typing import Final

from langchain_core.documents import Document

from debrief_agent.rag.loaders.docx_loader import DOCXLoaderService
from debrief_agent.rag.loaders.pdf_loader import PDFLoaderService
from debrief_agent.rag.loaders.text_loader import TextLoaderService

LoaderFn = Callable[[Path], list[Document]]


class LoaderFactory:
    def __init__(self) -> None:
        self._pdf_loader = PDFLoaderService()
        self._docx_loader = DOCXLoaderService()
        self._text_loader = TextLoaderService()
        self._loaders_by_extension: Final[dict[str, LoaderFn]] = {
            ".pdf": self._pdf_loader.load,
            ".docx": self._docx_loader.load,
            ".txt": self._text_loader.load,
        }

    def _resolve_loader(self, file_path: Path) -> LoaderFn | None:
        return self._loaders_by_extension.get(file_path.suffix.lower())

    def load_documents(self, knowledge_base_path: Path) -> list[Document]:
        """Recursively load all supported documents from the knowledge base directory."""

        documents: list[Document] = []

        for file_path in knowledge_base_path.rglob("*"):
            if not file_path.is_file():
                continue

            loader = self._resolve_loader(file_path)
            if loader is None:
                continue

            documents.extend(loader(file_path))

        return documents
