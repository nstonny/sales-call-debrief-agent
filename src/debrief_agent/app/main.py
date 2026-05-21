import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from langfuse import get_client

from debrief_agent.api.router import api_router

# --- Configure logging ---
# Sends all INFO+ messages to stdout in a readable format.
# You'll see logs from all debrief_agent modules in the uvicorn terminal.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        yield
    finally:
        try:
            # Flush buffered Langfuse traces before process exit.
            get_client().flush()
        except Exception:
            logging.exception("Failed to flush Langfuse traces on shutdown")


app = FastAPI(
    title="Sales Call Debrief Agent",
    description="LLM-powered pipeline for analysing sales call transcripts.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(api_router)
