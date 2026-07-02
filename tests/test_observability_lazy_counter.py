"""Lazy-counter internals for the optional Prometheus observability layer.

Covers ``observability._ensure_counter``'s duplicate-registration adoption
path (a second ``Counter(...)`` with the same name raises ``ValueError`` and
the already-registered collector is adopted) and the re-raise guard when the
collector is unexpectedly absent from the registry.

Complements ``test_inbound_validation.py`` (which exercises
``record_unrecognized_frame`` end-to-end with a mocked Counter); this file
pins the module-private lazy-init contract documented in the
``observability.py`` module docstring, using the *real* ``prometheus_client``
Counter pulled in by the ``[test]`` extra.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from juniper_cascor_client import observability as ws_obs

_METRIC_NAME = "juniper_cascor_client_unrecognized_ws_frames_total"


@pytest.fixture(autouse=True)
def _clean_counter_registry():
    """Guarantee a pristine counter cache + Prometheus registry per test.

    ``_ensure_counter`` caches a module-global Counter and registers it in
    the default ``prometheus_client`` REGISTRY. Tests here deliberately poke
    that global state, so both the cache and any live collector are torn
    down on each side of the test to avoid cross-test leakage.
    """
    ws_obs.reset_for_tests()
    yield
    try:
        from prometheus_client import REGISTRY

        existing = REGISTRY._names_to_collectors.get(_METRIC_NAME)
        if existing is not None:
            REGISTRY.unregister(existing)
    except ImportError:
        # Best-effort test teardown: if prometheus_client is unavailable,
        # there is no registry entry to remove.
        pass
    except KeyError:
        # Best-effort test teardown: collector may already be absent from
        # the registry by the time we attempt to unregister it.
        pass
    ws_obs.reset_for_tests()


@pytest.mark.unit
class TestEnsureCounterAdoption:
    """``_ensure_counter`` adopts an already-registered collector (obs.py:64-75)."""

    def test_adopts_existing_collector_on_duplicate_registration(self):
        """A cache reset that skips the REGISTRY scrub must not crash the next
        init: the duplicate ``Counter(...)`` raises ``ValueError`` and the live
        collector is adopted rather than re-registered."""
        first = ws_obs._ensure_counter()
        assert first is not None, "prometheus-client is a [test] dep; the counter must init"

        # Simulate a test (or in-process re-init) that cleared the cache
        # WITHOUT unregistering from the REGISTRY — the exact scenario the
        # observability.py:64 ValueError handler is written for.
        ws_obs._unrecognized_counter = None
        ws_obs._init_attempted = False

        second = ws_obs._ensure_counter()
        assert second is first, "must adopt the already-registered collector, not create a new one"

    def test_ensure_counter_is_idempotent_when_cache_warm(self):
        """Once the cache is warm, ``_ensure_counter`` short-circuits and
        returns the same object without touching the registry again."""
        first = ws_obs._ensure_counter()
        second = ws_obs._ensure_counter()
        assert first is second

    def test_reraises_valueerror_when_collector_absent_from_registry(self):
        """If ``Counter(...)`` raises ``ValueError`` but the name is *not* in
        the registry, the failure is genuine and must propagate (obs.py:73-74)."""
        ws_obs.reset_for_tests()
        from prometheus_client import REGISTRY

        assert REGISTRY._names_to_collectors.get(_METRIC_NAME) is None, "precondition: name unregistered"

        with patch("prometheus_client.Counter", side_effect=ValueError("boom")):
            with pytest.raises(ValueError, match="boom"):
                ws_obs._ensure_counter()

        # Nothing was adopted — the cache stayed empty.
        assert ws_obs._unrecognized_counter is None
