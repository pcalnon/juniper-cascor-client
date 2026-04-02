# AGENTS.md Update Development Roadmap - juniper-cascor-client

**Date**: 2026-04-02
**Based on**: AGENTS_MD_AUDIT_ANALYSIS_2026-04-02.md, AGENTS_MD_UPDATE_PLAN_2026-04-02.md

---

## Priority Matrix

| Priority | Phase | Description | Blocking? |
|----------|-------|-------------|-----------|
| P0 | 1 | Fix critical errors (wrong line length, wrong version) | Yes - agents produce incorrect output |
| P1 | 2 | Update existing sections with missing content | Yes - agents miss major codebase components |
| P2 | 3 | Add new sections for architecture, CI/CD, testing, etc. | No - improves agent effectiveness |
| P3 | 4-5 | Validation, commit, PR | No - standard process |

---

## Detailed Roadmap

### P0: Critical Fixes

| ID | Task | Files | Status |
|----|------|-------|--------|
| P0-1 | Update version 0.1.0 -> 0.3.0 | AGENTS.md | Pending |
| P0-2 | Update Last Updated date | AGENTS.md | Pending |
| P0-3 | Fix flake8 line length 120 -> 512 | AGENTS.md | Pending |

### P1: Content Updates

| ID | Task | Files | Status |
|----|------|-------|--------|
| P1-1 | Expand Key Files table (+15 entries) | AGENTS.md | Pending |
| P1-2 | Add testing submodule to Project Overview | AGENTS.md | Pending |
| P1-3 | Add version constraints to dependencies | AGENTS.md | Pending |
| P1-4 | Add test/dev dependency groups | AGENTS.md | Pending |
| P1-5 | Standardize ecosystem naming | AGENTS.md | Pending |
| P1-6 | Add missing essential commands | AGENTS.md | Pending |

### P2: New Sections

| ID | Task | Files | Status |
|----|------|-------|--------|
| P2-1 | Add Directory Layout section | AGENTS.md | Pending |
| P2-2 | Add Architecture section | AGENTS.md | Pending |
| P2-3 | Add CI/CD Pipeline section | AGENTS.md | Pending |
| P2-4 | Add Linting & Formatting section | AGENTS.md | Pending |
| P2-5 | Add Test Organization section | AGENTS.md | Pending |
| P2-6 | Add Environment Variables section | AGENTS.md | Pending |
| P2-7 | Add Security section | AGENTS.md | Pending |
| P2-8 | Add Python Version Support note | AGENTS.md | Pending |

### P3: Process Completion

| ID | Task | Status |
|----|------|--------|
| P3-1 | Cross-reference validation (paths, commands, versions) | Pending |
| P3-2 | Run pre-commit and test suite | Pending |
| P3-3 | Commit, push, create PR | Pending |
| P3-4 | Post-merge worktree cleanup | Pending |

---

## Dependencies

```
P0-1,P0-2,P0-3 (parallel)
    └── P1-1,P1-2,P1-3,P1-4,P1-5,P1-6 (parallel)
        └── P2-1,P2-2,P2-3,P2-4,P2-5,P2-6,P2-7,P2-8 (parallel)
            └── P3-1
                └── P3-2
                    └── P3-3
                        └── P3-4
```

All P0 items are independent. All P1 items are independent. All P2 items are independent. P3 items are sequential.

---

## Success Criteria

1. AGENTS.md version matches pyproject.toml and __init__.py (0.3.0)
2. Every file path in AGENTS.md resolves to an existing file
3. Every command in AGENTS.md runs without error
4. All dependency lists match pyproject.toml
5. Directory layout matches actual filesystem
6. Pre-commit hooks pass
7. Full test suite passes
8. PR created and ready for review
