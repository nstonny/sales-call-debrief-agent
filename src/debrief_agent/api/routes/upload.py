from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from debrief_agent.core.database import get_db
from debrief_agent.models.analysis import Analysis
from debrief_agent.models.call import Call
from debrief_agent.schemas.call import CallResponse
from debrief_agent.services.analysis import CallAnalyzer
from debrief_agent.services.extraction import MetadataExtractor

router = APIRouter()
metadata_extractor = MetadataExtractor()
call_analyzer = CallAnalyzer()


@router.post(
    "/upload",
    response_model=CallResponse,
    summary="Upload a sales call transcript",
    description=(
        "Accepts a .txt transcript file plus optional company name and deal value. "
        "Saves the transcript to the calls table, runs the LLM metadata extraction "
        "pass to populate rep_name, contact_name, contact_title and deal_stage, "
        "then returns the fully populated record."
    ),
)
async def upload_transcript(
    file: UploadFile = File(..., description="Plain-text transcript file (.txt)"),
    company: Optional[str] = Form(None, description="Company name (optional)"),
    deal_value: Optional[float] = Form(None, description="Estimated deal value in € (optional)"),
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

    # --- Save the transcript row first so we have a call ID ---
    call = Call(
        filename=file.filename,
        transcript_text=transcript_text,
        company=company or None,
        deal_value=deal_value,
    )

    db.add(call)
    await db.flush()        # assigns UUID and triggers server_default for created_at
    await db.refresh(call)  # load server-generated values back into the Python object

    # --- Run LLM metadata extraction pass ---
    # Raises HTTPException(502) on failure, which causes get_db to roll back
    metadata = await metadata_extractor.extract(transcript_text)

    # --- Write extracted metadata back to the call row ---
    call.rep_name = metadata["rep_name"]
    call.contact_name = metadata["contact_name"]
    call.contact_title = metadata["contact_title"]
    call.deal_stage = metadata["deal_stage"]

    # --- Run LLM analysis pass ---
    # Uses the extracted metadata to personalise the debrief prompt.
    # Raises HTTPException(502) on failure, which causes get_db to roll back.
    analysis_data = await call_analyzer.analyze(transcript_text, metadata)

    # --- Create Analysis ORM object and link it to the call ---
    analysis = Analysis(
        call_id=call.id,
        summary=analysis_data["summary"],
        next_steps=analysis_data["next_steps"],
        competitor_mentioned=analysis_data["competitor_mentioned"],
        strengths=analysis_data["strengths"],
        areas_for_improvement=analysis_data["areas_for_improvement"],
        action_items=analysis_data["action_items"],
        objections_raised=analysis_data["objections_raised"],
        sentiment=analysis_data["sentiment"],
        score=analysis_data["score"],
        raw_llm_output=analysis_data,   # full parsed response preserved for reuse
    )

    db.add(analysis)
    call.analysis = analysis  # wire the relationship so CallResponse can access it

    # get_db commits on success automatically
    return CallResponse.model_validate(call)
