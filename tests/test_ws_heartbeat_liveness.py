"""CL1: WebSocket heartbeat handling + liveness-surface tests.

Covers the client half of the cascor C3 heartbeat contract (the 2026-07-10
incident fix):

* ``ping`` frames are answered with ``{"type": "pong"}`` and consumed by the
  transport layer on both stream classes (``auto_pong=True`` default), and are
  NEVER recorded as unrecognized frames.
* ``auto_pong=False`` restores the legacy yield-the-ping behaviour.
* ``CascorControlStream.connect()`` starts the background recv loop eagerly so
  pings are answered before the first command (pre-CL1, nothing read the
  control socket until the first ``set_params`` — the 40s kill).
* The direct (uncorrelated) ``command()`` path skips pings so a ping can never
  be returned as a command's response.
* The liveness surface (``is_connected`` / ``is_alive`` / ``last_frame_at`` /
  ``pongs_sent``) — the seam canopy's supervisor hardening (plan unit N2)
  consumes — behaves identically on the real streams and the fake.
"""

import asyncio
import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from websockets.protocol import State

from juniper_cascor_client import CascorControlStream, CascorTrainingStream
from juniper_cascor_client.constants import DEFAULT_LIVENESS_WINDOW_SEC
from juniper_cascor_client.testing import FakeCascorTrainingStream

PING_FRAME = json.dumps({"type": "ping", "ts": 1234.5})
METRICS_FRAME = json.dumps({"type": "metrics", "timestamp": 1.0, "data": {"epoch": 1}})


def _iterating_ws(frames):
    """Build an AsyncMock websocket whose async-iteration yields ``frames``."""

    async def async_iter():
        for frame in frames:
            yield frame

    mock_ws = AsyncMock()
    mock_ws.__aiter__ = lambda self: async_iter()
    mock_ws.state = State.OPEN
    return mock_ws


@pytest.mark.unit
class TestTrainingStreamHeartbeat:
    """CL1 heartbeat handling on CascorTrainingStream."""

    @pytest.mark.asyncio
    async def test_ping_answered_and_swallowed(self):
        """Default auto_pong: pings are ponged, consumed, and never yielded."""
        mock_ws = _iterating_ws([PING_FRAME, METRICS_FRAME])
        stream = CascorTrainingStream()
        stream._ws = mock_ws

        received = [msg async for msg in stream.stream()]

        assert [m["type"] for m in received] == ["metrics"], "ping must not be yielded"
        sent = [json.loads(c.args[0]) for c in mock_ws.send.call_args_list]
        assert {"type": "pong"} in sent, "ping must be answered with a pong"
        assert stream.pongs_sent == 1

    @pytest.mark.asyncio
    async def test_ping_never_recorded_as_unrecognized(self):
        """CL1: ping is a RECOGNIZED transport frame — no warning spam."""
        mock_ws = _iterating_ws([PING_FRAME])
        stream = CascorTrainingStream()
        stream._ws = mock_ws

        with patch("juniper_cascor_client.ws_client.record_unrecognized_frame") as mock_record:
            async for _ in stream.stream():
                pass
        mock_record.assert_not_called()

    @pytest.mark.asyncio
    async def test_ping_yielded_when_auto_pong_disabled(self):
        """auto_pong=False: legacy behaviour — ping is yielded, no pong sent, still no warning."""
        mock_ws = _iterating_ws([PING_FRAME, METRICS_FRAME])
        stream = CascorTrainingStream(auto_pong=False)
        stream._ws = mock_ws

        with patch("juniper_cascor_client.ws_client.record_unrecognized_frame") as mock_record:
            received = [msg async for msg in stream.stream()]

        assert [m["type"] for m in received] == ["ping", "metrics"]
        sent = [json.loads(c.args[0]) for c in mock_ws.send.call_args_list]
        assert {"type": "pong"} not in sent
        assert stream.pongs_sent == 0
        mock_record.assert_not_called()

    @pytest.mark.asyncio
    async def test_stream_marks_liveness_per_frame(self):
        """Every inbound frame (including pings) updates the liveness clock."""
        mock_ws = _iterating_ws([PING_FRAME])
        stream = CascorTrainingStream()
        stream._ws = mock_ws
        assert stream.last_frame_at is None

        async for _ in stream.stream():
            pass

        assert stream.last_frame_at is not None
        assert stream.is_alive(DEFAULT_LIVENESS_WINDOW_SEC) is True

    @pytest.mark.asyncio
    async def test_connect_marks_first_liveness(self):
        """A successful connect is the first liveness evidence."""
        mock_ws = AsyncMock()
        mock_ws.state = State.OPEN
        with patch("juniper_cascor_client.ws_client.websockets.connect", new_callable=AsyncMock, return_value=mock_ws):
            stream = CascorTrainingStream()
            assert stream.is_alive() is False  # not connected yet
            await stream.connect()
            assert stream.last_frame_at is not None
            assert stream.is_alive() is True
            await stream.disconnect()


@pytest.mark.unit
class TestLivenessSurface:
    """is_connected / is_alive semantics (N2's seam)."""

    def test_is_connected_false_without_socket(self):
        stream = CascorTrainingStream()
        assert stream.is_connected is False
        assert stream.is_alive() is False

    def test_is_connected_reflects_protocol_state(self):
        stream = CascorTrainingStream()
        stream._ws = SimpleNamespace(state=State.OPEN)
        assert stream.is_connected is True
        # A processed close (e.g. the server's 1011 heartbeat-timeout close)
        # flips the protocol state — is_connected sees it, the historical
        # ``_ws is not None`` idiom did not.
        stream._ws = SimpleNamespace(state=State.CLOSED)
        assert stream.is_connected is False

    def test_is_connected_falls_back_to_presence_without_state(self):
        stream = CascorTrainingStream()
        stream._ws = SimpleNamespace(state=None)
        assert stream.is_connected is True

    def test_is_alive_detects_half_open_silence(self):
        """OPEN state + stale frames = half-open: is_connected True, is_alive False."""
        stream = CascorTrainingStream()
        stream._ws = SimpleNamespace(state=State.OPEN)
        stream._last_frame_monotonic = time.monotonic() - 1000.0
        stream._last_frame_wall = time.time() - 1000.0
        assert stream.is_connected is True
        assert stream.is_alive(90.0) is False
        # A fresh frame restores aliveness.
        stream._mark_inbound_frame()
        assert stream.is_alive(90.0) is True

    def test_is_alive_false_before_any_frame(self):
        stream = CascorTrainingStream()
        stream._ws = SimpleNamespace(state=State.OPEN)
        assert stream.is_alive() is False

    def test_control_stream_exposes_same_surface(self):
        ctrl = CascorControlStream()
        assert ctrl.is_connected is False
        assert ctrl.is_alive() is False
        assert ctrl.last_frame_at is None
        assert ctrl.pongs_sent == 0
        ctrl._ws = SimpleNamespace(state=State.OPEN)
        ctrl._mark_inbound_frame()
        assert ctrl.is_connected is True
        assert ctrl.is_alive() is True


@pytest.mark.unit
class TestControlStreamHeartbeat:
    """CL1 heartbeat handling on CascorControlStream."""

    @pytest.mark.asyncio
    async def test_connect_starts_recv_loop_eagerly(self):
        """The recv loop runs from connect() — pings are answered before any command."""
        mock_ws = AsyncMock()
        mock_ws.state = State.OPEN
        block = asyncio.Event()
        state = {"handshake_sent": False}

        async def fake_recv():
            if not state["handshake_sent"]:
                state["handshake_sent"] = True
                return json.dumps({"type": "connection_established"})
            await block.wait()  # park (cancelled by disconnect)
            return json.dumps({"type": "noop"})

        mock_ws.recv = fake_recv
        with patch("juniper_cascor_client.ws_client.websockets.connect", new_callable=AsyncMock, return_value=mock_ws):
            ctrl = CascorControlStream()
            await ctrl.connect()
            try:
                assert ctrl._recv_task is not None
                assert not ctrl._recv_task.done()
                assert ctrl.last_frame_at is not None  # handshake marked
                assert ctrl.is_alive() is True
            finally:
                await ctrl.disconnect()
        assert ctrl._recv_task is None

    @pytest.mark.asyncio
    async def test_recv_loop_answers_ping_and_still_correlates(self):
        """Pings are ponged + consumed; command_response correlation is untouched."""
        ctrl = CascorControlStream()
        mock_ws = AsyncMock()
        mock_ws.state = State.OPEN
        ctrl._ws = mock_ws

        loop = asyncio.get_running_loop()
        matched = loop.create_future()
        ctrl._pending["cid-1"] = matched

        frames = [
            PING_FRAME,
            json.dumps({"type": "command_response", "timestamp": 1.0, "data": {"command_id": "cid-1", "status": "success"}}),
        ]
        state = {"i": 0}

        async def fake_recv():
            i = state["i"]
            state["i"] += 1
            if i < len(frames):
                return frames[i]
            ctrl._ws = None  # exit the while-loop
            return json.dumps({"type": "noop", "timestamp": 1.0, "data": {}})

        mock_ws.recv = fake_recv
        await ctrl._recv_loop()

        assert matched.done()
        assert matched.result()["data"]["command_id"] == "cid-1"
        sent = [json.loads(c.args[0]) for c in mock_ws.send.call_args_list]
        assert {"type": "pong"} in sent
        assert ctrl.pongs_sent == 1

    @pytest.mark.asyncio
    async def test_recv_loop_ping_never_recorded_as_unrecognized(self):
        ctrl = CascorControlStream()
        mock_ws = AsyncMock()
        ctrl._ws = mock_ws

        frames = [PING_FRAME]
        state = {"i": 0}

        async def fake_recv():
            i = state["i"]
            state["i"] += 1
            if i < len(frames):
                return frames[i]
            ctrl._ws = None
            return json.dumps({"type": "noop", "timestamp": 1.0, "data": {}})

        mock_ws.recv = fake_recv
        with patch("juniper_cascor_client.ws_client.record_unrecognized_frame") as mock_record:
            await ctrl._recv_loop()
        recorded_types = [c.args[0] for c in mock_record.call_args_list]
        assert "ping" not in recorded_types

    @pytest.mark.asyncio
    async def test_recv_loop_no_pong_when_auto_pong_disabled(self):
        ctrl = CascorControlStream(auto_pong=False)
        mock_ws = AsyncMock()
        ctrl._ws = mock_ws

        frames = [PING_FRAME]
        state = {"i": 0}

        async def fake_recv():
            i = state["i"]
            state["i"] += 1
            if i < len(frames):
                return frames[i]
            ctrl._ws = None
            return json.dumps({"type": "noop", "timestamp": 1.0, "data": {}})

        mock_ws.recv = fake_recv
        await ctrl._recv_loop()
        sent = [json.loads(c.args[0]) for c in mock_ws.send.call_args_list]
        assert {"type": "pong"} not in sent
        assert ctrl.pongs_sent == 0

    @pytest.mark.asyncio
    async def test_direct_command_path_skips_ping(self):
        """A ping arriving ahead of the response is answered and never returned."""
        mock_ws = AsyncMock()
        mock_ws.state = State.OPEN
        response = json.dumps({"type": "command_response", "data": {"command": "stop", "status": "success"}})
        mock_ws.recv = AsyncMock(side_effect=[PING_FRAME, response])
        ctrl = CascorControlStream()
        ctrl._ws = mock_ws
        # No background recv task -> direct path.
        assert ctrl._recv_task is None

        result = await ctrl.command("stop")

        assert result["type"] == "command_response"
        assert result["data"]["status"] == "success"
        sent = [json.loads(c.args[0]) for c in mock_ws.send.call_args_list]
        assert {"type": "pong"} in sent
        assert ctrl.pongs_sent == 1


@pytest.mark.unit
class TestFakeTrainingStreamParity:
    """FakeCascorTrainingStream mirrors the CL1 contract (the #91 lesson)."""

    @pytest.mark.asyncio
    async def test_fake_swallows_ping_and_counts_pong(self):
        fake = FakeCascorTrainingStream(
            messages=[
                {"type": "ping", "ts": 1234.5},
                {"type": "metrics", "data": {"epoch": 1}},
            ],
            delay=0.01,
        )
        async with fake as stream:
            received = [msg async for msg in stream.stream()]

        assert [m["type"] for m in received] == ["metrics"], "fake must swallow pings like the real stream"
        assert fake.pongs_sent == 1

    @pytest.mark.asyncio
    async def test_fake_yields_ping_when_auto_pong_disabled(self):
        fake = FakeCascorTrainingStream(
            messages=[{"type": "ping", "ts": 1234.5}, {"type": "metrics", "data": {}}],
            delay=0.01,
            auto_pong=False,
        )
        async with fake as stream:
            received = [msg async for msg in stream.stream()]

        assert [m["type"] for m in received] == ["ping", "metrics"]
        assert fake.pongs_sent == 0

    @pytest.mark.asyncio
    async def test_fake_liveness_surface_parity(self):
        fake = FakeCascorTrainingStream(messages=[{"type": "metrics", "data": {}}], delay=0.01)
        assert fake.is_connected is False
        assert fake.is_alive() is False
        assert fake.last_frame_at is None

        await fake.connect()
        assert fake.is_connected is True
        assert fake.is_alive() is True  # connect marks first liveness
        assert fake.last_frame_at is not None

        async for _ in fake.stream():
            pass
        await fake.disconnect()
        assert fake.is_connected is False
        assert fake.is_alive() is False

    def test_fake_and_real_expose_identical_liveness_names(self):
        """Surface-name parity: every CL1 liveness name exists on both classes."""
        for name in ("is_connected", "is_alive", "last_frame_at", "pongs_sent"):
            assert hasattr(CascorTrainingStream, name), f"real stream missing {name}"
            assert hasattr(FakeCascorTrainingStream, name), f"fake missing {name}"
