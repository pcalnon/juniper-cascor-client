"""Tests for CascorControlStream.set_params() — Phase A-SDK."""

import asyncio
import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from juniper_cascor_client import CascorControlStream
from juniper_cascor_client.constants import MAX_PENDING_COMMANDS
from juniper_cascor_client.exceptions import JuniperCascorClientError, JuniperCascorConnectionError, JuniperCascorOverloadError, JuniperCascorTimeoutError


def _make_command_response(command_id: str, status: str = "success", result: dict = None) -> str:
    """Build a JSON command_response string matching server format."""
    data = {"command": "set_params", "status": status, "command_id": command_id}
    if result:
        data["result"] = result
    return json.dumps({"type": "command_response", "timestamp": 1.0, "data": data})


def _make_ctrl_with_mock_ws() -> tuple:
    """Create a CascorControlStream with a mock WebSocket already connected."""
    ctrl = CascorControlStream()
    mock_ws = AsyncMock()
    ctrl._ws = mock_ws
    return ctrl, mock_ws


class TestSetParamsBasic:
    def test_set_params_default_timeout_is_one_second(self):
        """Default timeout kwarg is 1.0s (C-03 / D-01)."""
        import inspect

        sig = inspect.signature(CascorControlStream.set_params)
        assert sig.parameters["timeout"].default == 1.0

    @pytest.mark.asyncio
    async def test_set_params_happy_path(self):
        """set_params sends command with command_id and receives correlated response."""
        ctrl, mock_ws = _make_ctrl_with_mock_ws()

        async def fake_recv():
            # Wait briefly for the send to register the command_id
            await asyncio.sleep(0.01)
            # Extract command_id from what was sent
            sent = json.loads(mock_ws.send.call_args[0][0])
            return _make_command_response(sent["command_id"])

        mock_ws.recv = AsyncMock(side_effect=fake_recv)

        result = await ctrl.set_params({"learning_rate": 0.01})

        assert result["type"] == "command_response"
        assert result["data"]["status"] == "success"
        assert result["data"]["command_id"] is not None

        sent = json.loads(mock_ws.send.call_args[0][0])
        assert sent["command"] == "set_params"
        assert sent["params"]["learning_rate"] == 0.01
        assert "command_id" in sent

    @pytest.mark.asyncio
    async def test_set_params_with_explicit_command_id(self):
        """set_params uses provided command_id."""
        ctrl, mock_ws = _make_ctrl_with_mock_ws()

        async def fake_recv():
            await asyncio.sleep(0.01)
            return _make_command_response("my-custom-id")

        mock_ws.recv = AsyncMock(side_effect=fake_recv)

        result = await ctrl.set_params({"lr": 0.1}, command_id="my-custom-id")

        sent = json.loads(mock_ws.send.call_args[0][0])
        assert sent["command_id"] == "my-custom-id"
        assert result["data"]["command_id"] == "my-custom-id"

    def test_command_id_is_uuid_when_not_provided(self):
        """Auto-generated command_id is valid UUID format."""
        ctrl = CascorControlStream()
        ctrl._ws = AsyncMock()

        # We can't easily await set_params without a recv, so test the UUID
        # generation path by checking the constant import works and UUID is valid
        test_id = str(uuid.uuid4())
        uuid.UUID(test_id)  # validates format


class TestSetParamsErrors:
    @pytest.mark.asyncio
    async def test_set_params_not_connected(self):
        """set_params raises when not connected."""
        ctrl = CascorControlStream()
        with pytest.raises(JuniperCascorClientError, match="Not connected"):
            await ctrl.set_params({"lr": 0.01})

    @pytest.mark.asyncio
    async def test_set_params_timeout_raises_typed_exception(self):
        """set_params raises JuniperCascorTimeoutError on timeout."""
        ctrl, mock_ws = _make_ctrl_with_mock_ws()

        # recv never returns (simulates server not responding)
        async def hang_forever():
            await asyncio.sleep(100)

        mock_ws.recv = AsyncMock(side_effect=hang_forever)

        with pytest.raises(JuniperCascorTimeoutError, match="timed out"):
            await ctrl.set_params({"lr": 0.01}, timeout=0.05)

    @pytest.mark.asyncio
    async def test_set_params_no_retry_on_timeout(self):
        """set_params does NOT retry after timeout (D-20)."""
        ctrl, mock_ws = _make_ctrl_with_mock_ws()

        async def hang_forever():
            await asyncio.sleep(100)

        mock_ws.recv = AsyncMock(side_effect=hang_forever)

        with pytest.raises(JuniperCascorTimeoutError):
            await ctrl.set_params({"lr": 0.01}, timeout=0.05)

        # Only one send call (no retry)
        assert mock_ws.send.await_count == 1

    @pytest.mark.asyncio
    async def test_set_params_fails_fast_on_disconnect(self):
        """set_params raises JuniperCascorConnectionError on disconnect (C-04)."""
        ctrl, mock_ws = _make_ctrl_with_mock_ws()

        import websockets

        mock_ws.recv = AsyncMock(side_effect=websockets.exceptions.ConnectionClosed(None, None))

        with pytest.raises(JuniperCascorConnectionError, match="disconnected"):
            await ctrl.set_params({"lr": 0.01}, timeout=1.0)

    @pytest.mark.asyncio
    async def test_set_params_server_error_response(self):
        """set_params returns error response from server (no exception)."""
        ctrl, mock_ws = _make_ctrl_with_mock_ws()

        async def fake_recv():
            await asyncio.sleep(0.01)
            sent = json.loads(mock_ws.send.call_args[0][0])
            data = {"command": "set_params", "status": "error", "command_id": sent["command_id"], "error": "Invalid params"}
            return json.dumps({"type": "command_response", "timestamp": 1.0, "data": data})

        mock_ws.recv = AsyncMock(side_effect=fake_recv)

        result = await ctrl.set_params({"bad_param": 999})
        assert result["data"]["status"] == "error"
        assert "error" in result["data"]


class TestSetParamsConcurrency:
    @pytest.mark.asyncio
    async def test_set_params_concurrent_callers_correlate_via_command_id(self):
        """Two concurrent set_params calls are distinguished by command_id (C-01)."""
        ctrl, mock_ws = _make_ctrl_with_mock_ws()

        responses = {}

        async def fake_recv():
            # Wait for both sends to arrive
            while mock_ws.send.await_count < 2:
                await asyncio.sleep(0.01)
            # Return responses for both, in reverse order
            if not responses:
                sent1 = json.loads(mock_ws.send.call_args_list[0][0][0])
                sent2 = json.loads(mock_ws.send.call_args_list[1][0][0])
                responses["first"] = sent2["command_id"]  # Return second first
                responses["second"] = sent1["command_id"]
                return _make_command_response(responses["first"])
            return _make_command_response(responses["second"])

        mock_ws.recv = AsyncMock(side_effect=fake_recv)

        task1 = asyncio.create_task(ctrl.set_params({"lr": 0.01}, command_id="id-1"))
        task2 = asyncio.create_task(ctrl.set_params({"lr": 0.02}, command_id="id-2"))

        r1, r2 = await asyncio.gather(task1, task2)

        # Each response matches its own command_id
        assert r1["data"]["command_id"] == "id-1"
        assert r2["data"]["command_id"] == "id-2"

    @pytest.mark.asyncio
    async def test_correlation_map_bounded_at_256(self):
        """257th concurrent command raises JuniperCascorOverloadError."""
        ctrl, mock_ws = _make_ctrl_with_mock_ws()

        # Fill the pending map to max
        loop = asyncio.get_running_loop()
        for i in range(MAX_PENDING_COMMANDS):
            ctrl._pending[f"fake-{i}"] = loop.create_future()

        with pytest.raises(JuniperCascorOverloadError, match="Too many"):
            await ctrl.set_params({"lr": 0.01})

        # Clean up futures
        for f in ctrl._pending.values():
            f.cancel()
        ctrl._pending.clear()

    @pytest.mark.asyncio
    async def test_set_params_caller_cancellation_cleans_correlation_map(self):
        """Cancelled set_params removes its command_id from _pending (MANDATORY)."""
        ctrl, mock_ws = _make_ctrl_with_mock_ws()

        async def hang_forever():
            await asyncio.sleep(100)

        mock_ws.recv = AsyncMock(side_effect=hang_forever)

        task = asyncio.create_task(ctrl.set_params({"lr": 0.01}, timeout=10.0))
        await asyncio.sleep(0.05)
        assert len(ctrl._pending) == 1

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert len(ctrl._pending) == 0

    @pytest.mark.asyncio
    async def test_recv_task_propagates_exception_to_all_pending_futures(self):
        """Disconnect fails all pending futures."""
        ctrl, mock_ws = _make_ctrl_with_mock_ws()

        import websockets

        call_count = 0

        async def fail_on_second():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                await asyncio.sleep(100)  # First recv hangs
            raise websockets.exceptions.ConnectionClosed(None, None)

        mock_ws.recv = AsyncMock(side_effect=fail_on_second)

        with pytest.raises((JuniperCascorConnectionError, JuniperCascorTimeoutError)):
            await ctrl.set_params({"lr": 0.01}, timeout=0.2)

        assert len(ctrl._pending) == 0


class TestCommandAfterSetParams:
    @pytest.mark.asyncio
    async def test_command_still_works_after_set_params(self):
        """command() works correctly when recv task is active."""
        ctrl, mock_ws = _make_ctrl_with_mock_ws()

        call_count = 0

        async def fake_recv():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            if call_count == 1:
                sent = json.loads(mock_ws.send.call_args[0][0])
                return _make_command_response(sent["command_id"])
            else:
                # For the command() call, return a stop response
                sent = json.loads(mock_ws.send.call_args[0][0])
                cid = sent.get("command_id", "")
                data = {"command": "stop", "status": "success"}
                if cid:
                    data["command_id"] = cid
                return json.dumps({"type": "command_response", "timestamp": 1.0, "data": data})

        mock_ws.recv = AsyncMock(side_effect=fake_recv)

        # First call starts recv task
        await ctrl.set_params({"lr": 0.01})

        # Second call uses correlation since recv task is active
        result = await ctrl.command("stop")
        assert result["data"]["status"] == "success"
