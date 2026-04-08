# juniper-cascor-client

Python HTTP/WebSocket client for the JuniperCascor cascade correlation neural network training service.

## Ecosystem Compatibility

This package is part of the [Juniper](https://github.com/pcalnon/juniper-ml) ecosystem.
Compatible with:

| juniper-data | juniper-cascor | juniper-canopy |
|---|---|---|
| 0.4.x | 0.3.x | 0.2.x |

## Installation

```bash
pip install juniper-cascor-client
```

## Usage

### REST Client

```python
from juniper_cascor_client import JuniperCascorClient

with JuniperCascorClient("http://localhost:8200") as client:
    # Create a network
    client.create_network(input_size=2, output_size=2, learning_rate=0.01)

    # Start training
    client.start_training(
        dataset={"source": "inline"},
        inline_data={
            "train_x": [[0, 0], [1, 0], [0, 1], [1, 1]],
            "train_y": [[1, 0], [0, 1], [0, 1], [1, 0]],
        },
        epochs=100,
    )

    # Check status
    status = client.get_training_status()
    print(status["data"]["training_active"])

    # Get metrics
    metrics = client.get_metrics()
    print(f"Loss: {metrics['data']['train_loss']}")
```

### WebSocket Training Stream

```python
import asyncio
from juniper_cascor_client import CascorTrainingStream

async def monitor():
    async with CascorTrainingStream("ws://localhost:8200") as stream:
        async for message in stream:
            if message["type"] == "metrics":
                print(f"Epoch {message['data']['epoch']}: loss={message['data']['train_loss']}")
            elif message["type"] == "cascade_add":
                print(f"New hidden unit added!")

asyncio.run(monitor())
```

### WebSocket Control

```python
import asyncio
from juniper_cascor_client import CascorControlStream

async def control():
    async with CascorControlStream("ws://localhost:8200") as ctrl:
        result = await ctrl.command("start", {"epochs": 200})
        print(result)

asyncio.run(control())
```

## API Reference

### JuniperCascorClient

| Method | Description |
|--------|-------------|
| `health_check()` | Service health check |
| `is_alive()` | Liveness probe |
| `is_ready()` | Readiness probe |
| `wait_for_ready(timeout)` | Wait for service readiness |
| `create_network(**kwargs)` | Create a CasCor network |
| `get_network()` | Get network state |
| `delete_network()` | Destroy network |
| `get_topology()` | Network topology for visualization |
| `get_statistics()` | Network weight statistics |
| `start_training(...)` | Start async training |
| `stop_training()` | Stop training |
| `pause_training()` | Pause training |
| `resume_training()` | Resume training |
| `reset_training()` | Reset state |
| `get_training_status()` | Current training status |
| `get_training_params()` | Training parameters |
| `get_metrics()` | Current metrics |
| `get_metrics_history(count)` | Metrics history |
| `get_dataset()` | Dataset metadata |
| `get_decision_boundary(resolution)` | Decision boundary grid |

### CascorTrainingStream

Async WebSocket client for `/ws/training`. Supports async iteration and callbacks.

### CascorControlStream

Async WebSocket client for `/ws/control`. Send commands and receive responses.

> **Important: WebSocket streams do not automatically reconnect.** If a connection
> is lost (network interruption, server restart, timeout), the stream silently
> terminates. Consumers must implement their own reconnection logic for
> long-running training monitoring. Example pattern:
>
> ```python
> import asyncio
> from juniper_cascor_client import CascorTrainingStream
>
> async def resilient_stream(url, api_key):
>     while True:
>         try:
>             async with CascorTrainingStream(url, api_key=api_key) as stream:
>                 async for message in stream.stream():
>                     process(message)
>         except Exception:
>             await asyncio.sleep(5)  # backoff before reconnect
> ```

## Juniper Ecosystem

This package is part of the Juniper Cascade Correlation Neural Network Research Platform.

| Package | Description | Install |
|---------|-------------|---------|
| [juniper-data-client](https://github.com/pcalnon/juniper-data-client) | Dataset service client | `pip install juniper-data-client` |
| [juniper-cascor-client](https://github.com/pcalnon/juniper-cascor-client) | Neural network service client (this package) | `pip install juniper-cascor-client` |
| [juniper-cascor-worker](https://github.com/pcalnon/juniper-cascor-worker) | Distributed training worker | `pip install juniper-cascor-worker` |

## License

MIT License - see [LICENSE](LICENSE) for details.
