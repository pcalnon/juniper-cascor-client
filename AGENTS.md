# AGENTS.md - Juniper Cascor Client

**Project**: juniper-cascor-client — HTTP/WebSocket Client for juniper-cascor
**Repository**: pcalnon/juniper-cascor-client
**Author**: Paul Calnon
**License**: MIT License
**Version**: 0.7.0
**Last Updated**: 2026-08-30

---

## Hazards (resident — do not relocate)

Directives whose **non-application destroys work**. Everything else in this file may be demoted to
`docs/REFERENCE.md` under the memory budget; these may not, because a pointer only helps an agent
that already knows to look. Adding a new hazard here is legitimate — ratchet space out of a
reference section in the same PR rather than waiving the budget gate.

- **`/tmp/` is prohibited** as the home for any script that produces, modifies or analyzes
  repository content — it is reaped when sessions, sandboxes or containers end, and the scripts are
  irrecoverable. Scratch *data* there is fine; source files are not. Permanent utilities live in
  `util/`, single-use ones in `util/ad-hoc/`. Full rule: § Script Placement.

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

The full client architecture: layers, transports, retry/backoff, and the reconnect state machine. Moved to [`docs/REFERENCE.md` § Architecture Reference](docs/REFERENCE.md#architecture-reference) — read it when working on this area.

## Directory Layout

The annotated source tree, with the purpose of every package and key module. Moved to [`docs/REFERENCE.md` § Directory Layout Reference](docs/REFERENCE.md#directory-layout-reference) — read it when working on this area.

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

Every exported constant, its default, and the failure each one guards against. Moved to [`docs/REFERENCE.md` § Constants Reference](docs/REFERENCE.md#constants-reference) — read it when working on this area.

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

Per-workflow reference for `.github/workflows/`, including the contract each job must not break. Moved to [`docs/REFERENCE.md` § CI/CD Pipeline Reference](docs/REFERENCE.md#cicd-pipeline-reference) — read it when working on this area.

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
