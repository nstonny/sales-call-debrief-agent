import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from debrief_agent.api.routes.upload import persist_call_and_analyze
from debrief_agent.core.database import get_db
from debrief_agent.schemas.call import CallResponse
from debrief_agent.schemas.transcript import AnalyzeTranscriptRequest, TranscriptContent

router = APIRouter()

# Sample transcripts bundled with the repo for demo/library selection in the UI.
TRANSCRIPTS_DIR = Path("src/data/transcripts")


def _list_transcript_filenames() -> list[str]:
    """List .txt transcripts, sorted numerically (transcript_2 before transcript_10)."""

    def _sort_key(filename: str) -> int:
        match = re.search(r"\d+", filename)
        return int(match.group()) if match else 0

    filenames = [path.name for path in TRANSCRIPTS_DIR.glob("*.txt")]
    return sorted(filenames, key=_sort_key)


def _resolve_transcript(filename: str) -> Path:
    """Return the path for `filename`, 404ing unless it's in the current listing.

    FastAPI's `{filename}` path segment can't itself contain `/`, so this
    whitelist is defense-in-depth against a bare `..` rather than the only guard.
    """
    if filename not in _list_transcript_filenames():
        raise HTTPException(status_code=404, detail=f"Transcript '{filename}' not found.")
    return TRANSCRIPTS_DIR / filename


def _read_transcript_text(path: Path) -> str:
    raw_bytes = path.read_bytes()
    try:
        transcript_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=422,
            detail="Could not decode file. Transcript must be UTF-8 encoded.",
        ) from exc

    if not transcript_text.strip():
        raise HTTPException(status_code=422, detail="Transcript file is empty.")

    return transcript_text


@router.get(
    "/transcripts",
    response_model=list[str],
    summary="List sample transcripts",
    description="Returns the filenames of sample transcripts bundled with the app.",
)
def list_transcripts() -> list[str]:
    return _list_transcript_filenames()


@router.get(
    "/transcripts/{filename}",
    response_model=TranscriptContent,
    summary="Get transcript content",
    description="Returns the raw text of a sample transcript, for UI preview.",
)
def get_transcript_content(filename: str) -> TranscriptContent:
    path = _resolve_transcript(filename)
    return TranscriptContent(filename=filename, content=_read_transcript_text(path))


@router.post(
    "/transcripts/{filename}/analyze",
    response_model=CallResponse,
    summary="Analyze a sample transcript",
    description=(
        "Runs the same extraction + analysis pipeline as /upload, but reads the "
        "transcript text from the bundled sample library instead of an uploaded file."
    ),
)
async def analyze_transcript(
    filename: str,
    payload: AnalyzeTranscriptRequest | None = None,
    db: AsyncSession = Depends(get_db),
) -> CallResponse:
    payload = payload or AnalyzeTranscriptRequest()
    path = _resolve_transcript(filename)
    transcript_text = _read_transcript_text(path)

    return await persist_call_and_analyze(
        filename=filename,
        transcript_text=transcript_text,
        company=payload.company,
        deal_value=payload.deal_value,
        db=db,
        trace_name="api.analyze_transcript",
    )
