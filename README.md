<div align="right" width="150px" height="150px" align="right" valign="top"> <img src="images/Juniper_Logo_150px.png" alt="Juniper" align="right" valign="top" width="150px" /></div>
<br /> <br /> <br /> <br />

# Juniper: Dynamic Neural Network Research Platform

Juniper is an AI/ML research platform for investigating dynamic neural network architectures and novel learning paradigms.  The project emphasizes ground-up implementations from primary literature, enabling a more transparent exploration of fundamental algorithms.

## Juniper Cascor Client

`juniper-cascor-client` is the **Python HTTP and WebSocket client library** for the `juniper-cascor` training service. The package exposes a synchronous `JuniperCascorClient` for the REST surface (network lifecycle, training control, snapshots, metrics, distributed-worker monitoring) and two async WebSocket clients — `CascorTrainingStream` over `/ws/training` for inbound training events and `CascorControlStream` over `/ws/control` for outbound runtime commands. Inbound WebSocket frames are validated against the Pydantic envelope models of `juniper-cascor-protocol`, with unrecognised frame types and malformed payloads logged and counted rather than crashing the stream. The two WebSocket streams **do not auto-reconnect**; callers are responsible for wrapping a stream in a retry loop with backoff if a long-running connection is expected to survive network interruptions.

## Distribution

`juniper-cascor-client` is published on PyPI as **[`juniper-cascor-client`](https://pypi.org/project/juniper-cascor-client/)**.
The package is also surfaced through the platform meta-distribution
**[`juniper-ml`](https://pypi.org/project/juniper-ml/)**, which installs
the full client stack via `pip install juniper-ml[all]`.

```bash
pip install juniper-cascor-client
```

## Ecosystem Compatibility

This client library is part of the [Juniper](https://github.com/pcalnon/juniper-ml) ecosystem.
Verified compatible versions:

| juniper-data | juniper-cascor | juniper-canopy | data-client | cascor-client | cascor-worker |
|--------------|----------------|----------------|-------------|---------------|---------------|
| 0.6.x        | 0.4.x          | 0.4.x          | >=0.4.1     | >=0.4.0       | >=0.3.0       |

For full-stack Docker deployment and integration tests, see [`juniper-deploy`](https://github.com/pcalnon/juniper-deploy).

## Architecture

`juniper-cascor-client` is a thin client surface over the `juniper-cascor` REST and WebSocket protocols. The REST client (`JuniperCascorClient`) is synchronous and built on `requests` + `urllib3` retry semantics; the two WebSocket clients (`CascorTrainingStream`, `CascorControlStream`) are async and built on `websockets`.

```text
┌─────────────────────────┐                ┌──────────────────────┐
│  Caller (e.g. juniper-  │   HTTP REST    │   juniper-cascor     │
│  canopy / research      │ ◄────────────► │   Training Svc       │
│  notebook / operator    │   WS / WSS     │   Port 8200          │
│  script)                │ ◄────────────► │   /v1/...            │
└──────────┬──────────────┘                │   /ws/training       │
           │ uses                          │   /ws/control        │
           ▼                               └──────────────────────┘
┌─────────────────────────┐
│  juniper-cascor-client  │
│  JuniperCascorClient    │
│  CascorTrainingStream   │
│  CascorControlStream    │
│  (this package)         │
└─────────────────────────┘
```

Inbound WebSocket frames are observed against `juniper_cascor_protocol.envelope.validate_envelope()` (METRICS-MON R2.2.4). Unknown frame types and malformed payloads are logged at WARNING level and — when `prometheus-client` is installed via the `[observability]` extra — counted via `juniper_cascor_client_unrecognized_ws_frames_total`. Cardinality is bounded: beyond the first sixteen distinct unrecognised types, observations collapse to `"_unmatched"`.

## Related Services

| Service | Relationship | Notes |
|---------|-------------|-------|
| [juniper-cascor](https://github.com/pcalnon/juniper-cascor) | The service this client targets | Set `base_url` (default `http://localhost:8200`) and the WebSocket origin |
| [juniper-canopy](https://github.com/pcalnon/juniper-canopy) | Primary consumer; uses this client to monitor and control CasCor training | Reads `JUNIPER_CANOPY_CASCOR_SERVICE_URL` |
| [juniper-cascor-protocol](https://pypi.org/project/juniper-cascor-protocol/) | Wire-protocol envelope schemas validated against inbound WS frames | `juniper-cascor-protocol>=0.1.0` is a runtime dependency |

## Active Research Components

`juniper-cascor-client` is the reference client implementation of two research artifacts of the Juniper platform: the **WebSocket training-stream protocol** (`/ws/training`), which carries cascade-add events, per-epoch metrics, network-topology updates, and state transitions as a Cascade-Correlation network grows; and the **WebSocket control-stream protocol** (`/ws/control`), which carries the operator-facing command surface (start, stop, pause, resume, reset, parameter updates) that an experimentation interface uses to steer a running training run. Both protocols are non-trivial enough to be worth naming as platform artifacts; the envelope schemas are defined in `juniper-cascor-protocol` and validated observationally on every inbound frame.

## Quick Start Guide

### Prerequisites

- Python ≥ 3.12
- A running `juniper-cascor` instance reachable at the `base_url` (typically `http://localhost:8200`)
- An API key configured on the cascor service (`JUNIPER_CASCOR_API_KEYS`); the client reads `JUNIPER_CASCOR_API_KEY` as a fallback

### Installation

```bash
pip install juniper-cascor-client
```

Optional extras: `[observability]` enables Prometheus counters for WebSocket-frame validation; `[test]` installs the testing dependencies; `[dev]` adds linting and type-checking tools.

### Verification — REST client

```python
from juniper_cascor_client import JuniperCascorClient

with JuniperCascorClient("http://localhost:8200") as client:
    client.create_network(input_size=2, output_size=2, learning_rate=0.01)
    client.start_training(
        dataset={"source": "inline"},
        inline_data={
            "train_x": [[0, 0], [1, 0], [0, 1], [1, 1]],
            "train_y": [[1, 0], [0, 1], [0, 1], [1, 0]],
        },
        epochs=100,
    )
    status = client.get_training_status()
    print(status["data"]["training_active"])

    metrics = client.get_metrics()
    print(f"Loss: {metrics['data']['train_loss']}")
```

### Verification — WebSocket training stream

```python
import asyncio
from juniper_cascor_client import CascorTrainingStream

async def monitor():
    async with CascorTrainingStream("ws://localhost:8200") as stream:
        async for message in stream:
            if message["type"] == "metrics":
                print(f"Epoch {message['data']['epoch']}: loss={message['data']['train_loss']}")
            elif message["type"] == "cascade_add":
                print("New hidden unit added")

asyncio.run(monitor())
```

### Verification — WebSocket control stream

```python
import asyncio
from juniper_cascor_client import CascorControlStream

async def control():
    async with CascorControlStream("ws://localhost:8200") as ctrl:
        result = await ctrl.command("start", {"epochs": 200})
        print(result)

asyncio.run(control())
```

### Reconnection contract

WebSocket streams **do not auto-reconnect**. If a connection is lost (network interruption, server restart, timeout), the stream silently terminates and the async iterator stops. Long-running consumers must wrap the stream in their own retry loop with backoff. The canonical pattern:

```python
import asyncio
from juniper_cascor_client import CascorTrainingStream

async def resilient_stream(url, api_key):
    while True:
        try:
            async with CascorTrainingStream(url, api_key=api_key) as stream:
                async for message in stream.stream():
                    process(message)
        except Exception:
            await asyncio.sleep(5)  # backoff before reconnect
```

### Next Steps

- [`docs/QUICK_START.md`](docs/QUICK_START.md) — complete installation and verification guide
- [`docs/REFERENCE.md`](docs/REFERENCE.md) — full API reference, error model, and WebSocket frame catalogue
- [`docs/DEVELOPER_CHEATSHEET.md`](docs/DEVELOPER_CHEATSHEET.md) — quick-reference card for development tasks
- [`juniper-cascor`](https://github.com/pcalnon/juniper-cascor) — the upstream training service
- [`juniper-ml`](https://pypi.org/project/juniper-ml/) — platform meta-package on PyPI

## Research Philosophy

The Juniper platform exists to study learning algorithms whose network architecture is not fixed in advance. Its initial anchor is the Cascade-Correlation algorithm of Fahlman and Lebiere (1990), implemented from the primary literature without recourse to higher-level abstractions that elide the algorithm's operational detail. The organising commitment is that algorithm implementations remain inspectable at the level at which they were originally specified: candidate units, correlation objectives, weight-freezing semantics, and the structural events that grow the network are first-class artifacts of the codebase rather than internal details of a library wrapper. This permits comparative work — across algorithms, datasets, and hyperparameter regimes — to be conducted on a known and reproducible substrate.

The current platform comprises a Cascade-Correlation training service exposing a REST and WebSocket interface, a dataset-generation service with a named-version registry that includes the ARC-AGI families, a real-time monitoring dashboard for inspecting training dynamics as they occur, and a distributed worker that parallelises candidate-unit training across hosts. Near-term work extends the architectural-growth catalogue beyond Cascade-Correlation, introduces multi-network orchestration for comparative experiments at the level of network populations rather than individual runs, and tightens the dataset–training–monitoring loop into a reproducible research workbench. The longer-term direction is the systematic empirical study of constructive and architecture-growing learning algorithms, with first-class infrastructure for the ablation, comparison, and replication that such a study requires.

## Documentation

### API Reference

#### `JuniperCascorClient` — REST client

| Method | Description |
|--------|-------------|
| `health_check()` | Service health check |
| `is_alive()` | Liveness probe |
| `is_ready()` | Readiness probe |
| `wait_for_ready(timeout, poll_interval)` | Wait for service readiness |
| `create_network(**kwargs)` | Create a CasCor network |
| `get_network()` / `delete_network()` | Network lifecycle |
| `get_topology()` / `get_statistics()` | Network introspection |
| `start_training(...)` / `stop_training()` | Training start / stop |
| `pause_training()` / `resume_training()` / `reset_training()` | Training control |
| `get_training_status()` / `get_training_params()` | Training state |
| `get_metrics()` / `get_metrics_history(count)` | Metrics retrieval |
| `update_params(params)` | Runtime training parameter updates |
| `get_dataset()` / `get_dataset_data()` | Dataset retrieval |
| `get_decision_boundary(resolution)` | Decision boundary for visualisation |
| `list_snapshots()` / `get_snapshot(id)` | Snapshot listing and inspection |
| `save_snapshot(description)` / `load_snapshot(id)` | Snapshot save / restore |
| `list_workers()` / `get_worker(id)` / `get_worker_stats()` | Distributed-worker monitoring |
| `close()` | Close the underlying HTTP session |

#### `CascorTrainingStream` — async WebSocket training stream

Connects to `/ws/training`. Yields inbound JSON frames as Python dicts. Supports both raw iteration (`async for message in stream`) and callback-based dispatch (`on_metrics`, `on_state`, `on_topology`, `on_cascade_add`, `on_event`). Context-manager API.

#### `CascorControlStream` — async WebSocket control stream

Connects to `/ws/control`. Sends outbound command frames and awaits their responses. Convenience: `set_params(params)` is sugar for `command("set_params", {...})`. Context-manager API.

### Reference documents

| Document | Purpose |
|----------|---------|
| [`docs/DOCUMENTATION_OVERVIEW.md`](docs/DOCUMENTATION_OVERVIEW.md) | Navigation index for all `juniper-cascor-client` documentation |
| [`docs/QUICK_START.md`](docs/QUICK_START.md) | Complete installation and verification guide |
| [`docs/REFERENCE.md`](docs/REFERENCE.md) | Full API reference, error model, and WebSocket frame catalogue |
| [`docs/DEVELOPER_CHEATSHEET.md`](docs/DEVELOPER_CHEATSHEET.md) | Quick-reference card for development tasks |
| [`CHANGELOG.md`](CHANGELOG.md) | Version history |

## License

MIT License — see [`LICENSE`](LICENSE) for details.
