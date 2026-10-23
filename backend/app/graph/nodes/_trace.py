"""Safe tracing wrapper for graph nodes."""

import logging
from datetime import datetime, timezone
from functools import wraps
from time import monotonic_ns
from typing import Callable, ParamSpec, TypeVar

from app.graph.state import TraceEvent

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R", bound=dict)


def traced(node_name: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Record a node outcome and duration without including case data."""

    def decorate(node: Callable[P, R]) -> Callable[P, R]:
        @wraps(node)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            started = monotonic_ns()
            error_category: str | None = None

            try:
                result = node(*args, **kwargs)
                if result.pop("_trace_skipped", False):
                    outcome = "skipped"
                else:
                    outcome = "success"
                if (
                    outcome == "success"
                    and result.get("status") == "needs_manual_review"
                ):
                    error_category = "manual_review"
            except Exception as error:
                logger.error(
                    "Node %s failed: %s",
                    node_name,
                    type(error).__name__,
                    exc_info=False,
                )
                result = {
                    "status": "needs_manual_review",
                    "errors": ["Node execution failed. Manual review is required."],
                }
                outcome = "failure"
                error_category = type(error).__name__

            duration_ms = (monotonic_ns() - started) // 1_000_000
            event = TraceEvent(
                node=node_name,
                timestamp=datetime.now(timezone.utc).isoformat(),
                outcome=outcome,
                duration_ms=duration_ms,
                error_category=error_category,
            )
            result["trace"] = [event]
            return result

        return wrapper

    return decorate
