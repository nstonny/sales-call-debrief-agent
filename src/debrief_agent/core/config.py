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
