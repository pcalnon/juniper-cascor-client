# Juniper CasCor Client - Other Dependencies

**Project**: Juniper
**Application**: juniper-cascor-client
**Last Updated**: 2026-02-25

---

## Overview

This document tracks dependencies that are **not** managed by pip or conda/mamba.
For pip-managed dependencies, see `conf/requirements_ci.txt`.
For conda/mamba-managed dependencies, see `conf/conda_environment_ci.yaml`.

---

## Build & Packaging Tools

| Dependency | Version | Management Method | Purpose |
|------------|---------|-------------------|---------|
| build | >=1.0.0 | pip | Python package builder |
| setuptools | >=61.0 | pip | Build backend |
| wheel | latest | pip | Wheel format support |
| twine | >=4.0.0 | pip | Package upload/validation for PyPI |

## CI/CD Dependencies

| Dependency | Version | Management Method | Purpose |
|------------|---------|-------------------|---------|
| GitHub Actions | N/A | github | CI/CD platform |
| actions/checkout | v4 | github-action | Repository checkout |
| actions/setup-python | v5 | github-action | Python environment setup |
| actions/upload-artifact | v4 | github-action | CI artifact storage |
| conda-incubator/setup-miniconda | v3 | github-action | Conda/Miniforge setup in CI |
| pypa/gh-action-pypi-publish | release/v1 | github-action | PyPI trusted publishing |

## Development Tools

| Dependency | Version | Management Method | Purpose |
|------------|---------|-------------------|---------|
| git | >=2.30 | apt / system | Version control |
| conda / mamba | latest | miniforge3 | Environment management |
| mypy | latest | pip | Type checking |
| flake8 | latest | pip | Linting |

## Notes

- This is an HTTP/WebSocket client library with WebSocket support for real-time training event streaming.
- The `websockets` package (>=11.0) is a core runtime dependency providing async WebSocket connectivity to the JuniperCascor training service.
- The shared `JuniperPython` conda environment is managed at the ecosystem level.
