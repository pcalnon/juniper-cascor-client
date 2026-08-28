# Reference

## juniper-cascor-client Technical Reference

**Version:** 0.1.0
**Status:** Active
**Last Updated:** March 3, 2026
**Project:** Juniper - CasCor Service Client Library

---

## Table of Contents

- [REST Client API](#rest-client-api)
- [WebSocket Clients](#websocket-clients)
- [Exception Hierarchy](#exception-hierarchy)
- [Testing Utilities](#testing-utilities)
- [Architecture Reference](#architecture-reference)
- [Directory Layout Reference](#directory-layout-reference)
- [Constants Reference](#constants-reference)
- [CI/CD Pipeline Reference](#cicd-pipeline-reference)
- [Scenario Reference](#scenario-reference)
- [Configuration Reference](#configuration-reference)
- [Environment Variables](#environment-variables)
- [Test Markers and Commands](#test-markers-and-commands)

---

## REST Client API

### Import

```python
from juniper_cascor_client import JuniperCascorClient
```

### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `base_url` | `str` | `"http://localhost:8200"` | JuniperCascor service URL |
| `timeout` | `int` | `30` | Request timeout in seconds |
| `retries` | `int` | `3` | Retry attempts for transient failures |
| `api_key` | `Optional[str]` | `None` | API key; falls back to `JUNIPER_CASCOR_API_KEY` env var |

### Context Manager

```python
with JuniperCascorClient("http://localhost:8200") as client:
    # Use client
    pass
# Session automatically closed
```

### Health and Readiness

| Method | Returns | Description |
|--------|---------|-------------|
| `health_check()` | `Dict[str, Any]` | Service health status |
| `is_alive()` | `bool` | Liveness probe; `True` if reachable |
| `is_ready()` | `bool` | Readiness probe; `True` if network loaded |
| `wait_for_ready(timeout=30.0, poll_interval=0.5)` | `bool` | Block until service ready or timeout |

### Network Lifecycle

| Method | Returns | Description |
|--------|---------|-------------|
| `create_network(**kwargs)` | `Dict[str, Any]` | Create CasCor network |
| `get_network()` | `Dict[str, Any]` | Get network state and configuration |
| `delete_network()` | `Dict[str, Any]` | Destroy current network |
| `get_topology()` | `Dict[str, Any]` | Network topology (layers, nodes, connections) |
| `get_statistics()` | `Dict[str, Any]` | Weight statistics per layer |

#### `create_network` Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `input_size` | `int` | Yes | Number of input features |
| `output_size` | `int` | Yes | Number of output classes |
| `learning_rate` | `float` | Yes | Output unit learning rate |
| `candidate_learning_rate` | `float` | No | Candidate unit learning rate |
| `max_hidden_units` | `int` | No | Maximum cascade hidden units |
| `candidate_pool_size` | `int` | No | Number of candidate units to evaluate |
| `correlation_threshold` | `float` | No | Min correlation for candidate installation |
| `patience` | `int` | No | Epochs without improvement before stopping phase |
| `candidate_epochs` | `int` | No | Max epochs for candidate training phase |
| `output_epochs` | `int` | No | Max epochs for output training phase |
| `epochs_max` | `int` | No | Global max epoch limit |

### Training Control

| Method | Returns | Description |
|--------|---------|-------------|
| `start_training(epochs=None, dataset=None, inline_data=None, params=None)` | `Dict[str, Any]` | Start asynchronous training |
| `stop_training()` | `Dict[str, Any]` | Stop training |
| `pause_training()` | `Dict[str, Any]` | Pause training |
| `resume_training()` | `Dict[str, Any]` | Resume paused training |
| `reset_training()` | `Dict[str, Any]` | Reset network and training state |

### Status and Monitoring

| Method | Returns | Description |
|--------|---------|-------------|
| `get_training_status()` | `Dict[str, Any]` | Current state, epoch, progress |
| `get_training_params()` | `Dict[str, Any]` | Active training parameters |
| `get_metrics()` | `Dict[str, Any]` | Current metrics snapshot |
| `get_metrics_history(count=None)` | `Dict[str, Any]` | Metrics history (optionally limited to last `count`) |

### Data and Visualization

| Method | Returns | Description |
|--------|---------|-------------|
| `get_dataset()` | `Dict[str, Any]` | Dataset metadata |
| `get_decision_boundary(resolution=50)` | `Dict[str, Any]` | 2D decision boundary grid (resolution 5-200) |

### Session Management

| Method | Returns | Description |
|--------|---------|-------------|
| `close()` | `None` | Close the HTTP session and release resources |

---

## WebSocket Clients

### CascorTrainingStream

Async WebSocket client for real-time training metric streaming.

```python
from juniper_cascor_client import CascorTrainingStream
```

#### Constructor

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `base_url` | `str` | `"ws://localhost:8200"` | WebSocket base URL |
| `api_key` | `Optional[str]` | `None` | API key; falls back to `JUNIPER_CASCOR_API_KEY` env var |

#### Connection Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `async connect(path="/ws/training")` | `None` | Connect to WebSocket endpoint |
| `async disconnect()` | `None` | Close connection |
| `async stream()` | `AsyncIterator[Dict]` | Async generator yielding messages |
| `async listen()` | `None` | Listen and dispatch to callbacks indefinitely |
| `async send_command(command, params=None)` | `None` | Send a control command |

#### Callback Registration

| Method | Dispatched On | Description |
|--------|---------------|-------------|
| `on_metrics(callback)` | `type: "metrics"` | Epoch metrics updates |
| `on_state(callback)` | `type: "state"` | Training state changes |
| `on_topology(callback)` | `type: "topology"` | Network topology updates |
| `on_cascade_add(callback)` | `type: "cascade_add"` | Hidden unit installation events |
| `on_event(callback)` | `type: "event"` | General events |

#### Usage Patterns

**Async iteration:**

```python
async with CascorTrainingStream("ws://localhost:8200") as stream:
    async for message in stream:
        print(message["type"], message["data"])
```

**Callback registration:**

```python
stream = CascorTrainingStream("ws://localhost:8200")
stream.on_metrics(lambda data: print(f"Loss: {data['train_loss']}"))
await stream.connect()
await stream.listen()
```

### CascorControlStream

Async WebSocket client for sending training control commands.

```python
from juniper_cascor_client import CascorControlStream
```

#### Constructor

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `base_url` | `str` | `"ws://localhost:8200"` | WebSocket base URL |
| `api_key` | `Optional[str]` | `None` | API key; falls back to `JUNIPER_CASCOR_API_KEY` env var |

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `async connect()` | `None` | Connect to `/ws/control` endpoint |
| `async disconnect()` | `None` | Close connection |
| `async command(command, params=None)` | `Dict[str, Any]` | Send command, wait for response |

#### Supported Commands

| Command | Description |
|---------|-------------|
| `"start"` | Start training |
| `"stop"` | Stop training |
| `"pause"` | Pause training |
| `"resume"` | Resume training |
| `"reset"` | Reset network and state |

---

## Exception Hierarchy

```
JuniperCascorClientError (base)
├── JuniperCascorConnectionError      # Connection to service failed
├── JuniperCascorTimeoutError         # Request timed out
├── JuniperCascorNotFoundError        # 404 - Resource not found
├── JuniperCascorConflictError        # 409 - State conflict
├── JuniperCascorValidationError      # 400/422 - Invalid parameters
└── JuniperCascorServiceUnavailableError  # 503 - Service unavailable
```

### Import

```python
from juniper_cascor_client import (
    JuniperCascorClientError,
    JuniperCascorConflictError,
    JuniperCascorConnectionError,
    JuniperCascorNotFoundError,
    JuniperCascorServiceUnavailableError,
    JuniperCascorTimeoutError,
    JuniperCascorValidationError,
)
```

### HTTP Status Code Mapping

| Status Code | Exception Raised |
|-------------|-----------------|
| 400 | `JuniperCascorValidationError` |
| 404 | `JuniperCascorNotFoundError` |
| 409 | `JuniperCascorConflictError` |
| 422 | `JuniperCascorValidationError` |
| 503 | `JuniperCascorServiceUnavailableError` |
| Connection failure | `JuniperCascorConnectionError` |
| Timeout | `JuniperCascorTimeoutError` |
| Other 4xx/5xx | `JuniperCascorClientError` |

---

## Testing Utilities

### FakeCascorClient

Drop-in replacement for `JuniperCascorClient` that simulates training in-memory. No HTTP calls are made.

```python
from juniper_cascor_client.testing import FakeCascorClient

with FakeCascorClient(scenario="two_spiral_training") as client:
    status = client.get_training_status()
    client.advance_epoch(10)
    metrics = client.get_metrics()
    print(f"Loss: {metrics['train_loss']:.4f}")
```

#### Constructor

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `scenario` | `str` | `"idle"` | Scenario preset (see [Scenario Reference](#scenario-reference)) |
| `base_url` | `str` | `"http://fake-cascor:8200"` | Fake base URL |
| `api_key` | `Optional[str]` | `None` | Unused; accepted for API compatibility |

#### Test-Only Methods

| Method | Description |
|--------|-------------|
| `advance_epoch(n=1)` | Advance training by `n` epochs, generating metrics and topology updates |
| `set_state(state)` | Force a training state (`"idle"`, `"training"`, `"paused"`, `"complete"`) |

### FakeCascorTrainingStream

Drop-in replacement for `CascorTrainingStream` for testing WebSocket consumers.

```python
from juniper_cascor_client.testing import FakeCascorTrainingStream

messages = [
    {"type": "metrics", "data": {"epoch": 1, "train_loss": 0.5}},
    {"type": "state", "data": {"state": "complete"}},
]

async with FakeCascorTrainingStream(messages=messages) as stream:
    async for msg in stream:
        print(msg["type"])
```

#### Constructor

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `messages` | `Optional[List[Dict]]` | `None` | Pre-loaded messages to deliver |
| `delay` | `float` | `0.1` | Delay in seconds between messages |
| `base_url` | `str` | `"ws://fake-cascor:8200"` | Fake base URL |
| `api_key` | `Optional[str]` | `None` | Unused; accepted for API compatibility |

#### Test-Only Methods

| Method | Description |
|--------|-------------|
| `inject_message(message)` | Add a message to the delivery queue at runtime |

---

## Architecture Reference

Relocated verbatim from `AGENTS.md` (P3 of the shared-session-memory plan) so it is read on demand rather than loaded into every session.

### Class Hierarchy

```text
JuniperCascorClient          Synchronous REST client (context manager)
  ├── Health:                health_check(), is_alive(), is_ready(), wait_for_ready()
  ├── Network:               create_network(), get_network(), delete_network(), get_topology(), get_statistics()
  ├── Training Control:      start_training(), stop_training(), pause_training(), resume_training(), reset_training()
  ├── Status & Params:       get_training_status(), get_training_params(), update_params()
  ├── Metrics:               get_metrics(), get_metrics_history()
  ├── Data & Visualization:  get_dataset(), get_dataset_data(), get_decision_boundary()
  ├── Snapshots:             list_snapshots(), get_snapshot(), save_snapshot(), load_snapshot()
  └── Workers:               list_workers(), get_worker(), get_worker_stats()

CascorTrainingStream         Async WebSocket streaming client (async context manager, async iterator)
  ├── connect(), disconnect()
  ├── stream() -> AsyncIterator
  ├── listen() (callback dispatch)
  ├── send_command()
  ├── Callbacks: on_metrics(), on_state(), on_topology(), on_cascade_add(), on_event()
  └── CL1 heartbeat + liveness: server ``{"type":"ping"}`` frames are answered
          with ``{"type":"pong"}`` and consumed (``auto_pong=True`` default;
          ``auto_pong=False`` yields pings to the consumer); liveness surface
          ``is_connected`` / ``is_alive(window_sec)`` / ``last_frame_at`` /
          ``pongs_sent`` (mirrored by FakeCascorTrainingStream).

CascorControlStream          Async WebSocket command/response client (async context manager)
  ├── connect(), disconnect()
  │       CL1: connect() starts the background recv loop eagerly so server
  │       heartbeat pings are answered from t0 (pre-0.7.0, an idle control
  │       connection was closed by cascor 40s after connect).
  ├── command(command, params=None) -> Dict
  │       Send a control command (start/stop/pause/resume/reset). Routes
  │       through the per-request correlation system whenever the background
  │       recv task is running (the normal case after connect()); the
  │       direct single-recv path remains as a fallback and skips/answers
  │       heartbeat pings. Both paths emit the canonical envelope
  │       ``{"type": "command", "command": ..., ...}`` (XREPO-07/08, CC-06).
  ├── Liveness surface: is_connected / is_alive(window_sec) / last_frame_at / pongs_sent (CL1)
  └── set_params(params, *, timeout=1.0, command_id=None) -> Dict
          Apply a runtime parameter update (e.g. ``{"learning_rate": 0.01}``)
          via /ws/control with per-request correlation by ``command_id``.
          Fails fast on timeout or disconnect with no automatic retries
          (D-20, C-04). The default 1.0 s timeout (D-01) lets callers fall
          back to a REST update without waiting indefinitely. Concurrent
          callers are bounded by ``MAX_PENDING_COMMANDS`` (256); exceeding
          the cap raises ``JuniperCascorOverloadError``.
```

### WebSocket Outbound Message Envelope

All client→server messages on `/ws/control` carry a uniform envelope so the
server can dispatch by `type` regardless of which client method produced
them (XREPO-07/08, CC-06; aligned in Phase 4D):

```json
{"type": "command", "command": "<name>", "params": {...}, "command_id": "<uuid>"}
```

`type` is always `"command"` (the constant `WS_MSG_TYPE_COMMAND_OUT`);
`params` is omitted when empty; `command_id` is present whenever per-request
correlation is in effect (`set_params()` always; `command()` only when the
correlated path is taken).

### Exception Hierarchy

```text
JuniperCascorClientError (base)
  ├── JuniperCascorConnectionError       Network/connection failures
  ├── JuniperCascorTimeoutError          Request timeout
  ├── JuniperCascorNotFoundError         HTTP 404
  ├── JuniperCascorConflictError         HTTP 409
  ├── JuniperCascorValidationError       HTTP 400/422
  └── JuniperCascorServiceUnavailableError  HTTP 503
```

#### Exception context (do not remove)

Every exception carries four attributes, set by the base `__init__`:

| Attribute | Meaning |
|-----------|---------|
| `message` | The human-readable summary; also what `str(exc)` returns. |
| `status_code` | HTTP status of the originating response, or `None` when raised without one (connection, timeout, "client is closed"). A **retry-exhausted** response now carries its real status too — see the retry note below; it used to be `None`. |
| `detail` | The server's error payload **exactly as decoded**. This service answers with two envelopes (`{"error": {"message": ...}}` and FastAPI's `{"detail": ...}`), and the latter is a `list[dict]` for a 422. Never stringified. |
| `response` | The originating `requests.Response`, when there was one. |

`status_code` is the **only** thing separating a 400 from a 422 — both raise
`JuniperCascorValidationError`. `_handle_response` used to compute the status
and then drop it on four of its five branches, which made those two responses
byte-identical (defect-register `APD-CCLIENT-004`, absorbing the retired
`APD-CCLIENT-003`).

Constraints a refactor must not break:

- **The extra parameters are keyword-only**, so the 29 single-positional-message
  raises in `FakeCascorClient` — and every consumer call site — keep working.
- **`detail` keeps the server's structure.** The message renders a 422 list as
  `body.input_size: Field required` via `client._render_error_detail`; the list
  itself stays on the attribute.
- **`__reduce__` must stay.** `BaseException.__reduce__` rebuilds from `args`,
  which holds only the message, so without it a pickle/copy round-trip returns an
  exception that looks right and has silently lost the context. That is what
  flake8-bugbear's `B042` warns about; the `noqa` on `__init__` is paired with
  `__reduce__`, not a dismissal.

`FakeCascorClient` populates `status_code` on every HTTP-shaped error it raises
(404 not-found, 409 conflict, 422 validation — the real service validates those
inputs with pydantic `Field(ge=1)` / `Query(ge=, le=)`, which FastAPI answers
422). Its one local-state error ("Client is closed") deliberately has none. The
fake claims full API parity, so a double raising the right type with
`status_code=None` would let a consumer's test pass against behaviour production
does not have.

**This mirrors `juniper-data-client` deliberately** (juniper-data-client#158 is
the reference implementation; `juniper-recurrence-client` is the third). The
three are separately released packages with no shared code, so no drift check can
enforce it — the alignment is a convention, kept by these notes and by each
package's tests.

### Testing Utilities (`juniper_cascor_client.testing`)

| Class | Purpose |
|-------|---------|
| `FakeCascorClient` | In-memory REST client fake with 5 scenarios, thread-safe, full API parity |
| `FakeCascorTrainingStream` | In-memory WebSocket stream fake with message injection |

**Scenarios**: `idle`, `two_spiral_training`, `xor_converged`, `empty`, `error_prone`

### Key Design Patterns

- **Context Manager**: REST client (sync `with`), WebSocket clients (async `async with`)
- **Callback/Observer**: WebSocket training stream dispatches to registered callbacks by message type
- **Async Iteration**: `async for message in stream.stream():`
- **Retry with Backoff**: HTTP adapter retries `RETRYABLE_STATUS_CODES` (429 / 502 / 503 / 504) with
  0.5s exponential backoff (3 retries by default). **`raise_on_status=False` is load-bearing — do not
  drop it.** urllib3 defaults it to `True`, which makes an exhausted retry raise `MaxRetryError`;
  requests surfaces that as `RetryError`, a plain `RequestException`, which `_request`'s generic
  handler flattens into `JuniperCascorClientError` *before* `_handle_response` can classify it. That
  is what made the 503 arm — and therefore `JuniperCascorServiceUnavailableError` — unreachable in
  every client built with retries (defect-register `APD-CCLIENT-002`). With it `False` the retries
  are unchanged; only the give-up path differs, returning the final response so a 503 that outlives
  its retries raises the typed error with `status_code=503`, and 429/502/504 keep their real status.
  Transport failures (refused connection, DNS, timeout) never produce a response and are unaffected.
  Pinned by `tests/test_client.py::TestRetryExhaustionSurfacesTypedStatus`, which deliberately uses a
  **retrying** client — every older 503 test mounts `HTTPAdapter(max_retries=0)` first, which is why
  the dead branch went unnoticed: the coverage proved the branch worked under a configuration
  production never uses.
- **Connection Pooling**: 10 max connections per host via `HTTPAdapter`
- **Response Envelope**: All responses wrapped as `{"status": "success", "data": {...}, "meta": {...}}`
- **State Machine**: FakeCascorClient implements training state transitions (idle -> training -> paused -> complete)
- **Scenario-Driven Testing**: Configurable scenarios generate realistic metric curves, topologies, and datasets

---

---

## Directory Layout Reference

Relocated verbatim from `AGENTS.md` (P3 of the shared-session-memory plan) so it is read on demand rather than loaded into every session.

```text
juniper-cascor-client/
├── juniper_cascor_client/           # Main package
│   ├── __init__.py                  # Public API exports, version (0.3.0)
│   ├── client.py                    # JuniperCascorClient (REST, 353 lines)
│   ├── constants.py                 # Endpoint paths, header names, defaults, scenario constants
│   ├── ws_client.py                 # CascorTrainingStream, CascorControlStream (212 lines)
│   ├── exceptions.py                # Exception hierarchy (43 lines)
│   ├── py.typed                     # PEP 561 marker
│   └── testing/                     # Testing utilities submodule
│       ├── __init__.py              # Exports FakeCascorClient, FakeCascorTrainingStream
│       ├── fake_client.py           # In-memory fake REST client (1003 lines)
│       ├── fake_ws_client.py        # In-memory fake WebSocket client (222 lines)
│       └── scenarios.py             # Scenario data, curve generators (554 lines)
├── tests/                           # Test suite
│   ├── conftest.py                  # Pytest fixtures (5 scenario fixtures)
│   ├── test_client.py               # REST client unit tests
│   ├── test_client_update_params.py # Parameter update tests
│   ├── test_fake_client.py          # FakeCascorClient comprehensive tests
│   ├── test_fake_client_update_params.py  # Fake client param update tests
│   ├── test_fake_client_workers.py  # Worker/async tests
│   ├── test_fake_ws_client.py       # FakeCascorTrainingStream tests
│   └── test_ws_client.py            # WebSocket client tests
├── docs/                            # User documentation
│   ├── DOCUMENTATION_OVERVIEW.md    # Documentation index and navigation
│   ├── REFERENCE.md                 # Complete API reference
│   ├── QUICK_START.md               # Getting started guide
│   └── DEVELOPER_CHEATSHEET.md      # Developer quick reference
├── notes/                           # Procedures and templates
│   ├── WORKTREE_SETUP_PROCEDURE.md
│   ├── WORKTREE_CLEANUP_PROCEDURE_V2.md
│   ├── THREAD_HANDOFF_PROCEDURE.md
│   ├── CONDA_DEPENDENCY_FILE_HEADER.md
│   ├── PIP_DEPENDENCY_FILE_HEADER.md
│   ├── juniper-cascor-client_OTHER_DEPENDENCIES.md
│   └── history/                     # Archived procedures
│       └── WORKTREE_CLEANUP_PROCEDURE_V1.md
├── scripts/                         # Utility scripts
│   ├── check_doc_links.py           # Documentation link validator
│   └── generate_dep_docs.sh         # Dependency doc generator (conf/*.txt, conf/*.yaml)
├── .github/
│   ├── CODEOWNERS                   # Code ownership (@pcalnon)
│   ├── dependabot.yml               # Automated dependency updates (weekly)
│   └── workflows/
│       ├── ci.yml                   # CI/CD pipeline (pre-commit, tests, build, security)
│       └── publish.yml              # PyPI/TestPyPI publishing
├── conf/                            # Generated dependency documentation (created by scripts/generate_dep_docs.sh, gitignored)
├── AGENTS.md                        # This file
├── CLAUDE.md                        # Symlink -> AGENTS.md
├── CHANGELOG.md                     # Version history
├── README.md                        # PyPI/GitHub landing page
├── LICENSE                          # MIT License
├── pyproject.toml                   # Package configuration
├── .pre-commit-config.yaml          # Pre-commit hooks
├── .env.example                     # Environment variable template
├── .sops.yaml                       # SOPS encryption config for .env files
├── .markdownlint.yaml               # Markdown linting rules
└── .gitignore
```

---

---

## Constants Reference

Relocated verbatim from `AGENTS.md` (P3 of the shared-session-memory plan) so it is read on demand rather than loaded into every session.

Every previously inline literal in `client.py`, `ws_client.py`, `testing/fake_client.py`, and `testing/scenarios.py` is now centralized in `juniper_cascor_client/constants.py`. Application code imports from this module rather than embedding literals.

### Categories

| Prefix / Group | Examples | Purpose |
|----------------|----------|---------|
| `API_KEY_*`, `API_VERSION_*` | `API_KEY_HEADER_NAME='X-API-Key'`, `API_KEY_ENV_VAR='JUNIPER_CASCOR_API_KEY'`, `API_VERSION_PATH='/v1'` | Wire-protocol identifiers shared with the `juniper-cascor` server |
| `ENDPOINT_*`, `WS_*_PATH` | `ENDPOINT_TRAINING_START='/training/start'`, `ENDPOINT_NETWORK_TOPOLOGY='/network/topology'`, `WS_TRAINING_PATH='/ws/training'` | Relative paths under each FastAPI router (server prefix + this constant = full URL) |
| `DEFAULT_*` | `DEFAULT_BASE_URL='http://localhost:8200'`, `DEFAULT_TIMEOUT_SECONDS`, `DEFAULT_BACKOFF_FACTOR=0.5` | Constructor defaults for `JuniperCascorClient` and `CascorTrainingStream` / `CascorControlStream` |
| `MSG_TYPE_*` | `MSG_TYPE_HEARTBEAT='heartbeat'`, `MSG_TYPE_REGISTRATION_ACK` | WebSocket message-type discriminators (must remain bit-identical to the server's `MessageType` enum) |
| Scenario / generator defaults | `SCENARIO_*`, fake-client tuning | Default values used by `testing/fake_client.py` and `testing/scenarios.py` to keep fakes deterministic |

### Alignment with `juniper-cascor`

- `API_KEY_HEADER_NAME` matches the literal `"X-API-Key"` checked by `juniper-cascor/src/api/security.py`.
- All `ENDPOINT_*` paths equal the relative routes declared on the corresponding `APIRouter` in `juniper-cascor/src/api/routes/`.
- `MSG_TYPE_*` values are bit-identical to the cascor server's `MessageType(StrEnum)` in `src/api/workers/protocol.py`. Wave 5 verified this with a programmatic comparison and the cascor-worker package shares the same set under `MSG_TYPE_*` names.

### Modifying

When the cascor server adds or renames an endpoint, header, or wire-protocol message type:

1. Update the constant in `constants.py` first (with a docstring noting cross-repo coupling)
2. Update the corresponding consumer in `client.py` / `ws_client.py` / `testing/`
3. Run the cross-repo alignment check from the project roadmap before merging

---

---

## CI/CD Pipeline Reference

Relocated verbatim from `AGENTS.md` (P3 of the shared-session-memory plan) so it is read on demand rather than loaded into every session.

### GitHub Actions Workflows

#### `ci.yml` — Main Pipeline

**Triggers**: push (main, develop, feature/\*\*, fix/\*\*), pull requests, workflow_dispatch

| Job | Matrix | Purpose |
|-----|--------|---------|
| **pre-commit** | Python 3.11, 3.12, 3.13 | All pre-commit hooks |
| **docs** | Single run | Documentation link validation |
| **unit-tests** | Python 3.11, 3.12, 3.13 | pytest with 80% coverage gate |
| **build** | Single run | sdist + wheel + twine check |
| **dependency-docs** | Single run | Generate conf/ files |
| **security** | Single run | Gitleaks, Bandit SARIF, pip-audit |
| **required-checks** | Aggregator | Quality gate (all jobs must pass) |
| **notify-downstream** | Main branch only | Triggers juniper-canopy CI via repository dispatch |

#### `publish.yml` — PyPI Publishing

**Trigger**: GitHub release published

1. Build and publish to TestPyPI, verify installation
2. Build and publish to production PyPI (trusted publishing / OIDC)

#### `sequence-safety.yml` — Per-PR Sequence-Safety Net (Advisory)

**Trigger**: pull requests (main, develop)

Advisory, standalone — never a required check and never wired into the CI Quality Gate. Runs the shared `juniper-ci-tools` (`>=0.8.0,<0.9.0`) sequence-safety screens over the PR's `base..HEAD` so silent compositional losses are visible at review:

- **symbol-loss screen** (`juniper-symbol-loss-check`, scoped `juniper_cascor_client/**/*.py` + `tests/**/*.py`) — FAILs on a silently deleted / gutted / duplicated `def` / `class` / method.
- **docs deletion-magnitude screen** (`juniper-docs-additions-check`, universal docs scope) — FAILs on a deleted heading or a run of consecutive deleted lines.

Both JSON reports upload as the `sequence-safety-report` artifact. An owner label hatch (`allow-symbol-loss` / `docs-rewrite`) demotes a screen to WARN-only; the `Allow-Symbol-Loss:` / `Allow-Docs-Rewrite:` commit trailers are the primary enumerated waivers.

#### `main-verify.yml` — Post-Merge Verification Net

**Trigger**: push (main), workflow_dispatch

Bypass-proof post-merge net: re-runs the two sequence-safety screens (same package + scope) against a catch-up base (the last successful `main-verify` tip, so a `[skip ci]` window is swept on the next run) after every merge to `main`. Per-SHA concurrency (`cancel-in-progress: false`) verifies every merge even during a storm; on failure it upserts a single stable-title tracking issue per red streak. Screens-only (no regression battery in this wave).

### Security Scanning

| Tool | Purpose | Integration |
|------|---------|-------------|
| **Gitleaks** | Secrets detection in git history | CI job |
| **Bandit** | Python SAST (SARIF upload to GitHub Security) | CI job + pre-commit |
| **pip-audit** | Dependency vulnerability scanning | CI job |
| **SOPS** | Age encryption for .env files | Pre-commit hook blocks unencrypted .env |

---

### PR base-branch guard (required check)

`.github/workflows/pr-base-branch-guard.yml` fails any PR whose base branch is not the
default branch. Its job name -- **`Guard PR base branch`** -- is a **required status check**
in this repo's ruleset, so renaming the job or deleting the file makes `main` unmergeable
until the context is un-required first.

**What it protects against.** A PR based on another feature branch can squash-merge into
that branch, stranding its content off `main` behind a green **MERGED** badge. It has
happened three times in this ecosystem (`juniper-recurrence#7`/`#8`, `juniper-canopy#365`).

**Why it matters more than it looks.** Both rulesets here are scoped to `~DEFAULT_BRANCH`, so
a PR whose base is a feature branch is governed by **no ruleset at all** -- it has zero
required status checks and merges clean with nothing having run:

```bash
gh api repos/pcalnon/<repo>/rules/branches/feature%2Fanything --jq length   # -> 0
gh api repos/pcalnon/<repo>/rules/branches/main               --jq length   # -> 9
```

This workflow carries no `branches:` filter, so it is the **only** check that runs on such a
PR. It cannot block the merge there -- no ruleset applies -- but it turns a silent merge into
a visibly red one.

**If it fails.** Re-open the work against the default branch. The house practice is
**close and re-open** a fresh PR titled `[retarget #NNN]`. Retargeting in place is *not*
sufficient on its own: every `ci*.yml` here uses the default `pull_request` types
`[opened, synchronize, reopened]`, which exclude `edited`, so a retarget re-runs this guard
and nothing else -- the PR stays blocked on its other required contexts until a push or a
close/re-open.

**`stacked-pr` label.** Silences this guard for a deliberate stack. It does **not** make the
PR mergeable into `main`, and it does **not** re-land the stack -- do that separately.

Rollout and rationale: [juniper-ml#434](https://github.com/pcalnon/juniper-ml/issues/434).

---

## Scenario Reference

### Available Scenarios (FakeCascorClient)

| Scenario | State | Network | Description |
|----------|-------|---------|-------------|
| `"idle"` | idle | None | No network loaded; ready for creation |
| `"two_spiral_training"` | training | 2-in, 1-out | Active training with realistic metric curves |
| `"xor_converged"` | complete | 2-in, 1-out, 2 hidden | Fully trained network with static metrics |
| `"empty"` | idle | None | Minimal responses for negative testing |
| `"error_prone"` | idle | None | Raises exceptions on ~10% of calls |

### Metric Curves (two_spiral_training)

- **Loss**: Exponential decay from ~2.5, noise scale 0.02
- **Accuracy**: Sigmoid curve, midpoint epoch 40, ceiling 0.98
- **Validation loss**: Training loss * 1.15 gap factor
- **Hidden units**: +1 every 20 epochs (max 8)
- **Phases**: Alternate between `"output_training"` and `"candidate_training"`

### State Transitions

```
idle ──create_network──> idle
idle ──start_training──> training
training ──pause──> paused
training ──stop──> idle
training ──(complete)──> complete
paused ──resume──> training
paused ──stop──> idle
complete ──reset──> idle
```

---

## Configuration Reference

### HTTP Behavior

- **Retried status codes:** 502, 504
- **Backoff factor:** 0.5 (exponential)
- **Connection pooling:** 10 max pool size
- **API prefix:** All REST requests target `/v1/` endpoints

### WebSocket Endpoints

| Endpoint | Client | Purpose |
|----------|--------|---------|
| `/ws/training` | `CascorTrainingStream` | Real-time metrics, state, topology events |
| `/ws/control` | `CascorControlStream` | Send training commands (start/stop/pause/resume/reset) |

### WebSocket Message Types

| Type | Source | Description |
|------|--------|-------------|
| `"metrics"` | Training stream | Epoch metrics (loss, accuracy, correlation, phase) |
| `"state"` | Training stream | Training state change |
| `"topology"` | Training stream | Network topology update |
| `"cascade_add"` | Training stream | Hidden unit installed |
| `"event"` | Training stream | General training event |
| `"connection_established"` | Control stream | Initial handshake on connect |
| `"command_response"` | Control stream | Response to a sent command |

---

## Environment Variables

| Variable | Purpose | Used By |
|----------|---------|---------|
| `JUNIPER_CASCOR_API_KEY` | API key for authentication (fallback if not passed to constructor) | All three clients |
| `CASCOR_SERVICE_URL` | Service URL used by consuming applications (not read by client directly) | juniper-canopy, juniper-deploy |

---

## Test Markers and Commands

### Running Tests

```bash
pytest tests/ -v                    # All tests
pytest tests/ -m unit -v            # Unit tests only
pytest tests/ --cov=juniper_cascor_client --cov-report=term-missing --cov-fail-under=80
```

### Test Files

| File | Purpose |
|------|---------|
| `tests/test_client.py` | REST client unit tests |
| `tests/test_ws_client.py` | WebSocket client unit tests |
| `tests/test_fake_client.py` | FakeCascorClient tests |
| `tests/test_fake_ws_client.py` | FakeCascorTrainingStream tests |
| `tests/conftest.py` | Shared fixtures |

### Quality Checks

```bash
mypy juniper_cascor_client --strict    # Type checking
flake8 juniper_cascor_client           # Linting
black --check juniper_cascor_client    # Format check
isort --check-only juniper_cascor_client  # Import order
```

---

**Last Updated:** March 3, 2026
**Version:** 0.1.0
**Maintainer:** Paul Calnon
