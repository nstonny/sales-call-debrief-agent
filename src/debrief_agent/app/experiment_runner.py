from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from debrief_agent.core.config import DEFAULT_ANALYSIS_RUBRICS
from debrief_agent.services.analysis import CallAnalyzer
from debrief_agent.services.extraction import MetadataExtractor


class ExperimentRunner:
    """Runs a single rubric-based transcript analysis experiment and writes JSONL output."""

    def __init__(
        self,
        rubrics: list[str] | None = None,
        transcript_path: str = "src/data/transcripts/transcript_1.txt",
        out_path: str = "experiments/rubric_runs.jsonl",
    ) -> None:
        self.rubrics = self._resolve_rubrics(rubrics)
        self.transcript_path = Path(transcript_path)
        self.out_path = Path(out_path)
        self.metadata_extractor = MetadataExtractor()
        self.call_analyzer = CallAnalyzer()

    @staticmethod
    def _resolve_rubrics(raw: list[str] | None) -> list[str]:
        if raw is None:
            return list(DEFAULT_ANALYSIS_RUBRICS)
        return [item.strip() for item in raw if item.strip()]

    def resolve_transcript(self) -> Path:
        if not self.transcript_path.exists() or not self.transcript_path.is_file():
            raise SystemExit(f"Transcript file not found: {self.transcript_path}")
        if self.transcript_path.suffix.lower() != ".txt":
            raise SystemExit(
                f"Transcript file must be .txt, got: {self.transcript_path}"
            )
        return self.transcript_path

    async def run_one(self, transcript_path: Path) -> dict:
        transcript_text = transcript_path.read_text(encoding="utf-8")
        metadata = await self.metadata_extractor.extract(transcript_text)

        # Inject all selected rubrics together and generate one analysis object.
        analysis = await self.call_analyzer.analyze(
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

        rubrics_display = ",".join(row["rubrics"]) if row["rubrics"] else "none"
        print(
            f"[{row['transcript_name']}] rubrics={rubrics_display} "
            f"score={row['score']} sentiment={row['sentiment']}"
        )

        return 1, 1
