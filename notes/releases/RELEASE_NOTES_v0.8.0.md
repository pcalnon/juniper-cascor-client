# Juniper Cascor Client v0.8.0 Release Notes

**Release Date:** DRAFT — owner cuts the GitHub Release
**Version:** 0.8.0
**Release Type:** MINOR

---

## Overview

This release exists because **the fix for a measured defect has been sitting unpublished on `main`**.

PyPI's `juniper-cascor-client` 0.7.0 retries on `["GET", "POST", "DELETE", "PUT", "PATCH"]`. `main` has carried `["HEAD", "GET"]` since `ff3df6c`, but `pyproject.toml` still read `0.7.0` against the existing `v0.7.0` tag — so every consumer installing from PyPI still gets retries on **non-idempotent verbs**, and cutting a Release without a version bump would try to republish an immutable version.

That is constraint **C8** of the X7 remediation design (juniper-ml `notes/JUNIPER_2026-09-03_JUNIPER-CANOPY_X7-EVENT-LOOP-BLOCKING-REMEDIATION-DESIGN.md`): *"Retries must not be applied to non-idempotent verbs"*, measured as **`POST /v1/training/start` reaching the server 4×**. A retried training-start is not a slow request; it is up to four training runs.

> **Status:** DRAFT — do not tag or publish from this document. The owner cuts the GitHub Release per the ecosystem release convention (juniper-ml `notes/JUNIPER_2026-06-18_JUNIPER-ECOSYSTEM_PYPI-PUBLISH-PROCEDURE.md` §11), which fires `publish.yml`.
>
> **Two things gate cutting it, in order.** Canopy capped this dependency at `<0.8.0`, which would exclude this artefact from the one consumer the release exists to serve, so **widening that cap must land first** (juniper-canopy `pyproject.toml`, a single line). Only after the wheel is on PyPI can canopy's floor move to `>=0.8.0` — pinning a floor at a version that is not published resolves nothing.

---

## Release Summary

- **Release type:** MINOR. `backoff_factor` became a public constructor parameter (`APD-CCLIENT-013`); an additive public-API change is a feature, and a feature is a minor bump.
- **Primary focus:** publish the C8 retry-idempotency fix that has been unreleased since `ff3df6c`
- **Breaking changes:** none for correct callers. A caller *relying* on `POST` being retried loses that, which is the point of the fix.
- **Downstream:** canopy's cap is widened from `<0.8.0` to `<0.9.0` **before** the Release is cut; its floor moves to `>=0.8.0` **after** the wheel is on PyPI.

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

## Verification

- Full test suite green on the release commit.
- Version consistent across `pyproject.toml`, `juniper_cascor_client/__init__.py` and `juniper_cascor_client/constants.py`.
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
