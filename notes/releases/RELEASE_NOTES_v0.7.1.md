# Juniper Cascor Client v0.7.1 Release Notes

**Release Date:** DRAFT — owner cuts the GitHub Release
**Version:** 0.7.1
**Release Type:** PATCH (see *Versioning note* — this is arguably a MINOR)

---

## Overview

This release exists because **the fix for a measured defect has been sitting unpublished on `main`**.

PyPI's `juniper-cascor-client` 0.7.0 retries on `["GET", "POST", "DELETE", "PUT", "PATCH"]`. `main` has carried `["HEAD", "GET"]` since `ff3df6c`, but `pyproject.toml` still read `0.7.0` against the existing `v0.7.0` tag — so every consumer installing from PyPI still gets retries on **non-idempotent verbs**, and cutting a Release without a version bump would try to republish an immutable version.

That is constraint **C8** of the X7 remediation design (juniper-ml `notes/JUNIPER_2026-09-03_JUNIPER-CANOPY_X7-EVENT-LOOP-BLOCKING-REMEDIATION-DESIGN.md`): *"Retries must not be applied to non-idempotent verbs"*, measured as **`POST /v1/training/start` reaching the server 4×**. A retried training-start is not a slow request; it is up to four training runs.

> **Status:** DRAFT — do not tag or publish from this document. The owner cuts the GitHub Release per the ecosystem release convention (juniper-ml `notes/JUNIPER_2026-06-18_JUNIPER-ECOSYSTEM_PYPI-PUBLISH-PROCEDURE.md` §11), which fires `publish.yml`. **Pinning canopy's floor to `>=0.7.1` must wait until this is on PyPI**, or canopy's install resolves nothing.

---

## Release Summary

- **Release type:** PATCH (with a caveat — see below)
- **Primary focus:** publish the C8 retry-idempotency fix that has been unreleased since `ff3df6c`
- **Breaking changes:** none for correct callers. A caller *relying* on `POST` being retried loses that, which is the point of the fix.
- **Downstream:** canopy floor bump to `>=0.7.1` follows publication; it fits canopy's existing `<0.8.0` cap.

## What is in it

Everything that accumulated in `[Unreleased]` since 0.7.0. The load-bearing entries:

| Change | Register id | Why it matters |
| --- | --- | --- |
| `RETRY_ALLOWED_METHODS` narrowed to `["HEAD", "GET"]` | C8 / `APD-CCLIENT-001` | Published 0.7.0 retries POST/PUT/PATCH/DELETE. Measured: one `POST /v1/training/start` reached cascor **4×**. |
| Retry backoff jitter (`backoff_jitter`) | `APD-ECO-002` | Without it every client tripping the same outage retried on an *identical* schedule — a synchronised herd against an already-failing service. |
| `backoff_factor` constructor-configurable | `APD-CCLIENT-013` | Both sibling clients already exposed it. |
| `pool_connections` set alongside `pool_maxsize` | `APD-CCLIENT-009` | Omitting one left it on the library default while the other was tuned. |
| `auto_pong=False` deprecated, removal dated 0.9.0 | `APD-ECO-007` | It shipped as a *silent* opt-out: no warning, no removal date. Fleet census found **zero** production users. |

Full detail: `CHANGELOG.md` `[0.7.1]`.

## Versioning note — read before cutting

**This is labelled PATCH but contains an additive public-API change**: `backoff_factor` became a constructor parameter (`APD-CCLIENT-013`). Under strict SemVer that is a MINOR feature, and 0.8.0 would be the more honest number.

It is 0.7.1 because the X7 design chose that explicitly, and the reason is downstream: **canopy caps this dependency at `<0.8.0`**, so a 0.8.0 release would be excluded by the very consumer the release exists to serve. Bumping to 0.8.0 instead is a two-part change — the release *and* widening canopy's cap — and that is a deliberate decision rather than a side effect of this one.

Flagged rather than left silent: a consumer pinning `~=0.7.0` will receive a new constructor parameter in a patch. Nothing breaks, but it is not what a patch usually means.

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

1. Verify the version resolves on PyPI (the CDN can lag ~5–30 s; query the version-specific endpoint).
2. Pin canopy's floor: `juniper-cascor-client>=0.7.1,<0.8.0`.
3. Re-run canopy's suite against the published wheel rather than the local checkout.
