"""WebSocket client for real-time JuniperCascor training streams.

Provides async iteration over training metrics, state changes, topology
updates, and cascade events. Also supports sending control commands
with per-request correlation via ``command_id``.

CL1 — heartbeat handling + liveness surfaces (the cascor C3 contract):

The cascor server sends an application-level ``{"type":"ping","ts":<float>}``
on both ``/ws/training`` and ``/ws/control`` every ``ws_heartbeat_interval_sec``
(default 30s) and closes the connection (1011, "Heartbeat timeout") when the
client sends nothing within ``ws_heartbeat_pong_timeout_sec`` (default 10s) of
a ping. Both stream classes now:

* answer pings automatically with ``{"type":"pong"}`` (``auto_pong=True``
  default; the control stream starts its background recv loop at connect time
  so pings are answered even before the first command),
* treat ``ping`` as a RECOGNIZED transport frame (no more
  ``unrecognized_ws_frame`` warning spam — one warning per ~30s per stream in
  the 2026-07-10 incident, with no ``type`` in the message text), and
* expose a liveness surface for supervisors: :attr:`is_connected` (transport
  state — detects processed closes), :meth:`is_alive` (frame recency — detects
  half-open sockets that ``is_connected`` alone cannot), and
  :attr:`last_frame_at` / :attr:`pongs_sent` for display and diagnostics.
"""

import asyncio
import json
import logging
import os
import time
import uuid
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Union

import websockets
from juniper_cascor_protocol.envelope import UnknownEnvelope, validate_envelope
from websockets.asyncio.client import ClientConnection
from websockets.protocol import State

from juniper_cascor_client.constants import API_KEY_ENV_VAR, API_KEY_HEADER_NAME, DEFAULT_CONTROL_STREAM_TIMEOUT, DEFAULT_LIVENESS_WINDOW_SEC, DEFAULT_SET_PARAMS_TIMEOUT, DEFAULT_WS_BASE_URL, MAX_PENDING_COMMANDS, WS_CONTROL_PATH, WS_MSG_TYPE_CANDIDATE_PROGRESS, WS_MSG_TYPE_CASCADE_ADD, WS_MSG_TYPE_COMMAND_OUT, WS_MSG_TYPE_COMMAND_RESPONSE, WS_MSG_TYPE_CONNECTION_ESTABLISHED, WS_MSG_TYPE_EVENT, WS_MSG_TYPE_METRICS, WS_MSG_TYPE_PING, WS_MSG_TYPE_PONG, WS_MSG_TYPE_STATE, WS_MSG_TYPE_TOPOLOGY, WS_ORIGIN_ENV_VAR, WS_TRAINING_PATH
from juniper_cascor_client.exceptions import JuniperCascorClientError, JuniperCascorConnectionError, JuniperCascorOverloadError, JuniperCascorTimeoutError
from juniper_cascor_client.observability import record_unrecognized_frame

logger = logging.getLogger(__name__)


def _parse_json_frame(raw: Union[str, bytes], *, endpoint: str) -> Dict[str, Any]:
    """Parse a raw WS frame as JSON, raising :class:`JuniperCascorClientError`
    with a clear message on decode failure.

    CC-09..12 (v7 roadmap §15): every prior ``json.loads(raw)`` call site
    in this module assumed the peer sent valid JSON. A single malformed
    frame would crash the iterator (``CascorTrainingStream.stream``) or
    the background recv loop (``CascorControlStream._recv_loop``) and
    fail all pending futures. This helper bounds the blast radius:

    * For one-shot reads (``connect``'s ``connection_established`` frame,
      ``command``'s direct response): callers let the exception
      propagate as a clean ``JuniperCascorClientError``.
    * For loop reads (the two recv loops): callers catch and continue,
      logging the bad frame at WARNING level via :func:`logging`.

    The ``endpoint`` arg (``"training"`` / ``"control"``) labels the log
    line and is reserved for future Prometheus instrumentation parity
    with :func:`record_unrecognized_frame`.
    """
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        preview = raw[:200] if isinstance(raw, (str, bytes)) else repr(raw)[:200]
        raise JuniperCascorClientError(f"Failed to decode WebSocket frame from {endpoint!r}: {e}; payload preview: {preview!r}") from e


def _validate_and_record(message: Dict[str, Any], endpoint: str) -> Dict[str, Any]:
    """Validate an inbound WS frame envelope; observe (don't reject) on failure.

    METRICS-MON R2.2.4 / seed-05: every frame the client deserializes is
    passed through :func:`juniper_cascor_protocol.envelope.validate_envelope`
    so a server-side schema regression surfaces here as a clean
    log+counter event instead of a downstream ``KeyError``. Validation is
    purely **observational** — the original ``message`` dict is returned
    unchanged so callers (`stream()`, `_dispatch`, `_recv_loop`) keep the
    historical contract.

    Args:
        message: The dict produced by ``json.loads(raw_ws_frame)``.
        endpoint: ``"training"`` or ``"control"`` — for the Prometheus label.

    Returns:
        ``message`` unchanged.
    """
    envelope = validate_envelope(message)
    if isinstance(envelope, UnknownEnvelope):
        record_unrecognized_frame(envelope.type, endpoint)
    return message


class _WsLivenessMixin:
    """Connection-liveness bookkeeping shared by the two stream classes (CL1).

    Two complementary signals, designed as the seam canopy's supervisor
    hardening (plan unit N2) consumes:

    * :attr:`is_connected` — the transport view: the underlying ``websockets``
      connection exists and its protocol state is OPEN. Detects processed
      closes (e.g. the server's 1011 heartbeat-timeout close), which the
      historical ``_ws is not None`` idiom could not.
    * :meth:`is_alive` — the traffic view: connected AND at least one inbound
      frame within the window. Detects HALF-OPEN sockets (peer gone without a
      close frame reaching us) that ``is_connected`` alone cannot, because a
      dead TCP peer leaves the local protocol state OPEN. Against a healthy
      cascor the server heartbeat guarantees at least one frame per
      ``ws_heartbeat_interval_sec`` (default 30s), so the default 90s window
      is three missed heartbeats.

    ``connect()`` marks the connection itself as the first liveness evidence,
    so ``is_alive`` is True immediately after a successful connect.
    """

    _ws: Optional[ClientConnection]
    _last_frame_monotonic: Optional[float]
    _last_frame_wall: Optional[float]
    _pongs_sent: int
    _auto_pong: bool

    def _init_liveness(self, auto_pong: bool) -> None:
        """Initialize liveness state; call from ``__init__``."""
        self._last_frame_monotonic = None
        self._last_frame_wall = None
        self._pongs_sent = 0
        self._auto_pong = auto_pong

    def _mark_inbound_frame(self) -> None:
        """Record inbound activity (any frame, including pings)."""
        self._last_frame_monotonic = time.monotonic()
        self._last_frame_wall = time.time()

    async def _send_pong(self) -> None:
        """Answer a server heartbeat ping with ``{"type": "pong"}``.

        Best-effort: a send failure (connection tearing down) is logged at
        DEBUG and never propagates — the surrounding recv path will surface
        the disconnect through its own machinery.
        """
        ws = self._ws
        if ws is None:
            return
        try:
            await ws.send(json.dumps({"type": WS_MSG_TYPE_PONG}))
            self._pongs_sent += 1
        except Exception:  # noqa: BLE001 — pong is best-effort by design
            logger.debug("auto-pong send failed (connection closing?)", exc_info=True)

    @property
    def last_frame_at(self) -> Optional[float]:
        """Wall-clock epoch seconds of the last inbound frame (None before connect)."""
        return self._last_frame_wall

    @property
    def pongs_sent(self) -> int:
        """Count of automatic pong replies sent on this connection object."""
        return self._pongs_sent

    @property
    def is_connected(self) -> bool:
        """True when the underlying WebSocket exists and its protocol state is OPEN.

        Falls back to presence-only (the pre-CL1 semantics) when the
        underlying object does not expose a ``state`` attribute (e.g. plain
        test doubles).
        """
        ws = self._ws
        if ws is None:
            return False
        state = getattr(ws, "state", None)
        if state is None:
            return True
        return bool(state is State.OPEN)

    def is_alive(self, window_sec: float = DEFAULT_LIVENESS_WINDOW_SEC) -> bool:
        """True when connected AND an inbound frame arrived within ``window_sec``.

        The half-open detector: a connection whose peer silently died keeps
        ``is_connected`` True but stops producing frames — with the cascor
        heartbeat pinging every 30s, silence longer than the window (default
        90s = three missed heartbeats) marks the socket dead. Supervisors
        should reconnect when this returns False.
        """
        if not self.is_connected:
            return False
        if self._last_frame_monotonic is None:
            return False
        return (time.monotonic() - self._last_frame_monotonic) <= window_sec


class CascorTrainingStream(_WsLivenessMixin):
    """Async WebSocket client for real-time training updates.

    Connects to the CasCor service's /ws/training endpoint and yields
    messages as they arrive. Supports both async iteration and callback APIs.

    CL1: server heartbeat pings (``{"type": "ping"}``) are answered
    automatically with ``{"type": "pong"}`` and consumed by the transport
    layer (not yielded, not dispatched, never logged as unrecognized).
    Pass ``auto_pong=False`` to restore the legacy behaviour where ping
    frames are yielded to the consumer, which must then reply itself
    (juniper-canopy's pre-CL1 relay did this) or be closed by the server
    ~40s after connect (30s ping interval + 10s pong window).

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
        base_url: str = DEFAULT_WS_BASE_URL,
        api_key: Optional[str] = None,
        origin: Optional[str] = None,
        auto_pong: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.environ.get(API_KEY_ENV_VAR)
        # Forward Origin to `websockets.connect` when set. The Python
        # `websockets` library omits Origin for non-browser callers; the
        # cascor server's per-WS Origin policies (e.g. control-path
        # fail-closed allowlist on `/ws/control`, training path) require
        # server-to-server callers to supply it explicitly. None → preserved
        # 0.4.x behaviour (no Origin header sent).
        self.origin = origin or os.environ.get(WS_ORIGIN_ENV_VAR)
        self._ws: Optional[ClientConnection] = None
        self._callbacks: Dict[str, List[Callable[[Dict[str, Any]], None]]] = {}
        # CL1: liveness bookkeeping + heartbeat auto-pong posture.
        self._init_liveness(auto_pong)
        # ERR-14: opt-in disconnect callbacks. The stream silently ended on
        # ``websockets.exceptions.ConnectionClosed`` historically; callers
        # had no signal to distinguish a clean end from an unexpected drop.
        # We now (a) always log the disconnect at WARNING and (b) dispatch
        # to any callbacks registered via ``on_disconnect``. Default behavior
        # of the stream generator is preserved: it still ends cleanly without
        # re-raising, so existing callers continue to work unchanged.
        self._disconnect_callbacks: List[Callable[[websockets.exceptions.ConnectionClosed], None]] = []

    async def connect(self, path: str = WS_TRAINING_PATH) -> None:
        """Connect to a WebSocket endpoint.

        Args:
            path: WebSocket path (default: /ws/training).
        """
        url = f"{self.base_url}{path}"
        extra_headers = {}
        if self.api_key:
            extra_headers[API_KEY_HEADER_NAME] = self.api_key
        connect_kwargs: Dict[str, Any] = {"additional_headers": extra_headers}
        if self.origin is not None:
            connect_kwargs["origin"] = self.origin
        try:
            self._ws = await websockets.connect(url, **connect_kwargs)
        except (OSError, websockets.exceptions.WebSocketException) as e:
            raise JuniperCascorConnectionError(f"Failed to connect to {url}: {e}") from e
        # CL1: a successful connect is the first liveness evidence.
        self._mark_inbound_frame()

    async def disconnect(self) -> None:
        """Close the WebSocket connection."""
        if self._ws:
            await self._ws.close()
            self._ws = None

    async def stream(self) -> AsyncIterator[Dict[str, Any]]:
        """Yield messages from the WebSocket as they arrive.

        CL1: server heartbeat ``ping`` frames are handled by the transport
        layer — answered with a pong and consumed — under the default
        ``auto_pong=True``; with ``auto_pong=False`` they are yielded to the
        consumer (legacy behaviour) but in both cases they are RECOGNIZED
        (no ``unrecognized_ws_frame`` warning).
        """
        if not self._ws:
            raise JuniperCascorClientError("Not connected. Call connect() first.")
        try:
            async for raw in self._ws:
                # CL1: any inbound frame (even a malformed one) proves the
                # peer is alive.
                self._mark_inbound_frame()
                try:
                    message = _parse_json_frame(raw, endpoint="training")
                except JuniperCascorClientError as e:
                    # CC-09: skip + log the bad frame so one corrupt envelope
                    # can't kill the entire training stream iterator.
                    logger.warning("CascorTrainingStream: dropping malformed frame: %s", e)
                    continue
                if isinstance(message, dict) and message.get("type") == WS_MSG_TYPE_PING:
                    # CL1: recognized transport heartbeat — never validated as
                    # an application envelope (kills the per-30s
                    # unrecognized_ws_frame warning spam).
                    if self._auto_pong:
                        await self._send_pong()
                        continue
                    # Legacy posture: the consumer sees the ping and must
                    # reply itself (pre-CL1 canopy relay behaviour).
                    yield message
                    continue
                # METRICS-MON R2.2.4: observational envelope validation; never raises.
                _validate_and_record(message, endpoint="training")
                self._dispatch(message)
                yield message
        except websockets.exceptions.ConnectionClosed as exc:
            # ERR-14: do not silently swallow disconnects. Always log at
            # WARNING with the close code + reason so operators can see
            # unexpected drops, then dispatch to any ``on_disconnect``
            # callbacks that registered for the signal. The generator
            # still exits cleanly (no re-raise) so existing async-for
            # consumers that treat exhaustion as "stream done" keep working.
            logger.warning(
                "CascorTrainingStream: WebSocket disconnected (%s: %s)",
                type(exc).__name__,
                exc,
            )
            self._dispatch_disconnect(exc)

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
        # XREPO-07/08, CC-06: include the canonical "type" envelope so the
        # server can dispatch by ``type`` consistently across send_command(),
        # CascorControlStream.command(), and set_params().
        message: Dict[str, Any] = {"type": WS_MSG_TYPE_COMMAND_OUT, "command": command}
        if params:
            message["params"] = params
        await self._ws.send(json.dumps(message))

    # ─── Callback Registration ─��─────────────────────────────────────────

    def on_metrics(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register a callback for metrics messages."""
        self._register(WS_MSG_TYPE_METRICS, callback)

    def on_state(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register a callback for state change messages."""
        self._register(WS_MSG_TYPE_STATE, callback)

    def on_topology(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register a callback for topology update messages."""
        self._register(WS_MSG_TYPE_TOPOLOGY, callback)

    def on_cascade_add(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register a callback for cascade unit addition messages."""
        self._register(WS_MSG_TYPE_CASCADE_ADD, callback)

    def on_event(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register a callback for general event messages."""
        self._register(WS_MSG_TYPE_EVENT, callback)

    def on_candidate_progress(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register a callback for candidate training progress messages (API-06 / XREPO-17).

        The cascor server broadcasts ``candidate_progress`` frames during the
        candidate-training phase (see ``juniper-cascor`` `create_candidate_progress_message`
        / ``CandidateProgressEnvelope`` in ``juniper-cascor-protocol``). Prior to
        this handler, those frames passed through the dispatcher silently —
        consumers had to attach a generic message handler to observe them.
        """
        self._register(WS_MSG_TYPE_CANDIDATE_PROGRESS, callback)

    def on_disconnect(self, callback: Callable[[websockets.exceptions.ConnectionClosed], None]) -> None:
        """Register a callback to be invoked when the WebSocket disconnects (ERR-14).

        The callback receives the ``websockets.exceptions.ConnectionClosed``
        instance raised by the underlying iterator, which exposes the close
        ``code`` and ``reason`` so reconnection / failover logic can decide
        whether the drop was clean or unexpected.

        Callbacks fire from inside :meth:`stream` (and therefore :meth:`listen`)
        immediately before the generator exits. Callback exceptions are
        logged at ``ERROR`` and do not prevent subsequent callbacks from
        running.

        Example::

            stream = CascorTrainingStream("ws://localhost:8200")
            stream.on_disconnect(
                lambda exc: print(f"dropped: code={exc.code} reason={exc.reason!r}")
            )
            async with stream:
                async for msg in stream:
                    ...
        """
        self._disconnect_callbacks.append(callback)

    # ─── Context Manager ─────────────────────────────────────────────────

    async def __aenter__(self) -> "CascorTrainingStream":
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.disconnect()

    def __aiter__(self) -> AsyncIterator[Dict[str, Any]]:
        return self.stream()

    # ���── Internal ─���──────────────────────────────────────────────────────

    def _register(self, message_type: str, callback: Callable[[Dict[str, Any]], None]) -> None:
        if message_type not in self._callbacks:
            self._callbacks[message_type] = []
        self._callbacks[message_type].append(callback)

    def _dispatch(self, message: Dict[str, Any]) -> None:
        msg_type = message.get("type", "")
        data = message.get("data", {})
        for callback in self._callbacks.get(msg_type, []):
            callback(data)

    def _dispatch_disconnect(self, exc: websockets.exceptions.ConnectionClosed) -> None:
        """ERR-14: invoke registered ``on_disconnect`` callbacks with ``exc``.

        Each callback is wrapped in a try/except so a single misbehaving
        listener cannot prevent subsequent listeners from running and
        cannot mask the original disconnect by leaking an exception out of
        :meth:`stream`.
        """
        for callback in self._disconnect_callbacks:
            try:
                callback(exc)
            except Exception:  # noqa: BLE001 -- isolate listener faults
                logger.exception("CascorTrainingStream: on_disconnect callback raised; continuing")


class CascorControlStream(_WsLivenessMixin):
    """Async WebSocket client for sending training control commands.

    Connects to /ws/control for bidirectional command/response communication.
    Supports per-request correlation via ``command_id`` for concurrent callers.

    CL1: the background recv loop starts at ``connect()`` (not lazily on the
    first correlated command) and answers server heartbeat pings with
    ``{"type": "pong"}``. Pre-CL1, nothing read the socket between connect
    and the first ``set_params`` and nothing ever answered pings, so cascor's
    heartbeat closed the connection 40s after connect (30s ping interval +
    10s pong window) — the 2026-07-10 incident that left canopy pushing every
    hot-parameter update at a half-open corpse for 12+ hours. Because the
    recv loop is always running, ``command()`` now always routes through the
    ``command_id`` correlation path after ``connect()``.

    Example:
        >>> async with CascorControlStream("ws://localhost:8200") as ctrl:
        ...     response = await ctrl.command("start", {"epochs": 100})
        ...     print(response)

    Example (set_params with correlation):
        >>> async with CascorControlStream("ws://localhost:8200") as ctrl:
        ...     result = await ctrl.set_params({"learning_rate": 0.01})
        ...     print(result["data"]["status"])
    """

    def __init__(
        self,
        base_url: str = DEFAULT_WS_BASE_URL,
        api_key: Optional[str] = None,
        timeout: float = DEFAULT_CONTROL_STREAM_TIMEOUT,
        origin: Optional[str] = None,
        auto_pong: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.environ.get(API_KEY_ENV_VAR)
        # Forward Origin to `websockets.connect` when set. Required for
        # server-to-server callers against cascor's `/ws/control` because
        # juniper-cascor#129 makes the endpoint fail-closed against missing
        # Origin. None preserves the pre-0.5.0 behaviour.
        self.origin = origin or os.environ.get(WS_ORIGIN_ENV_VAR)
        self._ws: Optional[ClientConnection] = None
        self._timeout = timeout
        # CL1: liveness bookkeeping + heartbeat auto-pong posture.
        self._init_liveness(auto_pong)

        # Correlation state for set_params (and future correlated commands)
        self._pending: Dict[str, "asyncio.Future[Dict[str, Any]]"] = {}
        self._recv_task: Optional["asyncio.Task[None]"] = None

    async def connect(self) -> None:
        """Connect to the /ws/control endpoint.

        CL1: starts the background recv loop immediately so server heartbeat
        pings are answered from the moment the connection exists — a control
        stream that connects and then idles no longer dies 40s later.
        """
        url = f"{self.base_url}{WS_CONTROL_PATH}"
        extra_headers = {}
        if self.api_key:
            extra_headers[API_KEY_HEADER_NAME] = self.api_key
        connect_kwargs: Dict[str, Any] = {"additional_headers": extra_headers}
        if self.origin is not None:
            connect_kwargs["origin"] = self.origin
        try:
            self._ws = await websockets.connect(url, **connect_kwargs)
            # Read and validate the connection_established message. CC-10:
            # malformed JSON here is a control-protocol violation by the
            # server — propagate as JuniperCascorClientError rather than
            # crashing with a raw JSONDecodeError.
            raw = await self._ws.recv()
            msg = _parse_json_frame(raw, endpoint="control")
            if msg.get("type") != WS_MSG_TYPE_CONNECTION_ESTABLISHED:
                raise JuniperCascorClientError(f"Expected {WS_MSG_TYPE_CONNECTION_ESTABLISHED}, got: {msg.get('type', 'unknown')}")
        except (OSError, websockets.exceptions.WebSocketException) as e:
            raise JuniperCascorConnectionError(f"Failed to connect to {url}: {e}") from e
        # CL1: handshake received — first liveness evidence; then keep the
        # socket read (and pings answered) from t0.
        self._mark_inbound_frame()
        await self._ensure_recv_task()

    async def disconnect(self) -> None:
        """Close the WebSocket connection."""
        if self._recv_task and not self._recv_task.done():
            self._recv_task.cancel()
            try:
                await self._recv_task
            except asyncio.CancelledError:
                pass
            self._recv_task = None
        if self._ws:
            await self._ws.close()
            self._ws = None

    async def command(self, command: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send a command and wait for the response.

        If the background recv task is active — CL1 starts it at ``connect()``,
        so this is the normal case — routes through the ``command_id``
        correlation system. The direct-recv path remains as a fallback for
        callers that attached a socket without ``connect()`` or whose recv
        task has exited; it skips (and answers) heartbeat pings so a ping can
        never be returned as the command's response.

        Args:
            command: Command name (start, stop, pause, resume, reset).
            params: Optional command parameters.

        Returns:
            The command_response message from the server.
        """
        if not self._ws:
            raise JuniperCascorClientError("Not connected. Call connect() first.")

        # XREPO-07/08, CC-06: include the canonical "type" envelope on both
        # the correlated and direct paths so all client→server WS messages
        # share a uniform format with set_params().
        # If recv task is running, route through correlation to avoid recv conflicts
        if self._recv_task and not self._recv_task.done():
            cid = str(uuid.uuid4())
            message: Dict[str, Any] = {"type": WS_MSG_TYPE_COMMAND_OUT, "command": command, "command_id": cid}
            if params:
                message["params"] = params
            return await self._send_correlated(message, cid, timeout=self._timeout)

        message = {"type": WS_MSG_TYPE_COMMAND_OUT, "command": command}
        if params:
            message["params"] = params
        await self._ws.send(json.dumps(message))
        # CL1: skip (and answer) any heartbeat pings that arrive ahead of the
        # response — pre-CL1 the direct path would have returned a ping frame
        # as the command's "response". The whole skip loop shares the single
        # timeout budget.
        response = await asyncio.wait_for(self._recv_skipping_pings(), timeout=self._timeout)
        # METRICS-MON R2.2.4: observational envelope validation; never raises.
        _validate_and_record(response, endpoint="control")
        return response

    async def _recv_skipping_pings(self) -> Dict[str, Any]:
        """Receive the next non-ping frame on the direct (uncorrelated) path.

        CL1: heartbeat pings are answered (under ``auto_pong``) and consumed;
        every inbound frame updates the liveness clock. CC-11: malformed JSON
        propagates as :class:`JuniperCascorClientError` (a server-side broken
        contract on this one-shot read path).
        """
        while True:
            if self._ws is None:
                raise JuniperCascorClientError("Not connected. Call connect() first.")
            raw = await self._ws.recv()
            self._mark_inbound_frame()
            response = _parse_json_frame(raw, endpoint="control")
            if isinstance(response, dict) and response.get("type") == WS_MSG_TYPE_PING:
                if self._auto_pong:
                    await self._send_pong()
                continue
            return response

    async def set_params(
        self,
        params: Dict[str, Any],
        *,
        timeout: float = DEFAULT_SET_PARAMS_TIMEOUT,
        command_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a set_params command with per-request correlation.

        Uses ``command_id`` to correlate the request with its response,
        allowing concurrent callers. Fails fast on timeout or disconnect
        with no retries (D-20, C-04).

        Args:
            params: Parameter dict to apply (e.g. {"learning_rate": 0.01}).
            timeout: Response timeout in seconds (default 1.0, D-01).
            command_id: Optional correlation ID (auto-generated UUID if absent).

        Returns:
            The command_response envelope from the server.

        Raises:
            JuniperCascorTimeoutError: Response not received within timeout.
            JuniperCascorConnectionError: WebSocket disconnected during wait.
            JuniperCascorOverloadError: Too many concurrent pending commands.
            JuniperCascorClientError: Not connected.
        """
        if not self._ws:
            raise JuniperCascorClientError("Not connected. Call connect() first.")

        if len(self._pending) >= MAX_PENDING_COMMANDS:
            raise JuniperCascorOverloadError(f"Too many pending commands ({MAX_PENDING_COMMANDS} max)")

        if command_id is None:
            command_id = str(uuid.uuid4())

        message: Dict[str, Any] = {
            "type": WS_MSG_TYPE_COMMAND_OUT,
            "command": "set_params",
            "command_id": command_id,
            "params": params,
        }

        return await self._send_correlated(message, command_id, timeout=timeout)

    # ─── Context Manager ─────────────────────��───────────────────────────

    async def __aenter__(self) -> "CascorControlStream":
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.disconnect()

    # ─── Internal: Correlation ───────────────────────────────────────────

    async def _send_correlated(self, message: Dict[str, Any], command_id: str, *, timeout: float) -> Dict[str, Any]:
        """Send a message and await its correlated response by command_id."""
        loop = asyncio.get_running_loop()
        future: "asyncio.Future[Dict[str, Any]]" = loop.create_future()
        self._pending[command_id] = future

        try:
            await self._ensure_recv_task()
            await self._ws.send(json.dumps(message))
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            raise JuniperCascorTimeoutError(f"set_params timed out after {timeout}s (command_id={command_id})") from None
        except asyncio.CancelledError:
            raise
        finally:
            self._pending.pop(command_id, None)

    async def _ensure_recv_task(self) -> None:
        """Start the background recv loop if not already running."""
        if self._recv_task is None or self._recv_task.done():
            self._recv_task = asyncio.create_task(self._recv_loop())

    async def _recv_loop(self) -> None:
        """Background task: answer pings and route responses to pending futures.

        CL1: runs from ``connect()`` onward (see :meth:`connect`). Heartbeat
        ``ping`` frames are answered with a pong (under ``auto_pong``) and
        consumed BEFORE envelope validation, so they are never logged as
        unrecognized. Every inbound frame updates the liveness clock. The
        ``asyncio.sleep(0)`` guarantees a scheduling/cancellation point per
        iteration even when ``recv()`` resolves without suspending (as
        immediate-result test doubles do).
        """
        try:
            while self._ws:
                await asyncio.sleep(0)
                raw = await self._ws.recv()
                self._mark_inbound_frame()
                try:
                    msg = _parse_json_frame(raw, endpoint="control")
                except JuniperCascorClientError as e:
                    # CC-12: skip + log so one malformed frame can't fail
                    # every in-flight ``set_params`` / ``command`` correlation.
                    logger.warning("CascorControlStream: dropping malformed frame: %s", e)
                    continue
                if isinstance(msg, dict) and msg.get("type") == WS_MSG_TYPE_PING:
                    # CL1: recognized transport heartbeat — the root fix for
                    # the 40s control-WS kill.
                    if self._auto_pong:
                        await self._send_pong()
                    continue
                # METRICS-MON R2.2.4: observational envelope validation; never raises.
                _validate_and_record(msg, endpoint="control")
                if msg.get("type") == WS_MSG_TYPE_COMMAND_RESPONSE:
                    cid = msg.get("data", {}).get("command_id")
                    if cid and cid in self._pending:
                        self._pending[cid].set_result(msg)
        except (websockets.exceptions.ConnectionClosed, OSError):
            # Fail all pending futures on disconnect (C-04). CC-13: narrowed
            # from ``Exception`` so unexpected programming errors propagate
            # instead of silently failing every pending future.
            for _cid, future in list(self._pending.items()):
                if not future.done():
                    future.set_exception(JuniperCascorConnectionError("WebSocket disconnected"))
