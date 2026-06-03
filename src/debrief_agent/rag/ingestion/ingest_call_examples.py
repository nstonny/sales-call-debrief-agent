"""CLI ingestion entrypoint for call-example chunking and optional Qdrant upsert.

This script:
1) loads call example documents from `call_examples`,
2) chunks by conversation text between dashed headings,
3) writes a JSONL trace artifact for review,
4) optionally stores chunks in Qdrant.
"""

import argparse
from pathlib import Path

from debrief_agent.app.bootstrap_qdrant import ensure_collection
from debrief_agent.rag.loaders.loader_factory import LoaderFactory
from debrief_agent.rag.splitters import CallExamplesChunker

DEFAULT_CALL_EXAMPLES_PATH = Path("src/data/knowledge_base/call_examples")
DEFAULT_TRACE_PATH = Path("experiments.local/call_examples_chunks.jsonl")


def build_parser() -> argparse.ArgumentParser:
    """Build and return CLI arguments for call-example ingestion."""
    parser = argparse.ArgumentParser(
        description="Chunk call example documents and ingest them into Qdrant."
    )
    parser.add_argument(
        "--call-examples-path",
        type=Path,
        default=DEFAULT_CALL_EXAMPLES_PATH,
        help="Path to the call_examples directory.",
    )
    parser.add_argument(
        "--trace-out",
        type=Path,
        default=DEFAULT_TRACE_PATH,
        help="JSONL file path for chunk review output.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Chunk and write trace output without storing vectors in Qdrant.",
    )
    return parser


def run_ingestion(
    call_examples_path: Path,
    trace_output_path: Path,
    dry_run: bool,
) -> None:
    """Run load -> chunk -> trace-write -> optional Qdrant upsert pipeline."""
    documents = LoaderFactory().load_documents(call_examples_path)
    chunker = CallExamplesChunker()
    chunks = chunker.chunk_documents(documents, trace_output_path=trace_output_path)

    if not dry_run and chunks:
        ensure_collection()
        # Lazy import keeps dry-run independent of Qdrant availability.
        from debrief_agent.rag.vectorstore.qdrant_store import get_vector_store

        get_vector_store().add_documents(chunks)

    print(f"Loaded {len(documents)} source documents from {call_examples_path}")
    print(f"Created {len(chunks)} chunks")
    print(f"Wrote chunk review JSONL to {trace_output_path}")
    if dry_run:
        print("Dry run enabled: skipped Qdrant storage")
    else:
        print("Stored chunks in Qdrant")


def main() -> None:
    """Parse CLI args and execute call-example ingestion."""
    args = build_parser().parse_args()
    run_ingestion(
        call_examples_path=args.call_examples_path,
        trace_output_path=args.trace_out,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
