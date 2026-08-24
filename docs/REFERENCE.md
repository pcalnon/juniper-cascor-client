# Reference

## juniper-cascor-client Technical Reference

**Version:** 0.1.2
**Status:** Active
**Last Updated:** August 24, 2026
**Project:** Juniper - CasCor Service Client Library

---

## Table of Contents

- [REST Client API](#rest-client-api)
- [Base URL normalisation](#base-url-normalisation-apd-cclient-005)
- [WebSocket Clients](#websocket-clients)
- [Exception Hierarchy](#exception-hierarchy)
- [Testing Utilities](#testing-utilities)
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

**Until #129 merges**, construction still only `base_url.rstrip("/")`. After it merges, `__init__` runs these steps in order:

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
| `tests/conftest.py` | Shared fixtures |

### Quality Checks

```bash
mypy juniper_cascor_client --strict    # Type checking
flake8 juniper_cascor_client           # Linting
black --check juniper_cascor_client    # Format check
isort --check-only juniper_cascor_client  # Import order
```

---

**Last Updated:** August 24, 2026
**Version:** 0.1.2
**Maintainer:** Paul Calnon
