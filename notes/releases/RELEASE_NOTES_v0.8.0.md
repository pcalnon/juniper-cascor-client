# Juniper Cascor Client v0.8.0 Release Notes

**Release Date:** 2026-09-05
**Version:** 0.8.0
**Release Type:** MINOR

---

## Overview

This release exists because **the fix for a measured defect has been sitting unpublished on `main`**.

PyPI's `juniper-cascor-client` 0.7.0 retries on `["GET", "POST", "DELETE", "PUT", "PATCH"]`. `main` has carried `["HEAD", "GET"]` since `ff3df6c`, but `pyproject.toml` still read `0.7.0` against the existing `v0.7.0` tag — so every consumer installing from PyPI still gets retries on **non-idempotent verbs**, and cutting a Release without a version bump would try to republish an immutable version.

That is constraint **C8** of the X7 remediation design (juniper-ml `notes/JUNIPER_2026-09-03_JUNIPER-CANOPY_X7-EVENT-LOOP-BLOCKING-REMEDIATION-DESIGN.md`): *"Retries must not be applied to non-idempotent verbs"*, measured as **`POST /v1/training/start` reaching the server 4×**. A retried training-start is not a slow request; it is up to four training runs.

> **Prerequisite satisfied before this Release was cut.** juniper-canopy capped this dependency at `<0.8.0`, which would have excluded this artefact from the one consumer the release exists to serve. That cap was widened to `<0.9.0` first (juniper-canopy#584, `pyproject.toml`), so 0.8.0 is admissible. Canopy's **floor** stays at `>=0.7.0` until this wheel is live on PyPI — a floor pinned at an unpublished version resolves nothing.

---

## Release Summary

- **Release type:** MINOR. `backoff_factor` became a public constructor parameter (`APD-CCLIENT-013`); an additive public-API change is a feature, and a feature is a minor bump.
- **Primary focus:** publish the C8 retry-idempotency fix that has been unreleased since `ff3df6c`
- **Breaking changes:** none for correct callers. A caller *relying* on `POST` being retried loses that, which is the point of the fix.
- **Downstream:** canopy's cap was widened from `<0.8.0` to `<0.9.0` before this Release; its floor moves to `>=0.8.0` after the wheel is on PyPI.

## What is in it

Everything that accumulated in `[Unreleased]` since 0.7.0. The load-bearing entries:

| Change | Register id | Why it matters |
| --- | --- | --- |
| `RETRY_ALLOWED_METHODS` narrowed to `["HEAD", "GET"]` | C8 / `APD-CCLIENT-001` | Published 0.7.0 retries POST/PUT/PATCH/DELETE. Measured: one `POST /v1/training/start` reached cascor **4×**. |
| Retry backoff jitter (`backoff_jitter`) | `APD-ECO-002` | Without it every client tripping the same outage retried on an *identical* schedule — a synchronised herd against an already-failing service. |
| `backoff_factor` constructor-configurable | `APD-CCLIENT-013` | Both sibling clients already exposed it. |
| `pool_connections` set alongside `pool_maxsize` | `APD-CCLIENT-009` | Omitting one left it on the library default while the other was tuned. |
| `auto_pong=False` deprecated, removal dated 0.9.0 | `APD-ECO-007` | It shipped as a *silent* opt-out: no warning, no removal date. Fleet census found **zero** production users. |

Full detail: `CHANGELOG.md` `[0.8.0]`.

## Why 0.8.0 and not 0.7.1

The release was first numbered 0.7.1 (#154). SemVer governs: `backoff_factor` is a **new public constructor parameter**, an additive public-API change, and that is a feature — a MINOR bump. 0.7.1 had been chosen for a downstream reason rather than a semantic one (canopy's `<0.8.0` cap), which would have meant a consumer pinning `~=0.7.0` silently receiving a new constructor parameter in a patch. The cap was the thing to change; #155 corrected the number.

## Verification

- Full test suite green on the release commit: **515 passed, 7 subtests passed, 0 failures**.
- Version consistent across `pyproject.toml`, `juniper_cascor_client/__init__.py`, `juniper_cascor_client/constants.py`, `AGENTS.md` and `CHANGELOG.md`.
- `Post-Merge Main Verification` green on the release commit (`6ffd567`).
- The published-vs-`main` divergence that motivated this release:

  ```
  git show v0.7.0:juniper_cascor_client/constants.py | grep RETRY_ALLOWED_METHODS
  # RETRY_ALLOWED_METHODS: List[str] = ["GET", "POST", "DELETE", "PUT", "PATCH"]
  grep RETRY_ALLOWED_METHODS juniper_cascor_client/constants.py
  # RETRY_ALLOWED_METHODS: List[str] = ["HEAD", "GET"]
  ```

## After publication

1. Verify the version resolves on PyPI (the CDN can lag ~5–30 s; query the version-specific endpoint, not the index).
2. Pin canopy's floor: `juniper-cascor-client>=0.8.0,<0.9.0`. The cap half of that line is already widened; only the floor waits on publication.
3. Re-run canopy's suite against the published wheel rather than the local checkout.
