"""
CLI utility to run transcript analysis with a selected rubric set.

Usage:
    uv run python -m debrief_agent.app.run_rubric_experiments \
      --transcript "src/data/transcripts/transcript_6.txt" \
      --rubrics overpitching_rubric.txt,discovery_rubric.txt,pricing_negotiation_rubric.txt \
      --out "experiments/transcript_6_all_rubrics.jsonl"

Behavior:
- Runs exactly one analysis per command invocation.
- If multiple rubrics are provided, all are injected together in one prompt.
- `--no-rubrics` disables rubric injection for that run.

Outputs:
- Prints a compact per-run summary to stdout.
- Writes full JSON results to experiments/rubric_runs.jsonl by default.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

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
        "--transcript",
        type=Path,
        required=True,
        help="Path to a single transcript .txt file.",
    )

    rubric_group = parser.add_mutually_exclusive_group()
    rubric_group.add_argument(
        "--rubrics",
        type=str,
        default=None,
        help=(
            "Comma-separated rubric names (with or without .txt). "
            "Defaults to DEFAULT_ANALYSIS_RUBRICS from config."
        ),
    )
    rubric_group.add_argument(
        "--no-rubrics",
        action="store_true",
        help="Disable rubric injection for this run.",
    )

    parser.add_argument(
        "--out",
        type=Path,
        default="experiments/rubric_runs.jsonl",
        help="Output JSONL path for full results.",
    )
    args = parser.parse_args()

    selected_rubrics = [] if args.no_rubrics else _parse_rubrics(args.rubrics)

    runner = ExperimentRunner(
        rubrics=selected_rubrics,
        transcript_path=str(args.transcript),
        out_path=str(args.out),
    )
    total_runs, transcript_count = await runner.run()

    print(f"\nCompleted {total_runs} run across {transcript_count} transcript.")
    print(f"Saved full results to: {runner.out_path}")


if __name__ == "__main__":
    asyncio.run(main())
