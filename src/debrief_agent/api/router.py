from fastapi import APIRouter

from debrief_agent.api.routes.upload import router as upload_router

# Main API router — all route modules are registered here
api_router = APIRouter(prefix="/api")

api_router.include_router(upload_router, tags=["Transcripts"])
