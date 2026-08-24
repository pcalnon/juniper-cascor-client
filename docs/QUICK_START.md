# Quick Start Guide

## Get juniper-cascor-client Working in 5 Minutes

**Version:** 0.1.2
**Status:** Active
**Last Updated:** August 24, 2026
**Project:** Juniper - CasCor Service Client Library

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Install](#1-install)
- [REST Client](#2-rest-client)
  - [Base URL](#base-url)
- [WebSocket Streaming](#3-websocket-streaming)
- [Error Handling](#4-error-handling)
- [Testing](#5-testing)
- [Next Steps](#6-next-steps)

---

## Prerequisites

- **Python 3.11+** (`python --version`)
- **juniper-cascor** service running on port 8200 (`curl http://localhost:8200/v1/health`)

---

## 1. Install

```bash
pip install juniper-cascor-client
```

Or install from source for development:

```bash
cd juniper-cascor-client
pip install -e ".[dev]"
```

---

## 2. REST Client

```python
from juniper_cascor_client import JuniperCascorClient

# Create client (default: localhost:8200). Pass the origin, not /v1.
client = JuniperCascorClient("http://localhost:8200")

# Check service health
health = client.health_check()
print(f"Service: {health['status']}")  # "ok"

# Create a CasCor network
client.create_network(input_size=2, output_size=1, learning_rate=0.01)

# Start training with inline data
client.start_training(epochs=100)

# Check training status
status = client.get_training_status()
print(f"State: {status['state']}, Epoch: {status['epoch']}")

# Get current metrics
metrics = client.get_metrics()
print(f"Loss: {metrics['train_loss']:.4f}, Accuracy: {metrics['train_accuracy']:.4f}")
```

### Context Manager

```python
with JuniperCascorClient("http://localhost:8200") as client:
    client.create_network(input_size=2, output_size=1, learning_rate=0.01)
    client.start_training(epochs=100)
# Session automatically closed
```

### Base URL

Pass the service origin, not the `/v1` API prefix. After APD-CCLIENT-005 ([#129](https://github.com/pcalnon/juniper-cascor-client/pull/129)):

```python
JuniperCascorClient("localhost:8200")            # → http://localhost:8200
JuniperCascorClient("http://localhost:8200/v1")  # → http://localhost:8200 (not /v1/v1)
JuniperCascorClient("HTTPS://localhost:8200")    # → https://localhost:8200 (scheme match is case-insensitive)
JuniperCascorClient("")                          # raises JuniperCascorConfigurationError
JuniperCascorClient("http://user:secret@")       # also hostless — hostname is None even though netloc is truthy
```

Until #129 merges, construction still only `rstrip("/")` — the schemeless form and a `/v1` suffix fail opaquely (or hit `/v1/v1`) on the first request, and `HTTPS://host` would be re-prefixed into `http://HTTPS://host`. `CascorTrainingStream` / `CascorControlStream` (`ws://...`) do not run this normalisation.

### Wait for Service

```python
client = JuniperCascorClient("http://localhost:8200")
if client.wait_for_ready(timeout=30):
    health = client.health_check()
else:
    print("Service not available")
```

---

## 3. WebSocket Streaming

```python
import asyncio
from juniper_cascor_client import CascorTrainingStream

async def monitor_training():
    async with CascorTrainingStream("ws://localhost:8200") as stream:
        async for message in stream:
            if message["type"] == "metrics":
                data = message["data"]
                print(f"Epoch {data['epoch']}: loss={data['train_loss']:.4f}")
            elif message["type"] == "state":
                print(f"State changed: {message['data']['state']}")

asyncio.run(monitor_training())
```

### Callback Style

```python
async def with_callbacks():
    stream = CascorTrainingStream("ws://localhost:8200")

    @stream.on_metrics
    def handle_metrics(data):
        print(f"Epoch {data['epoch']}: {data['train_loss']:.4f}")

    @stream.on_state
    def handle_state(data):
        print(f"State: {data['state']}")

    await stream.connect()
    await stream.listen()
```

---

## 4. Error Handling

```python
from juniper_cascor_client import (
    JuniperCascorClient,
    JuniperCascorConfigurationError,  # after #129
    JuniperCascorConnectionError,
    JuniperCascorConflictError,
    JuniperCascorValidationError,
)

try:
    client = JuniperCascorClient("http://localhost:8200")
    client.start_training(epochs=100)
except JuniperCascorConfigurationError as e:
    print(f"Bad base_url: {e}")  # hostless origin; construction-time, no HTTP
except JuniperCascorConflictError as e:
    print(f"Already training: {e}")
except JuniperCascorValidationError as e:
    print(f"Invalid parameters: {e}")
except JuniperCascorConnectionError as e:
    print(f"Service unreachable: {e}")
```

---

## 5. Testing

```bash
# Run all tests
pytest tests/ -v

# Run unit tests only
pytest tests/ -m unit -v

# Run with coverage
pytest tests/ --cov=juniper_cascor_client --cov-report=term-missing --cov-fail-under=80
```

The test suite includes `FakeCascorClient` and `FakeCascorTrainingStream` for testing consumers without a running service. See [REFERENCE.md](REFERENCE.md) for details.

---

## 6. Next Steps

- [Documentation Overview](DOCUMENTATION_OVERVIEW.md) -- navigation index
- [API Reference](REFERENCE.md) -- complete REST, WebSocket, and testing reference
- [README.md](../README.md) -- project overview with more examples
- [AGENTS.md](../AGENTS.md) -- development conventions and commands

---

**Last Updated:** August 24, 2026
**Version:** 0.1.2
**Status:** Active
