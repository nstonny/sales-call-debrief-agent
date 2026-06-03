"""CLI ingestion entrypoint for coaching guide chunking and optional Qdrant upsert.

This script:
1) loads DOCX guides from `coaching_guides`,
2) performs structure-aware chunking,
3) writes a JSONL trace artifact for review,
4) optionally stores chunks in Qdrant.
"""

import argparse
from pathlib import Path

from debrief_agent.app.bootstrap_qdrant import ensure_collection
from debrief_agent.rag.loaders.loader_factory import LoaderFactory
from debrief_agent.rag.splitters import CoachingGuideChunker

DEFAULT_GUIDES_PATH = Path("src/data/knowledge_base/coaching_guides")
DEFAULT_TRACE_PATH = Path("experiments.local/coaching_guides_level1_chunks.jsonl")


def build_parser() -> argparse.ArgumentParser:
    """Build and return CLI arguments for coaching-guide ingestion."""
    parser = argparse.ArgumentParser(
        description="Chunk coaching guide DOCX files and ingest them into Qdrant."
    )
    parser.add_argument(
        "--guides-path",
        type=Path,
        default=DEFAULT_GUIDES_PATH,
        help="Path to the coaching_guides directory.",
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
    guides_path: Path,
    trace_output_path: Path,
    max_chars: int,
    dry_run: bool,
) -> None:
    """Run load -> chunk -> trace-write -> optional Qdrant upsert pipeline."""
    documents = LoaderFactory().load_documents(guides_path)
    chunker = CoachingGuideChunker(max_chars=max_chars)
    chunks = chunker.chunk_documents(documents, trace_output_path=trace_output_path)

    if not dry_run and chunks:
        ensure_collection()
        # Lazy import keeps dry-run independent of Qdrant availability.
        from debrief_agent.rag.vectorstore.qdrant_store import get_vector_store

        get_vector_store().add_documents(chunks)

    print(f"Loaded {len(documents)} source documents from {guides_path}")
    print(f"Created {len(chunks)} chunks")
    print(f"Wrote chunk review JSONL to {trace_output_path}")
    if dry_run:
        print("Dry run enabled: skipped Qdrant storage")
    else:
        print("Stored chunks in Qdrant")


def main() -> None:
    """Parse CLI args and execute coaching-guide ingestion."""
    args = build_parser().parse_args()
    run_ingestion(
        guides_path=args.guides_path,
        trace_output_path=args.trace_out,
        max_chars=args.max_chars,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
