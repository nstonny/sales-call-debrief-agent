import json
import re
from pathlib import Path

from langchain_core.documents import Document


class PDFChunker:
	"""Chunk normalized markdown exports from PDF sources."""

	def __init__(self, max_chars: int = 1200) -> None:
		if max_chars <= 0:
			raise ValueError("max_chars must be > 0")
		self._max_chars = max_chars

	def chunk_markdown_directory(
		self,
		processed_markdown_path: Path,
		trace_output_path: Path | None = None,
	) -> list[Document]:
		"""Load all markdown files from a directory and return chunked documents."""
		documents = self._load_markdown_documents(processed_markdown_path)
		return self.chunk_documents(documents, trace_output_path=trace_output_path)

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
		"""Split one markdown document into heading-aware chunks."""
		sections = self._split_into_sections(document.page_content)

		chunks: list[Document] = []
		chunk_index = 0

		for section_title, section_text in sections:
			for section_chunk_index, section_chunk in enumerate(
				self._split_long_section(section_text)
			):
				chunks.append(
					Document(
						page_content=section_chunk,
						metadata={
							**document.metadata,
							"section_title": section_title,
							"chunk_index": chunk_index,
							"section_chunk_index": section_chunk_index,
						},
					)
				)
				chunk_index += 1

		return chunks

	def _load_markdown_documents(self, processed_markdown_path: Path) -> list[Document]:
		if not processed_markdown_path.exists() or not processed_markdown_path.is_dir():
			raise ValueError(
				f"processed_markdown_path must be an existing directory: {processed_markdown_path}"
			)

		markdown_files = sorted(processed_markdown_path.rglob("*.md"))
		documents: list[Document] = []

		for markdown_path in markdown_files:
			content = markdown_path.read_text(encoding="utf-8")
			documents.append(
				Document(
					page_content=content,
					metadata={
						"source": markdown_path.name,
						"category": markdown_path.parent.name,
						"document_type": "md",
						"path": str(markdown_path),
					},
				)
			)

		return documents

	@staticmethod
	def _split_into_sections(text: str) -> list[tuple[str, str]]:
		lines = [line.rstrip() for line in text.splitlines()]

		sections: list[tuple[str, str]] = []
		current_title = "Overview"
		current_lines: list[str] = []

		for raw_line in lines:
			heading_match = re.match(r"^(#{1,6})\s+(.+)\s*$", raw_line.strip())
			if heading_match:
				section_text = "\n".join(current_lines).strip()
				if section_text:
					sections.append((current_title, section_text))
				current_title = heading_match.group(2).strip()
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

			# Keep pathological paragraphs bounded by splitting on sentence boundaries.
			sentence_parts = [
				part.strip()
				for part in re.split(r"(?<=[.!?])\s+", paragraph)
				if part.strip()
			]
			sentence_chunk = ""
			for part in sentence_parts:
				candidate_sentence = (
					f"{sentence_chunk} {part}".strip() if sentence_chunk else part
				)
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
	def _write_trace_jsonl(rows: list[dict], output_path: Path) -> None:
		output_path.parent.mkdir(parents=True, exist_ok=True)
		with output_path.open("w", encoding="utf-8") as fp:
			for row in rows:
				fp.write(json.dumps(row, ensure_ascii=True) + "\n")

