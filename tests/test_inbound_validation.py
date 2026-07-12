"""Inbound WS frame validation — METRICS-MON R2.2.4 / seed-05.

These tests cover both the happy path (valid envelopes pass through
unchanged and reach registered callbacks) and the chaos path
(malformed / unknown / schema-mismatch frames are observed via
structured log + Prometheus counter, but **never** crash the consumer
or interrupt the stream).

The Prometheus counter is part of the optional ``[observability]``
extra. The ``[test]`` extra pulls ``prometheus-client`` so we exercise
both branches (counter installed vs not) deterministically.
"""

from __future__ import annotations

import asyncio
import json
import logging
from unittest.mock import MagicMock, patch

import pytest

from juniper_cascor_client import observability as ws_obs
from juniper_cascor_client.ws_client import CascorTrainingStream, _validate_and_record

# ---------------------------------------------------------------------------
# Fresh-state fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_observability_state():
    """Clear the cardinality tracker + counter cache between tests."""
    from juniper_cascor_protocol.envelope import reset_unknown_label_state

    reset_unknown_label_state()
    ws_obs.reset_for_tests()
    yield
    reset_unknown_label_state()
    ws_obs.reset_for_tests()


# ---------------------------------------------------------------------------
# _validate_and_record — the helper called by stream() / _recv_loop / command()
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestValidateAndRecord:
    """The validation helper is purely observational."""

    def test_known_envelope_returns_message_unchanged(self):
        msg = {"type": "metrics", "timestamp": 1.0, "data": {"loss": 0.1}, "seq": 5}
        result = _validate_and_record(msg, endpoint="training")
        assert result is msg
        assert result == {"type": "metrics", "timestamp": 1.0, "data": {"loss": 0.1}, "seq": 5}

    def test_unknown_type_returns_message_unchanged(self):
        msg = {"type": "garbage_type", "timestamp": 1.0, "data": {}}
        result = _validate_and_record(msg, endpoint="training")
        assert result is msg

    def test_known_type_with_invalid_payload_returns_message_unchanged(self):
        # initial_metrics payload requires count to be int — pass a string.
        msg = {"type": "initial_metrics", "timestamp": 1.0, "data": {"metrics": [], "count": "not-int", "current_seq": 0}}
        result = _validate_and_record(msg, endpoint="training")
        assert result is msg

    def test_unknown_envelope_increments_counter_when_prom_installed(self):
        ws_obs.reset_for_tests()
        mock_counter_inst = MagicMock()
        with patch("prometheus_client.Counter", return_value=mock_counter_inst):
            _validate_and_record({"type": "made_up_type", "timestamp": 0.0, "data": {}}, endpoint="training")
            mock_counter_inst.labels.assert_called_once_with(type="made_up_type", endpoint="training")
            mock_counter_inst.labels().inc.assert_called_once()

    def test_known_envelope_does_not_increment_counter(self):
        # Patch where ``record_unrecognized_frame`` is *bound* — ``ws_client``
        # imported it by name at module load, so patching the source module
        # would not affect the bound reference.
        with patch("juniper_cascor_client.ws_client.record_unrecognized_frame") as mock_record:
            _validate_and_record({"type": "metrics", "timestamp": 0.0, "data": {}}, endpoint="training")
            mock_record.assert_not_called()

    def test_unknown_envelope_emits_structured_log_warning(self, caplog):
        with caplog.at_level(logging.WARNING, logger="juniper_cascor_client.observability"):
            _validate_and_record({"type": "garbage_xyz", "timestamp": 0.0, "data": {}}, endpoint="training")
        warnings = [rec for rec in caplog.records if rec.levelno == logging.WARNING]
        assert len(warnings) >= 1
        rec = warnings[-1]
        # CL1: the type + endpoint are part of the MESSAGE text (previously
        # only in ``extra``, which standard formatters drop — the incident's
        # zero-diagnostic-value warning spam); the stable prefix is preserved
        # for log-grep continuity.
        assert rec.message == "juniper_cascor_client_unrecognized_ws_frame type=garbage_xyz endpoint=training"
        assert getattr(rec, "type", None) == "garbage_xyz"
        assert getattr(rec, "endpoint", None) == "training"

    def test_endpoint_label_distinguishes_training_and_control(self):
        # Patch where ``record_unrecognized_frame`` is *bound* — ``ws_client``
        # imported it by name at module load.
        with patch("juniper_cascor_client.ws_client.record_unrecognized_frame") as mock_record:
            _validate_and_record({"type": "_unknown_a", "timestamp": 0.0, "data": {}}, endpoint="training")
            _validate_and_record({"type": "_unknown_b", "timestamp": 0.0, "data": {}}, endpoint="control")
            assert mock_record.call_count == 2
            calls = [c.args for c in mock_record.call_args_list]
            assert ("_unknown_a", "training") in calls
            assert ("_unknown_b", "control") in calls


# ---------------------------------------------------------------------------
# Counter behavior — graceful degrade when prometheus-client missing
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCounterGracefulDegrade:

    def test_record_works_without_prometheus(self, caplog):
        """When prometheus_client import fails, only the log line fires."""
        # Force the Counter init to fail by making prometheus_client raise.
        with patch.dict("sys.modules", {"prometheus_client": None}):
            ws_obs.reset_for_tests()
            with caplog.at_level(logging.WARNING, logger="juniper_cascor_client.observability"):
                # Must not raise even though Counter is unavailable.
                ws_obs.record_unrecognized_frame("missing_prom_test", "training")
        assert any("juniper_cascor_client_unrecognized_ws_frame" in rec.message for rec in caplog.records)


# ---------------------------------------------------------------------------
# CascorTrainingStream chaos — malformed inbound frames must not crash stream()
# ---------------------------------------------------------------------------


class _FakeWs:
    """Minimal async iterator that yields pre-canned raw frames then closes."""

    def __init__(self, frames):
        self._frames = list(frames)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._frames:
            raise StopAsyncIteration
        return self._frames.pop(0)

    async def close(self):
        pass


@pytest.mark.asyncio
@pytest.mark.unit
async def test_stream_yields_through_malformed_frames(caplog):
    """A mix of healthy + malformed + unknown-type frames all reach the caller; nothing raises."""
    raw_frames = [
        json.dumps({"type": "metrics", "timestamp": 1.0, "data": {"loss": 0.1}, "seq": 1}),
        json.dumps({"type": "garbage_one", "timestamp": 2.0, "data": {}}),
        json.dumps({"type": "initial_metrics", "timestamp": 3.0, "data": {"metrics": [], "count": "BAD", "current_seq": 0}}),
        json.dumps({"type": "state", "timestamp": 4.0, "data": {"phase": "candidate"}}),
    ]
    stream = CascorTrainingStream(base_url="ws://localhost:8200")
    stream._ws = _FakeWs(raw_frames)

    received = []
    metrics_callback_args = []
    state_callback_args = []
    stream.on_metrics(lambda d: metrics_callback_args.append(d))
    stream.on_state(lambda d: state_callback_args.append(d))

    with caplog.at_level(logging.WARNING, logger="juniper_cascor_client.observability"):
        async for msg in stream.stream():
            received.append(msg)

    # Every frame was yielded — the stream did NOT swallow the bad ones.
    assert len(received) == 4
    types = [m["type"] for m in received]
    assert types == ["metrics", "garbage_one", "initial_metrics", "state"]

    # Known-type callbacks fired exactly for their types.
    assert metrics_callback_args == [{"loss": 0.1}]
    assert state_callback_args == [{"phase": "candidate"}]

    # The malformed frames produced WARNING log lines.
    warnings = [rec for rec in caplog.records if rec.levelno == logging.WARNING]
    # CL1: the warning message now carries ``type=... endpoint=...`` after the
    # stable grep prefix, so match on the prefix.
    types_warned = sorted({getattr(rec, "type", None) for rec in warnings if rec.message.startswith("juniper_cascor_client_unrecognized_ws_frame")})
    # Both ``garbage_one`` (unknown type) and ``initial_metrics`` (known
    # type, invalid payload) should each have raised exactly one warning.
    assert "garbage_one" in types_warned
    assert "initial_metrics" in types_warned


@pytest.mark.asyncio
@pytest.mark.unit
async def test_stream_raises_clean_error_when_not_connected():
    """The pre-existing ``stream()`` precondition contract is unchanged by R2.2.4."""
    stream = CascorTrainingStream(base_url="ws://localhost:8200")
    # _ws not set
    from juniper_cascor_client.exceptions import JuniperCascorClientError

    with pytest.raises(JuniperCascorClientError):
        async for _ in stream.stream():
            pass


# ---------------------------------------------------------------------------
# R1.1 cardinality bound — counter labels collapse after budget exhausted
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_unknown_label_collapses_after_budget(caplog):
    """METRICS-MON R1.1: distinct unknown types beyond UNKNOWN_TYPE_BUDGET collapse to ``_unmatched``."""
    from juniper_cascor_protocol.envelope import UNKNOWN_TYPE_BUDGET, UNMATCHED_TYPE_LABEL

    # Use real prometheus_client Counter via the production lazy init
    # path. We watch the counter's labels() calls to confirm the bound.
    fake_counter = MagicMock()
    with patch("prometheus_client.Counter", return_value=fake_counter):
        ws_obs.reset_for_tests()

        # Fire UNKNOWN_TYPE_BUDGET distinct unknowns.
        for i in range(UNKNOWN_TYPE_BUDGET):
            _validate_and_record({"type": f"unknown_{i}", "timestamp": 0.0, "data": {}}, endpoint="training")

        # The next distinct unknown collapses.
        _validate_and_record({"type": "another_one", "timestamp": 0.0, "data": {}}, endpoint="training")

        # Inspect the labels() calls — the last one was for ``_unmatched``.
        last_call_kwargs = fake_counter.labels.call_args_list[-1].kwargs
        assert last_call_kwargs == {"type": UNMATCHED_TYPE_LABEL, "endpoint": "training"}
