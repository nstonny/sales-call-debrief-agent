from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from debrief_agent.core.config import DEFAULT_ANALYSIS_RUBRICS
from debrief_agent.services.analysis import generate_call_analysis
from debrief_agent.services.extraction import extract_call_metadata


class ExperimentRunner:
    """Runs a single rubric-based transcript analysis experiment and writes JSONL output."""

    def __init__(
        self,
        rubrics: list[str] | None = None,
        transcripts_glob: str = "src/data/transcripts/**/*.txt",
        out_path: str = "experiments/rubric_runs.jsonl",
    ) -> None:
        self.rubrics = self._resolve_rubrics(rubrics)
        self.transcripts_glob = transcripts_glob
        self.out_path = Path(out_path)

    @staticmethod
    def _resolve_rubrics(raw: list[str] | None) -> list[str]:
        if not raw:
            return DEFAULT_ANALYSIS_RUBRICS
        return [item.strip() for item in raw if item.strip()]

    def resolve_transcript(self) -> Path:
        paths = sorted(Path.cwd().glob(self.transcripts_glob))
        txt_paths = [p for p in paths if p.is_file() and p.suffix.lower() == ".txt"]

        if not txt_paths:
            raise SystemExit(f"No transcript files found for pattern: {self.transcripts_glob}")
        if len(txt_paths) > 1:
            raise SystemExit(
                "Expected exactly one transcript file, "
                f"but found {len(txt_paths)} for pattern: {self.transcripts_glob}. "
                "Use a narrower --transcripts-glob pattern."
            )

        return txt_paths[0]

    async def run_one(self, transcript_path: Path) -> dict:
        transcript_text = transcript_path.read_text(encoding="utf-8")
        metadata = await extract_call_metadata(transcript_text)

        # Inject all selected rubrics together and generate one analysis object.
        analysis = await generate_call_analysis(
            transcript=transcript_text,
            metadata=metadata,
            rubric_names=self.rubrics,
        )

        return {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "transcript_path": str(transcript_path),
            "transcript_name": transcript_path.name,
            "rubrics": self.rubrics,
            "metadata": metadata,
            "analysis": analysis,
            "score": analysis.get("score"),
            "sentiment": analysis.get("sentiment"),
        }

    async def run(self) -> tuple[int, int]:
        transcript_path = self.resolve_transcript()
        self.out_path.parent.mkdir(parents=True, exist_ok=True)

        row = await self.run_one(transcript_path)
        with self.out_path.open("w", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

        print(
            f"[{row['transcript_name']}] rubrics={','.join(row['rubrics'])} "
            f"score={row['score']} sentiment={row['sentiment']}"
        )

        return 1, 1
