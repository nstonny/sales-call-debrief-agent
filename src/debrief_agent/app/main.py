import logging

from fastapi import FastAPI

from debrief_agent.api.router import api_router

# --- Configure logging ---
# Sends all INFO+ messages to stdout in a readable format.
# You'll see logs from all debrief_agent modules in the uvicorn terminal.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

app = FastAPI(
    title="Sales Call Debrief Agent",
    description="LLM-powered pipeline for analysing sales call transcripts.",
    version="0.1.0",
)

app.include_router(api_router)
