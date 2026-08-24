# Developer Cheatsheet — juniper-cascor-client

**Version**: 1.0.2
**Date**: 2026-08-24
**Project**: juniper-cascor-client

---

## Common Commands

| Command | Description |
|---------|-------------|
| `pip install -e ".[dev]"` | Install in development mode |
| `pip install juniper-cascor-client` | Install from PyPI |
| `pytest tests/ -v` | Run all tests |
| `pytest tests/ -m unit -v` | Run unit tests only |
| `pytest tests/ --cov=juniper_cascor_client --cov-report=term-missing --cov-fail-under=80` | Run with coverage |
| `mypy juniper_cascor_client --strict` | Type checking (strict) |
| `flake8 juniper_cascor_client --max-line-length=120` | Linting |
| `black --check juniper_cascor_client` | Format check |
| `isort --check-only juniper_cascor_client` | Import order check |

---

## REST Client

### Initialization

```python
from juniper_cascor_client import JuniperCascorClient

client = JuniperCascorClient(
    base_url="http://localhost:8200",
    timeout=30,
    retries=3,
    api_key="my-key",  # or set JUNIPER_CASCOR_API_KEY env var
)

with JuniperCascorClient("http://localhost:8200") as client:
    client.health_check()
```

Pass the origin, not `/v1`. After APD-CCLIENT-005 ([#129](https://github.com/pcalnon/juniper-cascor-client/pull/129)), `JuniperCascorClient` strips whitespace, defaults `http://` with **case-insensitive** scheme matching (so `HTTPS://host` stays `https`, not `http://HTTPS://host`), rejects a hostless value with `JuniperCascorConfigurationError`, drops a trailing slash, and strips a trailing `/v1` so `api_url` is not `/v1/v1`.

The host guard reads `hostname`, not `netloc` — a userinfo-only authority (`http://user:secret@`) is hostless. Until #129 merges, construction still only `rstrip("/")`. WS constructors and both fakes stay rstrip-only.

> See: [docs/REFERENCE.md](REFERENCE.md#base-url-normalisation-apd-cclient-005) for the input/result table and the fake-parity pitfall.

### Key Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `health_check()` | `Dict` | Service health status |
| `is_ready()` | `bool` | `True` if network loaded and ready |
| `create_network(**kwargs)` | `Dict` | Create CasCor network |
| `start_training(epochs, dataset)` | `Dict` | Start async training |
| `get_training_status()` | `Dict` | Current state, epoch, progress |
| `get_metrics()` | `Dict` | Current metrics snapshot |
| `stop_training()` | `Dict` | Stop training |
| `pause_training()` / `resume_training()` | `Dict` | Pause/resume control |
| `get_topology()` | `Dict` | Network layers, nodes, connections |

> See: [docs/REFERENCE.md](REFERENCE.md#rest-client-api) for full method signatures and `create_network` parameters.

---

## WebSocket Streaming

### Endpoints

| Endpoint | Client Class | Purpose |
|----------|-------------|---------|
| `/ws/training` | `CascorTrainingStream` | Real-time metrics, state, topology events |
| `/ws/control` | `CascorControlStream` | Send training commands |

### Message Types (Training Stream)

| Type | Description | Key Data Fields |
|------|-------------|-----------------|
| `metrics` | Epoch metrics update | `epoch`, `train_loss`, `accuracy`, `correlation`, `phase` |
| `state` | Training state change | `state` (`idle`, `training`, `paused`, `complete`) |
| `topology` | Network topology update | Layers, nodes, connections |
| `cascade_add` | Hidden unit installed | Unit index, correlation |
| `event` | General training event | Event-specific payload |

### Stream Lifecycle

```python
from juniper_cascor_client import CascorTrainingStream

# Async iteration pattern
async with CascorTrainingStream("ws://localhost:8200") as stream:
    async for message in stream:
        print(message["type"], message["data"])

# Callback pattern
stream = CascorTrainingStream("ws://localhost:8200")
stream.on_metrics(lambda data: print(f"Loss: {data['train_loss']}"))
stream.on_state(lambda data: print(f"State: {data['state']}"))
await stream.connect()       # connect
await stream.listen()        # blocks, dispatches to callbacks
await stream.disconnect()    # cleanup
```

### Control Stream

```python
from juniper_cascor_client import CascorControlStream

async with CascorControlStream("ws://localhost:8200") as ctrl:
    response = await ctrl.command("start")   # start, stop, pause, resume, reset
```

> See: [docs/REFERENCE.md](REFERENCE.md#websocket-clients) for full WebSocket API reference.

---

## Testing with Fake Clients

### FakeCascorClient (REST)

```python
from juniper_cascor_client.testing import FakeCascorClient

with FakeCascorClient(scenario="two_spiral_training") as client:
    client.advance_epoch(10)
    metrics = client.get_metrics()
    print(f"Loss: {metrics['train_loss']:.4f}")
```

Available scenarios: `idle`, `two_spiral_training`, `xor_converged`, `empty`, `error_prone`.

### FakeCascorTrainingStream (WebSocket)

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

> See: [docs/REFERENCE.md](REFERENCE.md#testing-utilities) for FakeClient constructors and scenario reference.

---

## Error Handling

```
JuniperCascorClientError (base)
+-- JuniperCascorConnectionError         # Connection failed
+-- JuniperCascorTimeoutError            # Request timed out
+-- JuniperCascorNotFoundError           # 404
+-- JuniperCascorConflictError           # 409 - State conflict
+-- JuniperCascorValidationError         # 400/422
+-- JuniperCascorServiceUnavailableError # 503
+-- JuniperCascorOverloadError           # Control WS pending-command cap (256)
+-- JuniperCascorConfigurationError      # Hostless base_url (after #129; no HTTP)
```

> See: [docs/REFERENCE.md](REFERENCE.md#exception-hierarchy) for HTTP status code mapping.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `JUNIPER_CASCOR_API_KEY` | *(unset)* | API key fallback (if not passed to constructor) |
| `CASCOR_SERVICE_URL` | `http://localhost:8200` | Used by consuming apps (juniper-canopy, juniper-deploy) |

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `JuniperCascorConfigurationError` at construct (`base_url must include a host`) | Empty, whitespace-only, scheme-only, path-only, or userinfo-only (`http://user:secret@`) origin (after #129) | Pass a host, e.g. `http://localhost:8200`. Until #129 merges this type does not exist and the same values fail opaquely on the first request. |
| First request hits hostname `https` over HTTP | `base_url` used an uppercase `HTTPS://` scheme (main / pre-#129 case-sensitive prefix) | After #129, scheme matching is case-insensitive and `urlparse` stores canonical `https://...`. |
| First REST call 404s on `/v1/v1/...` | `base_url` included `/v1` (main / pre-#129) | Pass the origin only. After #129 the trailing `/v1` is stripped. |
| `JuniperCascorConnectionError` | Service not running | Start juniper-cascor: `make up` in juniper-deploy or run natively |
| `JuniperCascorConflictError` on start | Training already active | Call `stop_training()` or `reset_training()` first |
| `JuniperCascorServiceUnavailableError` | Service overloaded or initializing | Retry after delay; use `wait_for_ready()` |
| `JuniperCascorOverloadError` | More than 256 in-flight control-WS commands | Bound concurrent `command()` / `set_params()` callers |
| WebSocket disconnects unexpectedly | Network interruption or server restart | Reconnect; `CascorTrainingStream` supports re-calling `connect()` |
| Auth failures (401/403) | Missing or wrong API key | Set `JUNIPER_CASCOR_API_KEY` or pass `api_key=` to constructor |
| Hostless URL accepted by `FakeCascorClient` | Fake still `rstrip("/")` only | Do not pin APD-CCLIENT-005 against the fake; use `JuniperCascorClient` |

---

## Cross-References

- [juniper-cascor-client REFERENCE.md](REFERENCE.md) -- Full API reference
- [juniper-cascor-client QUICK_START.md](QUICK_START.md) -- Getting started guide
- [juniper-cascor-client AGENTS.md](../AGENTS.md) -- Agent development guide
- [Ecosystem Cheatsheet](../../juniper-ml/docs/DEVELOPER_CHEATSHEET_JUNIPER-ML.md) -- Cross-project procedures
- [juniper-data-client Cheatsheet](../../juniper-data-client/docs/DEVELOPER_CHEATSHEET.md) -- Companion client library
