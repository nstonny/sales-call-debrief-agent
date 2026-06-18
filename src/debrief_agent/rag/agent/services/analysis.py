"""Re-export shim — the real implementation lives in sales_debrief_agent.py."""

from debrief_agent.rag.agent.sales_debrief_agent import CallAnalyzer, analyze_transcript

__all__ = ["CallAnalyzer", "analyze_transcript"]

