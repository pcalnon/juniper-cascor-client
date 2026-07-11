# Juniper Cascor Client v0.6.0 Release Notes

**Release Date:** 2026-07-11
**Version:** 0.6.0
**Release Type:** MINOR

---

## Overview

This release restores test-double fidelity between `FakeCascorClient` and `JuniperCascorClient`: the fake now implements the real client's private `_request` escape hatch and answers the cascor dataset-staging and experimental-functions routes in memory. Consumer code that drives those endpoints through `client._request(...)` — juniper-canopy's `CascorServiceAdapter` is the motivating case — now works identically against the fake and the real backend.

> **Status:** STABLE — Backward-compatible additive release.

---

## Release Summary

- **Release type:** MINOR
- **Primary focus:** `FakeCascorClient._request` in-memory parity (dataset staging + experimental-functions gate)
- **Breaking changes:** No
- **Priority summary:** Fixes the `AttributeError: 'FakeCascorClient' object has no attribute '_request'` crash class for canopy's trivial-case Start-Training flow (canopy#438); no removals

---

## What's New

### `FakeCascorClient._request` — in-memory escape-hatch parity

`JuniperCascorClient` has always exposed `_request(method, path, json=None, params=None)` as the "public-but-private" escape hatch for endpoints without first-class client methods (cascor #242). juniper-canopy's `CascorServiceAdapter` drives five such routes for dataset staging and the experimental-functions gate, and canopy #438 put that path on canopy's first-start flow — so any test driving `ServiceBackend.start_training()` against the fake crashed with `AttributeError` under the real installed package.

`FakeCascorClient._request` now mirrors the real signature (pinned by a conformance test) and answers, with response `data` shapes copied from the cascor server handlers:

| Route | Behaviour |
|---|---|
| `POST /training/dataset` | Stages the config (`{"status": "staged", "config": ...}`); an empty body clears (`{"status": "cleared", "config": null}`) |
| `DELETE /training/dataset` | Discards staging, echoing the prior config (`{"status": "cleared", "discarded": ...}`) |
| `GET /training/dataset/pending` | Returns the staged config or `null` (`{"pending": ...}`) |
| `GET /admin/experimental_functions` | Returns the gate state (`{"enabled": bool}`) |
| `POST /admin/experimental_functions` | Sets the gate (`{"experimental_functions_enabled": bool}`) |

Unknown routes raise `JuniperCascorNotFoundError` exactly like a real 404; closed-client refusal and `error_prone`-scenario injection behave like every other fake method.

### Consume-on-start parity (cascor #396)

`FakeCascorClient.start_training` now consumes any staged dataset config on a successful start, mirroring the real cascor's consume-on-start so the canopy pending banner clears after a start.

---

## Testing

- New regression class `tests/test_fake_client.py::TestPrivateRequestEscapeHatch` (9 tests): signature parity with `JuniperCascorClient._request`, all five route round-trips, unknown-route 404 behaviour, closed-client refusal, and consume-on-start.
- Full suite green (348 tests); `mypy --strict` delta vs main: zero new errors.
- Cross-verified against juniper-canopy main (889dbfa): the previously-failing `test_fake_service_backend.py::test_idle_scenario_start_training_fails` plus every fake-dependent canopy suite (`test_fake_client_conformance`, `test_state_sync`, four adapter suites) pass with this branch shadowing the installed 0.5.0 — zero skips, zero failures.

---

## Compatibility

- Pure-additive: no existing public API, envelope, or wire shape is touched.
- Downstream: juniper-canopy should bump its floor to `juniper-cascor-client>=0.6.0` so developer machines (where the real package supplies `juniper_cascor_client.testing`) get the fixed fake.
