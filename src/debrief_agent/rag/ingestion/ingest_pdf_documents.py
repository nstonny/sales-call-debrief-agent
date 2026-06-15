"""CLI ingestion entrypoint for markdown file chunking and optional Qdrant upsert.

This script:
1) loads markdown files from `sales_frameworks` (or any directory passed via CLI),
2) performs structure-aware chunking,
3) writes a JSONL trace artifact for review,
4) optionally stores chunks in Qdrant.
"""

import argparse
from pathlib import Path

from debrief_agent.app.bootstrap_qdrant import ensure_collection
from debrief_agent.rag.splitters import PDFChunker

DEFAULT_PROCESSED_MARKDOWN_PATH = Path("src/data/knowledge_base/sales_frameworks")
DEFAULT_PROCESSED_MARKDOWN_PATH = Path("src/data/knowledge_base/sales_frameworks")


def build_parser() -> argparse.ArgumentParser:
    """Build and return CLI arguments for processed-markdown ingestion."""
    parser = argparse.ArgumentParser(
        description="Chunk processed markdown files and ingest them into Qdrant."
    )
    parser.add_argument(
        "--processed-markdown-path",
        type=Path,
        default=DEFAULT_PROCESSED_MARKDOWN_PATH,
        help="Path to the directory containing markdown files to ingest (default: sales_frameworks).",
    )
    parser.add_argument(
        "--trace-out",
        type=Path,
        default=DEFAULT_TRACE_PATH,
        help="JSONL file path for chunk review output.",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=1200,
        help="Maximum characters per chunk.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Chunk and write trace output without storing vectors in Qdrant.",
    )
    return parser


def run_ingestion(
    processed_markdown_path: Path,
    trace_output_path: Path,
    max_chars: int,
    dry_run: bool,
) -> None:
    """Run chunk -> trace-write -> optional Qdrant upsert pipeline."""
    chunker = PDFChunker(max_chars=max_chars)
    chunks = chunker.chunk_markdown_directory(
        processed_markdown_path=processed_markdown_path,
        trace_output_path=trace_output_path,
    )

    source_count = len(list(processed_markdown_path.rglob("*.md")))

    if not dry_run and chunks:
        ensure_collection()
        # Lazy import keeps dry-run independent of Qdrant availability.
        from debrief_agent.rag.vectorstore.qdrant_store import get_vector_store

        get_vector_store().add_documents(chunks)

    print(
        f"Loaded {source_count} source markdown documents from {processed_markdown_path}"
    )
    print(f"Created {len(chunks)} chunks")
    print(f"Wrote chunk review JSONL to {trace_output_path}")
    if dry_run:
        print("Dry run enabled: skipped Qdrant storage")
    elif chunks:
        print("Stored chunks in Qdrant")
    else:
        print("No chunks to store in Qdrant")


def main() -> None:
    """Parse CLI args and execute processed-markdown ingestion."""
    args = build_parser().parse_args()
    run_ingestion(
        processed_markdown_path=args.processed_markdown_path,
        trace_output_path=args.trace_out,
        max_chars=args.max_chars,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
