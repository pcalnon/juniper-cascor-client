# Reference

## juniper-cascor-client Technical Reference

**Version:** 0.1.5
**Status:** Active
**Last Updated:** November 15, 2026
**Project:** Juniper - CasCor Service Client Library

---

## Table of Contents

- [REST Client API](#rest-client-api)
- [Base URL normalisation](#base-url-normalisation-apd-cclient-005)
- [WebSocket Clients](#websocket-clients)
- [Exception Hierarchy](#exception-hierarchy)
- [Testing Utilities](#testing-utilities)
- [Architecture Reference](#architecture-reference)
- [Directory Layout Reference](#directory-layout-reference)
- [Constants Reference](#constants-reference)
- [CI/CD Pipeline Reference](#cicd-pipeline-reference)
- [Claude Code workflow](#claude-code-workflow-claudeyml)
- [Secret scan (Gitleaks)](#secret-scan-gitleaks)
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
| `base_url` | `str` | `"http://localhost:8200"` | Service origin. After APD-CCLIENT-005 ([#129](https://github.com/pcalnon/juniper-cascor-client/pull/129)) this is normalised — see [Base URL normalisation](#base-url-normalisation-apd-cclient-005). Do not include `/v1`. |
| `timeout` | `int` | `30` | Request timeout in seconds |
| `retries` | `int` | `3` | Retry attempts for transient failures |
| `api_key` | `Optional[str]` | `None` | API key; falls back to `JUNIPER_CASCOR_API_KEY` env var |

### Base URL normalisation (APD-CCLIENT-005)

`JuniperCascorClient` builds every REST path as `api_url = f"{base_url}/v1"`. A schemeless host, a `/v1`-suffixed origin, or a hostless value used to construct silently and fail opaquely on the first request. [#129](https://github.com/pcalnon/juniper-cascor-client/pull/129) ports `_normalize_url` from the sibling clients (juniper-recurrence-client is the reference; the same host guard is `APD-DCLIENT-004` in juniper-data-client). Two hardenings beyond that port, both from a confirmed review finding on #129:

- Scheme matching is **case-insensitive** (RFC 3986 §3.1). A case-sensitive `startswith` would re-prefix `HTTPS://host` into `http://HTTPS://host` — a silent TLS downgrade that sends `X-API-Key` over HTTP to hostname `https`.
- The host guard reads `parsed.hostname`, not `netloc`. `netloc` is truthy for a userinfo-only authority (`http://user:secret@`) while `hostname` is `None`.

`__init__` runs these steps in order:

1. Strip surrounding whitespace.
2. If the value does not **case-insensitively** start with `http://` or `https://` (`url.lower().startswith(URL_SCHEME_PREFIXES)`), prefix `http://` (`DEFAULT_URL_SCHEME_PREFIX`).
3. Parse with `urllib.parse.urlparse`. An empty `hostname` raises `JuniperCascorConfigurationError` (`base_url must include a host; got ...`). The typed error subclasses `JuniperCascorClientError` and carries no HTTP `status_code` — there was no response.
4. Rebuild as `f"{parsed.scheme}://{parsed.netloc}{parsed.path}"` (so `urlparse`'s lowercased scheme is what is stored) and drop a trailing slash.
5. If the remaining URL ends with `/v1` (`API_VERSION_PATH`), strip that suffix so `api_url` is not `/v1/v1`.

Pinned by `tests/test_client.py::TestClientInit`:

| Input | Stored `base_url` | `api_url` |
|-------|-------------------|-----------|
| `"example.com:9000"` | `http://example.com:9000` | `http://example.com:9000/v1` |
| `"http://example.com:9000/v1"` | `http://example.com:9000` | `http://example.com:9000/v1` |
| `"  http://example.com:9000  "` | `http://example.com:9000` | `http://example.com:9000/v1` |
| `"https://example.com:9000"` | `https://example.com:9000` (`https` kept) | `https://example.com:9000/v1` |
| `"HTTPS://example.com:9000"` | `https://example.com:9000` (canonical; not `http://HTTPS://...`) | `https://example.com:9000/v1` |
| `"Http://example.com:9000"` | `http://example.com:9000` | `http://example.com:9000/v1` |
| `"http://example.com:9000/"` | `http://example.com:9000` | `http://example.com:9000/v1` |
| `""`, `"   "`, `"http://"`, `"https://"`, `"/v1"`, `"http:///v1"`, `"http://user:secret@"` | raises `JuniperCascorConfigurationError` (also catchable as the base) | — |

**Not covered by `_normalize_url` (deliberate):**

- `CascorTrainingStream` and `CascorControlStream` still `rstrip("/")` only. The `ws://` scheme family needs its own defaulting rules; #129 records this as out of scope.
- `FakeCascorClient` and `FakeCascorTrainingStream` still `rstrip("/")` only. A test that expects the hostless typed error or a repaired `/v1` `api_url` will pass against the real REST client after #129 and **not** against the fake. Do not pin this contract on the fake.

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
| `base_url` | `str` | `"ws://localhost:8200"` | WebSocket origin. Trailing slash stripped only — no HTTP-style scheme default, host check, or `/v1` strip (APD-CCLIENT-005 left the `ws://` family out of scope). |
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
| `base_url` | `str` | `"ws://localhost:8200"` | WebSocket origin. Trailing slash stripped only — same out-of-scope note as `CascorTrainingStream`. |
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
├── JuniperCascorConnectionError           # Connection to service failed
├── JuniperCascorTimeoutError              # Request timed out
├── JuniperCascorNotFoundError             # 404 - Resource not found
├── JuniperCascorConflictError             # 409 - State conflict
├── JuniperCascorValidationError           # 400/422 - Invalid parameters
├── JuniperCascorServiceUnavailableError   # 503 - Service unavailable
├── JuniperCascorOverloadError             # Control-stream pending-command cap (256)
└── JuniperCascorConfigurationError        # Invalid client config (hostless base_url); lands with #129
```

`JuniperCascorOverloadError` is already on main (`CascorControlStream` raises it when pending commands exceed `MAX_PENDING_COMMANDS`). `JuniperCascorConfigurationError` is the APD-CCLIENT-005 sibling-alignment type; until [#129](https://github.com/pcalnon/juniper-cascor-client/pull/129) merges it is not importable.

### Import

```python
from juniper_cascor_client import (
    JuniperCascorClientError,
    JuniperCascorConfigurationError,  # after #129
    JuniperCascorConflictError,
    JuniperCascorConnectionError,
    JuniperCascorNotFoundError,
    JuniperCascorOverloadError,
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
| Construction, hostless `base_url` (no HTTP) | `JuniperCascorConfigurationError` (after #129) |
| Control WS pending-command cap (no HTTP) | `JuniperCascorOverloadError` |

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
| `base_url` | `str` | `"http://fake-cascor:8200"` | Fake origin. **rstrip-only** — no scheme default, host check, or `/v1` strip. Do not use the fake to pin APD-CCLIENT-005. |
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
| `base_url` | `str` | `"ws://fake-cascor:8200"` | Fake origin. **rstrip-only**, matching the real WS constructors. |
| `api_key` | `Optional[str]` | `None` | Unused; accepted for API compatibility |

#### Test-Only Methods

| Method | Description |
|--------|-------------|
| `inject_message(message)` | Add a message to the delivery queue at runtime |

---

## Test Organization Reference

Relocated verbatim from `AGENTS.md` (P3 of the shared-session-memory plan) so it is read on demand rather than loaded into every session.

### Structure

- **Framework**: pytest with strict markers
- **Coverage requirement**: 80% (branch coverage enabled)
- **Timeout**: 30 seconds per test
- **Markers**: `unit`, `integration`

### Fixtures (conftest.py)

| Fixture | Scenario | Description |
|---------|----------|-------------|
| `fake_idle` | `idle` | Ready for network creation |
| `fake_training` | `two_spiral_training` | Active training with realistic metric curves |
| `fake_converged` | `xor_converged` | Fully trained network |
| `fake_empty` | `empty` | Minimal responses (negative testing) |
| `fake_error` | `error_prone` | ~10% random error rate |

### Test Files

| File | Coverage |
|------|----------|
| `test_client.py` | REST client methods (mocked HTTP via `responses`) |
| `test_client_update_params.py` | Runtime parameter update method |
| `test_ws_client.py` | WebSocket client connect/stream/disconnect |
| `test_fake_client.py` | FakeCascorClient all methods, scenarios, state machine |
| `test_fake_client_update_params.py` | FakeCascorClient parameter updates |
| `test_fake_client_workers.py` | FakeCascorClient worker endpoints |
| `test_fake_ws_client.py` | FakeCascorTrainingStream message injection, callbacks |

---

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

## Linting and Formatting Reference

Relocated verbatim from `AGENTS.md` (P3 of the shared-session-memory plan) so it is read on demand rather than loaded into every session.

All tools use the **Juniper ecosystem standard line length of 512**.

| Tool | Config Location | Key Settings |
|------|-----------------|--------------|
| **black** | `pyproject.toml` | line-length=512, target py311/py312/py313 |
| **isort** | `pyproject.toml` | profile=black, line-length=512 |
| **flake8** | `.pre-commit-config.yaml` | max-line-length=512, max-complexity=15 (source) / 25 (tests) |
| **mypy** | `pyproject.toml` | strict=true, python_version=3.11, ignore_missing_imports=false |
| **bandit** | `.pre-commit-config.yaml` | Strict for source, relaxed for tests (allows assert, hardcoded values) |
| **markdownlint** | `.markdownlint.yaml` | line-length=512, excludes CHANGELOG.md/notes/docs |
| **shellcheck** | `.pre-commit-config.yaml` | severity=warning |
| **yamllint** | `.pre-commit-config.yaml` | relaxed config |

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

**Triggers**: push (main, develop), pull requests (main, develop), workflow_dispatch

| Job | Matrix | Purpose |
|-----|--------|---------|
| **pre-commit** | Python 3.11, 3.12, 3.13 | All pre-commit hooks |
| **docs** | Single run | Documentation link validation |
| **unit-tests** | Python 3.12, 3.13, 3.14 on Ubuntu; 3.12 on macOS; 3.15 on Ubuntu (informational, never blocks) | pytest with 80% coverage gate |
| **build** | Single run | sdist + wheel + twine check |
| **dependency-docs** | Single run | Generate conf/ files |
| **security** | Single run | Gitleaks (see [Secret scan (Gitleaks)](#secret-scan-gitleaks)), Bandit SARIF, pip-audit |
| **required-checks** | Aggregator | Quality gate (all jobs must pass) |
| **notify-downstream** | Main branch only | Triggers juniper-canopy CI via repository dispatch |

#### `publish.yml` — PyPI Publishing

**Trigger**: GitHub release published

1. Build and publish to TestPyPI, verify installation
2. Build and publish to production PyPI (trusted publishing / OIDC)

#### `sequence-safety.yml` — Per-PR Sequence-Safety Net (Required)

**Trigger**: pull requests (main, develop)

Required, standalone. The job publishes the status check **`Sequence Safety`**, and ruleset `juniper-cascor-client-rules` (id `13490605`) requires that context on the default branch, so a red run blocks merge into `main`. Runs the shared `juniper-ci-tools` (`>=0.9.0,<0.10.0`) sequence-safety screens over the PR's `base..HEAD` so silent compositional losses are visible at review:

- **symbol-loss screen** (`juniper-symbol-loss-check`, scoped `juniper_cascor_client/**/*.py` + `tests/**/*.py`) — FAILs on a silently deleted / gutted / duplicated `def` / `class` / method.
- **docs deletion-magnitude screen** (`juniper-docs-additions-check`, universal docs scope) — FAILs on a deleted heading or a run of consecutive deleted lines.

**Quality Gate and the ruleset are different levers.** `sequence-safety.yml` is its own workflow, so its job is not in `ci.yml`'s Quality Gate (`required-checks`) `needs:` — a `needs:` entry can only name a job in the same workflow. A green Quality Gate therefore does not mean the PR is mergeable. Being required is a ruleset property; read the ruleset when this page and a workflow header disagree:

```bash
gh api repos/pcalnon/juniper-cascor-client/rulesets/13490605 \
  --jq '.rules[] | select(.type=="required_status_checks") | .parameters.required_status_checks[].context'
```

Both JSON reports upload as the `sequence-safety-report` artifact. An owner label hatch (`allow-symbol-loss` / `docs-rewrite`) demotes that screen to WARN-only (`--advisory`: findings still print, exit `0`), which greens the required context for that PR; it does not clear the post-merge net.
The `Allow-Symbol-Loss:` / `Allow-Docs-Rewrite:` commit trailers are the primary enumerated waivers and the only ones `main-verify.yml` honours — on a squash merge, carry them into the squash commit message, because that commit is what it screens on `main`.

#### `main-verify.yml` — Post-Merge Verification Net

**Trigger**: push (main), workflow_dispatch

Bypass-proof post-merge net: re-runs the two sequence-safety screens (same package + scope) against a catch-up base after every merge to `main`, so a `[skip ci]` window is swept on the next run. The base is the `head_sha` of the newest of the last 20 completed `main-verify` runs whose `Assert screens reached a verdict` step succeeded, when it is an ancestor of `HEAD` (a run with a finding counts: its window was screened); else the last successful run's, then `github.event.before`, then `HEAD^1`. Per-SHA concurrency (`cancel-in-progress: false`) verifies every merge even during a storm; on failure it upserts a single stable-title tracking issue per red streak. Screens-only (no regression battery in this wave).

#### Claude Code workflow (`claude.yml`)

`.github/workflows/claude.yml` is the fleet `@claude` assistant for this repo.
The file header says it is a drop-in copy of `juniper-ml/.github/workflows/claude.yml`.
The job grants `contents: write`, `pull-requests: write`, `issues: write`, `id-token: write`, and `actions: read`.
Checkout uses `fetch-depth: 1`.
The only action input is `anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}`.
The header names it as a repository secret.
This repository is owned by a user account, so no organization secret reaches it: `ANTHROPIC_API_KEY` has to be a repository secret, and without it a run that gets past the trigger check fails at authentication. List the secret names with `gh api repos/pcalnon/juniper-cascor-client/actions/secrets --jq '.secrets[].name'`.
The live action pin is the `# vX.Y.Z` comment on the `uses:` line.

**What starts the job.** Four events are listened for. The job `if` uses GitHub's `contains`, which ignores case:

| Event | Job runs when |
|-------|----------------|
| `issue_comment` (`created`) | Comment body contains `@claude` |
| `pull_request_review_comment` (`created`) | Comment body contains `@claude` |
| `pull_request_review` (`submitted`) | Review body contains `@claude` |
| `issues` (`opened` or `assigned`) | Issue title or body contains `@claude` |

**What does not start the job.**

- `@claude` in a pull request title or body. `pull_request` is not an event on this workflow.
- The label `claude`. `issues: [labeled]` is not an event here, and `label_trigger` is left at the action default.
- Assigning an issue, by itself. `assigned` starts the job only when the title or body already contains `@claude`.

Case is not one of the gates: `@Claude` and `@CLAUDE` start the job, and the action's phrase check below ignores case too.

**Second gate, inside the action.** Write access is checked first.
The actor's collaborator permission must be `admin` or `write`.
Otherwise the step throws `Actor does not have write permissions to the repository` and the job fails.
A login ending in `[bot]` passes this check without a permission lookup.
A non-user whose lookup fails with `is not a user` is allowed only when `allowed_bots` lists them.
This workflow leaves `allowed_bots` empty, so that lookup returns false and the job fails with the same write-permission error.

If write access passes, the action looks for `@claude` with a case-insensitive match preceded by the start of the text or whitespace, and followed by whitespace, the end of the text, or one of `.,!?;:`. A miss logs `No trigger found, skipping remaining steps` and the step returns success: the job is green and Claude does not run. Two common misses:

- An `assigned` event whose title or body contains `@claude`. The workflow `if` matched, but the action reads the title and body only on `opened`, and `assignee_trigger` is unset, so the assignee check cannot succeed.
- A substring such as `@claude-code-action`. Workflow `contains` starts the job; the action's boundary check does not treat `-` as the end of the phrase.

When the phrase matches, tag mode requires a human actor. With `allowed_bots` empty, a non-User fails the job with `Workflow initiated by non-human actor:`.

**Where a commit lands.** An open pull request is checked out on its head branch. A fork pull request is fetched as `refs/pull/<n>/head`. This workflow's checkout is shallow, so that fetch uses depth `max(pull request commit count, 20)`. An issue, or a closed or merged pull request, creates `claude/issue-<n>-<YYYYMMDD-HHmm>` or `claude/pr-<n>-<YYYYMMDD-HHmm>` from the default branch (lowercase, 50-character cap, runner clock — UTC on `ubuntu-latest`).

**Dependabot.** The `github-actions` updates in `.github/dependabot.yml` group only `github/codeql-action*`. `anthropics/claude-code-action` is ungrouped, so each pin bump is its own pull request. That bump changes the `uses:` SHA and the version comment. It does not change the events, the job `if`, the permissions, or the `with:` inputs above.

### Security Scanning

| Tool | Purpose | Integration |
|------|---------|-------------|
| **Gitleaks** | Secrets detection in git history | CI job `security`; see [Secret scan (Gitleaks)](#secret-scan-gitleaks) |
| **Bandit** | Python SAST (SARIF upload to GitHub Security) | CI job + pre-commit |
| **pip-audit** | Dependency vulnerability scanning | CI job |
| **SOPS** | Age encryption for .env files | Pre-commit hook blocks unencrypted .env |

### Secret scan (Gitleaks)

Gitleaks runs in one place, the `security` job (`Security Scans`, a required check in ruleset `juniper-cascor-client-rules`) of `.github/workflows/ci.yml`. The weekly `security-scan.yml` and pre-commit do not run it. The engine is gitleaks **8.24.3** on every event. It loads this repository's `.gitleaks.toml`, which extends the built-in ruleset (`[extend] useDefault = true`) and adds a top-level allowlist: `tests/*.py`, `juniper_cascor_client/testing/*.py`, and values shaped like `test-key-123` (validation finding V22). The job log says so on every run: `using existing gitleaks config .gitleaks.toml from (--source)/.gitleaks.toml`, then `extending config with default config`. There is no `.gitleaksignore`.

| Event | Step | What is scanned |
|-------|------|-----------------|
| `push` to `main` / `develop` | `gitleaks/gitleaks-action` at `e0c47f4f8be36e29cdc102c57e68cb5cbf0e8d1e` (v3.0.0) | `--no-merges --first-parent <first>^..<last>` across the push payload's commits, `git log -1` when the payload holds one commit, and nothing when it holds none |
| `workflow_dispatch` | The same action | No `--log-opts`, so gitleaks runs `git log -p -U0 --full-history --all`: every commit reachable from every branch and tag of the `fetch-depth: 0` checkout |
| `pull_request` | `Install Gitleaks (pull request)`, then `Run Gitleaks over the pull request (Secrets Detection)` | Every commit in `<base>..<head>`, from the event payload's `pull_request.base.sha` and `pull_request.head.sha`, with `--remerge-diff`, which adds what each two-parent merge commit changed itself |

**Engine pin.** The action step sets `GITLEAKS_VERSION: "8.24.3"`. That is the action's own default at the pinned SHA (`src/index.js`) and the version its log named here before the variable was set (`gitleaks version: 8.24.3`, pull request #195's run on 2026-11-15), so setting it changes no engine. It is set so that a bump of the action SHA cannot move the engine on `push` while pull requests stay on the installed one. The install step carries the same version and `GITLEAKS_SHA256` (`9991e0b2903da4c8f6122b5c3186448b927a5da4deef1fe45271c3793f4ee29c`, the `linux_x64` line of the release's `gitleaks_8.24.3_checksums.txt`), and runs `sha256sum --check --strict` before it unpacks the tarball. A bump moves both versions and the digest together.

**Pull requests.** The two pull-request steps are juniper-data's (juniper-data#530), ported under ruling 10 in section 8 of juniper-ml's `notes/JUNIPER_2026-11-06_JUNIPER-ECOSYSTEM_CURSOR-FLOOD-4-DISPOSITION.md`, as juniper-data-client#260 ported them there; the scan step's shell is unchanged. gitleaks-action lists a pull request's commits with one unpaginated request (30 per page, oldest first) and scans `--no-merges --first-parent <page[0]>^..<page[-1]>`. Commit 31 onwards is never scanned, and from the page's last commit `--first-parent` drops every commit a merge brought into the branch: on juniper-ml#1797 (88 commits) the action logged `12 commits scanned.`, 11 of them already on `main`. Neither loss has happened in this repository. Of the 194 pull requests before this change (#1 to #195, read on 2026-11-15), the largest had 6 commits, and in each of the 20 that hold a merge commit every merge's first parent is the pull request's own previous commit, with no side branch of the pull request merged in. What no pull-request scan here saw is what those merge commits changed themselves, because the action passes `--no-merges`: pull request #187, three commits and two merges of `main`, logged `3 commits scanned.`. The scan step:

- refuses a base or head SHA that is not a 40-hex commit in the checkout, before it scans
- logs `Scanning N commit(s) in <base>..<head>; the pull request reports M.`, and warns when N and M differ
- refuses a range that holds an octopus merge, for which git prints no `--remerge-diff` patch
- puts a `git` filter first on the engine's `PATH`, which deletes the `remerge ...` notes git writes into a merge's file headers and exits with `git`'s status; with the notes left in, gitleaks 8.24.3 can report a finding in a merge's own changes as `b/<path>`, or without its commit
- runs the action's detect flags, `detect --redact -v --exit-code=2 --report-format=sarif --log-level=debug`, with `--log-opts=--remerge-diff <base>..<head>` and the report at `reports/security/gitleaks.sarif`
- fails the way the action does: a leak (gitleaks exit 2) fails the step with 1, and any other non-zero gitleaks exit fails it with that code

The scan makes no API call, reads no token and posts no review comment (the action's comments needed `pull-requests: write`, which this job does not grant). A finding is in the step log, with its `Fingerprint:` line, and in the report. The job summary carries the range's commit count and gitleaks' exit code. Gitleaks' own `N commits scanned.` line counts only the commits for which `git log -p` printed a patch of a text file that is not a deletion (`detect/git.go` in 8.24.3), so it is smaller than N when the range holds clean merges: juniper-data#532 logged `Scanning 5 commit(s)` and `1 commits scanned.` for one commit and four clean merges of `main`.

**Reports.** On a pull request the redacted report is `gitleaks.sarif` in the `security-reports` artifact (30 days), beside Bandit's SARIF and pip-audit's requirements. The action's own `gitleaks-results.sarif` artifact is still uploaded on `push` and `workflow_dispatch`, and no longer on a pull request.

**Tests.** `tests/test_gitleaks_pr_scan.py` has 25 cases. Six read `ci.yml`: the engine version on both paths, the digest and its check line, the action's `if`, the scan's event range and step order, `fetch-depth: 0`, the unit lane's unfiltered `pytest tests/`, and the wiring that makes a leak fail the required check. For that wiring, the job must keep the name `Security Scans` with no `if` and no `continue-on-error`, the install step, the scan step and the self-test must carry no `continue-on-error`, the self-test's `run:` must be exactly the `python -m pytest` command below, and `Upload Security Reports` must run under `if: always()` on `reports/security/`, after the scan, so that a failed scan still uploads its report. Eleven run the scan step's own `run:` under `bash -e` with a stand-in `gitleaks`. Eight run it with the real engine in a scratch repository that carries this repository's `.gitleaks.toml`: a token in the 1st and the 35th commit of a 35-commit range, one a merge brought in, one that only a merge commit's own changes hold, a finding's commit and path under a conflict note that says `commit`, a clean range, and a clean merge of a base branch that holds a token. The file sits under `tests/`, which the allowlist exempts, and builds its tokens at run time; the scratch repositories plant them outside the allowlisted paths, so a config that stopped extending the built-in rules, or allowed every path, turns the finding cases red. Two lanes run the file. The `unit-tests` job collects all of `tests/` on each of its five legs (the informational Python 3.15 leg among them), where the eight real-engine cases skip when no `gitleaks` is on `PATH`. The `security` job then runs the file alone with `GITLEAKS_PARITY_REQUIRED=1`, which turns a missing binary into a failure:

```bash
GITLEAKS_PARITY_REQUIRED=1 python -m pytest tests/test_gitleaks_pr_scan.py -v -v --timeout=120
```

The binary is the one the action put on `PATH`, or on a pull request the one the install step put there. Locally, set `GITLEAKS_BIN` to a gitleaks 8.24.3 binary. `util/ad-hoc/2026-11-14_verify_gitleaks_pr_scan_tests_are_not_vacuous.py` undoes one property at a time, nearly always by an edit of `ci.yml`, and shows the cases that pin it fail. CI does not call it. The action's window is rebuilt in a scratch repository by juniper-data's `util/ad-hoc/2026-11-08_reproduce_gitleaks_pr_commit_window.py` and juniper-data-client's `util/ad-hoc/2026-11-11_reproduce_gitleaks_pr_commit_window.py`.

**A finding that is a false positive.** For one finding, commit a `.gitleaksignore` at the repo root holding the finding's `Fingerprint:` line as the log prints it, `<40-hex commit>:<file>:<rule>:<line>`, under a comment that names the class. A fingerprint that does not start with a commit is file-scoped and would hide a later secret on that line: never add one. A class of fixture values belongs in `.gitleaks.toml`'s allowlist, as V22's did.

**Not covered on a pull request**, as before this change: a commit that a force-push removed from the branch before any run scanned it (`cancel-in-progress` cancels the run that would have; juniper-data#536 tracks that gap), and whatever a `.gitleaks.toml` or `.gitleaksignore` changed or added by the pull request itself allows, because the scan reads both from the merge checkout. On `push`, the action's `--first-parent` still leaves out the commits a merge commit brought in; the pull-request scan covered them when they came through a pull request.

**When a step fails.**

- `Install Gitleaks (pull request)` fails at `sha256sum`: the downloaded tarball does not match `GITLEAKS_SHA256`. After an engine bump, set `GITLEAKS_VERSION` on this step and on the action step, and take the digest from the `linux_x64` line of the new release's `gitleaks_<version>_checksums.txt`, never from the file the runner downloaded. The step also refuses a runner that is not `Linux/X64`.
- The scan fails with `is not a commit in this checkout`: `pull_request.base.sha` or `pull_request.head.sha` is not a commit the checkout holds. Check that the job's checkout still sets `fetch-depth: 0`.
- The scan fails with `octopus merge(s)`: redo the merge as two-parent merges, one branch at a time, and push.
- The self-test errors at setup with `GITLEAKS_PARITY_REQUIRED=1 but no gitleaks binary`: neither path put the binary on `PATH`. `ci.yml` runs on `push`, `pull_request` and `workflow_dispatch`; an event added to `on:` that the action rejects fails `test_the_action_no_longer_scans_a_pull_request` first.
- A token you planted stays green: on a pull request a commit already on the base branch is outside `<base>..<head>`, a `push` whose payload has no commits scans nothing, a file under `tests/` or `juniper_cascor_client/testing/` is allowlisted, and a `.gitleaks.toml` without `[extend] useDefault = true` loads no built-in rule.

Local commands, run at the repo root:

```bash
gitleaks git --redact .
gitleaks dir --redact .
gitleaks git --redact --log-opts="--remerge-diff origin/main..HEAD" .
```

`git` scans history and `dir` scans the working tree, gitignored files included. The third scans what a pull request from the current branch into an up-to-date `main` would, without the step's `git` filter.

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
- **API prefix:** All REST requests target `/v1/` endpoints. After #129, a caller-supplied trailing `/v1` is stripped from `base_url` first so this prefix is applied once.

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
| `tests/test_gitleaks_pr_scan.py` | The `Security Scans` job's Gitleaks wiring and its pull-request scan step; see [Secret scan (Gitleaks)](#secret-scan-gitleaks) |
| `tests/conftest.py` | Shared fixtures |

### Quality Checks

```bash
mypy juniper_cascor_client --strict    # Type checking
flake8 juniper_cascor_client           # Linting
black --check juniper_cascor_client    # Format check
isort --check-only juniper_cascor_client  # Import order
```

---

**Last Updated:** November 15, 2026
**Version:** 0.1.5
**Maintainer:** Paul Calnon
