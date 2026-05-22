"""Shared observability helpers used by service-layer tracing.

This module centralizes Langfuse helpers so service files avoid duplicated
best-effort tracing logic.
"""

import logging
from typing import Any

from langfuse import get_client, observe

logger = logging.getLogger(__name__)


def update_current_span_metadata(metadata: dict[str, Any]) -> None:
    """Attach filterable metadata to the current Langfuse span.

    This is best-effort only; tracing failures must never affect request handling.
    """
    try:
        get_client().update_current_span(metadata=metadata)
    except Exception:
        logger.debug("Could not update Langfuse span metadata", exc_info=True)


def set_current_trace_session(session_id: str | None) -> None:
    """Attach session_id to the current trace-level input for cross-span correlation.

    This is best-effort only; tracing failures must never affect request handling.
    """
    if not session_id:
        return

    try:
        get_client().set_current_trace_io(input={"session_id": session_id})
    except Exception:
        logger.debug("Could not set Langfuse trace session_id", exc_info=True)


__all__ = ["observe", "update_current_span_metadata", "set_current_trace_session"]
