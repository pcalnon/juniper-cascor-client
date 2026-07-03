"""Targeted coverage for the async WebSocket clients.

Complements ``test_ws_client.py`` / ``test_set_params.py`` / ``test_inbound_validation.py``
by exercising the connect-time branches (API-key header forwarding, transport-error
wrapping, control-handshake rejection), the training-stream sugar
(``listen`` / ``on_candidate_progress`` / ``async with`` / ``async for``), the
control-stream ``disconnect`` recv-task teardown, the correlated ``command``
params branch, and the background ``_recv_loop`` routing + disconnect-fanout.

Drives the *real* ``CascorTrainingStream`` / ``CascorControlStream`` via
``AsyncMock`` (the established idiom in ``test_ws_client.py``) so the production
code paths — not a fake — are what gets measured.
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import websockets

from juniper_cascor_client import CascorControlStream, CascorTrainingStream
from juniper_cascor_client.exceptions import JuniperCascorClientError, JuniperCascorConnectionError


@pytest.fixture(autouse=True)
def _reset_observability_state():
    """Reset the cardinality tracker + counter cache around each test.

    ``_recv_loop`` / ``stream`` run inbound frames through the observational
    envelope validator, which lazily registers a real Prometheus counter for
    unknown types. Reset on both sides so counters created here never leak into
    (or duplicate-register against) sibling test modules.
    """
    from juniper_cascor_client import observability as _obs

    try:
        from juniper_cascor_protocol.envelope import reset_unknown_label_state

        reset_unknown_label_state()
    except ImportError:  # pragma: no cover - protocol pkg is a hard dep
        pass
    _obs.reset_for_tests()
    yield
    try:
        from juniper_cascor_protocol.envelope import reset_unknown_label_state

        reset_unknown_label_state()
    except ImportError:  # pragma: no cover
        pass
    _obs.reset_for_tests()


# ---------------------------------------------------------------------------
# CascorTrainingStream — connect branches + iteration sugar
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestTrainingStreamConnect:
    @pytest.mark.asyncio
    async def test_connect_forwards_api_key_header(self):
        """A configured api_key is sent as the X-API-Key additional header (ws_client.py:130)."""
        mock_ws = AsyncMock()
        with patch("juniper_cascor_client.ws_client.websockets.connect", new_callable=AsyncMock, return_value=mock_ws) as mock_connect:
            stream = CascorTrainingStream("ws://localhost:8200", api_key="secret-key")
            await stream.connect()
            headers = mock_connect.call_args.kwargs["additional_headers"]
            assert headers["X-API-Key"] == "secret-key"
            await stream.disconnect()

    @pytest.mark.asyncio
    async def test_connect_wraps_oserror_as_connection_error(self):
        """A socket-level failure during connect is wrapped (ws_client.py:136-137)."""
        with patch("juniper_cascor_client.ws_client.websockets.connect", new_callable=AsyncMock, side_effect=OSError("refused")):
            stream = CascorTrainingStream("ws://localhost:8200")
            with pytest.raises(JuniperCascorConnectionError, match="Failed to connect"):
                await stream.connect()


@pytest.mark.unit
class TestTrainingStreamSugar:
    @pytest.mark.asyncio
    async def test_listen_consumes_stream_via_callbacks(self):
        """``listen()`` drains ``stream()`` dispatching to callbacks (ws_client.py:181)."""
        frames = [
            json.dumps({"type": "metrics", "timestamp": 1.0, "data": {"epoch": 1}}),
            json.dumps({"type": "state", "timestamp": 2.0, "data": {"state": "running"}}),
        ]

        async def async_iter():
            for m in frames:
                yield m

        mock_ws = AsyncMock()
        mock_ws.__aiter__ = lambda self: async_iter()
        stream = CascorTrainingStream()
        stream._ws = mock_ws

        seen = []
        stream.on_metrics(lambda d: seen.append(("metrics", d)))
        stream.on_state(lambda d: seen.append(("state", d)))
        await stream.listen()

        assert ("metrics", {"epoch": 1}) in seen
        assert ("state", {"state": "running"}) in seen

    def test_on_candidate_progress_registers_and_dispatches(self):
        """``on_candidate_progress`` wires the candidate_progress type (ws_client.py:232)."""
        stream = CascorTrainingStream()
        cb = MagicMock()
        stream.on_candidate_progress(cb)
        assert "candidate_progress" in stream._callbacks
        stream._dispatch({"type": "candidate_progress", "data": {"round": 2}})
        cb.assert_called_once_with({"round": 2})

    @pytest.mark.asyncio
    async def test_async_context_manager_connects_and_disconnects(self):
        """``async with`` drives __aenter__/__aexit__ (ws_client.py:262-263, 266)."""
        mock_ws = AsyncMock()
        with patch("juniper_cascor_client.ws_client.websockets.connect", new_callable=AsyncMock, return_value=mock_ws):
            async with CascorTrainingStream("ws://localhost:8200") as stream:
                assert stream._ws is mock_ws
            assert stream._ws is None
        mock_ws.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_async_iter_iterates_stream(self):
        """``async for msg in stream`` routes through __aiter__ (ws_client.py:269)."""
        frames = [json.dumps({"type": "metrics", "timestamp": 1.0, "data": {"epoch": 1}})]

        async def async_iter():
            for m in frames:
                yield m

        mock_ws = AsyncMock()
        mock_ws.__aiter__ = lambda self: async_iter()
        stream = CascorTrainingStream()
        stream._ws = mock_ws

        received = []
        async for msg in stream:
            received.append(msg)
        assert received[0]["type"] == "metrics"


# ---------------------------------------------------------------------------
# CascorControlStream — connect branches, disconnect teardown, correlated params
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestControlStreamConnect:
    @pytest.mark.asyncio
    async def test_connect_forwards_api_key_header(self):
        """A configured api_key is sent as the X-API-Key additional header (ws_client.py:342)."""
        mock_ws = AsyncMock()
        mock_ws.recv = AsyncMock(return_value=json.dumps({"type": "connection_established"}))
        with patch("juniper_cascor_client.ws_client.websockets.connect", new_callable=AsyncMock, return_value=mock_ws) as mock_connect:
            ctrl = CascorControlStream(api_key="ctrl-secret")
            await ctrl.connect()
            headers = mock_connect.call_args.kwargs["additional_headers"]
            assert headers["X-API-Key"] == "ctrl-secret"
            await ctrl.disconnect()

    @pytest.mark.asyncio
    async def test_connect_rejects_unexpected_first_frame(self):
        """A non-handshake first frame is a protocol violation (ws_client.py:355)."""
        mock_ws = AsyncMock()
        mock_ws.recv = AsyncMock(return_value=json.dumps({"type": "metrics", "data": {}}))
        with patch("juniper_cascor_client.ws_client.websockets.connect", new_callable=AsyncMock, return_value=mock_ws):
            ctrl = CascorControlStream()
            with pytest.raises(JuniperCascorClientError, match="Expected connection_established"):
                await ctrl.connect()

    @pytest.mark.asyncio
    async def test_connect_wraps_oserror_as_connection_error(self):
        """A socket-level failure during connect is wrapped (ws_client.py:356-357)."""
        with patch("juniper_cascor_client.ws_client.websockets.connect", new_callable=AsyncMock, side_effect=OSError("refused")):
            ctrl = CascorControlStream()
            with pytest.raises(JuniperCascorConnectionError, match="Failed to connect"):
                await ctrl.connect()


@pytest.mark.unit
class TestControlStreamDisconnect:
    @pytest.mark.asyncio
    async def test_disconnect_cancels_active_recv_task(self):
        """disconnect cancels + awaits a live recv task, then closes (ws_client.py:362-370)."""
        ctrl = CascorControlStream()
        mock_ws = AsyncMock()

        async def _never():
            await asyncio.Event().wait()

        mock_ws.recv = _never
        ctrl._ws = mock_ws
        await ctrl._ensure_recv_task()
        await asyncio.sleep(0.01)  # let the recv task start and block on recv()
        assert ctrl._recv_task is not None and not ctrl._recv_task.done()

        await ctrl.disconnect()

        assert ctrl._recv_task is None
        assert ctrl._ws is None
        mock_ws.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected_is_noop(self):
        """No recv task and no socket -> disconnect is a clean no-op (ws_client.py:368->exit)."""
        ctrl = CascorControlStream()
        await ctrl.disconnect()  # must not raise
        assert ctrl._ws is None
        assert ctrl._recv_task is None


@pytest.mark.unit
class TestControlStreamCorrelatedCommand:
    @pytest.mark.asyncio
    async def test_command_correlated_path_includes_params(self):
        """The correlated command() path attaches params to the envelope (ws_client.py:396)."""
        ctrl = CascorControlStream()
        ctrl._ws = AsyncMock()

        # Force the correlated branch without a live recv loop: a not-done task.
        fake_task = MagicMock()
        fake_task.done.return_value = False
        ctrl._recv_task = fake_task

        with patch.object(ctrl, "_send_correlated", new_callable=AsyncMock) as mock_send_corr:
            mock_send_corr.return_value = {"type": "command_response", "data": {"status": "success"}}
            result = await ctrl.command("start", {"epochs": 100})

        assert result["data"]["status"] == "success"
        sent_message = mock_send_corr.call_args.args[0]
        sent_cid = mock_send_corr.call_args.args[1]
        assert sent_message["type"] == "command"
        assert sent_message["command"] == "start"
        assert sent_message["params"] == {"epochs": 100}
        assert sent_message["command_id"] == sent_cid


# ---------------------------------------------------------------------------
# CascorControlStream._recv_loop — routing, malformed-skip, disconnect fanout
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestControlStreamRecvLoop:
    @pytest.mark.asyncio
    async def test_recv_loop_routes_matching_response_and_skips_the_rest(self):
        """_recv_loop drops malformed frames, ignores non/unmatched responses,
        routes a matching command_response to its future, then exits cleanly
        when the socket reference clears (ws_client.py:492-506 + branches)."""
        ctrl = CascorControlStream()
        mock_ws = AsyncMock()
        ctrl._ws = mock_ws

        loop = asyncio.get_running_loop()
        matched = loop.create_future()
        ctrl._pending["cid-match"] = matched

        frames = [
            "not json {",  # malformed -> dropped + continue (496, 499-500)
            json.dumps({"type": "metrics", "timestamp": 1.0, "data": {}}),  # non-response (503->492)
            json.dumps({"type": "command_response", "timestamp": 1.0, "data": {"command_id": "ghost"}}),  # unknown cid (505->492)
            json.dumps({"type": "command_response", "timestamp": 1.0, "data": {"command_id": "cid-match", "status": "success"}}),  # routed (506)
        ]
        state = {"i": 0}

        async def fake_recv():
            i = state["i"]
            state["i"] += 1
            if i < len(frames):
                return frames[i]
            # Exhausted: clear the socket so the while-loop exits normally
            # (ws_client.py:492 -> exit) after this benign non-response frame.
            ctrl._ws = None
            return json.dumps({"type": "noop", "timestamp": 1.0, "data": {}})

        mock_ws.recv = fake_recv
        await ctrl._recv_loop()

        assert matched.done()
        assert matched.result()["data"]["command_id"] == "cid-match"

    @pytest.mark.asyncio
    async def test_recv_loop_fails_pending_futures_on_disconnect(self):
        """On a mid-flight disconnect, still-pending futures fail with a typed
        connection error while already-resolved ones are left alone
        (ws_client.py:507-513, incl. the 512->511 already-done skip)."""
        ctrl = CascorControlStream()
        mock_ws = AsyncMock()
        ctrl._ws = mock_ws

        loop = asyncio.get_running_loop()
        already_done = loop.create_future()
        already_done.set_result({"pre": "resolved"})
        still_pending = loop.create_future()
        ctrl._pending["done-cid"] = already_done
        ctrl._pending["pending-cid"] = still_pending

        async def fake_recv():
            raise websockets.exceptions.ConnectionClosedError(None, None)

        mock_ws.recv = fake_recv
        await ctrl._recv_loop()

        assert still_pending.done()
        with pytest.raises(JuniperCascorConnectionError):
            still_pending.result()
        # The already-resolved future was untouched (512->511 skip branch).
        assert already_done.result() == {"pre": "resolved"}
