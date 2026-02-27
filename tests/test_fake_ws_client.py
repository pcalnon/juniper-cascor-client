"""Comprehensive tests for FakeCascorTrainingStream (Task 6.6).

Tests cover all public methods, callback registration and dispatch,
async iteration, message injection, context manager, and edge cases
for the in-memory fake WebSocket training stream.

Project: Juniper
Sub-Project: juniper-cascor-client
Application: FakeCascorTrainingStream Tests
Author: Paul Calnon
Version: 0.1.0
License: MIT License
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from juniper_cascor_client.exceptions import JuniperCascorClientError
from juniper_cascor_client.testing import FakeCascorTrainingStream

# Small nonzero delay to avoid asyncio.wait_for(timeout=0.0) issues on Python 3.13.
# The stream terminates via TimeoutError when the queue is empty and timeout expires.
_TEST_DELAY = 0.01


async def _collect_stream(stream):
    """Consume all messages from a connected stream and return them as a list.

    Schedules disconnect() after a short delay so the stream terminates
    cleanly via the None sentinel rather than relying solely on timeout.
    """
    received = []
    async for msg in stream.stream():
        received.append(msg)
    return received


# ─── Connection Tests ────────────────────────────────────────────────────────


class TestConnection:
    """Tests for connect, disconnect, and connection state."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_connect_and_disconnect(self):
        """Connecting and disconnecting updates the internal connected state."""
        stream = FakeCascorTrainingStream()
        assert stream._connected is False

        await stream.connect()
        assert stream._connected is True

        await stream.disconnect()
        assert stream._connected is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_connect_loads_initial_messages(self):
        """Connecting loads pre-configured messages into the async queue."""
        messages = [
            {"type": "metrics", "data": {"epoch": 1}},
            {"type": "state", "data": {"state": "training"}},
        ]
        stream = FakeCascorTrainingStream(messages=messages)
        await stream.connect()

        # Queue should have 2 messages
        assert stream._queue.qsize() == 2
        await stream.disconnect()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_connect_idempotent_message_load(self):
        """Connecting multiple times does not re-load initial messages."""
        messages = [{"type": "metrics", "data": {"epoch": 1}}]
        stream = FakeCascorTrainingStream(messages=messages)

        await stream.connect()
        assert stream._queue.qsize() == 1

        # Disconnect and reconnect
        await stream.disconnect()
        # After disconnect, a None sentinel is added
        # Clear the queue for a clean check
        while not stream._queue.empty():
            stream._queue.get_nowait()

        stream._connected = False
        await stream.connect()
        # Should not reload since _initial_loaded is True
        assert stream._queue.qsize() == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self):
        """Disconnecting when not connected is a no-op."""
        stream = FakeCascorTrainingStream()
        await stream.disconnect()  # Should not raise
        assert stream._connected is False


# ─── Stream Tests ────────────────────────────────────────────────────────────


class TestStream:
    """Tests for the stream() async generator."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_stream_yields_messages(self):
        """stream() yields all pre-configured messages in order."""
        messages = [
            {"type": "metrics", "data": {"epoch": 1, "train_loss": 0.5}},
            {"type": "metrics", "data": {"epoch": 2, "train_loss": 0.3}},
            {"type": "state", "data": {"state": "complete"}},
        ]
        stream = FakeCascorTrainingStream(messages=messages, delay=_TEST_DELAY)
        await stream.connect()

        received = await _collect_stream(stream)

        assert len(received) == 3
        assert received[0]["data"]["epoch"] == 1
        assert received[1]["data"]["epoch"] == 2
        assert received[2]["data"]["state"] == "complete"
        await stream.disconnect()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_stream_dispatches_callbacks(self):
        """stream() dispatches each message to registered callbacks."""
        messages = [
            {"type": "metrics", "data": {"epoch": 1}},
            {"type": "state", "data": {"state": "training"}},
        ]
        stream = FakeCascorTrainingStream(messages=messages, delay=_TEST_DELAY)

        metrics_cb = MagicMock()
        state_cb = MagicMock()
        stream.on_metrics(metrics_cb)
        stream.on_state(state_cb)

        await stream.connect()
        await _collect_stream(stream)

        metrics_cb.assert_called_once_with({"epoch": 1})
        state_cb.assert_called_once_with({"state": "training"})
        await stream.disconnect()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_stream_without_connect_raises(self):
        """stream() raises JuniperCascorClientError when not connected."""
        stream = FakeCascorTrainingStream()
        with pytest.raises(JuniperCascorClientError, match="Not connected"):
            async for _ in stream.stream():
                pass

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_empty_messages_list(self):
        """stream() with no messages terminates cleanly."""
        stream = FakeCascorTrainingStream(messages=[], delay=_TEST_DELAY)
        await stream.connect()

        received = await _collect_stream(stream)

        assert len(received) == 0
        await stream.disconnect()


# ─── Listen Tests ────────────────────────────────────────────────────────────


class TestListen:
    """Tests for the listen() method that dispatches to callbacks."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_listen_dispatches_all(self):
        """listen() consumes all messages and dispatches to callbacks."""
        messages = [
            {"type": "metrics", "data": {"epoch": 1}},
            {"type": "metrics", "data": {"epoch": 2}},
            {"type": "state", "data": {"state": "complete"}},
        ]
        stream = FakeCascorTrainingStream(messages=messages, delay=_TEST_DELAY)

        call_log = []
        stream.on_metrics(lambda data: call_log.append(("metrics", data)))
        stream.on_state(lambda data: call_log.append(("state", data)))

        await stream.connect()
        await stream.listen()

        assert len(call_log) == 3
        assert call_log[0] == ("metrics", {"epoch": 1})
        assert call_log[1] == ("metrics", {"epoch": 2})
        assert call_log[2] == ("state", {"state": "complete"})
        await stream.disconnect()


# ─── Send Command Tests ──────────────────────────────────────────────────────


class TestSendCommand:
    """Tests for send_command recording."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_send_command_records_command(self):
        """send_command records the command in _sent_commands."""
        stream = FakeCascorTrainingStream()
        await stream.connect()

        await stream.send_command("start", {"epochs": 100})
        await stream.send_command("stop")

        assert len(stream._sent_commands) == 2
        assert stream._sent_commands[0] == {"command": "start", "params": {"epochs": 100}}
        assert stream._sent_commands[1] == {"command": "stop"}
        await stream.disconnect()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_send_command_without_connect_raises(self):
        """send_command raises JuniperCascorClientError when not connected."""
        stream = FakeCascorTrainingStream()
        with pytest.raises(JuniperCascorClientError, match="Not connected"):
            await stream.send_command("stop")


# ─── Message Injection Tests ────────────────────────────────────────────────


class TestInjectMessage:
    """Tests for the inject_message test helper."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_inject_message_before_connect(self):
        """Messages injected before connect are yielded during stream()."""
        stream = FakeCascorTrainingStream(delay=_TEST_DELAY)
        stream.inject_message({"type": "event", "data": {"action": "start"}})
        stream.inject_message({"type": "metrics", "data": {"epoch": 1}})

        await stream.connect()
        received = await _collect_stream(stream)

        assert len(received) == 2
        assert received[0]["type"] == "event"
        assert received[1]["type"] == "metrics"
        await stream.disconnect()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_inject_message_after_connect(self):
        """Messages injected after connect are yielded during active streaming."""
        stream = FakeCascorTrainingStream(delay=_TEST_DELAY)
        await stream.connect()

        # Inject a message while connected
        stream.inject_message({"type": "metrics", "data": {"epoch": 99}})

        received = await _collect_stream(stream)

        assert len(received) == 1
        assert received[0]["data"]["epoch"] == 99
        await stream.disconnect()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_inject_message_deep_copies(self):
        """inject_message deep-copies the message to prevent mutation."""
        original = {"type": "metrics", "data": {"epoch": 1, "values": [1, 2, 3]}}
        stream = FakeCascorTrainingStream(delay=_TEST_DELAY)
        stream.inject_message(original)

        # Mutate the original after injection
        original["data"]["epoch"] = 999
        original["data"]["values"].append(4)

        await stream.connect()
        received = await _collect_stream(stream)

        assert received[0]["data"]["epoch"] == 1
        assert received[0]["data"]["values"] == [1, 2, 3]
        await stream.disconnect()


# ─── Context Manager Tests ──────────────────────────────────────────────────


class TestContextManager:
    """Tests for async context manager usage."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """FakeCascorTrainingStream works as an async context manager."""
        messages = [{"type": "metrics", "data": {"epoch": 1}}]
        async with FakeCascorTrainingStream(messages=messages, delay=_TEST_DELAY) as stream:
            assert stream._connected is True
            received = await _collect_stream(stream)
            assert len(received) == 1

        # After exiting, stream is disconnected
        assert stream._connected is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_context_manager_auto_connect(self):
        """Entering the context manager calls connect() automatically."""
        async with FakeCascorTrainingStream() as stream:
            assert stream._connected is True


# ─── Async Iteration Tests ──────────────────────────────────────────────────


class TestAsyncIteration:
    """Tests for __aiter__ protocol support."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_async_iteration(self):
        """FakeCascorTrainingStream supports async for ... in stream syntax."""
        messages = [
            {"type": "metrics", "data": {"epoch": 1}},
            {"type": "metrics", "data": {"epoch": 2}},
        ]
        stream = FakeCascorTrainingStream(messages=messages, delay=_TEST_DELAY)
        await stream.connect()

        received = []
        async for msg in stream:
            received.append(msg)

        assert len(received) == 2
        assert received[0]["data"]["epoch"] == 1
        assert received[1]["data"]["epoch"] == 2
        await stream.disconnect()


# ─── Callback Registration Tests ────────────────────────────────────────────


class TestCallbacks:
    """Tests for individual callback registration methods."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_on_metrics_callback(self):
        """on_metrics callback receives metrics message data."""
        messages = [{"type": "metrics", "data": {"epoch": 5, "train_loss": 0.1}}]
        stream = FakeCascorTrainingStream(messages=messages, delay=_TEST_DELAY)

        received_data = []
        stream.on_metrics(lambda data: received_data.append(data))

        await stream.connect()
        await stream.listen()

        assert len(received_data) == 1
        assert received_data[0]["epoch"] == 5
        assert received_data[0]["train_loss"] == 0.1
        await stream.disconnect()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_on_state_callback(self):
        """on_state callback receives state change message data."""
        messages = [{"type": "state", "data": {"state": "complete", "epoch": 100}}]
        stream = FakeCascorTrainingStream(messages=messages, delay=_TEST_DELAY)

        received_data = []
        stream.on_state(lambda data: received_data.append(data))

        await stream.connect()
        await stream.listen()

        assert len(received_data) == 1
        assert received_data[0]["state"] == "complete"
        await stream.disconnect()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_on_topology_callback(self):
        """on_topology callback receives topology update data."""
        messages = [{"type": "topology", "data": {"hidden_units": 3, "nodes": 8}}]
        stream = FakeCascorTrainingStream(messages=messages, delay=_TEST_DELAY)

        received_data = []
        stream.on_topology(lambda data: received_data.append(data))

        await stream.connect()
        await stream.listen()

        assert len(received_data) == 1
        assert received_data[0]["hidden_units"] == 3
        await stream.disconnect()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_on_cascade_add_callback(self):
        """on_cascade_add callback receives cascade unit addition data."""
        messages = [{"type": "cascade_add", "data": {"unit_id": "hidden_2", "correlation": 0.85}}]
        stream = FakeCascorTrainingStream(messages=messages, delay=_TEST_DELAY)

        received_data = []
        stream.on_cascade_add(lambda data: received_data.append(data))

        await stream.connect()
        await stream.listen()

        assert len(received_data) == 1
        assert received_data[0]["unit_id"] == "hidden_2"
        assert received_data[0]["correlation"] == 0.85
        await stream.disconnect()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_on_event_callback(self):
        """on_event callback receives general event message data."""
        messages = [{"type": "event", "data": {"event": "patience_exceeded", "epoch": 50}}]
        stream = FakeCascorTrainingStream(messages=messages, delay=_TEST_DELAY)

        received_data = []
        stream.on_event(lambda data: received_data.append(data))

        await stream.connect()
        await stream.listen()

        assert len(received_data) == 1
        assert received_data[0]["event"] == "patience_exceeded"
        await stream.disconnect()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_multiple_callbacks_same_type(self):
        """Multiple callbacks for the same message type are all invoked."""
        messages = [{"type": "metrics", "data": {"epoch": 1}}]
        stream = FakeCascorTrainingStream(messages=messages, delay=_TEST_DELAY)

        cb1 = MagicMock()
        cb2 = MagicMock()
        stream.on_metrics(cb1)
        stream.on_metrics(cb2)

        await stream.connect()
        await stream.listen()

        cb1.assert_called_once_with({"epoch": 1})
        cb2.assert_called_once_with({"epoch": 1})
        await stream.disconnect()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_callback_not_called_for_other_types(self):
        """A metrics callback is not called for a state message."""
        messages = [{"type": "state", "data": {"state": "idle"}}]
        stream = FakeCascorTrainingStream(messages=messages, delay=_TEST_DELAY)

        metrics_cb = MagicMock()
        stream.on_metrics(metrics_cb)

        await stream.connect()
        await stream.listen()

        metrics_cb.assert_not_called()
        await stream.disconnect()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_all_callback_types_dispatched(self):
        """All five callback types dispatch correctly for their message types."""
        messages = [
            {"type": "metrics", "data": {"m": True}},
            {"type": "state", "data": {"s": True}},
            {"type": "topology", "data": {"t": True}},
            {"type": "cascade_add", "data": {"c": True}},
            {"type": "event", "data": {"e": True}},
        ]
        stream = FakeCascorTrainingStream(messages=messages, delay=_TEST_DELAY)

        callbacks = {}
        for msg_type in ["metrics", "state", "topology", "cascade_add", "event"]:
            cb = MagicMock()
            callbacks[msg_type] = cb
            getattr(stream, f"on_{msg_type}")(cb)

        await stream.connect()
        await stream.listen()

        for msg_type, cb in callbacks.items():
            cb.assert_called_once(), f"Callback for '{msg_type}' should have been called exactly once"
        await stream.disconnect()


# ─── Miscellaneous Tests ────────────────────────────────────────────────────


class TestMiscellaneous:
    """Additional tests for edge cases and constructor parameters."""

    @pytest.mark.unit
    def test_constructor_defaults(self):
        """Constructor sets sensible defaults."""
        stream = FakeCascorTrainingStream()
        assert stream.base_url == "ws://fake-cascor:8200"
        assert stream.api_key is None
        assert stream._delay == 0.1
        assert stream._connected is False

    @pytest.mark.unit
    def test_constructor_custom_params(self):
        """Constructor accepts custom base_url, api_key, and delay."""
        stream = FakeCascorTrainingStream(
            delay=0.5,
            base_url="ws://custom:9999/",
            api_key="my-key",
        )
        assert stream.base_url == "ws://custom:9999"
        assert stream.api_key == "my-key"
        assert stream._delay == 0.5

    @pytest.mark.unit
    def test_constructor_deep_copies_messages(self):
        """Constructor deep-copies the messages list to prevent external mutation."""
        original_messages = [{"type": "metrics", "data": {"epoch": 1}}]
        stream = FakeCascorTrainingStream(messages=original_messages)

        # Mutate the original list
        original_messages.append({"type": "state", "data": {"state": "done"}})
        original_messages[0]["data"]["epoch"] = 999

        # Stream's internal copy should be unaffected
        assert len(stream._messages) == 1
        assert stream._messages[0]["data"]["epoch"] == 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_sent_commands_empty_initially(self):
        """_sent_commands list is empty before any commands are sent."""
        stream = FakeCascorTrainingStream()
        assert stream._sent_commands == []

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_disconnect_adds_sentinel(self):
        """disconnect() adds a None sentinel to the queue."""
        stream = FakeCascorTrainingStream()
        await stream.connect()
        await stream.disconnect()
        # The sentinel should be in the queue
        sentinel = stream._queue.get_nowait()
        assert sentinel is None
