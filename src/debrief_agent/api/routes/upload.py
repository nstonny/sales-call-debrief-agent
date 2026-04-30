from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from debrief_agent.core.database import get_db
from debrief_agent.models.call import Call
from debrief_agent.schemas.call import CallResponse

router = APIRouter()


@router.post(
    "/upload",
    response_model=CallResponse,
    summary="Upload a sales call transcript",
    description=(
        "Accepts a .txt transcript file plus optional company name and deal value. "
        "Saves a new row to the calls table and returns the created record. "
        "LLM metadata fields (rep_name, contact_name, etc.) are populated later "
        "by the extraction pass."
    ),
)
async def upload_transcript(
    file: UploadFile = File(..., description="Plain-text transcript file (.txt)"),
    company: Optional[str] = Form(None, description="Company name (optional)"),
    deal_value: Optional[float] = Form(None, description="Estimated deal value in $ (optional)"),
    db: AsyncSession = Depends(get_db),
) -> CallResponse:
    # --- Validate file type ---
    if not file.filename.endswith(".txt"):
        raise HTTPException(
            status_code=422,
            detail="Only .txt files are supported at this time.",
        )

    # --- Read transcript text ---
    raw_bytes = await file.read()
    try:
        transcript_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=422,
            detail="Could not decode file. Please upload a UTF-8 encoded .txt file.",
        )

    if not transcript_text.strip():
        raise HTTPException(status_code=422, detail="Uploaded file is empty.")

    # --- Create Call ORM object ---
    call = Call(
        filename=file.filename,
        transcript_text=transcript_text,
        company=company or None,
        deal_value=deal_value,
    )

    db.add(call)
    await db.flush()     # assigns UUID and triggers server_default for created_at
    await db.refresh(call)  # load server-generated values back into the Python object

    # get_db commits on success automatically
    return CallResponse.model_validate(call)

