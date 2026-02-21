"""WebSocket client for real-time JuniperCascor training streams.

Provides async iteration over training metrics, state changes, topology
updates, and cascade events. Also supports sending control commands.
"""

import json
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

import websockets
from websockets.asyncio.client import ClientConnection

from juniper_cascor_client.exceptions import (
    JuniperCascorClientError,
    JuniperCascorConnectionError,
)


class CascorTrainingStream:
    """Async WebSocket client for real-time training updates.

    Connects to the CasCor service's /ws/training endpoint and yields
    messages as they arrive. Supports both async iteration and callback APIs.

    Example (async iteration):
        >>> async with CascorTrainingStream("ws://localhost:8200") as stream:
        ...     async for message in stream:
        ...         print(f"[{message['type']}] {message['data']}")

    Example (callback):
        >>> stream = CascorTrainingStream("ws://localhost:8200")
        >>> stream.on_metrics(lambda data: print(f"Loss: {data['train_loss']}"))
        >>> await stream.connect()
        >>> await stream.listen()
    """

    def __init__(
        self,
        base_url: str = "ws://localhost:8200",
        api_key: Optional[str] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._ws: Optional[ClientConnection] = None
        self._callbacks: Dict[str, List[Callable[[Dict[str, Any]], None]]] = {}

    async def connect(self, path: str = "/ws/training") -> None:
        """Connect to a WebSocket endpoint.

        Args:
            path: WebSocket path (default: /ws/training).
        """
        url = f"{self.base_url}{path}"
        extra_headers = {}
        if self.api_key:
            extra_headers["X-API-Key"] = self.api_key
        try:
            self._ws = await websockets.connect(url, additional_headers=extra_headers)
        except (OSError, websockets.exceptions.WebSocketException) as e:
            raise JuniperCascorConnectionError(f"Failed to connect to {url}: {e}") from e

    async def disconnect(self) -> None:
        """Close the WebSocket connection."""
        if self._ws:
            await self._ws.close()
            self._ws = None

    async def stream(self) -> AsyncIterator[Dict[str, Any]]:
        """Yield messages from the WebSocket as they arrive."""
        if not self._ws:
            raise JuniperCascorClientError("Not connected. Call connect() first.")
        try:
            async for raw in self._ws:
                message = json.loads(raw)
                self._dispatch(message)
                yield message
        except websockets.exceptions.ConnectionClosed:
            pass

    async def listen(self) -> None:
        """Listen for messages and dispatch to registered callbacks.

        Blocks until the connection is closed.
        """
        async for _ in self.stream():
            pass

    async def send_command(self, command: str, params: Optional[Dict[str, Any]] = None) -> None:
        """Send a control command via WebSocket.

        Args:
            command: Command name (start, stop, pause, resume, reset).
            params: Optional command parameters.
        """
        if not self._ws:
            raise JuniperCascorClientError("Not connected. Call connect() first.")
        message: Dict[str, Any] = {"command": command}
        if params:
            message["params"] = params
        await self._ws.send(json.dumps(message))

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

    # ─── Context Manager ─────────────────────────────────────────────────

    async def __aenter__(self) -> "CascorTrainingStream":
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.disconnect()

    def __aiter__(self) -> AsyncIterator[Dict[str, Any]]:
        return self.stream()

    # ─── Internal ────────────────────────────────────────────────────────

    def _register(self, message_type: str, callback: Callable[[Dict[str, Any]], None]) -> None:
        if message_type not in self._callbacks:
            self._callbacks[message_type] = []
        self._callbacks[message_type].append(callback)

    def _dispatch(self, message: Dict[str, Any]) -> None:
        msg_type = message.get("type", "")
        data = message.get("data", {})
        for callback in self._callbacks.get(msg_type, []):
            callback(data)


class CascorControlStream:
    """Async WebSocket client for sending training control commands.

    Connects to /ws/control for bidirectional command/response communication.

    Example:
        >>> async with CascorControlStream("ws://localhost:8200") as ctrl:
        ...     response = await ctrl.command("start", {"epochs": 100})
        ...     print(response)
    """

    def __init__(
        self,
        base_url: str = "ws://localhost:8200",
        api_key: Optional[str] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._ws: Optional[ClientConnection] = None

    async def connect(self) -> None:
        """Connect to the /ws/control endpoint."""
        url = f"{self.base_url}/ws/control"
        extra_headers = {}
        if self.api_key:
            extra_headers["X-API-Key"] = self.api_key
        try:
            self._ws = await websockets.connect(url, additional_headers=extra_headers)
            # Read the connection_established message
            raw = await self._ws.recv()
            json.loads(raw)  # Consume connection_established message
        except (OSError, websockets.exceptions.WebSocketException) as e:
            raise JuniperCascorConnectionError(f"Failed to connect to {url}: {e}") from e

    async def disconnect(self) -> None:
        """Close the WebSocket connection."""
        if self._ws:
            await self._ws.close()
            self._ws = None

    async def command(self, command: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send a command and wait for the response.

        Args:
            command: Command name (start, stop, pause, resume, reset).
            params: Optional command parameters.

        Returns:
            The command_response message from the server.
        """
        if not self._ws:
            raise JuniperCascorClientError("Not connected. Call connect() first.")
        message: Dict[str, Any] = {"command": command}
        if params:
            message["params"] = params
        await self._ws.send(json.dumps(message))
        raw = await self._ws.recv()
        return json.loads(raw)

    async def __aenter__(self) -> "CascorControlStream":
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.disconnect()
