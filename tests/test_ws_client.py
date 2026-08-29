"""Tests for CascorTrainingStream and CascorControlStream WebSocket clients."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from juniper_cascor_client import CascorControlStream, CascorTrainingStream
from juniper_cascor_client.exceptions import JuniperCascorClientError, JuniperCascorConnectionError


class TestCascorTrainingStream:
    def test_init_defaults(self):
        stream = CascorTrainingStream()
        assert stream.base_url == "ws://localhost:8200"
        assert stream.api_key is None
        assert stream._ws is None

    def test_init_custom(self):
        stream = CascorTrainingStream("ws://example.com:9000", api_key="key123")
        assert stream.base_url == "ws://example.com:9000"
        assert stream.api_key == "key123"

    def test_trailing_slash_stripped(self):
        stream = CascorTrainingStream("ws://example.com:9000/")
        assert stream.base_url == "ws://example.com:9000"

    def test_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("JUNIPER_CASCOR_API_KEY", "env-ws-key")
        stream = CascorTrainingStream()
        assert stream.api_key == "env-ws-key"

    def test_explicit_api_key_overrides_env(self, monkeypatch):
        monkeypatch.setenv("JUNIPER_CASCOR_API_KEY", "env-ws-key")
        stream = CascorTrainingStream(api_key="explicit-key")
        assert stream.api_key == "explicit-key"

    @pytest.mark.asyncio
    async def test_connect_calls_websockets(self):
        mock_ws = AsyncMock()
        with patch("juniper_cascor_client.ws_client.websockets.connect", new_callable=AsyncMock, return_value=mock_ws):
            stream = CascorTrainingStream("ws://localhost:8200")
            await stream.connect()
            assert stream._ws is mock_ws
            await stream.disconnect()

    @pytest.mark.asyncio
    async def test_connect_omits_origin_when_unset(self):
        """0.5.0 behaviour: with no ``origin=`` and no ``JUNIPER_CASCOR_WS_ORIGIN``,
        ``websockets.connect`` is called without an ``origin`` kwarg so the
        pre-0.5.0 machine-to-machine default (no Origin header sent) is preserved.
        """
        mock_ws = AsyncMock()
        with patch("juniper_cascor_client.ws_client.websockets.connect", new_callable=AsyncMock, return_value=mock_ws) as mock_connect:
            stream = CascorTrainingStream("ws://localhost:8200")
            await stream.connect()
            kwargs = mock_connect.call_args.kwargs
            assert "origin" not in kwargs, f"origin must not be forwarded when unset; got kwargs={kwargs}"

    @pytest.mark.asyncio
    async def test_connect_forwards_origin_when_set(self):
        """0.5.0 behaviour: explicit ``origin=...`` is forwarded to
        ``websockets.connect`` so the cascor server's per-WS Origin policy
        (e.g. ``/ws/training`` if a future server-side policy adds one)
        receives the configured Origin verbatim.
        """
        mock_ws = AsyncMock()
        with patch("juniper_cascor_client.ws_client.websockets.connect", new_callable=AsyncMock, return_value=mock_ws) as mock_connect:
            stream = CascorTrainingStream("ws://localhost:8200", origin="http://juniper-canopy:8050")
            await stream.connect()
            kwargs = mock_connect.call_args.kwargs
            assert kwargs.get("origin") == "http://juniper-canopy:8050"

    @pytest.mark.asyncio
    async def test_connect_picks_up_ws_origin_env_var(self, monkeypatch):
        """0.5.0 behaviour: when ``origin=`` is not supplied, ``JUNIPER_CASCOR_WS_ORIGIN``
        env-var fallback supplies the Origin header — symmetric with the existing
        ``JUNIPER_CASCOR_API_KEY`` env-var fallback for ``api_key``.
        """
        monkeypatch.setenv("JUNIPER_CASCOR_WS_ORIGIN", "http://env-origin:8050")
        mock_ws = AsyncMock()
        with patch("juniper_cascor_client.ws_client.websockets.connect", new_callable=AsyncMock, return_value=mock_ws) as mock_connect:
            stream = CascorTrainingStream("ws://localhost:8200")
            await stream.connect()
            assert mock_connect.call_args.kwargs.get("origin") == "http://env-origin:8050"

    @pytest.mark.asyncio
    async def test_disconnect(self):
        mock_ws = AsyncMock()
        stream = CascorTrainingStream()
        stream._ws = mock_ws
        await stream.disconnect()
        mock_ws.close.assert_awaited_once()
        assert stream._ws is None

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self):
        stream = CascorTrainingStream()
        await stream.disconnect()  # Should not raise

    @pytest.mark.asyncio
    async def test_stream_not_connected(self):
        stream = CascorTrainingStream()
        with pytest.raises(JuniperCascorClientError, match="Not connected"):
            async for _ in stream.stream():
                pass

    @pytest.mark.asyncio
    async def test_stream_yields_messages(self):
        messages = [
            json.dumps({"type": "metrics", "timestamp": 1.0, "data": {"epoch": 1}}),
            json.dumps({"type": "state", "timestamp": 2.0, "data": {"state": "running"}}),
        ]

        async def async_iter():
            for m in messages:
                yield m

        mock_ws = AsyncMock()
        mock_ws.__aiter__ = lambda self: async_iter()
        stream = CascorTrainingStream()
        stream._ws = mock_ws

        received = []
        async for msg in stream.stream():
            received.append(msg)

        assert len(received) == 2
        assert received[0]["type"] == "metrics"
        assert received[1]["type"] == "state"

    @pytest.mark.asyncio
    async def test_send_command(self):
        mock_ws = AsyncMock()
        stream = CascorTrainingStream()
        stream._ws = mock_ws

        await stream.send_command("start", {"epochs": 100})
        mock_ws.send.assert_awaited_once()
        sent = json.loads(mock_ws.send.call_args[0][0])
        # XREPO-07/08, CC-06: every client→server WS message carries the
        # canonical "type": "command" envelope so the server can dispatch
        # uniformly across send_command(), command(), and set_params().
        assert sent["type"] == "command"
        assert sent["command"] == "start"
        assert sent["params"]["epochs"] == 100

    @pytest.mark.asyncio
    async def test_send_command_without_params_includes_type(self):
        """XREPO-07/08: send_command emits "type": "command" even when no params are supplied."""
        mock_ws = AsyncMock()
        stream = CascorTrainingStream()
        stream._ws = mock_ws

        await stream.send_command("stop")
        sent = json.loads(mock_ws.send.call_args[0][0])
        assert sent == {"type": "command", "command": "stop"}

    @pytest.mark.asyncio
    async def test_send_command_not_connected(self):
        stream = CascorTrainingStream()
        with pytest.raises(JuniperCascorClientError, match="Not connected"):
            await stream.send_command("stop")

    def test_callback_registration(self):
        stream = CascorTrainingStream()
        cb = MagicMock()
        stream.on_metrics(cb)
        assert "metrics" in stream._callbacks
        assert cb in stream._callbacks["metrics"]

    def test_callback_dispatch(self):
        stream = CascorTrainingStream()
        cb = MagicMock()
        stream.on_metrics(cb)
        stream._dispatch({"type": "metrics", "data": {"epoch": 5}})
        cb.assert_called_once_with({"epoch": 5})

    def test_callback_dispatch_no_match(self):
        stream = CascorTrainingStream()
        cb = MagicMock()
        stream.on_metrics(cb)
        stream._dispatch({"type": "state", "data": {}})
        cb.assert_not_called()

    def test_multiple_callbacks(self):
        stream = CascorTrainingStream()
        cb1 = MagicMock()
        cb2 = MagicMock()
        stream.on_metrics(cb1)
        stream.on_metrics(cb2)
        stream._dispatch({"type": "metrics", "data": {"epoch": 1}})
        cb1.assert_called_once()
        cb2.assert_called_once()

    def test_all_callback_types(self):
        stream = CascorTrainingStream()
        callbacks = {}
        for msg_type in ["metrics", "state", "topology", "cascade_add", "event"]:
            cb = MagicMock()
            callbacks[msg_type] = cb
            getattr(stream, f"on_{msg_type}")(cb)

        for msg_type, cb in callbacks.items():
            stream._dispatch({"type": msg_type, "data": {"test": True}})
            cb.assert_called_once_with({"test": True})

    def test_dispatch_isolates_faulty_callback(self, caplog):
        """APD-CCLIENT-006: a message callback that raises must not prevent
        subsequent callbacks for the same message from running — the guard
        ``_dispatch_disconnect`` always had, now on ``_dispatch`` too."""
        import logging as _logging

        stream = CascorTrainingStream()
        good_cb = MagicMock()

        def bad_cb(data):
            raise RuntimeError("boom")

        stream.on_metrics(bad_cb)
        stream.on_metrics(good_cb)

        caplog.set_level(_logging.ERROR, logger="juniper_cascor_client.ws_client")

        stream._dispatch({"type": "metrics", "data": {"epoch": 3}})

        good_cb.assert_called_once_with({"epoch": 3})
        error_records = [r for r in caplog.records if r.levelno == _logging.ERROR]
        assert any("metrics callback raised" in r.getMessage() for r in error_records), f"Expected ERROR log about callback fault; got: {[r.getMessage() for r in caplog.records]}"

    @pytest.mark.asyncio
    async def test_stream_survives_faulty_message_callback(self):
        """APD-CCLIENT-006: ``_dispatch`` runs before ``stream()``'s yield, so an
        unguarded listener fault tore down the whole training stream. A raising
        listener must cost only its own callback: every message still reaches the
        consumer, and later messages still reach the surviving listeners."""
        import websockets as _websockets

        async def async_iter_two_then_close():
            yield json.dumps({"type": "metrics", "timestamp": 1.0, "data": {"epoch": 1}})
            yield json.dumps({"type": "metrics", "timestamp": 2.0, "data": {"epoch": 2}})
            raise _websockets.exceptions.ConnectionClosedOK(None, None)

        mock_ws = AsyncMock()
        mock_ws.__aiter__ = lambda self: async_iter_two_then_close()
        stream = CascorTrainingStream()
        stream._ws = mock_ws

        good_seen = []

        def bad_cb(data):
            raise RuntimeError("boom")

        stream.on_metrics(bad_cb)
        stream.on_metrics(good_seen.append)

        received = []
        async for msg in stream.stream():
            received.append(msg)

        assert [m["data"]["epoch"] for m in received] == [1, 2]
        assert [d["epoch"] for d in good_seen] == [1, 2]

    # ─── ERR-14: on_disconnect callbacks + WARNING log on drop ───────────

    @pytest.mark.asyncio
    async def test_stream_logs_warning_on_disconnect(self, caplog):
        """ERR-14: stream() must log at WARNING when the underlying socket
        raises ``ConnectionClosed``, instead of silently swallowing it."""
        import logging as _logging

        import websockets as _websockets

        async def async_iter_then_close():
            yield json.dumps({"type": "metrics", "timestamp": 1.0, "data": {"epoch": 1}})
            raise _websockets.exceptions.ConnectionClosedOK(None, None)

        mock_ws = AsyncMock()
        mock_ws.__aiter__ = lambda self: async_iter_then_close()
        stream = CascorTrainingStream()
        stream._ws = mock_ws

        caplog.set_level(_logging.WARNING, logger="juniper_cascor_client.ws_client")

        received = []
        async for msg in stream.stream():
            received.append(msg)

        assert len(received) == 1
        # The disconnect must have produced a WARNING-level record naming
        # the stream class, not been silently swallowed.
        warning_records = [r for r in caplog.records if r.levelno == _logging.WARNING]
        assert any("CascorTrainingStream: WebSocket disconnected" in r.getMessage() for r in warning_records), f"Expected a WARNING about WebSocket disconnect; got: {[r.getMessage() for r in caplog.records]}"

    @pytest.mark.asyncio
    async def test_stream_invokes_on_disconnect_callback_with_exc(self):
        """ERR-14: on_disconnect callbacks fire with the ``ConnectionClosed``
        instance so callers can read ``code``/``reason`` for reconnection logic."""
        import websockets as _websockets

        close_exc = _websockets.exceptions.ConnectionClosedError(None, None)

        async def async_iter_then_close():
            yield json.dumps({"type": "metrics", "timestamp": 1.0, "data": {"epoch": 1}})
            raise close_exc

        mock_ws = AsyncMock()
        mock_ws.__aiter__ = lambda self: async_iter_then_close()
        stream = CascorTrainingStream()
        stream._ws = mock_ws

        received_disconnects = []
        stream.on_disconnect(lambda exc: received_disconnects.append(exc))

        async for _ in stream.stream():
            pass

        assert len(received_disconnects) == 1
        assert received_disconnects[0] is close_exc

    @pytest.mark.asyncio
    async def test_stream_invokes_multiple_on_disconnect_callbacks(self):
        """ERR-14: all registered ``on_disconnect`` callbacks fire on a single drop."""
        import websockets as _websockets

        async def async_iter_then_close():
            if False:  # pragma: no cover - empty stream that closes immediately
                yield ""
            raise _websockets.exceptions.ConnectionClosedOK(None, None)

        mock_ws = AsyncMock()
        mock_ws.__aiter__ = lambda self: async_iter_then_close()
        stream = CascorTrainingStream()
        stream._ws = mock_ws

        cb1 = MagicMock()
        cb2 = MagicMock()
        stream.on_disconnect(cb1)
        stream.on_disconnect(cb2)

        async for _ in stream.stream():
            pass

        cb1.assert_called_once()
        cb2.assert_called_once()

    @pytest.mark.asyncio
    async def test_stream_isolates_faulty_on_disconnect_callback(self, caplog):
        """ERR-14: a callback that raises must not prevent subsequent
        callbacks from running and must not leak out of ``stream()``."""
        import logging as _logging

        import websockets as _websockets

        async def async_iter_then_close():
            if False:  # pragma: no cover
                yield ""
            raise _websockets.exceptions.ConnectionClosedOK(None, None)

        mock_ws = AsyncMock()
        mock_ws.__aiter__ = lambda self: async_iter_then_close()
        stream = CascorTrainingStream()
        stream._ws = mock_ws

        good_cb = MagicMock()

        def bad_cb(exc):
            raise RuntimeError("boom")

        stream.on_disconnect(bad_cb)
        stream.on_disconnect(good_cb)

        caplog.set_level(_logging.ERROR, logger="juniper_cascor_client.ws_client")

        # stream() must complete cleanly despite the faulty callback.
        async for _ in stream.stream():
            pass

        good_cb.assert_called_once()
        error_records = [r for r in caplog.records if r.levelno == _logging.ERROR]
        assert any("on_disconnect callback raised" in r.getMessage() for r in error_records), f"Expected ERROR log about callback fault; got: {[r.getMessage() for r in caplog.records]}"

    def test_on_disconnect_register_only(self):
        """ERR-14: ``on_disconnect`` registration is idempotent in the sense
        that multiple registrations stack and the in-memory list grows."""
        stream = CascorTrainingStream()
        assert stream._disconnect_callbacks == []
        cb1 = MagicMock()
        cb2 = MagicMock()
        stream.on_disconnect(cb1)
        stream.on_disconnect(cb2)
        assert stream._disconnect_callbacks == [cb1, cb2]


class TestCascorControlStream:
    def test_init_defaults(self):
        ctrl = CascorControlStream()
        assert ctrl.base_url == "ws://localhost:8200"

    def test_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("JUNIPER_CASCOR_API_KEY", "env-ctrl-key")
        ctrl = CascorControlStream()
        assert ctrl.api_key == "env-ctrl-key"

    def test_explicit_api_key_overrides_env(self, monkeypatch):
        monkeypatch.setenv("JUNIPER_CASCOR_API_KEY", "env-ctrl-key")
        ctrl = CascorControlStream(api_key="explicit-key")
        assert ctrl.api_key == "explicit-key"

    @pytest.mark.asyncio
    async def test_connect(self):
        mock_ws = AsyncMock()
        mock_ws.recv = AsyncMock(return_value=json.dumps({"type": "connection_established"}))
        with patch("juniper_cascor_client.ws_client.websockets.connect", new_callable=AsyncMock, return_value=mock_ws):
            ctrl = CascorControlStream()
            await ctrl.connect()
            assert ctrl._ws is mock_ws
            await ctrl.disconnect()

    @pytest.mark.asyncio
    async def test_connect_omits_origin_when_unset(self):
        """0.5.0 behaviour: ``CascorControlStream`` without ``origin=`` calls
        ``websockets.connect`` without an ``origin`` kwarg.  Preserves the
        pre-0.5.0 behaviour for direct-Python and CLI callers.
        """
        mock_ws = AsyncMock()
        mock_ws.recv = AsyncMock(return_value=json.dumps({"type": "connection_established"}))
        with patch("juniper_cascor_client.ws_client.websockets.connect", new_callable=AsyncMock, return_value=mock_ws) as mock_connect:
            ctrl = CascorControlStream()
            await ctrl.connect()
            assert "origin" not in mock_connect.call_args.kwargs

    @pytest.mark.asyncio
    async def test_connect_forwards_origin_when_set(self):
        """0.5.0 behaviour: ``CascorControlStream(origin=...)`` forwards
        the Origin to ``websockets.connect``. This is the canopy-side
        unblock for the juniper-cascor#129 fail-closed Origin policy.
        """
        mock_ws = AsyncMock()
        mock_ws.recv = AsyncMock(return_value=json.dumps({"type": "connection_established"}))
        with patch("juniper_cascor_client.ws_client.websockets.connect", new_callable=AsyncMock, return_value=mock_ws) as mock_connect:
            ctrl = CascorControlStream(origin="http://juniper-canopy:8050")
            await ctrl.connect()
            assert mock_connect.call_args.kwargs.get("origin") == "http://juniper-canopy:8050"

    @pytest.mark.asyncio
    async def test_command(self):
        mock_ws = AsyncMock()
        mock_ws.recv = AsyncMock(return_value=json.dumps({"type": "command_response", "data": {"command": "stop", "status": "success"}}))
        ctrl = CascorControlStream()
        ctrl._ws = mock_ws

        result = await ctrl.command("stop")
        assert result["data"]["status"] == "success"
        mock_ws.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_command_with_params(self):
        mock_ws = AsyncMock()
        mock_ws.recv = AsyncMock(return_value=json.dumps({"type": "command_response", "data": {"status": "success"}}))
        ctrl = CascorControlStream()
        ctrl._ws = mock_ws

        await ctrl.command("start", {"epochs": 100})
        sent = json.loads(mock_ws.send.call_args[0][0])
        # XREPO-07/08, CC-06: command() now emits the canonical "type":
        # "command" envelope on both correlated and direct paths.
        assert sent["type"] == "command"
        assert sent["command"] == "start"
        assert sent["params"]["epochs"] == 100

    @pytest.mark.asyncio
    async def test_command_direct_path_emits_type_envelope(self):
        """XREPO-07/08: direct (non-correlated) command() path includes "type": "command"."""
        mock_ws = AsyncMock()
        mock_ws.recv = AsyncMock(return_value=json.dumps({"type": "command_response", "data": {"status": "success"}}))
        ctrl = CascorControlStream()
        ctrl._ws = mock_ws
        # No background recv task → direct path
        assert ctrl._recv_task is None

        await ctrl.command("stop")
        sent = json.loads(mock_ws.send.call_args[0][0])
        assert sent == {"type": "command", "command": "stop"}

    @pytest.mark.asyncio
    async def test_command_correlated_path_emits_type_envelope(self):
        """XREPO-07/08: correlated command() path includes "type": "command" alongside command_id."""
        ctrl = CascorControlStream()
        mock_ws = AsyncMock()
        ctrl._ws = mock_ws

        # Manufacture a recv task so command() takes the correlated path
        async def fake_recv():
            import asyncio as _asyncio

            await _asyncio.sleep(0.01)
            sent = json.loads(mock_ws.send.call_args[0][0])
            cid = sent["command_id"]
            return json.dumps({"type": "command_response", "data": {"command": "stop", "status": "success", "command_id": cid}})

        mock_ws.recv = AsyncMock(side_effect=fake_recv)
        # Start the recv loop manually so the next command() call routes through correlation
        await ctrl._ensure_recv_task()
        try:
            await ctrl.command("stop")
        finally:
            # Tear down the recv task to avoid leaking
            if ctrl._recv_task and not ctrl._recv_task.done():
                ctrl._recv_task.cancel()

        sent = json.loads(mock_ws.send.call_args[0][0])
        assert sent["type"] == "command"
        assert sent["command"] == "stop"
        assert "command_id" in sent

    @pytest.mark.asyncio
    async def test_command_not_connected(self):
        ctrl = CascorControlStream()
        with pytest.raises(JuniperCascorClientError, match="Not connected"):
            await ctrl.command("stop")

    @pytest.mark.asyncio
    async def test_context_manager(self):
        mock_ws = AsyncMock()
        mock_ws.recv = AsyncMock(return_value=json.dumps({"type": "connection_established"}))
        with patch("juniper_cascor_client.ws_client.websockets.connect", new_callable=AsyncMock, return_value=mock_ws):
            async with CascorControlStream() as ctrl:
                assert ctrl._ws is not None


# ---------------------------------------------------------------------------
# CC-09..12 (v7 roadmap §15) — JSON decode error handling on inbound WS frames
# ---------------------------------------------------------------------------


class TestJsonFrameDecodeErrors:
    """Pins how each ``json.loads`` call site behaves when the peer sends a
    malformed frame. Previously every call site was unguarded and a single
    bad frame would crash the iterator (training stream) or fail every
    pending future (control stream)."""

    def test_parse_json_frame_returns_dict_on_valid_input(self):
        from juniper_cascor_client.ws_client import _parse_json_frame

        msg = _parse_json_frame('{"type": "metrics", "data": {"epoch": 1}}', endpoint="training")
        assert msg == {"type": "metrics", "data": {"epoch": 1}}

    def test_parse_json_frame_raises_with_payload_preview_on_garbage(self):
        from juniper_cascor_client.ws_client import _parse_json_frame

        with pytest.raises(JuniperCascorClientError, match="Failed to decode WebSocket frame from 'training'"):
            _parse_json_frame("this is not json {", endpoint="training")

    def test_parse_json_frame_accepts_bytes(self):
        from juniper_cascor_client.ws_client import _parse_json_frame

        msg = _parse_json_frame(b'{"type": "state"}', endpoint="control")
        assert msg == {"type": "state"}

    @pytest.mark.asyncio
    async def test_stream_skips_malformed_frame_and_continues(self, caplog):
        """CC-09: a malformed frame in the training stream is logged at
        WARNING and the iterator yields the remaining valid frames. One
        bad frame must NOT kill the stream."""
        import logging

        messages = [
            json.dumps({"type": "metrics", "data": {"epoch": 1}}),
            "this is not json {",  # malformed — should be dropped
            json.dumps({"type": "state", "data": {"state": "running"}}),
        ]

        async def async_iter():
            for m in messages:
                yield m

        mock_ws = AsyncMock()
        mock_ws.__aiter__ = lambda self: async_iter()
        stream = CascorTrainingStream()
        stream._ws = mock_ws

        with caplog.at_level(logging.WARNING, logger="juniper_cascor_client.ws_client"):
            received = []
            async for msg in stream.stream():
                received.append(msg)

        # Only the two valid frames make it through.
        assert [m["type"] for m in received] == ["metrics", "state"]
        # The bad frame surfaced as a warning log.
        assert any("malformed frame" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_connect_raises_client_error_on_malformed_connection_established(self):
        """CC-10: the connection_established handshake is one-shot. A
        malformed frame here is a control-protocol violation, not a
        recoverable hiccup — propagate as JuniperCascorClientError so the
        connect() call fails cleanly."""
        mock_ws = AsyncMock()
        mock_ws.recv = AsyncMock(return_value="this is not json {")
        with patch("juniper_cascor_client.ws_client.websockets.connect", new_callable=AsyncMock, return_value=mock_ws):
            ctrl = CascorControlStream()
            with pytest.raises(JuniperCascorClientError, match="Failed to decode WebSocket frame from 'control'"):
                await ctrl.connect()

    @pytest.mark.asyncio
    async def test_command_raises_client_error_on_malformed_response(self):
        """CC-11: a malformed direct-path command response is a typed
        error, not a raw JSONDecodeError leaked from the stdlib."""
        mock_ws = AsyncMock()
        mock_ws.recv = AsyncMock(return_value="this is not json {")
        ctrl = CascorControlStream()
        ctrl._ws = mock_ws

        with pytest.raises(JuniperCascorClientError, match="Failed to decode WebSocket frame from 'control'"):
            await ctrl.command("stop")
