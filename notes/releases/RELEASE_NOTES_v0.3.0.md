# Juniper Cascor Client v0.3.0 Release Notes

**Release Date:** 2026-03-30
**Version:** 0.3.0
**Release Type:** MINOR

---

## Overview

This release adds remote worker monitoring, snapshot management, and dataset retrieval methods to `JuniperCascorClient`, plus matching support in `FakeCascorClient`. It also aligns the FakeCascorClient response format with the real cascor `ResponseEnvelope` so consumer code that works against the fake also works against the real backend.

> **Status:** STABLE — Backward-compatible additive release.

---

## Release Summary

- **Release type:** MINOR
- **Primary focus:** New API surface (worker monitoring, snapshot management, dataset retrieval)
- **Breaking changes:** No
- **Priority summary:** Adds 8 new client methods + matching FakeCascorClient support; no removals

---

## What's New

### Remote Worker Monitoring

New client methods for querying CasCor distributed worker state:

- `list_workers()` — list all known workers
- `get_worker(worker_id)` — fetch a single worker by ID
- `get_worker_stats()` — aggregate statistics across workers

### Snapshot Management

New client methods for creating, listing, and loading training snapshots:

- `list_snapshots()` — list all available snapshots
- `get_snapshot(snapshot_id)` — fetch a snapshot by ID
- `save_snapshot(...)` — create a snapshot of current network state
- `load_snapshot(snapshot_id)` — restore a snapshot

### Dataset Retrieval

- `get_dataset_data()` — fetch dataset arrays via `GET /v1/dataset/data`

### Scenario Generators (testing)

- `generate_dataset_inputs()` and `generate_dataset_targets()` functions in the `scenarios` module for synthetic dataset creation in tests

### FakeCascorClient Parity

- `FakeCascorClient` now supports all worker, snapshot, and dataset-data methods with scenario-driven behavior, enabling consumers to test against an in-process fake without a running cascor backend.

### Documentation

- Comprehensive `AGENTS.md` documenting architecture, directory layout, CI/CD pipeline, linting configuration, and test conventions.

---

## Bug Fixes

### FakeCascorClient Response Format Alignment

**Problem:** `FakeCascorClient` returned bare dicts that didn't match the real cascor `ResponseEnvelope` structure, causing consumer code that worked against the fake to fail when wired to a real backend.

**Solution:** Wrapped all FakeCascorClient responses in `_success_envelope()` matching the real cascor envelope format. Specifically:

- Nested `state_machine/monitor/training_state` structure for monitor responses
- Bare list (not envelope-wrapped) for metrics history responses
- Flat param dict for parameter responses

**Files:** `juniper_cascor_client/testing/fake_client.py`

---

## Changes

### Dependencies

- Bumped `github/codeql-action` from 4.33.0 → 4.34.1 → 4.35.1 (Dependabot)
- Bumped `actions/cache` from 5.0.3 → 5.0.4 (Dependabot)

---

## Upgrade Notes

This is a backward-compatible release. No migration steps required. All changes are additive.

```bash
# Install via pip
pip install --upgrade juniper-cascor-client==0.3.0

# Or via juniper-ml meta-package
pip install --upgrade "juniper-ml[clients]"
```

---

## Known Issues

None known at time of release.

---

## Version History

| Version | Date       | Description                                                                              |
| ------- | ---------- | ---------------------------------------------------------------------------------------- |
| 0.1.0   | 2026-02-22 | Initial release — REST + WebSocket client for juniper-cascor                             |
| 0.2.0   | 2026-03-21 | `update_params()` method, FakeCascorClient testing module, full documentation suite      |
| 0.3.0   | 2026-03-30 | Worker monitoring, snapshot management, dataset retrieval, FakeCascorClient envelope fix |

---

## Links

- [Full Changelog](../../CHANGELOG.md)
- [Previous Release: v0.2.0](RELEASE_NOTES_v0.2.0.md)
