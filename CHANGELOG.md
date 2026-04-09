# Changelog

All notable changes to `juniper-cascor-client` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Serena code agent integration configuration (`.serena/project.yml`)

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
