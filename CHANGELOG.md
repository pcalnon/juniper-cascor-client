# Changelog

All notable changes to `juniper-cascor-client` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed (potentially breaking)

- **METRICS-MON R2.2.4 / seed-05**: `juniper-cascor-client` now consumes the shared `juniper-cascor-protocol>=0.1.0` package as a runtime dependency and validates every inbound `/ws/training` and `/ws/control` frame against its canonical Pydantic envelope models. Validation is purely **observational** — the wire-format dict is yielded / passed to callbacks unchanged so the public `stream()`, `on_metrics`, `on_state`, `on_topology`, `on_cascade_add`, `on_event`, `command()`, and `set_params()` APIs are byte-compatible with the pre-migration behaviour. **Python floor bumped to `>=3.12`** (was `>=3.11`) to match the cascor server and the protocol package; `Programming Language :: Python :: 3.11` classifier removed. **New observability surface**: when an inbound frame fails validation (unknown `type`, missing required field, wrong field types) the client emits a structured WARNING log line `juniper_cascor_client_unrecognized_ws_frame` with `type` and `endpoint` extra keys, and (when `juniper-cascor-client[observability]` is installed) increments a new Prometheus counter `juniper_cascor_client_unrecognized_ws_frames_total{type, endpoint}`. The `type` label is bounded by the same R1.1 cardinality discipline the protocol package uses (first 16 distinct unknowns tracked verbatim per process; subsequent unknowns collapse to `"_unmatched"`) so an attacker emitting many distinct frame types cannot inflate label cardinality. New optional extra `[observability]` adds `prometheus-client>=0.20.0`. New chaos-coverage test suite at `tests/test_inbound_validation.py` (10+ tests) pinning: known envelopes pass through unchanged, unknown types are observed but not rejected, malformed payloads do not crash `stream()`, the cardinality bound holds, and the counter degrades gracefully when `prometheus-client` is not installed. See [`notes/code-review/METRICS_MONITORING_R2.2_WS_FRAME_SCHEMA_DESIGN_2026-04-29.md`](https://github.com/pcalnon/juniper-ml/blob/main/notes/code-review/METRICS_MONITORING_R2.2_WS_FRAME_SCHEMA_DESIGN_2026-04-29.md) in juniper-ml.

### Added

- **`util/test_agents_md_version_drift.py`** -- portable port of juniper-ml's lint test pinning `AGENTS.md`'s `**Version**:` header to `pyproject.toml`'s `[project].version`. Catches the failure class where a `pyproject.toml` bump leaves the agent-facing contract stale. Bundled with a one-line `AGENTS.md` bump 0.3.0 → 0.4.0 to clear the pre-existing drift this lint surfaces. Wired into the CI tests job next to the existing `test_workflow_script_paths.py` lint.

- Track 5B — CI-04: Weekly security-scan workflow (`.github/workflows/security-scan.yml`) running Bandit (SAST, SARIF output) and `pip-audit --strict --desc on` against the package on a Monday-06:00-UTC cron plus `workflow_dispatch`. Mirrors the established pattern in `juniper-cascor-worker`. Reports upload as a 30-day-retention artifact.
- Track 5B — CI-05: Lockfile update workflow (`.github/workflows/lockfile-update.yml`) that regenerates `requirements.lock` via `uv pip compile pyproject.toml --extra dev --upgrade` whenever Dependabot pushes to `dependabot/pip/**`, and commits the result back. Uses `CROSS_REPO_DISPATCH_TOKEN` so the push re-triggers CI. Mirrors the pattern in `juniper-canopy`, `juniper-data`, and `juniper-cascor`. Workflow is dormant until the first Dependabot push — `juniper-cascor-client` does not currently ship a `requirements.lock`, and the first run will create one.
- Serena code agent integration configuration (`.serena/project.yml`)
- New `juniper_cascor_client/constants.py` module centralizing wire-protocol identifiers (`API_KEY_*`, `API_VERSION_*`), the full set of REST `ENDPOINT_*` paths, WebSocket `WS_*_PATH` constants, `DEFAULT_*` constructor defaults, `MSG_TYPE_*` discriminators bit-identical to the cascor server's `MessageType` enum, and scenario/fake-client defaults.
- `tests/test_retry_policy.py`: new regression suite asserting that the retryable-status list covers 429/502/503/504 in both directions (canonical transients retried, non-transient 4xx/5xx not) and that the `Retry` adapter mounted on the session reflects these constants end-to-end.

### Changed

- `client.py`, `ws_client.py`, `testing/fake_client.py`, and `testing/scenarios.py` now import from `juniper_cascor_client.constants` instead of embedding inline literals (~200 replacements total across REST + WebSocket + testing utilities).
- `MSG_TYPE_*` values are guaranteed to remain bit-identical to the `juniper-cascor` server's `MessageType(StrEnum)` and to the matching constants in `juniper-cascor-worker` — verified by Wave 5 cross-repo alignment checks.
- `AGENTS.md` gained a new "Constants" section documenting the categories, server alignment, and contribution rules.
- **XREPO-02 / CC-02 (Phase 4B)**: `RETRYABLE_STATUS_CODES` now includes 429 (Too Many Requests) and 503 (Service Unavailable) in addition to the existing 502/504. 503 is the canonical transient error emitted by the cascor service during restart / deploy; prior behavior surfaced deploy windows as hard failures at the caller. 429 is retried so clients back off cleanly when the server applies rate limits.

### Notes

- No public API changes; constructor signatures, method behavior, and exception types are unchanged.
- All 223 existing tests pass without modification; pre-commit (22 hooks) is clean.

## [0.3.0] - 2026-03-30

### Added

- `list_workers()`, `get_worker()`, `get_worker_stats()` client methods for remote worker monitoring
- `list_snapshots()`, `get_snapshot()`, `save_snapshot()`, `load_snapshot()` client methods for snapshot management
- `get_dataset_data()` client method for dataset array retrieval (`GET /v1/dataset/data`)
- `generate_dataset_inputs()` and `generate_dataset_targets()` functions in scenarios for synthetic dataset creation
- FakeCascorClient support for worker, snapshot, and dataset data methods with scenario-driven behavior
- Comprehensive AGENTS.md with architecture, directory layout, CI/CD, linting, and test documentation

### Fixed

- Aligned FakeCascorClient response format with real cascor `ResponseEnvelope` (`_success_envelope()` wrapping, nested `state_machine/monitor/training_state` structure, bare list for metrics history, flat param dict)

### Changed

- Bumped github/codeql-action from 4.33.0 to 4.34.1 (Dependabot)
- Bumped actions/cache from 5.0.3 to 5.0.4 (Dependabot)
- Bumped github/codeql-action from 4.34.1 to 4.35.1 (Dependabot)

## [0.2.0] - 2026-03-21

### Added

- `update_params()` client method for runtime training parameter updates (`PATCH /v1/training/params`)
- `_patch()` helper method and `PATCH` in `ALLOWED_METHODS` set on `JuniperCascorClient`
- FakeCascorClient `update_params()` with scenario-aware state updates
- Tests for `update_params()` on both real client (responses mock) and fake client
- FakeCascorClient and FakeCascorTrainingStream testing submodule (`juniper_cascor_client.testing`)
- `JUNIPER_CASCOR_API_KEY` environment variable fallback for API key
- Cross-repo CI dispatch to juniper-canopy on push to main
- Dependabot configuration for automated dependency updates (weekly)
- CODEOWNERS file for PR review routing
- SOPS config (`.sops.yaml`) and `.env.example` for secrets management
- CHANGELOG.md following Keep a Changelog format
- Documentation suite: DOCUMENTATION_OVERVIEW.md, QUICK_START.md, REFERENCE.md
- Developer cheatsheet (`docs/DEVELOPER_CHEATSHEET.md`)
- AGENTS.md with thread handoff and worktree procedures
- Pre-commit hooks configuration with markdownlint, shellcheck, flake8, bandit, yamllint
- Ecosystem compatibility matrix in README

### Fixed

- Aligned FakeCascorClient decision boundary format with real API (`grid_x`/`grid_y` as 2D meshgrid arrays, integer argmax class indices instead of 1D arrays with continuous sigmoid values)
- Incorrect file references in AGENTS.md key files table

### Changed

- SHA-pinned all GitHub Actions to immutable commit hashes
- Expanded `.gitignore` to cover all `.env` variants and `.env.secrets`
- Set line length to 512 for all linters (black, isort, flake8) per Juniper ecosystem standard
- Removed py314 from black target versions
- Propagated V2 worktree cleanup procedure (CWD-trap bug fix)
- Bumped actions/checkout from 4 to 6 (Dependabot)
- Bumped actions/setup-python from 5 to 6 (Dependabot)
- Bumped actions/upload-artifact from 4 to 6 (Dependabot)
- Bumped actions/cache from 4.2.3 to 5.0.3 (Dependabot)
- Bumped github/codeql-action from 3.28.0 to 4.33.0 (Dependabot)

## [0.1.0] - 2026-02-22

### Added

- Initial release of `juniper-cascor-client`
- `CascorClient` class with REST API coverage for juniper-cascor
- `CascorTrainingStream` WebSocket client for real-time training monitoring
- `CascorClientError` exception hierarchy
- Type annotations with `py.typed` marker
- Unit test suite with 80%+ coverage
- CI/CD pipeline with GitHub Actions
- PyPI and TestPyPI trusted publishing
- README with API documentation and examples
- Ecosystem compatibility matrix
- AGENTS.md with thread handoff and worktree procedures

[Unreleased]: https://github.com/pcalnon/juniper-cascor-client/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/pcalnon/juniper-cascor-client/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/pcalnon/juniper-cascor-client/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/pcalnon/juniper-cascor-client/releases/tag/v0.1.0
