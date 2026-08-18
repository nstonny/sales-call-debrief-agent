import json
import re
from pathlib import Path

from langchain_core.documents import Document


class CoachingGuideChunker:
    """Structure-aware chunker for coaching guides loaded from DOCX text."""

    def __init__(self, max_chars: int = 1200) -> None:
        if max_chars <= 0:
            raise ValueError("max_chars must be > 0")
        self._max_chars = max_chars

    def chunk_documents(
        self,
        documents: list[Document],
        trace_output_path: Path | None = None,
    ) -> list[Document]:
        """Chunk multiple documents and optionally write a JSONL review artifact."""
        all_chunks: list[Document] = []
        trace_rows: list[dict] = []

        for document in documents:
            chunks = self.chunk_document(document)
            all_chunks.extend(chunks)

            if trace_output_path is not None:
                trace_rows.append(
                    {
                        "source": document.metadata.get("source", "unknown"),
                        "category": document.metadata.get("category", "unknown"),
                        "total_chunks": len(chunks),
                        "chunks": [
                            {
                                "chunk_index": chunk.metadata.get("chunk_index"),
                                "section_title": chunk.metadata.get("section_title"),
                                "char_count": len(chunk.page_content),
                                "preview": chunk.page_content[:160],
                            }
                            for chunk in chunks
                        ],
                    }
                )

        if trace_output_path is not None:
            self._write_trace_jsonl(trace_rows, trace_output_path)

        return all_chunks

    def chunk_document(self, document: Document) -> list[Document]:
        """Split one document into heading-aware chunks with stable metadata."""
        sections = self._split_into_sections(document.page_content)

        chunks: list[Document] = []
        chunk_index = 0

        for section_title, section_text in sections:
            for section_chunk_index, section_chunk in enumerate(
                self._split_long_section(section_text)
            ):
                chunk_metadata = {
                    **document.metadata,
                    "section_title": section_title,
                    "chunk_index": chunk_index,
                    "section_chunk_index": section_chunk_index,
                }
                chunks.append(Document(page_content=section_chunk, metadata=chunk_metadata))
                chunk_index += 1

        return chunks

    def _split_into_sections(self, text: str) -> list[tuple[str, str]]:
        lines = [line.rstrip() for line in text.splitlines()]

        sections: list[tuple[str, str]] = []
        current_title = "Overview"
        current_lines: list[str] = []

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                current_lines.append("")
                continue

            if self._looks_like_heading(line):
                section_text = "\n".join(current_lines).strip()
                if section_text:
                    sections.append((current_title, section_text))
                current_title = line.rstrip(":")
                current_lines = []
                continue

            current_lines.append(raw_line)

        trailing_text = "\n".join(current_lines).strip()
        if trailing_text:
            sections.append((current_title, trailing_text))

        if not sections:
            full_text = text.strip()
            if not full_text:
                return []
            return [("Overview", full_text)]

        return sections

    def _split_long_section(self, section_text: str) -> list[str]:
        section_text = section_text.strip()
        if not section_text:
            return []
        if len(section_text) <= self._max_chars:
            return [section_text]

        paragraphs = [
            paragraph.strip()
            for paragraph in re.split(r"\n\s*\n", section_text)
            if paragraph.strip()
        ]

        chunks: list[str] = []
        current = ""

        for paragraph in paragraphs:
            candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
            if len(candidate) <= self._max_chars:
                current = candidate
                continue

            if current:
                chunks.append(current)
                current = ""

            if len(paragraph) <= self._max_chars:
                current = paragraph
                continue

            # Extremely long paragraphs are sentence-split to keep chunk size bounded.
            sentence_parts = [
                part.strip() for part in re.split(r"(?<=[.!?])\s+", paragraph) if part.strip()
            ]
            sentence_chunk = ""
            for part in sentence_parts:
                candidate_sentence = f"{sentence_chunk} {part}".strip() if sentence_chunk else part
                if len(candidate_sentence) <= self._max_chars:
                    sentence_chunk = candidate_sentence
                else:
                    if sentence_chunk:
                        chunks.append(sentence_chunk)
                    sentence_chunk = part

            if sentence_chunk:
                current = sentence_chunk

        if current:
            chunks.append(current)

        return chunks

    @staticmethod
    def _looks_like_heading(text: str) -> bool:
        if len(text) > 90:
            return False
        if text.endswith("."):
            return False

        if re.match(r"^\d+[.)]\s+", text):
            return True

        words = [word for word in text.split() if word]
        if not words or len(words) > 10:
            return False

        letters_only = [re.sub(r"[^A-Za-z]", "", word) for word in words]
        letters_only = [word for word in letters_only if word]
        if not letters_only:
            return False

        titleish_ratio = sum(
            1 for word in letters_only if word[0].isupper() or word.isupper()
        ) / len(letters_only)
        return titleish_ratio >= 0.8

    @staticmethod
    def _write_trace_jsonl(rows: list[dict], output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as fp:
            for row in rows:
                fp.write(json.dumps(row, ensure_ascii=True) + "\n")
