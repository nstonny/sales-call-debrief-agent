"""
CLI utility to run transcript analysis with a selected rubric set.

Usage:
    uv run python -m debrief_agent.app.run_rubric_experiments \
      --rubrics overpitching_rubric.txt,discovery_rubric.txt,pricing_negotiation_rubric.txt \
      --transcripts-glob "src/data/transcripts/transcript_6.txt"

Behavior:
- Runs exactly one analysis per command invocation.
- If multiple rubrics are provided, all are injected together in one prompt.

Outputs:
- Prints a compact per-run summary to stdout.
- Writes full JSON results to experiments/rubric_runs.jsonl by default.
"""

from __future__ import annotations

import argparse
import asyncio

from debrief_agent.app.experiment_runner import ExperimentRunner


def _parse_rubrics(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    return [item.strip() for item in raw.split(",") if item.strip()]


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run one analysis for one transcript with a selected rubric set.",
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
        default="src/data/transcripts/transcript_1.txt",
        help="Glob pattern that must resolve to exactly one transcript file.",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="experiments/rubric_runs.jsonl",
        help="Output JSONL path for full results.",
    )
    args = parser.parse_args()

    runner = ExperimentRunner(
        rubrics=_parse_rubrics(args.rubrics),
        transcripts_glob=args.transcripts_glob,
        out_path=args.out,
    )
    total_runs, transcript_count = await runner.run()

    print(f"\nCompleted {total_runs} run across {transcript_count} transcript.")
    print(f"Saved full results to: {runner.out_path}")


if __name__ == "__main__":
    asyncio.run(main())
