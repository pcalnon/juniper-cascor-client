# Juniper Cascor Client v0.7.0 Release Notes

**Release Date:** DRAFT — owner cuts the GitHub Release (plan unit CL2)
**Version:** 0.7.0
**Release Type:** MINOR

---

## Overview

This release makes the client a first-class citizen of the cascor WebSocket heartbeat contract and gives consumers a real connection-liveness surface. It is the client half (plan unit CL1) of the 2026-07-10 incident fix: cascor pings every WS connection every 30 seconds and closes it when nothing comes back within 10 seconds, but this client never answered pings — and on `/ws/control` nothing even read the socket until the first `set_params` — so canopy's control WebSocket was silently killed 40 seconds after connect and then held as a half-open corpse for 12+ hours, burning every hot-parameter push's WS window before the REST fallback. The server half (explicit contract, tolerance, deliverable close frames, emission instrumentation) is cascor unit C3.

> **Status:** DRAFT — additive, backward-compatible MINOR release. Do not tag or publish from this document; the owner cuts the GitHub Release per the ecosystem release convention (juniper-ml `notes/JUNIPER_2026-06-18_JUNIPER-ECOSYSTEM_PYPI-PUBLISH-PROCEDURE.md` §11), which triggers `publish.yml`. The canopy floor bump + `FakeCascorClient`-consumer verification follow as CL2.

---

## Release Summary

- **Release type:** MINOR
- **Primary focus:** WS heartbeat auto-pong (both streams), eager control-stream recv loop, liveness surface (`is_connected` / `is_alive` / `last_frame_at` / `pongs_sent`), `msg_type` in unrecognized-frame warnings, `FakeCascorTrainingStream` parity
- **Breaking changes:** No (pure-additive public surface; one log-message format enrichment with a preserved grep prefix)
- **Priority summary:** Root fix for the 40s control-WS kill (I-1/I-4 WS leg, cross-cutting themes T2/T5 of the 2026-07-11 training-runtime-defects plan)

---

## What's New

### Heartbeat auto-pong (the root fix)

The cascor server sends an application-level `{"type":"ping","ts":<float>}` on `/ws/training` and `/ws/control` every `ws_heartbeat_interval_sec` (default 30s) and closes the connection when the client sends nothing within `ws_heartbeat_pong_timeout_sec` (default 10s) of a ping.

- `CascorTrainingStream` and `CascorControlStream` now answer pings automatically with `{"type":"pong"}` (`auto_pong: bool = True`; pass `auto_pong=False` to restore the legacy behaviour where ping frames are yielded and the consumer replies itself — juniper-canopy's pre-CL1 relay pattern).
- `CascorControlStream.connect()` starts the background recv loop eagerly, so pings are answered from the moment the connection exists. Previously the loop started lazily on the first `set_params`, which is exactly why an idle control connection died 40s after connect. After `connect()`, `command()` always routes through the `command_id` correlation path; the direct-recv fallback now skips (and answers) pings so a ping can never be returned as a command's response.
- `ping` is a **recognized transport frame**: it is consumed before envelope validation, so the per-30s `juniper_cascor_client_unrecognized_ws_frame` warning spam (~2,400 warnings in the incident session, mirrored again by canopy) is gone.

### Liveness surface (the seam canopy's supervisor hardening consumes)

Both stream classes — and `FakeCascorTrainingStream` — expose:

| Surface | Meaning |
|---|---|
| `is_connected` (property) | Underlying `websockets` protocol state is OPEN — detects processed closes, which the historical `_ws is not None` idiom could not |
| `is_alive(window_sec=90.0)` | Connected AND at least one inbound frame within the window — detects **half-open** sockets that `is_connected` alone cannot; the default 90s window is three missed 30s server heartbeats |
| `last_frame_at` (property) | Wall-clock epoch seconds of the last inbound frame |
| `pongs_sent` (property) | Count of automatic pong replies on this connection object |

A successful `connect()` counts as the first liveness evidence. New constants: `WS_MSG_TYPE_PING`, `WS_MSG_TYPE_PONG`, `DEFAULT_LIVENESS_WINDOW_SEC`.

### Diagnosable unrecognized-frame warnings

`record_unrecognized_frame` now logs `juniper_cascor_client_unrecognized_ws_frame type=<type> endpoint=<endpoint>` — the frame type was previously visible only in the `extra` dict, which standard `%(message)s` formatters drop, so the incident produced thousands of warnings with zero diagnostic value in the log files. The stable prefix, the Prometheus counter, and the `extra` keys are unchanged.

### `FakeCascorTrainingStream` parity

The fake mirrors the new contract (the #91 lesson): `auto_pong` kwarg, injected `{"type":"ping"}` frames consumed (counted in `pongs_sent`, never yielded) by default and yielded under `auto_pong=False`, plus the full liveness surface.

### Housekeeping

- `__init__.__version__` corrected to `0.7.0` (had drifted to `0.4.0` while the package shipped 0.5.x/0.6.x).

---

## Compatibility

| Combination | Behaviour |
|---|---|
| New client (0.7.0) + old server | Pongs answered as the server always expected (heartbeat shipped in cascor#133) — strictly better; unknown-to-server extra pongs are routed by type and ignored otherwise |
| Old client (≤0.6.0) + new server (C3) | Unchanged failure mode for idle control connections (closed after the pong window), but the close is now observable (valid close code 1011 + reason instead of a silent half-open); canopy's relay keeps `/ws/training` alive via its own pong workaround |
| New client + new server | Heartbeat honoured on both streams; control WS survives idle periods indefinitely |
| New client + canopy's existing relay workaround | The relay's manual `ping` branch simply never fires (pings are consumed by the client) — no double-pong |

No public API or wire-format removals. Consumers that relied on seeing raw `ping` frames in `stream()` must pass `auto_pong=False`.

---

## Testing

- New suite `tests/test_ws_heartbeat_liveness.py`: training-stream auto-pong (answered, swallowed, no unrecognized warning, counted), `auto_pong=False` legacy yield, control-stream eager recv + ping answering + correlation coexistence, direct-path ping skipping, liveness surfaces (`is_connected` / `is_alive` / `last_frame_at`) across connect/close/half-open scenarios, and fake parity.
- Updated: `tests/test_inbound_validation.py` message-format assertions (type/endpoint now part of the warning text).
- Full suite green; `pre-commit run --all-files` green (black, isort, flake8, mypy, bandit).

---

## Post-release (CL2 — owner-gated)

1. Cut the GitHub Release for `v0.7.0` (triggers `publish.yml`: TestPyPI verify → PyPI).
2. Bump juniper-canopy's `juniper-cascor-client` floor to `>=0.7.0` and wire its supervisor (plan unit N2) to `is_alive()` / `is_connected`.
3. Retire canopy's manual ping-pong relay workaround (`cascor_service_adapter.py:399-403`) once the floor bump lands.
