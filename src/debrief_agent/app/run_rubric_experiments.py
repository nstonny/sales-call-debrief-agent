"""
CLI utility to compare LLM analysis outputs across different rubrics.

Usage:
    uv run python -m debrief_agent.app.run_rubric_experiments \
      --rubrics overpitching_rubric.txt,discovery_rubric.txt,pricing_negotiation_rubric.txt \
      --transcripts-glob "src/data/transcripts/**/*.txt" \
      --limit 5

Outputs:
- Prints a compact per-run summary to stdout.
- Writes full JSON results to experiments/rubric_runs.jsonl by default.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from debrief_agent.core.config import DEFAULT_ANALYSIS_RUBRICS
from debrief_agent.services.analysis import generate_call_analysis
from debrief_agent.services.extraction import extract_call_metadata


def _parse_rubrics(raw: str | None) -> list[str]:
    if not raw:
        return DEFAULT_ANALYSIS_RUBRICS
    return [item.strip() for item in raw.split(",") if item.strip()]


def _iter_transcripts(glob_pattern: str, limit: int | None) -> Iterable[Path]:
    paths = sorted(Path.cwd().glob(glob_pattern))
    txt_paths = [p for p in paths if p.is_file() and p.suffix.lower() == ".txt"]
    return txt_paths[:limit] if limit else txt_paths


async def _run_one(transcript_path: Path, rubrics: list[str]) -> list[dict]:
    transcript_text = transcript_path.read_text(encoding="utf-8")
    metadata = await extract_call_metadata(transcript_text)

    rows: list[dict] = []
    for rubric in rubrics:
        analysis = await generate_call_analysis(
            transcript=transcript_text,
            metadata=metadata,
            rubric_names=[rubric],
        )
        rows.append(
            {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "transcript_path": str(transcript_path),
                "transcript_name": transcript_path.name,
                "rubric": rubric,
                "metadata": metadata,
                "analysis": analysis,
                "score": analysis.get("score"),
                "sentiment": analysis.get("sentiment"),
                "summary": analysis.get("summary"),
            }
        )
    return rows


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run transcript analysis across one or more rubrics and compare outputs.",
    )
    parser.add_argument(
        "--rubrics",
        type=str,
        default=None,
        help=(
            "Comma-separated rubric names (with or without .txt). "
            "Defaults to DEFAULT_ANALYSIS_RUBRICS from config."
        ),
    )
    parser.add_argument(
        "--transcripts-glob",
        type=str,
        default="src/data/transcripts/**/*.txt",
        help="Glob pattern to select transcript files.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional max number of transcript files to process.",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="experiments/rubric_runs.jsonl",
        help="Output JSONL path for full results.",
    )
    args = parser.parse_args()

    rubrics = _parse_rubrics(args.rubrics)
    transcripts = list(_iter_transcripts(args.transcripts_glob, args.limit))

    if not transcripts:
        raise SystemExit(f"No transcript files found for pattern: {args.transcripts_glob}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    total_runs = 0
    with out_path.open("w", encoding="utf-8") as fh:
        for transcript_path in transcripts:
            rows = await _run_one(transcript_path, rubrics)
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                total_runs += 1
                print(
                    f"[{row['transcript_name']}] rubric={row['rubric']} "
                    f"score={row['score']} sentiment={row['sentiment']}"
                )

    print(f"\nCompleted {total_runs} runs across {len(transcripts)} transcripts.")
    print(f"Saved full results to: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())

