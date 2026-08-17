"""Idempotent knowledge-base seeding, intended for container startup.

Runs the three ingestion CLIs in order, but only when the Qdrant collection is
empty. The guard matters: `get_vector_store().add_documents(...)` mints fresh
point IDs on every call, so an unguarded re-run silently duplicates every chunk
rather than replacing it.

Usage:
    python -m debrief_agent.rag.ingestion.seed_all
    python -m debrief_agent.rag.ingestion.seed_all --force
"""

from __future__ import annotations

import argparse
import sys
import time
from types import ModuleType

from debrief_agent.core.qdrant import (
    get_sync_qdrant_client,
    get_sync_qdrant_collection_name,
)
from debrief_agent.rag.ingestion import (
    ingest_call_examples,
    ingest_coaching_guides,
    ingest_pdf_documents,
)
from debrief_agent.rag.ingestion.bootstrap_qdrant import ensure_collection

# Order matters only for readable logs; the collection is shared.
INGESTION_MODULES: tuple[ModuleType, ...] = (
    ingest_pdf_documents,
    ingest_coaching_guides,
    ingest_call_examples,
)


def build_parser() -> argparse.ArgumentParser:
    """Build and return CLI arguments for knowledge-base seeding."""
    parser = argparse.ArgumentParser(
        description="Seed the Qdrant knowledge base once, skipping if already populated."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Drop the collection and re-seed even if populated. Required because "
            "re-running ingestion over a populated collection appends duplicates."
        ),
    )
    return parser


def wait_for_qdrant(attempts: int = 30, delay_seconds: float = 2.0) -> None:
    """Poll Qdrant until it answers, then return.

    The `qdrant/qdrant` image ships no curl or wget, which makes a Compose
    healthcheck awkward. Polling from the client side is more reliable, and it
    also helps native runs against a container that is still booting.
    """
    client = get_sync_qdrant_client()

    for attempt in range(1, attempts + 1):
        try:
            client.get_collections()
            return
        except Exception:
            # Any failure here is treated as "not up yet" -- connection refused,
            # DNS not resolving, or a partially initialized server.
            if attempt == attempts:
                raise
            print(f"Waiting for Qdrant ({attempt}/{attempts})...")
            time.sleep(delay_seconds)


def collection_point_count() -> int:
    """Return the number of points in the configured collection, 0 if absent."""
    client = get_sync_qdrant_client()
    collection_name = get_sync_qdrant_collection_name()

    if not client.collection_exists(collection_name=collection_name):
        return 0

    return client.count(collection_name=collection_name, exact=True).count


def _run_with_defaults(module: ModuleType) -> None:
    """Call an ingestion module's `main()` with its own argparse defaults.

    Each CLI resolves its paths and chunk sizes through `build_parser()`, and the
    arg-to-parameter mapping differs per module. Blanking `sys.argv` reuses those
    defaults without restating any of them here, and keeps flags passed to
    seed_all (like --force) from leaking into the sub-parsers.
    """
    original_argv = sys.argv
    sys.argv = [module.__name__]
    try:
        module.main()
    finally:
        sys.argv = original_argv


def main() -> None:
    """Seed the knowledge base unless it is already populated."""
    args = build_parser().parse_args()

    wait_for_qdrant()

    if args.force:
        client = get_sync_qdrant_client()
        collection_name = get_sync_qdrant_collection_name()
        if client.collection_exists(collection_name=collection_name):
            print(f"--force: deleting existing collection {collection_name!r}")
            client.delete_collection(collection_name=collection_name)

    ensure_collection()

    existing_points = collection_point_count()
    if existing_points > 0:
        print(f"Qdrant collection already holds {existing_points} points -- skipping seed.")
        return

    for module in INGESTION_MODULES:
        print(f"--- seeding via {module.__name__}")
        _run_with_defaults(module)

    print(f"Seeding complete: {collection_point_count()} points in collection.")


if __name__ == "__main__":
    main()
