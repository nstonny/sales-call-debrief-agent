"""Service exports.

Preferred usage in new code is class-based (`MetadataExtractor`, `CallAnalyzer`).
`generate_call_analysis` remains as a backward-compatible wrapper.
"""

from debrief_agent.services.analysis import CallAnalyzer, generate_call_analysis
from debrief_agent.services.extraction import MetadataExtractor

__all__ = [
    "CallAnalyzer",
    "MetadataExtractor",
    "generate_call_analysis",
]
