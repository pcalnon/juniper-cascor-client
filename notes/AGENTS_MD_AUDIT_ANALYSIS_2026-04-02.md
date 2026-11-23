# AGENTS.md Drift Analysis - juniper-cascor-client

**Date**: 2026-04-02
**Auditor**: Claude Code (automated)
**Scope**: Full audit of AGENTS.md against codebase state at commit 3851ea8
**Version**: AGENTS.md declares 0.1.0; actual package version is 0.3.0

---

## Executive Summary

The juniper-cascor-client AGENTS.md file has significant drift from the current codebase state. The file was last meaningfully updated at the 0.1.0 release (2026-02-25) and has not been updated through the subsequent development of features including: testing utilities submodule, snapshot management, worker management, dataset data endpoints, runtime parameter updates, security tooling, and CI/CD enhancements.

The document is structurally sparse compared to peer AGENTS.md files in the Juniper ecosystem. It lacks sections for directory layout, CI/CD details, linting/formatting configuration, environment variables, test organization, security scanning, and documentation references.

---

## Drift Analysis by Section

### 1. Header Metadata

| Field | AGENTS.md Value | Actual Value | Status |
|-------|-----------------|--------------|--------|
| Version | 0.1.0 | 0.3.0 | **STALE** |
| Last Updated | 2026-02-25 | N/A (needs update to 2026-04-02) | **STALE** |
| Project name | juniper-cascor-client | juniper-cascor-client | Correct |
| License | MIT License | MIT License | Correct |
| Author | Paul Calnon | Paul Calnon | Correct |

### 2. Essential Commands

| Command | AGENTS.md | Actual | Status |
|---------|-----------|--------|--------|
| Install dev | `pip install -e ".[dev]"` | `pip install -e ".[dev]"` | Correct |
| Run tests | `pytest tests/ -v` | `pytest tests/ -v` | Correct |
| Coverage | `pytest tests/ --cov=... --cov-fail-under=80` | Same | Correct |
| Type checking | `mypy juniper_cascor_client --strict` | Same | Correct |
| Flake8 line length | `--max-line-length=120` | `--max-line-length=512` | **WRONG** |
| Black check | `black --check --diff juniper_cascor_client` | Same | Correct |
| isort check | `isort --check-only --diff juniper_cascor_client` | Same | Correct |
| Pre-commit | Not mentioned | `pre-commit run --all-files` | **MISSING** |
| Build | Not mentioned | `python -m build && twine check dist/*` | **MISSING** |
| Doc link check | Not mentioned | `python scripts/check_doc_links.py` | **MISSING** |
| Dep docs gen | Not mentioned | `bash scripts/generate_dep_docs.sh` | **MISSING** |

**Critical finding**: The flake8 `--max-line-length=120` is incorrect. The Juniper ecosystem standard is 512, and pyproject.toml/.pre-commit-config.yaml both specify 512.

### 3. Key Files Table

| Listed in AGENTS.md | Exists | Status |
|---------------------|--------|--------|
| `juniper_cascor_client/client.py` | Yes | Correct |
| `juniper_cascor_client/ws_client.py` | Yes | Correct |
| `juniper_cascor_client/exceptions.py` | Yes | Correct |
| `juniper_cascor_client/__init__.py` | Yes | Correct |
| `pyproject.toml` | Yes | Correct |
| `tests/` | Yes | Correct |

**Missing from Key Files table**:

| File/Directory | Purpose | Status |
|----------------|---------|--------|
| `juniper_cascor_client/testing/` | Testing utilities submodule (FakeCascorClient, FakeCascorTrainingStream, scenarios) | **MISSING** |
| `juniper_cascor_client/py.typed` | PEP 561 type marker | **MISSING** |
| `CHANGELOG.md` | Version history | **MISSING** |
| `docs/` | User documentation (REFERENCE.md, QUICK_START.md, DEVELOPER_CHEATSHEET.md, DOCUMENTATION_OVERVIEW.md) | **MISSING** |
| `scripts/` | Utility scripts (check_doc_links.py, generate_dep_docs.sh) | **MISSING** |
| `notes/` | Procedures and templates | **MISSING** |
| `.env.example` | Environment variable template | **MISSING** |
| `.pre-commit-config.yaml` | Pre-commit hook configuration | **MISSING** |
| `.github/workflows/ci.yml` | CI/CD pipeline | **MISSING** |
| `.github/workflows/publish.yml` | PyPI publishing workflow | **MISSING** |
| `.github/CODEOWNERS` | Code ownership | **MISSING** |
| `.github/dependabot.yml` | Automated dependency updates | **MISSING** |
| `.sops.yaml` | Secrets encryption configuration | **MISSING** |
| `conf/` | Generated dependency documentation | **MISSING** |
| `tests/conftest.py` | Shared pytest fixtures | **MISSING** |

### 4. Project Overview

**Current state**: Minimal — one paragraph describing the project as "the official Python client library" with "synchronous REST client and async WebSocket streams."

**Missing content**:
- No mention of the `testing` submodule (FakeCascorClient, FakeCascorTrainingStream)
- No description of exception hierarchy (7 exception classes)
- No API surface area summary (42+ REST methods across 8 categories: health, network, training, metrics, data, snapshots, workers, params)
- No mention of PEP 561 type compliance
- No mention of thread-safe fake client design
- No mention of scenario-driven testing system (5 scenarios)

### 5. Dependencies Table

**Current state**: Lists only 3 core runtime dependencies.

| Listed | Actual | Status |
|--------|--------|--------|
| `requests` | `requests>=2.28.0` | Correct (version missing) |
| `urllib3` | `urllib3>=2.0.0` | Correct (version missing) |
| `websockets` | `websockets>=11.0` | Correct (version missing) |

**Missing dependency groups**:
- `[test]`: pytest, pytest-cov, pytest-timeout, pytest-asyncio, responses
- `[dev]`: black, isort, mypy, flake8, types-requests (plus all test deps)

### 6. Ecosystem Context

**Current state**: Basic dependency graph showing juniper-ml and JuniperCanopy as consumers.

**Issues**:
- Uses "JuniperCanopy" and "JuniperCascor" (PascalCase) instead of the standard repo names "juniper-canopy" and "juniper-cascor"
- Missing cross-repo CI dispatch relationship (juniper-cascor-client triggers juniper-canopy CI)
- Missing version compatibility information (available in docs/DOCUMENTATION_OVERVIEW.md)

### 7. Missing Sections (Not Present in AGENTS.md)

The following sections should exist based on peer AGENTS.md files and the directives:

| Section | Priority | Rationale |
|---------|----------|-----------|
| **Directory Layout** | High | Required by directives; provides codebase orientation |
| **Architecture** | High | Required by directives; documents class hierarchy, API categories, patterns |
| **CI/CD Pipeline** | Medium | Documents GitHub Actions workflow structure and quality gates |
| **Pre-commit Hooks** | Medium | Documents local quality enforcement |
| **Linting & Formatting** | Medium | Documents line length (512), tool versions, complexity limits |
| **Test Organization** | Medium | Documents test structure, markers, fixtures, coverage requirements |
| **Environment Variables** | Medium | Documents JUNIPER_CASCOR_API_KEY, CASCOR_SERVICE_URL |
| **Security** | Medium | Documents SOPS, Gitleaks, Bandit, pip-audit |
| **Publishing** | Low | Documents PyPI/TestPyPI workflow |
| **Documentation Files** | Low | Points to docs/ directory contents |
| **Python Version Support** | Medium | Documents >=3.11, tested on 3.11-3.14 |
| **MCP Server Availability** | Low | Requested by directives |

### 8. Worktree Procedures Section

**Status**: Up to date and accurate. References correct procedure files.

### 9. Thread Handoff Section

**Status**: Up to date and accurate. References correct procedure file.

---

## Severity Classification

### Critical (Incorrect Information)

1. **Flake8 line length**: AGENTS.md says 120, actual is 512. An agent following this instruction would produce false-positive linting failures.
2. **Version mismatch**: AGENTS.md says 0.1.0, package is 0.3.0. Misleads agents about the maturity and feature set.

### High (Missing Significant Content)

3. **No directory layout**: Agents cannot orient themselves in the codebase.
4. **No architecture section**: Agents have no guidance on the class hierarchy, API categories, or design patterns.
5. **Missing testing submodule from key files**: The testing/ submodule (1,807 lines) is a major part of the codebase and is invisible to agents.
6. **Missing API surface area**: 42+ REST methods, WebSocket callbacks, exception hierarchy — none documented.
7. **Missing test files**: 8 test modules, conftest.py with 5 scenario fixtures — none documented.

### Medium (Missing Supporting Content)

8. **Missing CI/CD documentation**: 2 workflows, quality gates, downstream dispatch.
9. **Missing environment variables**: JUNIPER_CASCOR_API_KEY, CASCOR_SERVICE_URL.
10. **Missing pre-commit hooks**: 10+ hooks across formatting, linting, security, SOPS.
11. **Missing Python version support**: >=3.11, tested on 3.11-3.14.
12. **Missing linting configuration**: Line length 512, complexity limits.
13. **Missing docs/ directory reference**: 4 documentation files.
14. **Missing scripts/ directory reference**: 2 utility scripts.

### Low (Nice to Have)

15. **Missing dependency version constraints**: Core deps listed without version bounds.
16. **Missing dev/test dependency groups**: Only runtime deps listed.
17. **Missing publishing workflow documentation**.
18. **Missing MCP server availability note**.

---

## Quantitative Summary

| Metric | Count |
|--------|-------|
| Total drift items identified | 18 |
| Critical (incorrect info) | 2 |
| High (missing significant content) | 5 |
| Medium (missing supporting content) | 7 |
| Low (nice to have) | 4 |
| Sections needing update | 5 of 7 |
| New sections needed | ~8 |
| Accurate/up-to-date sections | 2 (Worktree, Thread Handoff) |
