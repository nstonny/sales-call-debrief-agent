from pydantic import BaseModel


class AnalyzeTranscriptRequest(BaseModel):
    """Optional metadata supplied when analyzing a transcript already on disk."""

    company: str | None = None
    deal_value: float | None = None


class TranscriptContent(BaseModel):
    """Raw text content of a transcript, for the UI preview panel."""

    filename: str
    content: str
