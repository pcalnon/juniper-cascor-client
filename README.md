# juniper-cascor-client

[![PyPI](https://img.shields.io/pypi/v/juniper-cascor-client)](https://pypi.org/project/juniper-cascor-client/)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)

**Python HTTP and WebSocket client for the juniper-cascor training service.**

`juniper-cascor-client` is the REST and async-WebSocket client for `juniper-cascor`, the
Cascade-Correlation training service. The synchronous `JuniperCascorClient` covers network lifecycle,
training control, snapshots, metrics, and distributed-worker monitoring; two async WebSocket streams
cover live monitoring (`/ws/training`, inbound events) and runtime control (`/ws/control`, outbound
commands). It's the same client `juniper-canopy` uses to drive and observe a cascor backend.

> **Part of the Juniper platform.** juniper-cascor-client is the HTTP/WebSocket client for the
> juniper-cascor training service in [Juniper](https://github.com/pcalnon/juniper-ml) — a
> multi-package ML research platform built around constructive (Cascade-Correlation) and recurrent
> neural networks.

## Install

```bash
pip install juniper-cascor-client
```

Optional extras: `[observability]` adds Prometheus counters for WebSocket frame validation; `[test]`
and `[dev]` install the test and lint/type-check toolchains.

## Quick start

REST:

```python
from juniper_cascor_client import JuniperCascorClient

with JuniperCascorClient("http://localhost:8200") as client:  # origin only; not /v1
    client.create_network(input_size=2, output_size=2)
    client.start_training(
        dataset={"source": "inline"},
        inline_data={"train_x": [[0, 0], [1, 0], [0, 1], [1, 1]],
                     "train_y": [[1, 0], [0, 1], [0, 1], [1, 0]]},
        epochs=100,
    )
    print(client.get_training_status()["data"]["training_active"])
```

Live training stream (async):

```python
import asyncio
from juniper_cascor_client import CascorTrainingStream

async def monitor():
    async with CascorTrainingStream("ws://localhost:8200") as stream:
        async for msg in stream:
            if msg["type"] == "metrics":
                print(msg["data"]["epoch"], msg["data"]["train_loss"])

asyncio.run(monitor())
```

Control stream (async): `CascorControlStream(...).command("start", {"epochs": 200})`.

## API

**`JuniperCascorClient`** (synchronous REST): `health_check` / `is_alive` / `is_ready` /
`wait_for_ready`; `create_network` / `get_network` / `delete_network` / `get_topology` /
`get_statistics`; `start_training` / `stop_training` / `pause_training` / `resume_training` /
`reset_training`; `get_training_status` / `get_training_params` / `update_params`; `get_metrics` /
`get_metrics_history`; `get_dataset` / `get_dataset_data` / `get_decision_boundary`; `list_snapshots`
/ `get_snapshot` / `save_snapshot` / `load_snapshot`; `list_workers` / `get_worker` /
`get_worker_stats`.

**`CascorTrainingStream`** (async, `/ws/training`): yields inbound JSON frames; raw iteration
(`async for`) or callbacks (`on_metrics`, `on_state`, `on_topology`, `on_cascade_add`,
`on_candidate_progress`, `on_event`, `on_disconnect`).

**`CascorControlStream`** (async, `/ws/control`): `command(command, params)` / `set_params(params)`
with per-request correlation.

## Status

**Live** on PyPI. The current version is shown by the badge above; see [`CHANGELOG.md`](./CHANGELOG.md).
The WebSocket streams **do not auto-reconnect** — wrap reconnection logic around the stream context
manager for long-running consumers.

## Documentation

- [`docs/QUICK_START.md`](docs/QUICK_START.md) — installation and verification guide
- [`docs/REFERENCE.md`](docs/REFERENCE.md) — full API reference, error model, WebSocket frame catalogue, and `base_url` normalisation (APD-CCLIENT-005)
- [`docs/DEVELOPER_CHEATSHEET.md`](docs/DEVELOPER_CHEATSHEET.md) — development quick-reference

## License

MIT — see [LICENSE](./LICENSE).
