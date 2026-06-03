import json
from pathlib import Path

from langchain_core.documents import Document


class CallExamplesChunker:
    """Chunk call examples by section headers wrapped in dashed separators."""

    def chunk_documents(
        self,
        documents: list[Document],
        trace_output_path: Path | None = None,
    ) -> list[Document]:
        """Chunk documents and optionally write one JSONL review row per source file."""
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
        """Create one chunk per section between dashed headline blocks."""
        lines = document.page_content.splitlines()
        headers = self._find_section_headers(lines)

        ranges: list[tuple[str, int, int]] = []

        if headers:
            first_header_start = headers[0][0]
            if first_header_start > 0:
                ranges.append(("Overview", 0, first_header_start))

            for idx, (header_start, header_title) in enumerate(headers):
                section_start = header_start + 3
                while section_start < len(lines) and not lines[section_start].strip():
                    section_start += 1

                section_end = headers[idx + 1][0] if idx + 1 < len(headers) else len(lines)
                ranges.append((header_title, section_start, section_end))
        else:
            ranges.append(("Overview", 0, len(lines)))

        chunks: list[Document] = []
        chunk_index = 0

        for section_title, start, end in ranges:
            section_text = "\n".join(lines[start:end]).strip()
            if not section_text:
                continue

            chunks.append(
                Document(
                    page_content=section_text,
                    metadata={
                        **document.metadata,
                        "section_title": section_title,
                        "chunk_index": chunk_index,
                    },
                )
            )
            chunk_index += 1

        return chunks

    @staticmethod
    def _find_section_headers(lines: list[str]) -> list[tuple[int, str]]:
        """Find headings in the form: dashed-line, title, dashed-line."""
        matches: list[tuple[int, str]] = []

        for idx in range(len(lines) - 2):
            top = lines[idx].strip()
            title = lines[idx + 1].strip()
            bottom = lines[idx + 2].strip()

            if CallExamplesChunker._is_dashed_line(top) and title and CallExamplesChunker._is_dashed_line(bottom):
                matches.append((idx, title))

        return matches

    @staticmethod
    def _is_dashed_line(value: str) -> bool:
        return len(value) >= 10 and set(value) == {"-"}

    @staticmethod
    def _write_trace_jsonl(rows: list[dict], output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as fp:
            for row in rows:
                fp.write(json.dumps(row, ensure_ascii=True) + "\n")

