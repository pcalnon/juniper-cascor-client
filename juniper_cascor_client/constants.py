"""Constants for the JuniperCascor REST and WebSocket clients.

Centralizes all hardcoded literals used by ``client.py`` and ``ws_client.py``
so that consumers can override them and so that protocol-level identifiers
(endpoints, headers, message types) are discoverable in one place.

This module contains *production* constants only. Constants used by the
in-memory testing fakes live in ``juniper_cascor_client.testing.constants``.

Project: Juniper
Sub-Project: juniper-cascor-client
Application: JuniperCascorClient
Author: Paul Calnon
Version: 0.8.0
License: MIT License
"""

from typing import List, Tuple

# ─── Service Configuration ───────────────────────────────────────────────────

DEFAULT_BASE_URL: str = "http://localhost:8200"
DEFAULT_WS_BASE_URL: str = "ws://localhost:8200"
API_VERSION_PATH: str = "/v1"

# ─── Base-URL normalisation (APD-CCLIENT-005; mirrors the sibling clients) ───

URL_SCHEME_PREFIXES: Tuple[str, str] = ("http://", "https://")
DEFAULT_URL_SCHEME_PREFIX: str = "http://"

# ─── HTTP Configuration ──────────────────────────────────────────────────────

DEFAULT_REQUEST_TIMEOUT: int = 30
DEFAULT_RETRY_COUNT: int = 3
DEFAULT_BACKOFF_FACTOR: float = 0.5
# APD-ECO-002: urllib3 applies this as an ABSOLUTE additive term --
# ``backoff_value += random.random() * backoff_jitter`` -- not a proportional
# one. Without it every client that trips the same transient outage retries on
# an identical schedule, so a service that is already failing is hit by a
# synchronised herd. Matched to DEFAULT_BACKOFF_FACTOR so the spread is a full
# window on the first retry, which is the step that carries the most callers.
DEFAULT_BACKOFF_JITTER: float = 0.5
# XREPO-02 / CC-02 (2026-04-24): 503 is the canonical transient error
# emitted by services during restart / deploy; 429 (Too Many Requests)
# is also safe to retry when the server sets Retry-After. Both were
# previously missing from the retry list, causing short outages to
# bubble up as hard failures to callers.
RETRYABLE_STATUS_CODES: List[int] = [429, 502, 503, 504]
# APD-CCLIENT-001 (2026-08-28): auto-retry is restricted to idempotent methods
# per RFC 9110 §9.2.2. urllib3 replays inside the HTTP adapter, where the caller
# never learns it happened, and there is no idempotency key anywhere in the
# stack (APD-ECO-001), so a transient 502/503 on a mutation silently repeats it.
# Both sibling clients already restricted theirs -- juniper-data-client to
# ["HEAD","GET","PUT"], juniper-recurrence-client to ["HEAD","GET"] -- and this
# was the last unrestricted client in the fleet.
#
# Per method, why it is out:
#   POST   -- ``save_snapshot`` (POST /v1/snapshots) has no server-side guard, so
#             a replay writes a DUPLICATE snapshot row. This is the one call site
#             that genuinely duplicates today. The training lifecycle POSTs are
#             only *accidentally* safe: cascor's FSM 409s a second start, and 409
#             is not in RETRYABLE_STATUS_CODES, so the replay surfaces as a
#             conflict rather than a second run. That is a property of the
#             server's state machine, not an idempotency contract -- any new
#             mutating endpoint without an FSM guard inherits the raw behaviour.
#   PATCH  -- non-idempotent by RFC 9110; ``update_training_params`` applies a
#             partial update whose replay is not guaranteed to be a no-op.
#   DELETE -- RFC-idempotent in END STATE, but the only call site destroys a
#             trained network. A replay landing after another actor recreated it
#             deletes the new one, which is the classic DELETE-replay hazard and
#             the reason juniper-data-client dropped it too.
#   PUT    -- never issued by this client; dropped rather than carried as dead
#             configuration that implies a capability the client does not have.
#
# HEAD is included for parity with both siblings: it is safe by RFC 9110 §9.2.1
# and costs nothing if the client never issues one.
RETRY_ALLOWED_METHODS: List[str] = ["HEAD", "GET"]
# APD-CCLIENT-009: both sibling clients set pool_connections alongside
# pool_maxsize (10/10); omitting it here left the adapter on urllib3's
# default and encoded silent sibling drift rather than a decision.
DEFAULT_POOL_CONNECTIONS: int = 10
DEFAULT_POOL_MAXSIZE: int = 10

# ─── Readiness Polling ───────────────────────────────────────────────────────

DEFAULT_READY_TIMEOUT: float = 30.0
DEFAULT_READY_POLL_INTERVAL: float = 0.5

# ─── Authentication ──────────────────────────────────────────────────────────

API_KEY_HEADER_NAME: str = "X-API-Key"
API_KEY_ENV_VAR: str = "JUNIPER_CASCOR_API_KEY"

# ─── WebSocket Origin ────────────────────────────────────────────────────────
# The cascor server's `/ws/control` endpoint fail-closes against missing
# Origin headers (juniper-cascor#129 — control-path security § origin
# validation). The Python `websockets` library does not auto-emit Origin
# for non-browser callers, so server-to-server callers (e.g. juniper-canopy
# inside docker compose) must supply the configured Origin explicitly.
# Set this env var, or pass `origin=` to `CascorControlStream` /
# `CascorTrainingStream`, to opt in. Default (None) preserves the
# pre-0.5.0 behaviour of sending no Origin header.
WS_ORIGIN_ENV_VAR: str = "JUNIPER_CASCOR_WS_ORIGIN"

# ─── REST Endpoints (relative to API_VERSION_PATH) ───────────────────────────

# Health
ENDPOINT_HEALTH: str = "/health"
ENDPOINT_HEALTH_LIVE: str = "/health/live"
ENDPOINT_HEALTH_READY: str = "/health/ready"

# Network lifecycle
ENDPOINT_NETWORK: str = "/network"
ENDPOINT_NETWORK_TOPOLOGY: str = "/network/topology"
ENDPOINT_NETWORK_STATS: str = "/network/stats"

# Training control
ENDPOINT_TRAINING_START: str = "/training/start"
ENDPOINT_TRAINING_STOP: str = "/training/stop"
ENDPOINT_TRAINING_PAUSE: str = "/training/pause"
ENDPOINT_TRAINING_RESUME: str = "/training/resume"
ENDPOINT_TRAINING_RESET: str = "/training/reset"
ENDPOINT_TRAINING_STATUS: str = "/training/status"
ENDPOINT_TRAINING_PARAMS: str = "/training/params"

# Metrics
ENDPOINT_METRICS: str = "/metrics"
ENDPOINT_METRICS_HISTORY: str = "/metrics/history"

# Data
ENDPOINT_DATASET: str = "/dataset"
ENDPOINT_DATASET_DATA: str = "/dataset/data"
ENDPOINT_DECISION_BOUNDARY: str = "/decision-boundary"

# Snapshots (templates use ``{snapshot_id}`` placeholder for ``str.format``)
ENDPOINT_SNAPSHOTS: str = "/snapshots"
ENDPOINT_SNAPSHOT_BY_ID_TEMPLATE: str = "/snapshots/{snapshot_id}"
ENDPOINT_SNAPSHOT_RESTORE_TEMPLATE: str = "/snapshots/{snapshot_id}/restore"

# Workers (template uses ``{worker_id}`` placeholder for ``str.format``)
ENDPOINT_WORKERS: str = "/workers"
ENDPOINT_WORKER_BY_ID_TEMPLATE: str = "/workers/{worker_id}"
ENDPOINT_WORKERS_STATS: str = "/workers/stats"

# ─── WebSocket Endpoints ─────────────────────────────────────────────────────

WS_TRAINING_PATH: str = "/ws/training"
WS_CONTROL_PATH: str = "/ws/control"

# ─── WebSocket Defaults ──────────────────────────────────────────────────────

DEFAULT_CONTROL_STREAM_TIMEOUT: float = 30.0

# ─── WebSocket Message Types ─────────────────────────────────────────────────

# Server-emitted message ``type`` values dispatched by CascorTrainingStream.
WS_MSG_TYPE_METRICS: str = "metrics"
WS_MSG_TYPE_STATE: str = "state"
WS_MSG_TYPE_TOPOLOGY: str = "topology"
WS_MSG_TYPE_CASCADE_ADD: str = "cascade_add"
WS_MSG_TYPE_EVENT: str = "event"
# API-06 / XREPO-17: cascor server broadcasts candidate training progress
# via ``create_candidate_progress_message`` in
# ``juniper-cascor/src/api/websocket/messages.py:165`` (wraps the shared
# ``CandidateProgressEnvelope`` in ``juniper-cascor-protocol``). Surfaced
# here so consumers can register a callback via
# ``CascorTrainingStream.on_candidate_progress(...)``.
WS_MSG_TYPE_CANDIDATE_PROGRESS: str = "candidate_progress"

# Server-emitted control-stream handshake message type.
WS_MSG_TYPE_CONNECTION_ESTABLISHED: str = "connection_established"

# Server-emitted command response (echoes command_id for correlation).
WS_MSG_TYPE_COMMAND_RESPONSE: str = "command_response"

# ─── WebSocket Heartbeat (CL1 — cascor C3 contract) ─────────────────────────

# The cascor server sends an application-level ``{"type":"ping","ts":<float>}``
# on /ws/training and /ws/control every ``ws_heartbeat_interval_sec`` (default
# 30s) and closes the connection (code 1011, "Heartbeat timeout") when the
# client sends nothing within ``ws_heartbeat_pong_timeout_sec`` (default 10s)
# of a ping. CascorTrainingStream / CascorControlStream answer these pings
# automatically with ``{"type":"pong"}`` (``auto_pong=True`` default); the
# 2026-07-10 incident (canopy's control WS silently killed 40s after connect,
# then held as a half-open corpse for 12+ hours) traces to this layer
# previously implementing no ping handling at all.
WS_MSG_TYPE_PING: str = "ping"
WS_MSG_TYPE_PONG: str = "pong"

# Default window for ``is_alive()``: 3x the server's 30s heartbeat interval,
# so a healthy socket (which sees at least one ping per interval) is never
# reported dead, while a genuinely silent one is flagged within ~3 missed
# heartbeats. Consumers with different server settings should pass their own
# window.
DEFAULT_LIVENESS_WINDOW_SEC: float = 90.0

# Release that removes the legacy ``auto_pong=False`` posture (defect-register
# ``APD-ECO-007``, which owns the removal-date half of ``APD-CCLIENT-012``).
#
# ``auto_pong=False`` restores the pre-CL1 behaviour where ping frames are yielded
# to the consumer, which must then reply itself or be closed by the server ~40s
# after connect -- the 2026-07-10 incident. It shipped as a silent opt-out with no
# warning and **no stated removal**, which is the defect: a compatibility flag that
# nothing dates is a permanent tax rather than a plan, and nothing tells you who
# still sets it.
#
# A fleet census answers that: ``auto_pong=False`` has **zero** production users --
# every occurrence across juniper-canopy / cascor / cascor-worker / data /
# recurrence / ml is absent, and all eleven inside this repo are its own tests. So
# the posture is dated rather than kept indefinitely. One release cycle, matching
# the ``juniper-data-client`` alias precedent ("Remove in the release after v0.5"):
# deprecated in 0.8.0, removed here.
AUTO_PONG_REMOVAL_VERSION: str = "0.9.0"

# ─── WebSocket set_params Defaults ──────────────────────────────────────────

DEFAULT_SET_PARAMS_TIMEOUT: float = 1.0  # D-01: fail fast to REST fallback
MAX_PENDING_COMMANDS: int = 256

# ─── WebSocket Outbound Message Envelope (XREPO-07/08, CC-06) ───────────────

# All client→server WS messages on /ws/control share this envelope ``type``.
# Phase 4D unifies send_command() and CascorControlStream.command() with
# set_params() so the server can dispatch by ``type`` regardless of which
# client method produced the message.
WS_MSG_TYPE_COMMAND_OUT: str = "command"

# ─── Canonical Training State Names (XREPO-05) ──────────────────────────────

# Source of truth: cascor server FSM state names. Clients comparing against
# server-emitted ``state`` / ``training_state`` values should use these
# constants rather than hand-rolled string literals to avoid casing drift.
TRAINING_STATE_STOPPED: str = "STOPPED"
TRAINING_STATE_STARTED: str = "STARTED"
TRAINING_STATE_PAUSED: str = "PAUSED"
TRAINING_STATE_FAILED: str = "FAILED"
TRAINING_STATE_COMPLETED: str = "COMPLETED"

# ─── epochs_max Fallback (XREPO-06 — partial; full alignment deferred) ──────

# Cascor server's compiled-in default for ``epochs_max``. Canopy and other
# clients SHOULD prefer the value returned by ``GET /v1/network`` and only
# fall back to this constant when the server is unreachable during initial
# render. See roadmap XREPO-06 for the complete cross-repo alignment plan.
DEFAULT_EPOCHS_MAX_FALLBACK: int = 10_000

# ─── Decision Boundary ───────────────────────────────────────────────────────

DEFAULT_DECISION_BOUNDARY_RESOLUTION: int = 50
MIN_DECISION_BOUNDARY_RESOLUTION: int = 5
MAX_DECISION_BOUNDARY_RESOLUTION: int = 200

# ─── HTTP Status Codes ───────────────────────────────────────────────────────

HTTP_400_BAD_REQUEST: int = 400
HTTP_404_NOT_FOUND: int = 404
HTTP_409_CONFLICT: int = 409
HTTP_422_UNPROCESSABLE_ENTITY: int = 422
HTTP_503_SERVICE_UNAVAILABLE: int = 503
