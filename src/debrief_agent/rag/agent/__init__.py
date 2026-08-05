"""Sales debrief agent package."""

from debrief_agent.rag.agent.sales_debrief_agent import CallAnalyzer, analyze_transcript

# Backward-compatible alias used by upload.py and other callers
SalesDebriefAgent = CallAnalyzer

__all__ = ["SalesDebriefAgent", "CallAnalyzer", "analyze_transcript"]

