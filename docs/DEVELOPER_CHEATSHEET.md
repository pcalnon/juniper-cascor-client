# Developer Cheatsheet — juniper-cascor-client

**Version**: 1.0.0
**Date**: 2026-03-15
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
| `JuniperCascorConnectionError` | Service not running | Start juniper-cascor: `make up` in juniper-deploy or run natively |
| `JuniperCascorConflictError` on start | Training already active | Call `stop_training()` or `reset_training()` first |
| `JuniperCascorServiceUnavailableError` | Service overloaded or initializing | Retry after delay; use `wait_for_ready()` |
| WebSocket disconnects unexpectedly | Network interruption or server restart | Reconnect; `CascorTrainingStream` supports re-calling `connect()` |
| Auth failures (401/403) | Missing or wrong API key | Set `JUNIPER_CASCOR_API_KEY` or pass `api_key=` to constructor |

---

## Cross-References

- [juniper-cascor-client REFERENCE.md](REFERENCE.md) -- Full API reference
- [juniper-cascor-client QUICK_START.md](QUICK_START.md) -- Getting started guide
- [juniper-cascor-client AGENTS.md](../AGENTS.md) -- Agent development guide
- [Ecosystem Cheatsheet](../../juniper-ml/notes/DEVELOPER_CHEATSHEET.md) -- Cross-project procedures
- [juniper-data-client Cheatsheet](../../juniper-data-client/docs/DEVELOPER_CHEATSHEET.md) -- Companion client library
