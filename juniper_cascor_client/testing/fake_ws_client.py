"""Fake WebSocket client for JuniperCascor training streams.

Provides an in-memory fake of CascorTrainingStream that yields pre-configured
messages on demand. Supports callback APIs, async iteration, and message
injection for testing.

CL1 parity: mirrors the real client's heartbeat handling and liveness
surfaces — injected ``{"type": "ping"}`` frames are consumed by the fake
transport layer (counted in :attr:`pongs_sent`, never yielded) under the
default ``auto_pong=True``, and :attr:`is_connected` / :attr:`last_frame_at`
/ :meth:`is_alive` behave like the real stream's surfaces so consumer
supervision logic can be tested against the fake.

Project: Juniper
Sub-Project: juniper-cascor-client
Application: FakeCascorTrainingStream
Author: Paul Calnon
Version: 0.7.0
License: MIT License
"""

import asyncio
import copy
import time
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

from juniper_cascor_client.constants import DEFAULT_LIVENESS_WINDOW_SEC, WS_MSG_TYPE_COMMAND_OUT, WS_MSG_TYPE_PING
from juniper_cascor_client.exceptions import JuniperCascorClientError
from juniper_cascor_client.ws_client import warn_if_legacy_auto_pong


class FakeCascorTrainingStream:
    """In-memory fake of CascorTrainingStream for testing.

    Yields pre-configured messages on demand without making real WebSocket
    connections. Supports the same callback and async iteration APIs as
    CascorTrainingStream.

    Test helpers:
        - inject_message(message): Add a message to the internal queue
          that will be yielded by stream() / listened by listen().

    Example (async iteration):
        >>> messages = [
        ...     {"type": "metrics", "data": {"epoch": 1, "train_loss": 0.5}},
        ...     {"type": "state", "data": {"state": "complete"}},
        ... ]
        >>> async with FakeCascorTrainingStream(messages=messages) as stream:
        ...     async for msg in stream:
        ...         print(msg["type"])

    Example (callback):
        >>> stream = FakeCascorTrainingStream()
        >>> stream.on_metrics(lambda data: print(f"Loss: {data['train_loss']}"))
        >>> stream.inject_message({"type": "metrics", "data": {"train_loss": 0.1}})
        >>> await stream.connect()
        >>> await stream.listen()
    """

    def __init__(
        self,
        messages: Optional[List[Dict[str, Any]]] = None,
        delay: float = 0.1,
        base_url: str = "ws://fake-cascor:8200",
        api_key: Optional[str] = None,
        # APD-CCLIENT-012 parity: keyword-only exactly like the real streams,
        # so a consumer test calling the fake positionally fails as production would.
        *,
        auto_pong: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._delay = delay
        self._connected = False
        self._callbacks: Dict[str, List[Callable[[Dict[str, Any]], None]]] = {}
        self._sent_commands: List[Dict[str, Any]] = []
        # CL1 parity: heartbeat auto-pong posture + liveness bookkeeping,
        # mirroring the real CascorTrainingStream surfaces.
        #
        # The fake warns too (APD-ECO-007). A consumer that migrates against the
        # fake must see the same deprecation the real stream emits, or the fake
        # would quietly certify a posture production is dating for removal --
        # the #91 fake-parity lesson. stacklevel=3 here, not 4: this class sets
        # ``_auto_pong`` directly rather than through ``_init_liveness``, so the
        # chain is one frame shorter (warn <- __init__ <- user).
        warn_if_legacy_auto_pong(auto_pong, stacklevel=3)
        self._auto_pong = auto_pong
        self._last_frame_monotonic: Optional[float] = None
        self._last_frame_wall: Optional[float] = None
        self._pongs_sent: int = 0

        # Internal message queue: pre-loaded messages + injected messages
        self._messages: List[Dict[str, Any]] = []
        if messages:
            self._messages.extend(copy.deepcopy(messages))

        # Async queue for messages injected after connect
        self._queue: asyncio.Queue[Optional[Dict[str, Any]]] = asyncio.Queue()

        # Track whether initial messages have been loaded into the queue
        self._initial_loaded = False

    async def connect(self, path: str = "/ws/training") -> None:
        """Simulate connecting to a WebSocket endpoint.

        Args:
            path: WebSocket path (default: /ws/training).
        """
        self._connected = True
        # CL1 parity: a successful connect is the first liveness evidence.
        self._mark_inbound_frame()
        # Load pre-configured messages into the async queue
        if not self._initial_loaded:
            for msg in self._messages:
                await self._queue.put(copy.deepcopy(msg))
            self._initial_loaded = True

    async def disconnect(self) -> None:
        """Simulate closing the WebSocket connection."""
        if self._connected:
            self._connected = False
            # Signal stream termination by putting a sentinel
            await self._queue.put(None)

    async def stream(self) -> AsyncIterator[Dict[str, Any]]:
        """Yield messages from the internal queue as they arrive.

        Yields pre-configured messages first, then any injected messages.
        Terminates when disconnect() is called or queue receives a None sentinel.
        """
        if not self._connected:
            raise JuniperCascorClientError("Not connected. Call connect() first.")

        while self._connected:
            try:
                message = await asyncio.wait_for(self._queue.get(), timeout=self._delay * 10)
            except asyncio.TimeoutError:
                # No more messages and queue is empty — check if still connected
                if self._queue.empty():
                    break
                continue

            if message is None:
                # Sentinel: stream ended
                break

            # CL1 parity: any inbound frame proves liveness; heartbeat pings
            # are consumed by the (fake) transport layer under auto_pong,
            # exactly like the real CascorTrainingStream.
            self._mark_inbound_frame()
            if isinstance(message, dict) and message.get("type") == WS_MSG_TYPE_PING:
                if self._auto_pong:
                    self._pongs_sent += 1
                    continue
                yield message
                continue

            self._dispatch(message)

            if self._delay > 0:
                await asyncio.sleep(self._delay)

            yield message

    async def listen(self) -> None:
        """Listen for messages and dispatch to registered callbacks.

        Blocks until the connection is closed or all messages are consumed.
        """
        async for _ in self.stream():
            pass

    async def send_command(self, command: str, params: Optional[Dict[str, Any]] = None) -> None:
        """Simulate sending a control command via WebSocket.

        Records the command for later inspection in tests.

        Args:
            command: Command name (start, stop, pause, resume, reset).
            params: Optional command parameters.
        """
        if not self._connected:
            raise JuniperCascorClientError("Not connected. Call connect() first.")

        # Mirror the real CascorTrainingStream.send_command() envelope so the
        # fake's recorded commands match what the production client puts on
        # the wire (XREPO-07/08, CC-06).
        message: Dict[str, Any] = {"type": WS_MSG_TYPE_COMMAND_OUT, "command": command}
        if params:
            message["params"] = params
        self._sent_commands.append(message)

    # ─── Callback Registration ───────────────────────────────────────────

    def on_metrics(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register a callback for metrics messages."""
        self._register("metrics", callback)

    def on_state(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register a callback for state change messages."""
        self._register("state", callback)

    def on_topology(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register a callback for topology update messages."""
        self._register("topology", callback)

    def on_cascade_add(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register a callback for cascade unit addition messages."""
        self._register("cascade_add", callback)

    def on_event(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register a callback for general event messages."""
        self._register("event", callback)

    def on_candidate_progress(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register a callback for candidate training progress messages (API-06 / XREPO-17)."""
        self._register("candidate_progress", callback)

    # ─── Context Manager ─────────────────────────────────────────────────

    async def __aenter__(self) -> "FakeCascorTrainingStream":
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.disconnect()

    def __aiter__(self) -> AsyncIterator[Dict[str, Any]]:
        return self.stream()

    # ─── Test Helpers ────────────────────────────────────────────────────

    def inject_message(self, message: Dict[str, Any]) -> None:
        """Add a message to the internal queue.

        Messages injected here will be yielded by stream() and dispatched
        to any registered callbacks. Can be called before or after connect().

        This is a test helper not present on the real CascorTrainingStream.

        Args:
            message: A message dictionary with "type" and "data" keys.
        """
        msg_copy = copy.deepcopy(message)
        if self._connected:
            # If connected, put directly into the async queue
            # Use a fire-and-forget approach that works from sync code
            try:
                self._queue.put_nowait(msg_copy)
            except asyncio.QueueFull:
                # Queue is unbounded by default, but handle gracefully
                self._messages.append(msg_copy)
        else:
            # If not yet connected, add to the pre-load list
            self._messages.append(msg_copy)

    # ─── Liveness Surface (CL1 parity with CascorTrainingStream) ─────────

    @property
    def last_frame_at(self) -> Optional[float]:
        """Wall-clock epoch seconds of the last (fake) inbound frame."""
        return self._last_frame_wall

    @property
    def pongs_sent(self) -> int:
        """Count of heartbeat pings the fake transport layer consumed/answered."""
        return self._pongs_sent

    @property
    def is_connected(self) -> bool:
        """True while the fake connection is open (parity with the real stream)."""
        return self._connected

    def is_alive(self, window_sec: float = DEFAULT_LIVENESS_WINDOW_SEC) -> bool:
        """True when connected AND a frame arrived within ``window_sec`` (parity)."""
        if not self.is_connected:
            return False
        if self._last_frame_monotonic is None:
            return False
        return (time.monotonic() - self._last_frame_monotonic) <= window_sec

    # ─── Internal ────────────────────────────────────────────────────────

    def _mark_inbound_frame(self) -> None:
        """Record inbound activity (CL1 parity with the real stream)."""
        self._last_frame_monotonic = time.monotonic()
        self._last_frame_wall = time.time()

    def _register(self, message_type: str, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register a callback for a specific message type."""
        if message_type not in self._callbacks:
            self._callbacks[message_type] = []
        self._callbacks[message_type].append(callback)

    def _dispatch(self, message: Dict[str, Any]) -> None:
        """Dispatch a message to registered callbacks."""
        msg_type = message.get("type", "")
        data = message.get("data", {})
        for callback in self._callbacks.get(msg_type, []):
            callback(data)
