# AGENTS.md Update Plan - juniper-cascor-client

**Date**: 2026-04-02
**Based on**: AGENTS_MD_AUDIT_ANALYSIS_2026-04-02.md
**Objective**: Bring AGENTS.md into full alignment with codebase state at commit 3851ea8

---

## Phase 1: Fix Critical Errors (Immediate)

### Step 1.1: Update Header Metadata
- **Task**: Update version from 0.1.0 to 0.3.0
- **Task**: Update Last Updated date to 2026-04-02

### Step 1.2: Fix Incorrect Commands
- **Task**: Change flake8 `--max-line-length=120` to `--max-line-length=512` in Essential Commands
- **Task**: Add missing commands: pre-commit, build, doc link check, dep docs generation

---

## Phase 2: Update Existing Sections (High Priority)

### Step 2.1: Expand Key Files Table
- **Task**: Add testing submodule files (fake_client.py, fake_ws_client.py, scenarios.py)
- **Task**: Add py.typed, CHANGELOG.md, .pre-commit-config.yaml
- **Task**: Add docs/, scripts/, notes/ directory references
- **Task**: Add CI/CD files (.github/workflows/ci.yml, publish.yml)
- **Task**: Add configuration files (.env.example, .sops.yaml, CODEOWNERS, dependabot.yml)

### Step 2.2: Expand Project Overview
- **Task**: Add testing submodule description
- **Task**: Add API surface area summary
- **Task**: Add PEP 561 type compliance note

### Step 2.3: Update Dependencies Table
- **Task**: Add version constraints to core dependencies
- **Task**: Add test and dev dependency groups

### Step 2.4: Update Ecosystem Context
- **Task**: Standardize naming (juniper-canopy, juniper-cascor instead of PascalCase)
- **Task**: Add cross-repo CI dispatch relationship
- **Task**: Add service port reference

---

## Phase 3: Add New Sections (Medium Priority)

### Step 3.1: Directory Layout
- **Task**: Add complete directory tree with annotations

### Step 3.2: Architecture
- **Task**: Document class hierarchy (JuniperCascorClient, CascorTrainingStream, CascorControlStream)
- **Task**: Document API method categories (health, network, training, metrics, data, snapshots, workers)
- **Task**: Document exception hierarchy
- **Task**: Document key design patterns (context manager, callback/observer, retry, envelope)

### Step 3.3: CI/CD Pipeline
- **Task**: Document GitHub Actions workflow structure
- **Task**: Document quality gates and required checks
- **Task**: Document downstream CI dispatch

### Step 3.4: Linting & Formatting Configuration
- **Task**: Document line length (512), tool versions, complexity limits
- **Task**: Document pre-commit hooks inventory

### Step 3.5: Test Organization
- **Task**: Document test file structure and markers
- **Task**: Document conftest.py fixtures
- **Task**: Document coverage requirements (80%)

### Step 3.6: Environment Variables
- **Task**: Document JUNIPER_CASCOR_API_KEY, CASCOR_SERVICE_URL
- **Task**: Reference .env.example

### Step 3.7: Security
- **Task**: Document SOPS encryption, Gitleaks, Bandit, pip-audit

### Step 3.8: Python Version Support
- **Task**: Document >=3.11, supported/tested versions 3.11-3.14

---

## Phase 4: Validation

### Step 4.1: Cross-Reference Validation
- **Task**: Verify every file path mentioned in AGENTS.md exists
- **Task**: Verify every command in AGENTS.md runs successfully
- **Task**: Verify dependency lists match pyproject.toml
- **Task**: Verify version numbers match pyproject.toml and __init__.py

### Step 4.2: Peer Review
- **Task**: Compare updated AGENTS.md structure against juniper-ml AGENTS.md and juniper-data-client AGENTS.md for consistency

---

## Phase 5: Commit and PR

### Step 5.1: Final Checks
- **Task**: Run pre-commit hooks
- **Task**: Run full test suite
- **Task**: Verify CLAUDE.md symlink still points to AGENTS.md

### Step 5.2: Commit and Push
- **Task**: Commit all changes (analysis doc, plan doc, roadmap, updated AGENTS.md)
- **Task**: Push branch to remote
- **Task**: Create PR

### Step 5.3: Post-Merge Cleanup
- **Task**: Perform worktree cleanup v2 procedure after merge

---

## Estimated Scope

| Phase | Items | Complexity |
|-------|-------|------------|
| Phase 1 | 3 tasks | Low |
| Phase 2 | 8 tasks | Medium |
| Phase 3 | 12 tasks | Medium-High |
| Phase 4 | 4 tasks | Low |
| Phase 5 | 4 tasks | Low |
| **Total** | **31 tasks** | — |
