from fastapi import FastAPI

from debrief_agent.api.router import api_router

app = FastAPI(
    title="Sales Call Debrief Agent",
    description="LLM-powered pipeline for analysing sales call transcripts.",
    version="0.1.0",
)

app.include_router(api_router)

