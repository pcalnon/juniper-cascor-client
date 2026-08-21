# AGENTS.md - Juniper Cascor Client

**Project**: juniper-cascor-client — HTTP/WebSocket Client for juniper-cascor
**Repository**: pcalnon/juniper-cascor-client
**Author**: Paul Calnon
**License**: MIT License
**Version**: 0.7.0
**Last Updated**: 2026-08-21

---

## Quick Reference

### Essential Commands

```bash
# Install in development mode
pip install -e ".[dev]"

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=juniper_cascor_client --cov-report=term-missing --cov-fail-under=80

# Type checking (strict mode)
mypy juniper_cascor_client --strict

# Linting
flake8 juniper_cascor_client --max-line-length=512
black --check --diff juniper_cascor_client
isort --check-only --diff juniper_cascor_client

# Pre-commit (all hooks)
pre-commit run --all-files

# Build package
python -m build
twine check dist/*

# Validate documentation links
python scripts/check_doc_links.py

# Generate dependency documentation
bash scripts/generate_dep_docs.sh
```

### Coverage

Reproduce the CI coverage gate locally (full suite):

```bash
make coverage                 # convenience wrapper
bash util/run_coverage.bash   # source of truth (mirrors .github/workflows/ci.yml)
```

Gate: 80% aggregate (override with `COVERAGE_FAIL_UNDER=<n>`). The script runs the full suite by design so the percentage matches CI; for a narrower run use plain `pytest`.

### Key Files

| File | Purpose |
|------|---------|
| `juniper_cascor_client/client.py` | REST client class (`JuniperCascorClient`) |
| `juniper_cascor_client/ws_client.py` | WebSocket clients (`CascorTrainingStream`, `CascorControlStream`) |
| `juniper_cascor_client/exceptions.py` | Exception hierarchy (7 classes) |
| `juniper_cascor_client/__init__.py` | Public API exports and version |
| `juniper_cascor_client/py.typed` | PEP 561 typed package marker |
| `juniper_cascor_client/testing/` | Testing utilities submodule |
| `juniper_cascor_client/testing/fake_client.py` | In-memory fake REST client (`FakeCascorClient`) |
| `juniper_cascor_client/testing/fake_ws_client.py` | In-memory fake WebSocket client (`FakeCascorTrainingStream`) |
| `juniper_cascor_client/testing/scenarios.py` | Scenario data, metric curve generators, topology builders |
| `pyproject.toml` | Package config, dependencies, tool settings |
| `tests/` | Test suite (pytest, pytest-asyncio, responses) |
| `tests/conftest.py` | Shared fixtures (5 scenario-based fake clients) |
| `docs/` | User documentation (reference, quick start, cheatsheet) |
| `scripts/` | Utility scripts (doc link check, dep doc generation) |
| `notes/` | Procedures and templates |
| `CHANGELOG.md` | Version history (Keep a Changelog format) |
| `.pre-commit-config.yaml` | Pre-commit hook configuration (10+ hooks) |
| `.github/workflows/ci.yml` | CI/CD pipeline (GitHub Actions) |
| `.github/workflows/publish.yml` | PyPI publishing workflow |
| `.env.example` | Environment variable template |

---

## Project Overview

`juniper-cascor-client` is the official Python client library for the juniper-cascor training service. It provides:

- **Synchronous REST client** (`JuniperCascorClient`) — 42+ methods across 8 API categories with connection pooling, retry logic, and structured error handling
- **Async WebSocket streams** — `CascorTrainingStream` (callback/iterator-based real-time monitoring) and `CascorControlStream` (command/response control)
- **Testing utilities submodule** (`juniper_cascor_client.testing`) — Thread-safe fake clients with scenario-driven state machines for consumer testing without a live service

### Python Version Support

- **Requires**: `>=3.11`
- **Tested on**: 3.11, 3.12, 3.13
- **Classified for**: 3.11, 3.12, 3.13, 3.14

### Dependencies

#### Runtime

| Library | Version | Purpose |
|---------|---------|---------|
| `requests` | `>=2.28.0` | HTTP REST client with session management |
| `urllib3` | `>=2.0.0` | HTTP connection pooling and retry strategy |
| `websockets` | `>=11.0` | Async WebSocket client |

#### Test (`pip install -e ".[test]"`)

| Library | Version | Purpose |
|---------|---------|---------|
| `pytest` | `>=7.0.0` | Test framework |
| `pytest-cov` | `>=4.0.0` | Coverage reporting |
| `pytest-timeout` | `>=2.2.0` | Per-test timeout enforcement (30s) |
| `pytest-asyncio` | `>=0.21.0` | Async test support |
| `responses` | `>=0.23.0` | HTTP response mocking |

#### Dev (`pip install -e ".[dev]"`)

Includes all test dependencies plus:

| Library | Version | Purpose |
|---------|---------|---------|
| `black` | `>=23.0.0` | Code formatting |
| `isort` | `>=5.12.0` | Import sorting |
| `mypy` | `>=1.0.0` | Static type checking (strict mode) |
| `flake8` | `>=7.0.0` | Linting |
| `types-requests` | `>=2.28.0` | Type stubs for requests |

---

## Architecture

### Class Hierarchy

```text
JuniperCascorClient          Synchronous REST client (context manager)
  ├── Health:                health_check(), is_alive(), is_ready(), wait_for_ready()
  ├── Network:               create_network(), get_network(), delete_network(), get_topology(), get_statistics()
  ├── Training Control:      start_training(), stop_training(), pause_training(), resume_training(), reset_training()
  ├── Status & Params:       get_training_status(), get_training_params(), update_params()
  ├── Metrics:               get_metrics(), get_metrics_history()
  ├── Data & Visualization:  get_dataset(), get_dataset_data(), get_decision_boundary()
  ├── Snapshots:             list_snapshots(), get_snapshot(), save_snapshot(), load_snapshot()
  └── Workers:               list_workers(), get_worker(), get_worker_stats()

CascorTrainingStream         Async WebSocket streaming client (async context manager, async iterator)
  ├── connect(), disconnect()
  ├── stream() -> AsyncIterator
  ├── listen() (callback dispatch)
  ├── send_command()
  ├── Callbacks: on_metrics(), on_state(), on_topology(), on_cascade_add(), on_event()
  └── CL1 heartbeat + liveness: server ``{"type":"ping"}`` frames are answered
          with ``{"type":"pong"}`` and consumed (``auto_pong=True`` default;
          ``auto_pong=False`` yields pings to the consumer); liveness surface
          ``is_connected`` / ``is_alive(window_sec)`` / ``last_frame_at`` /
          ``pongs_sent`` (mirrored by FakeCascorTrainingStream).

CascorControlStream          Async WebSocket command/response client (async context manager)
  ├── connect(), disconnect()
  │       CL1: connect() starts the background recv loop eagerly so server
  │       heartbeat pings are answered from t0 (pre-0.7.0, an idle control
  │       connection was closed by cascor 40s after connect).
  ├── command(command, params=None) -> Dict
  │       Send a control command (start/stop/pause/resume/reset). Routes
  │       through the per-request correlation system whenever the background
  │       recv task is running (the normal case after connect()); the
  │       direct single-recv path remains as a fallback and skips/answers
  │       heartbeat pings. Both paths emit the canonical envelope
  │       ``{"type": "command", "command": ..., ...}`` (XREPO-07/08, CC-06).
  ├── Liveness surface: is_connected / is_alive(window_sec) / last_frame_at / pongs_sent (CL1)
  └── set_params(params, *, timeout=1.0, command_id=None) -> Dict
          Apply a runtime parameter update (e.g. ``{"learning_rate": 0.01}``)
          via /ws/control with per-request correlation by ``command_id``.
          Fails fast on timeout or disconnect with no automatic retries
          (D-20, C-04). The default 1.0 s timeout (D-01) lets callers fall
          back to a REST update without waiting indefinitely. Concurrent
          callers are bounded by ``MAX_PENDING_COMMANDS`` (256); exceeding
          the cap raises ``JuniperCascorOverloadError``.
```

### WebSocket Outbound Message Envelope

All client→server messages on `/ws/control` carry a uniform envelope so the
server can dispatch by `type` regardless of which client method produced
them (XREPO-07/08, CC-06; aligned in Phase 4D):

```json
{"type": "command", "command": "<name>", "params": {...}, "command_id": "<uuid>"}
```

`type` is always `"command"` (the constant `WS_MSG_TYPE_COMMAND_OUT`);
`params` is omitted when empty; `command_id` is present whenever per-request
correlation is in effect (`set_params()` always; `command()` only when the
correlated path is taken).

### Exception Hierarchy

```text
JuniperCascorClientError (base)
  ├── JuniperCascorConnectionError       Network/connection failures
  ├── JuniperCascorTimeoutError          Request timeout
  ├── JuniperCascorNotFoundError         HTTP 404
  ├── JuniperCascorConflictError         HTTP 409
  ├── JuniperCascorValidationError       HTTP 400/422
  └── JuniperCascorServiceUnavailableError  HTTP 503
```

#### Exception context (do not remove)

Every exception carries four attributes, set by the base `__init__`:

| Attribute | Meaning |
|-----------|---------|
| `message` | The human-readable summary; also what `str(exc)` returns. |
| `status_code` | HTTP status of the originating response, or `None` when raised without one (connection, timeout, "client is closed", retry-exhausted). |
| `detail` | The server's error payload **exactly as decoded**. This service answers with two envelopes (`{"error": {"message": ...}}` and FastAPI's `{"detail": ...}`), and the latter is a `list[dict]` for a 422. Never stringified. |
| `response` | The originating `requests.Response`, when there was one. |

`status_code` is the **only** thing separating a 400 from a 422 — both raise
`JuniperCascorValidationError`. `_handle_response` used to compute the status
and then drop it on four of its five branches, which made those two responses
byte-identical (defect-register `APD-CCLIENT-004`, absorbing the retired
`APD-CCLIENT-003`).

Constraints a refactor must not break:

- **The extra parameters are keyword-only**, so the 29 single-positional-message
  raises in `FakeCascorClient` — and every consumer call site — keep working.
- **`detail` keeps the server's structure.** The message renders a 422 list as
  `body.input_size: Field required` via `client._render_error_detail`; the list
  itself stays on the attribute.
- **`__reduce__` must stay.** `BaseException.__reduce__` rebuilds from `args`,
  which holds only the message, so without it a pickle/copy round-trip returns an
  exception that looks right and has silently lost the context. That is what
  flake8-bugbear's `B042` warns about; the `noqa` on `__init__` is paired with
  `__reduce__`, not a dismissal.

`FakeCascorClient` populates `status_code` on every HTTP-shaped error it raises
(404 not-found, 409 conflict, 422 validation — the real service validates those
inputs with pydantic `Field(ge=1)` / `Query(ge=, le=)`, which FastAPI answers
422). Its one local-state error ("Client is closed") deliberately has none. The
fake claims full API parity, so a double raising the right type with
`status_code=None` would let a consumer's test pass against behaviour production
does not have.

**This mirrors `juniper-data-client` deliberately** (juniper-data-client#158 is
the reference implementation; `juniper-recurrence-client` is the third). The
three are separately released packages with no shared code, so no drift check can
enforce it — the alignment is a convention, kept by these notes and by each
package's tests.

### Testing Utilities (`juniper_cascor_client.testing`)

| Class | Purpose |
|-------|---------|
| `FakeCascorClient` | In-memory REST client fake with 5 scenarios, thread-safe, full API parity |
| `FakeCascorTrainingStream` | In-memory WebSocket stream fake with message injection |

**Scenarios**: `idle`, `two_spiral_training`, `xor_converged`, `empty`, `error_prone`

### Key Design Patterns

- **Context Manager**: REST client (sync `with`), WebSocket clients (async `async with`)
- **Callback/Observer**: WebSocket training stream dispatches to registered callbacks by message type
- **Async Iteration**: `async for message in stream.stream():`
- **Retry with Backoff**: HTTP adapter retries 502/504 with 0.5s exponential backoff (3 retries)
- **Connection Pooling**: 10 max connections per host via `HTTPAdapter`
- **Response Envelope**: All responses wrapped as `{"status": "success", "data": {...}, "meta": {...}}`
- **State Machine**: FakeCascorClient implements training state transitions (idle -> training -> paused -> complete)
- **Scenario-Driven Testing**: Configurable scenarios generate realistic metric curves, topologies, and datasets

---

## Directory Layout

```text
juniper-cascor-client/
├── juniper_cascor_client/           # Main package
│   ├── __init__.py                  # Public API exports, version (0.3.0)
│   ├── client.py                    # JuniperCascorClient (REST, 353 lines)
│   ├── constants.py                 # Endpoint paths, header names, defaults, scenario constants
│   ├── ws_client.py                 # CascorTrainingStream, CascorControlStream (212 lines)
│   ├── exceptions.py                # Exception hierarchy (43 lines)
│   ├── py.typed                     # PEP 561 marker
│   └── testing/                     # Testing utilities submodule
│       ├── __init__.py              # Exports FakeCascorClient, FakeCascorTrainingStream
│       ├── fake_client.py           # In-memory fake REST client (1003 lines)
│       ├── fake_ws_client.py        # In-memory fake WebSocket client (222 lines)
│       └── scenarios.py             # Scenario data, curve generators (554 lines)
├── tests/                           # Test suite
│   ├── conftest.py                  # Pytest fixtures (5 scenario fixtures)
│   ├── test_client.py               # REST client unit tests
│   ├── test_client_update_params.py # Parameter update tests
│   ├── test_fake_client.py          # FakeCascorClient comprehensive tests
│   ├── test_fake_client_update_params.py  # Fake client param update tests
│   ├── test_fake_client_workers.py  # Worker/async tests
│   ├── test_fake_ws_client.py       # FakeCascorTrainingStream tests
│   └── test_ws_client.py            # WebSocket client tests
├── docs/                            # User documentation
│   ├── DOCUMENTATION_OVERVIEW.md    # Documentation index and navigation
│   ├── REFERENCE.md                 # Complete API reference
│   ├── QUICK_START.md               # Getting started guide
│   └── DEVELOPER_CHEATSHEET.md      # Developer quick reference
├── notes/                           # Procedures and templates
│   ├── WORKTREE_SETUP_PROCEDURE.md
│   ├── WORKTREE_CLEANUP_PROCEDURE_V2.md
│   ├── THREAD_HANDOFF_PROCEDURE.md
│   ├── CONDA_DEPENDENCY_FILE_HEADER.md
│   ├── PIP_DEPENDENCY_FILE_HEADER.md
│   ├── juniper-cascor-client_OTHER_DEPENDENCIES.md
│   └── history/                     # Archived procedures
│       └── WORKTREE_CLEANUP_PROCEDURE_V1.md
├── scripts/                         # Utility scripts
│   ├── check_doc_links.py           # Documentation link validator
│   └── generate_dep_docs.sh         # Dependency doc generator (conf/*.txt, conf/*.yaml)
├── .github/
│   ├── CODEOWNERS                   # Code ownership (@pcalnon)
│   ├── dependabot.yml               # Automated dependency updates (weekly)
│   └── workflows/
│       ├── ci.yml                   # CI/CD pipeline (pre-commit, tests, build, security)
│       └── publish.yml              # PyPI/TestPyPI publishing
├── conf/                            # Generated dependency documentation (created by scripts/generate_dep_docs.sh, gitignored)
├── AGENTS.md                        # This file
├── CLAUDE.md                        # Symlink -> AGENTS.md
├── CHANGELOG.md                     # Version history
├── README.md                        # PyPI/GitHub landing page
├── LICENSE                          # MIT License
├── pyproject.toml                   # Package configuration
├── .pre-commit-config.yaml          # Pre-commit hooks
├── .env.example                     # Environment variable template
├── .sops.yaml                       # SOPS encryption config for .env files
├── .markdownlint.yaml               # Markdown linting rules
└── .gitignore
```

---

## Script Placement

**Permanent utilities** live in `util/`. **Single-use / temporary / unfinished scripts** go in `util/ad-hoc/` (create on first use). See [`util/ad-hoc/README.md`](util/ad-hoc/README.md) for the per-script header / lifecycle conventions.

`/tmp/` is **prohibited** as the home for any script that produces, modifies, or analyzes repository content. `/tmp/` is reaped when sessions / sandboxes / containers end, and scripts placed there are lost (irrecoverable). `/tmp/` remains fine as a scratch *workspace* for intermediate artifacts the script itself creates and reads — the prohibition is on script *source files*.

This is an ecosystem-wide rule restated in the parent `Juniper/AGENTS.md` "Cross-Project Conventions" section. Motivating incident: irrecoverable loss of `phase4_consolidate.py` and `v2_citation_validate.py` from the juniper-ml requirements-snapshot effort.

---

## Environment Variables

| Variable | Used By | Purpose | Default |
|----------|---------|---------|---------|
| `JUNIPER_CASCOR_API_KEY` | `JuniperCascorClient` | API key fallback (if not passed to constructor) | None |
| `CASCOR_SERVICE_URL` | Consumers (juniper-canopy, juniper-deploy) | Service URL override | `http://localhost:8200` |

Template: `.env.example`

---

## Constants

Every previously inline literal in `client.py`, `ws_client.py`, `testing/fake_client.py`, and `testing/scenarios.py` is now centralized in `juniper_cascor_client/constants.py`. Application code imports from this module rather than embedding literals.

### Categories

| Prefix / Group | Examples | Purpose |
|----------------|----------|---------|
| `API_KEY_*`, `API_VERSION_*` | `API_KEY_HEADER_NAME='X-API-Key'`, `API_KEY_ENV_VAR='JUNIPER_CASCOR_API_KEY'`, `API_VERSION_PATH='/v1'` | Wire-protocol identifiers shared with the `juniper-cascor` server |
| `ENDPOINT_*`, `WS_*_PATH` | `ENDPOINT_TRAINING_START='/training/start'`, `ENDPOINT_NETWORK_TOPOLOGY='/network/topology'`, `WS_TRAINING_PATH='/ws/training'` | Relative paths under each FastAPI router (server prefix + this constant = full URL) |
| `DEFAULT_*` | `DEFAULT_BASE_URL='http://localhost:8200'`, `DEFAULT_TIMEOUT_SECONDS`, `DEFAULT_BACKOFF_FACTOR=0.5` | Constructor defaults for `JuniperCascorClient` and `CascorTrainingStream` / `CascorControlStream` |
| `MSG_TYPE_*` | `MSG_TYPE_HEARTBEAT='heartbeat'`, `MSG_TYPE_REGISTRATION_ACK` | WebSocket message-type discriminators (must remain bit-identical to the server's `MessageType` enum) |
| Scenario / generator defaults | `SCENARIO_*`, fake-client tuning | Default values used by `testing/fake_client.py` and `testing/scenarios.py` to keep fakes deterministic |

### Alignment with `juniper-cascor`

- `API_KEY_HEADER_NAME` matches the literal `"X-API-Key"` checked by `juniper-cascor/src/api/security.py`.
- All `ENDPOINT_*` paths equal the relative routes declared on the corresponding `APIRouter` in `juniper-cascor/src/api/routes/`.
- `MSG_TYPE_*` values are bit-identical to the cascor server's `MessageType(StrEnum)` in `src/api/workers/protocol.py`. Wave 5 verified this with a programmatic comparison and the cascor-worker package shares the same set under `MSG_TYPE_*` names.

### Modifying

When the cascor server adds or renames an endpoint, header, or wire-protocol message type:

1. Update the constant in `constants.py` first (with a docstring noting cross-repo coupling)
2. Update the corresponding consumer in `client.py` / `ws_client.py` / `testing/`
3. Run the cross-repo alignment check from the project roadmap before merging

---

## Linting & Formatting

All tools use the **Juniper ecosystem standard line length of 512**.

| Tool | Config Location | Key Settings |
|------|-----------------|--------------|
| **black** | `pyproject.toml` | line-length=512, target py311/py312/py313 |
| **isort** | `pyproject.toml` | profile=black, line-length=512 |
| **flake8** | `.pre-commit-config.yaml` | max-line-length=512, max-complexity=15 (source) / 25 (tests) |
| **mypy** | `pyproject.toml` | strict=true, python_version=3.11, ignore_missing_imports=false |
| **bandit** | `.pre-commit-config.yaml` | Strict for source, relaxed for tests (allows assert, hardcoded values) |
| **markdownlint** | `.markdownlint.yaml` | line-length=512, excludes CHANGELOG.md/notes/docs |
| **shellcheck** | `.pre-commit-config.yaml` | severity=warning |
| **yamllint** | `.pre-commit-config.yaml` | relaxed config |

---

## Test Organization

### Structure

- **Framework**: pytest with strict markers
- **Coverage requirement**: 80% (branch coverage enabled)
- **Timeout**: 30 seconds per test
- **Markers**: `unit`, `integration`

### Fixtures (conftest.py)

| Fixture | Scenario | Description |
|---------|----------|-------------|
| `fake_idle` | `idle` | Ready for network creation |
| `fake_training` | `two_spiral_training` | Active training with realistic metric curves |
| `fake_converged` | `xor_converged` | Fully trained network |
| `fake_empty` | `empty` | Minimal responses (negative testing) |
| `fake_error` | `error_prone` | ~10% random error rate |

### Test Files

| File | Coverage |
|------|----------|
| `test_client.py` | REST client methods (mocked HTTP via `responses`) |
| `test_client_update_params.py` | Runtime parameter update method |
| `test_ws_client.py` | WebSocket client connect/stream/disconnect |
| `test_fake_client.py` | FakeCascorClient all methods, scenarios, state machine |
| `test_fake_client_update_params.py` | FakeCascorClient parameter updates |
| `test_fake_client_workers.py` | FakeCascorClient worker endpoints |
| `test_fake_ws_client.py` | FakeCascorTrainingStream message injection, callbacks |

---

## CI/CD Pipeline

### GitHub Actions Workflows

#### `ci.yml` — Main Pipeline

**Triggers**: push (main, develop, feature/\*\*, fix/\*\*), pull requests, workflow_dispatch

| Job | Matrix | Purpose |
|-----|--------|---------|
| **pre-commit** | Python 3.11, 3.12, 3.13 | All pre-commit hooks |
| **docs** | Single run | Documentation link validation |
| **unit-tests** | Python 3.11, 3.12, 3.13 | pytest with 80% coverage gate |
| **build** | Single run | sdist + wheel + twine check |
| **dependency-docs** | Single run | Generate conf/ files |
| **security** | Single run | Gitleaks, Bandit SARIF, pip-audit |
| **required-checks** | Aggregator | Quality gate (all jobs must pass) |
| **notify-downstream** | Main branch only | Triggers juniper-canopy CI via repository dispatch |

#### `publish.yml` — PyPI Publishing

**Trigger**: GitHub release published

1. Build and publish to TestPyPI, verify installation
2. Build and publish to production PyPI (trusted publishing / OIDC)

#### `sequence-safety.yml` — Per-PR Sequence-Safety Net (Advisory)

**Trigger**: pull requests (main, develop)

Advisory, standalone — never a required check and never wired into the CI Quality Gate. Runs the shared `juniper-ci-tools` (`>=0.8.0,<0.9.0`) sequence-safety screens over the PR's `base..HEAD` so silent compositional losses are visible at review:

- **symbol-loss screen** (`juniper-symbol-loss-check`, scoped `juniper_cascor_client/**/*.py` + `tests/**/*.py`) — FAILs on a silently deleted / gutted / duplicated `def` / `class` / method.
- **docs deletion-magnitude screen** (`juniper-docs-additions-check`, universal docs scope) — FAILs on a deleted heading or a run of consecutive deleted lines.

Both JSON reports upload as the `sequence-safety-report` artifact. An owner label hatch (`allow-symbol-loss` / `docs-rewrite`) demotes a screen to WARN-only; the `Allow-Symbol-Loss:` / `Allow-Docs-Rewrite:` commit trailers are the primary enumerated waivers.

#### `main-verify.yml` — Post-Merge Verification Net

**Trigger**: push (main), workflow_dispatch

Bypass-proof post-merge net: re-runs the two sequence-safety screens (same package + scope) against a catch-up base (the last successful `main-verify` tip, so a `[skip ci]` window is swept on the next run) after every merge to `main`. Per-SHA concurrency (`cancel-in-progress: false`) verifies every merge even during a storm; on failure it upserts a single stable-title tracking issue per red streak. Screens-only (no regression battery in this wave).

### Security Scanning

| Tool | Purpose | Integration |
|------|---------|-------------|
| **Gitleaks** | Secrets detection in git history | CI job |
| **Bandit** | Python SAST (SARIF upload to GitHub Security) | CI job + pre-commit |
| **pip-audit** | Dependency vulnerability scanning | CI job |
| **SOPS** | Age encryption for .env files | Pre-commit hook blocks unencrypted .env |

---

### PR base-branch guard (required check)

`.github/workflows/pr-base-branch-guard.yml` fails any PR whose base branch is not the
default branch. Its job name -- **`Guard PR base branch`** -- is a **required status check**
in this repo's ruleset, so renaming the job or deleting the file makes `main` unmergeable
until the context is un-required first.

**What it protects against.** A PR based on another feature branch can squash-merge into
that branch, stranding its content off `main` behind a green **MERGED** badge. It has
happened three times in this ecosystem (`juniper-recurrence#7`/`#8`, `juniper-canopy#365`).

**Why it matters more than it looks.** Both rulesets here are scoped to `~DEFAULT_BRANCH`, so
a PR whose base is a feature branch is governed by **no ruleset at all** -- it has zero
required status checks and merges clean with nothing having run:

```bash
gh api repos/pcalnon/<repo>/rules/branches/feature%2Fanything --jq length   # -> 0
gh api repos/pcalnon/<repo>/rules/branches/main               --jq length   # -> 9
```

This workflow carries no `branches:` filter, so it is the **only** check that runs on such a
PR. It cannot block the merge there -- no ruleset applies -- but it turns a silent merge into
a visibly red one.

**If it fails.** Re-open the work against the default branch. The house practice is
**close and re-open** a fresh PR titled `[retarget #NNN]`. Retargeting in place is *not*
sufficient on its own: every `ci*.yml` here uses the default `pull_request` types
`[opened, synchronize, reopened]`, which exclude `edited`, so a retarget re-runs this guard
and nothing else -- the PR stays blocked on its other required contexts until a push or a
close/re-open.

**`stacked-pr` label.** Silences this guard for a deliberate stack. It does **not** make the
PR mergeable into `main`, and it does **not** re-land the stack -- do that separately.

Rollout and rationale: [juniper-ml#434](https://github.com/pcalnon/juniper-ml/issues/434).

## Ecosystem Context

Part of the Juniper ecosystem. See the parent directory's `CLAUDE.md` at `/home/pcalnon/Development/python/Juniper/CLAUDE.md` for the full project map, dependency graph, shared conventions, and conda environment details.

### Position in Dependency Graph

```text
juniper-ml[clients]  ──depends on──>  juniper-cascor-client  ──calls──>  juniper-cascor (REST/WebSocket)
juniper-canopy       ──depends on──>  juniper-cascor-client  ──calls──>  juniper-cascor (REST/WebSocket)
```

### Cross-Repo CI

On push to `main`, the CI pipeline dispatches a workflow trigger to `juniper-canopy` to verify downstream compatibility.

### Service Port

juniper-cascor listens on port **8200** (host and container). The default `base_url` for the REST client is `http://localhost:8200`.

---

## Worktree Procedures (Mandatory — Task Isolation)

> **OPERATING INSTRUCTION**: All feature, bugfix, and task work SHOULD use git worktrees for isolation. Worktrees keep the main working directory on the default branch while task work proceeds in a separate checkout.

### What This Is

Git worktrees allow multiple branches of a repository to be checked out simultaneously in separate directories. For the Juniper ecosystem, all worktrees are centralized in **`/home/pcalnon/Development/python/Juniper/worktrees/`** using a standardized naming convention.

The full setup and cleanup procedures are defined in:

- **`notes/WORKTREE_SETUP_PROCEDURE.md`** — Creating a worktree for a new task
- **`notes/WORKTREE_CLEANUP_PROCEDURE_V2.md`** — Merging, removing, and pushing after task completion (V2 — fixes CWD-trap bug)

Read the appropriate file when starting or completing a task.

### Worktree Directory Naming

Format: `<repo-name>--<branch-name>--<YYYYMMDD-HHMM>--<short-hash>`

Example: `juniper-cascor-client--feature--add-retry--20260225-1430--410161a1`

- Slashes in branch names are replaced with `--`
- All worktrees reside in `/home/pcalnon/Development/python/Juniper/worktrees/`

### When to Use Worktrees

| Scenario | Use Worktree? |
| -------- | ------------- |
| Feature development (new feature branch) | **Yes** |
| Bug fix requiring a dedicated branch | **Yes** |
| Quick single-file documentation fix on main | No |
| Exploratory work that may be discarded | **Yes** |
| Hotfix requiring immediate merge | **Yes** |

### Quick Reference

**Setup** (full procedure in `notes/WORKTREE_SETUP_PROCEDURE.md`):

```bash
cd /home/pcalnon/Development/python/Juniper/juniper-cascor-client
git fetch origin && git checkout main && git pull origin main
BRANCH_NAME="feature/my-task"
git branch "$BRANCH_NAME" main
REPO_NAME=$(basename "$(pwd)")
SAFE_BRANCH=$(echo "$BRANCH_NAME" | sed 's|/|--|g')
WORKTREE_DIR="/home/pcalnon/Development/python/Juniper/worktrees/${REPO_NAME}--${SAFE_BRANCH}--$(date +%Y%m%d-%H%M)--$(git rev-parse --short=8 HEAD)"
git worktree add "$WORKTREE_DIR" "$BRANCH_NAME"
cd "$WORKTREE_DIR"
```

**Cleanup** (full procedure in `notes/WORKTREE_CLEANUP_PROCEDURE_V2.md`):

```bash
# Phase 1: Push current work
cd "$OLD_WORKTREE_DIR" && git push origin "$OLD_BRANCH"
# Phase 2: Create new worktree BEFORE removing old (prevents CWD-trap)
git fetch origin
git worktree add "$NEW_WORKTREE_DIR" -b "$NEW_BRANCH" origin/main
cd "$NEW_WORKTREE_DIR"
# Phase 3: Create PR (do NOT merge directly to main)
gh pr create --base main --head "$OLD_BRANCH" --title "<title>" --body "<body>"
# Phase 4: Cleanup
git worktree remove "$OLD_WORKTREE_DIR"
git branch -d "$OLD_BRANCH"
git worktree prune
```

### Rules

- **Centralized location**: All worktrees go in `/home/pcalnon/Development/python/Juniper/worktrees/`. Never create worktrees inside the repo directory.
- **Clean before you start**: Ensure the main working directory is clean before creating a worktree.
- **Push before you merge**: Always push the working branch to remote before merging (backup).
- **Prune after cleanup**: Run `git worktree prune` after removing a worktree to clean metadata.
- **Do not leave stale worktrees**: Clean up worktrees promptly after merging.

---

## Thread Handoff (Mandatory — Replaces Thread Compaction)

> **CRITICAL OPERATING INSTRUCTION**: Thread handoff MUST be performed instead of thread compaction. This section defines mandatory behavior that overrides Claude Code's default compaction process.

### What This Is

When a long-running conversation approaches context limits, Claude Code normally performs **thread compaction** — summarizing prior context to free token capacity. This introduces information loss. Instead, Claude Code instances working on this project MUST perform a **proactive thread handoff**: transferring a curated, high-signal summary to a fresh thread with full context capacity.

The full handoff protocol is defined in **`notes/THREAD_HANDOFF_PROCEDURE.md`**. Read that file when a handoff is triggered.

### When to Trigger a Handoff

**Automatic trigger (pre-compaction threshold):** Initiate a thread handoff when token utilization reaches **95% to 99%** of the level at which thread compaction would normally be triggered.

**Additional triggers**:

| Condition | Indicator |
| --------- | --------- |
| **Context saturation** | Thread has performed 15+ tool calls or edited 5+ files |
| **Phase boundary** | A logical phase of work is complete |
| **Degraded recall** | Re-reading a file already read, or re-asking a resolved question |
| **Multi-module transition** | Moving between major components |
| **User request** | User says "hand off", "new thread", or similar |

**Do NOT handoff** when:

- The task is nearly complete (< 2 remaining steps)
- The current thread is still sharp and producing correct output
- The work is tightly coupled and splitting would lose critical in-flight state

### How to Execute a Handoff

1. **Checkpoint**: Inventory what was done, what remains, what was discovered, and what files are in play
2. **Compose the handoff goal**: Write a concise, actionable summary (see templates in `notes/THREAD_HANDOFF_PROCEDURE.md`)
3. **Present to user**: Output the handoff goal to the user and recommend starting a new thread with that goal as the initial prompt
4. **Include verification commands**: Always specify how the new thread should verify its starting state
5. **State git status**: Mention branch, staged files, and any uncommitted work

### Rules

- **This is not optional.** Every Claude Code instance on this project must follow these rules.
- **Handoff early, not late.** A handoff at 70% context usage is better than compaction at 95%.
- **Do not duplicate CLAUDE.md content** in the handoff goal — the new thread reads CLAUDE.md automatically.
- **Be specific** in the handoff goal: include file paths, decisions made, and test status.
