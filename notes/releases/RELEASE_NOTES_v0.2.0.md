# Juniper Cascor Client v0.2.0 Release Notes

**Release Date:** 2026-03-21
**Version:** 0.2.0
**Release Type:** MINOR

---

## Overview

This release adds the `update_params()` client method for runtime training parameter updates and introduces the `juniper_cascor_client.testing` submodule with `FakeCascorClient` and `FakeCascorTrainingStream` for consumer testing without a running cascor backend. Also includes a comprehensive documentation suite, pre-commit hooks, and SOPS-based secrets management.

> **Status:** STABLE — Backward-compatible additive release.

---

## Release Summary

- **Release type:** MINOR
- **Primary focus:** Runtime parameter updates, consumer testing infrastructure, documentation suite
- **Breaking changes:** No
- **Priority summary:** New testing module + `update_params()` API + full documentation suite + Dependabot/CI hardening

---

## What's New

### Runtime Parameter Updates

- `update_params()` client method on `JuniperCascorClient` — updates training parameters at runtime via `PATCH /v1/training/params`
- `_patch()` helper method and `PATCH` added to `ALLOWED_METHODS` set
- Tests for `update_params()` against both real client (responses mock) and fake client

### Consumer Testing Submodule

New `juniper_cascor_client.testing` submodule for testing consumers without a running cascor service:

- `FakeCascorClient` — in-process fake matching the real client's interface
- `FakeCascorTrainingStream` — fake WebSocket training stream
- `update_params()` support with scenario-aware state updates
- Consumers can switch between real and fake by importing from one or the other

### Configuration & Authentication

- `JUNIPER_CASCOR_API_KEY` environment variable fallback for API key
- SOPS configuration (`.sops.yaml`) and `.env.example` for secrets management

### Documentation Suite

- `DOCUMENTATION_OVERVIEW.md` — navigation index
- `QUICK_START.md` — installation and first-call walkthrough
- `REFERENCE.md` — full method and configuration reference
- `docs/DEVELOPER_CHEATSHEET.md` — quick-reference card
- `AGENTS.md` — thread handoff and worktree procedures
- Ecosystem compatibility matrix in README
- This `CHANGELOG.md` (Keep a Changelog format)

### CI/CD Infrastructure

- Pre-commit hooks: markdownlint, shellcheck, flake8, bandit, yamllint
- Cross-repo CI dispatch to juniper-canopy on push to main
- Dependabot configuration for automated dependency updates (weekly)
- CODEOWNERS file for PR review routing

---

## Bug Fixes

### FakeCascorClient Decision Boundary Format Alignment

**Problem:** `FakeCascorClient` returned 1D arrays with continuous sigmoid values for decision boundaries, while the real cascor API returns 2D meshgrid arrays with integer argmax class indices. Consumer code that worked against the fake would behave incorrectly when wired to a real backend.

**Solution:** Aligned `FakeCascorClient` decision boundary format with the real API:

- `grid_x` / `grid_y` now returned as 2D meshgrid arrays
- Class predictions returned as integer argmax class indices

**Files:** `juniper_cascor_client/testing/fake_client.py`

### AGENTS.md Key Files Table

**Problem:** Several file references in the AGENTS.md key files table pointed to incorrect paths.

**Solution:** Corrected all file references to match the actual repository layout.

---

## Changes

### Linting & Formatting

- Set line length to **512** for all linters (black, isort, flake8) per Juniper ecosystem standard
- Removed `py314` from black target versions
- Expanded `.gitignore` to cover all `.env` variants and `.env.secrets`
- Propagated V2 worktree cleanup procedure (CWD-trap bug fix)

### Dependencies

- SHA-pinned all GitHub Actions to immutable commit hashes
- Bumped `actions/checkout` 4 → 6 (Dependabot)
- Bumped `actions/setup-python` 5 → 6 (Dependabot)
- Bumped `actions/upload-artifact` 4 → 6 (Dependabot)
- Bumped `actions/cache` 4.2.3 → 5.0.3 (Dependabot)
- Bumped `github/codeql-action` 3.28.0 → 4.33.0 (Dependabot)

---

## Upgrade Notes

This is a backward-compatible release. No migration steps required. All changes are additive.

```bash
# Install via pip
pip install --upgrade juniper-cascor-client==0.2.0

# Or via juniper-ml meta-package
pip install --upgrade "juniper-ml[clients]"
```

### Using the Testing Submodule

```python
from juniper_cascor_client.testing import FakeCascorClient

client = FakeCascorClient()
client.update_params(learning_rate=0.05)
```

---

## Known Issues

None known at time of release.

---

## Version History

| Version | Date       | Description                                                                         |
| ------- | ---------- | ----------------------------------------------------------------------------------- |
| 0.1.0   | 2026-02-22 | Initial release — REST + WebSocket client for juniper-cascor                        |
| 0.2.0   | 2026-03-21 | `update_params()` method, FakeCascorClient testing module, full documentation suite |

---

## Links

- [Full Changelog](../../CHANGELOG.md)
- [Previous Release: v0.1.0](https://github.com/pcalnon/juniper-cascor-client/releases/tag/v0.1.0)
