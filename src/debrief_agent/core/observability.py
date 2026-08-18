"""Shared observability helpers used by service-layer tracing.

This module centralizes Langfuse helpers so service files avoid duplicated
best-effort tracing logic.
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from langfuse import get_client, observe, propagate_attributes

logger = logging.getLogger(__name__)


def update_current_span_metadata(metadata: dict[str, Any]) -> None:
    """Attach filterable metadata to the current Langfuse span.

    This is best-effort only; tracing failures must never affect request handling.
    """
    try:
        get_client().update_current_span(metadata=metadata)
    except Exception:
        logger.debug("Could not update Langfuse span metadata", exc_info=True)


def get_current_trace_id() -> str | None:
    """Return the current Langfuse trace id, if available.

    This is best-effort only; tracing failures must never affect request handling.
    """
    try:
        trace_id = get_client().get_current_trace_id()
    except Exception:
        logger.debug("Could not read Langfuse trace id", exc_info=True)
        return None

    return str(trace_id) if trace_id else None


@contextmanager
def propagate_trace_session(
    session_id: str | None,
    trace_name: str | None = None,
) -> Iterator[None]:
    """Context manager that propagates trace-level attributes for session correlation.

    Uses Langfuse `propagate_attributes(session_id=...)` so child spans inherit
    the trace session identifier.

    This is best-effort only; tracing failures must never affect request handling.
    """
    if not session_id:
        yield
        return

    try:
        propagation_ctx = propagate_attributes(
            session_id=session_id,
            trace_name=trace_name,
        )
    except Exception:
        logger.debug("Could not initialize Langfuse session propagation", exc_info=True)
        yield
        return

    with propagation_ctx:
        yield


__all__ = [
    "get_current_trace_id",
    "observe",
    "propagate_trace_session",
    "update_current_span_metadata",
]
