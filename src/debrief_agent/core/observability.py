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


__all__ = ["observe", "update_current_span_metadata"]
