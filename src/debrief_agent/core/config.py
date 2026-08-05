from dotenv import load_dotenv
import os

load_dotenv()

# --- Database ---
DATABASE_URL: str = os.getenv("DATABASE_URL", "")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set. Please add it to your .env file.")

# --- OpenAI ---
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is not set. Please add it to your .env file.")

# --- Analysis rubrics ---
# Backend-controlled default rubric set (users do not select this in the UI).
# Override with env var e.g.
# ANALYSIS_RUBRICS="overpitching_rubric.txt,discovery_rubric.txt,pricing_negotiation_rubric.txt"
_raw_rubrics = os.getenv(
    "ANALYSIS_RUBRICS",
    "overpitching_rubric.txt,discovery_rubric.txt,pricing_negotiation_rubric.txt",
)
DEFAULT_ANALYSIS_RUBRICS: list[str] = [
    rubric.strip() for rubric in _raw_rubrics.split(",") if rubric.strip()
]

# --- Qdrant ---
# Loaded from .env via load_dotenv() above.
QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY: str | None = os.getenv("QDRANT_API_KEY", "") or None
QDRANT_COLLECTION_NAME: str = os.getenv("QDRANT_COLLECTION_NAME", "sales_knowledge_chunks")

_raw_qdrant_timeout = os.getenv("QDRANT_TIMEOUT_SECONDS", "10")
try:
    QDRANT_TIMEOUT_SECONDS: int = int(_raw_qdrant_timeout)
except ValueError as exc:
    raise ValueError("QDRANT_TIMEOUT_SECONDS must be an integer.") from exc

if QDRANT_TIMEOUT_SECONDS <= 0:
    raise ValueError("QDRANT_TIMEOUT_SECONDS must be > 0.")
