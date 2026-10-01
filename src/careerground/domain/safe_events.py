"""Payload-free application events; never serialize exceptions or request values."""

import logging
from threading import Lock

logger = logging.getLogger("careerground.security")
_RESULTS = frozenset(
    {"OK", "VALIDATION_FAILED", "FORBIDDEN", "NOT_FOUND", "INTERNAL_ERROR", "RATE_LIMITED"}
)
_ADAPTERS = frozenset({"web", "mcp"})
_MAINTENANCE_RESULTS = frozenset({"OK", "ERROR"})
_MAX_COUNT = 2**63 - 1
_metrics_lock = Lock()
_request_counts = {(adapter, result): 0 for adapter in _ADAPTERS for result in _RESULTS}
_maintenance_counts = {result: 0 for result in _MAINTENANCE_RESULTS}
_deleted_buckets = 0


def _increment(value: int, amount: int = 1) -> int:
    return min(_MAX_COUNT, value + amount)


def record_result(adapter: str, result: str) -> None:
    if adapter not in _ADAPTERS or result not in _RESULTS:
        raise ValueError("unsupported security event")
    with _metrics_lock:
        key = (adapter, result)
        _request_counts[key] = _increment(_request_counts[key])
    logger.info("request_result adapter=%s result=%s", adapter, result)


def record_request_limit_cleanup(result: str, *, deleted_buckets: int = 0) -> None:
    """Count fixed-label outcomes; never accept row keys or exception details."""

    if result not in _MAINTENANCE_RESULTS or (
        type(deleted_buckets) is not int or not 0 <= deleted_buckets <= 10_000
    ):
        raise ValueError("unsupported maintenance event")
    global _deleted_buckets
    with _metrics_lock:
        _maintenance_counts[result] = _increment(_maintenance_counts[result])
        _deleted_buckets = _increment(_deleted_buckets, deleted_buckets)
    logger.info("request_limit_cleanup result=%s deleted_buckets=%d", result, deleted_buckets)


def security_metrics_snapshot() -> dict[str, object]:
    """Return a detached snapshot with a fixed set of labels and saturated counts.

    These process-local counters support local inspection only. A multi-process
    deployment must aggregate the payload-free log events from each process.
    """

    with _metrics_lock:
        return {
            "requests": {
                adapter: {result: _request_counts[adapter, result] for result in sorted(_RESULTS)}
                for adapter in sorted(_ADAPTERS)
            },
            "request_limit_cleanup": {
                **{result: _maintenance_counts[result] for result in sorted(_MAINTENANCE_RESULTS)},
                "deleted_buckets": _deleted_buckets,
            },
        }
