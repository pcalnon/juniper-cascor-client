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
Version: 0.3.0
License: MIT License
"""

from typing import List

# ─── Service Configuration ───────────────────────────────────────────────────

DEFAULT_BASE_URL: str = "http://localhost:8200"
DEFAULT_WS_BASE_URL: str = "ws://localhost:8200"
API_VERSION_PATH: str = "/v1"

# ─── HTTP Configuration ──────────────────────────────────────────────────────

DEFAULT_REQUEST_TIMEOUT: int = 30
DEFAULT_RETRY_COUNT: int = 3
DEFAULT_BACKOFF_FACTOR: float = 0.5
# XREPO-02 / CC-02 (2026-04-24): 503 is the canonical transient error
# emitted by services during restart / deploy; 429 (Too Many Requests)
# is also safe to retry when the server sets Retry-After. Both were
# previously missing from the retry list, causing short outages to
# bubble up as hard failures to callers.
RETRYABLE_STATUS_CODES: List[int] = [429, 502, 503, 504]
RETRY_ALLOWED_METHODS: List[str] = ["GET", "POST", "DELETE", "PUT", "PATCH"]
DEFAULT_POOL_MAXSIZE: int = 10

# ─── Readiness Polling ───────────────────────────────────────────────────────

DEFAULT_READY_TIMEOUT: float = 30.0
DEFAULT_READY_POLL_INTERVAL: float = 0.5

# ─── Authentication ──────────────────────────────────────────────────────────

API_KEY_HEADER_NAME: str = "X-API-Key"
API_KEY_ENV_VAR: str = "JUNIPER_CASCOR_API_KEY"

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

# Server-emitted control-stream handshake message type.
WS_MSG_TYPE_CONNECTION_ESTABLISHED: str = "connection_established"

# Server-emitted command response (echoes command_id for correlation).
WS_MSG_TYPE_COMMAND_RESPONSE: str = "command_response"

# ─── WebSocket set_params Defaults ──────────────────────────────────────────

DEFAULT_SET_PARAMS_TIMEOUT: float = 1.0  # D-01: fail fast to REST fallback
MAX_PENDING_COMMANDS: int = 256

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
