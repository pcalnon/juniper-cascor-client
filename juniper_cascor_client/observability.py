"""Optional Prometheus observability for inbound WS frame validation.

METRICS-MON R2.2.4 / seed-05: when an inbound frame on ``/ws/training``
or ``/ws/control`` fails validation against the canonical envelope
schemas in :mod:`juniper_cascor_protocol.envelope`, the client emits
a structured WARNING log line and (when ``prometheus-client`` is
installed) increments
``juniper_cascor_client_unrecognized_ws_frames_total{type, endpoint}``.

The Prometheus dependency is **optional** — install
``juniper-cascor-client[observability]`` to enable the counter.
Consumers who skip the extra still get the structured log line and
all validation behaviour; they just don't get the metric.

The ``type`` label is bounded by the same R1.1 cardinality discipline
the protocol package uses for ``UnknownEnvelope.type`` (the first
``UNKNOWN_TYPE_BUDGET = 16`` distinct unknowns are tracked verbatim;
subsequent unknowns collapse to ``"_unmatched"``). This means an
attacker emitting many distinct frame types cannot inflate the
counter's label cardinality.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


# Lazy-init Counter — None when prometheus_client is unavailable.
# Typed as ``Any`` so callers can ``.labels(...).inc()`` without MyPy
# tripping over the runtime ``Optional[object]`` placeholder we'd
# otherwise need to keep the prometheus-client import optional.
_unrecognized_counter: Optional[Any] = None
_init_attempted = False


def _ensure_counter() -> Optional[Any]:
    """Create the unrecognized-frame counter on first use, or return None.

    Returns ``None`` when ``prometheus-client`` isn't installed; callers
    handle that case by emitting a log line and moving on. Idempotent:
    repeated calls return the same Counter object (or repeatedly
    return ``None`` when the import remains unavailable).
    """
    global _unrecognized_counter, _init_attempted
    if _init_attempted:
        return _unrecognized_counter

    _init_attempted = True
    try:
        from prometheus_client import Counter
    except ImportError:
        return None

    _unrecognized_counter = Counter(
        "juniper_cascor_client_unrecognized_ws_frames_total",
        "WS frames that failed envelope validation, by reported type and endpoint.",
        ["type", "endpoint"],
    )
    return _unrecognized_counter


def record_unrecognized_frame(type_label: str, endpoint: str) -> None:
    """Record an unrecognized WS frame.

    Always emits a structured WARNING log line; additionally increments
    the Prometheus counter when ``prometheus-client`` is installed.

    Args:
        type_label: The cardinality-bounded type string from the
            ``UnknownEnvelope`` returned by
            :func:`juniper_cascor_protocol.envelope.validate_envelope`.
            Already collapsed to ``"_unmatched"`` if the per-process
            distinct-unknown-type budget is exhausted.
        endpoint: ``"training"`` or ``"control"`` — which WS endpoint
            the frame arrived on.
    """
    logger.warning(
        "juniper_cascor_client_unrecognized_ws_frame",
        extra={"type": type_label, "endpoint": endpoint},
    )
    counter = _ensure_counter()
    if counter is not None:
        counter.labels(type=type_label, endpoint=endpoint).inc()


def reset_for_tests() -> None:
    """Clear the cached Counter so tests can patch ``prometheus_client`` behaviour.

    Also unregisters the live Counter from the default Prometheus
    registry (when present) so the next ``_ensure_counter()`` call
    creates a fresh instance instead of crashing with ``Duplicated
    timeseries in CollectorRegistry``.

    Production callers should never invoke this.
    """
    global _unrecognized_counter, _init_attempted
    if _unrecognized_counter is not None:
        try:
            from prometheus_client import REGISTRY

            REGISTRY.unregister(_unrecognized_counter)
        except (ImportError, KeyError):
            # ImportError: prometheus_client never imported in the first place.
            # KeyError: counter wasn't actually registered (race / double-reset).
            pass
    _unrecognized_counter = None
    _init_attempted = False
