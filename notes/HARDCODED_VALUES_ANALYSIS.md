# Hardcoded Values Analysis — juniper-cascor-client

**Version**: 0.3.0
**Analysis Date**: 2026-04-08
**Analyst**: Claude Code (Automated Code Review)
**Status**: PLANNING ONLY — No source code modifications

---

## Executive Summary

The juniper-cascor-client codebase contains **95+ hardcoded values** with **zero dedicated constants module**. All values are inline literals, default parameter values, or magic numbers embedded in functions. The `testing/` subpackage (fake client and scenario generators) accounts for the majority of hardcoded values due to extensive training simulation parameters.

---

## 1. Existing Constants Infrastructure

**No constants module exists.** Zero dedicated constants files of any kind.

---

## 2. Hardcoded Values Inventory

### 2.1 Service Configuration — NOT COVERED

| File | Line | Value | Type | Context | Proposed Constant Name |
|------|------|-------|------|---------|----------------------|
| `client.py` | 33 | `"http://localhost:8200"` | str | REST API default URL | `DEFAULT_BASE_URL` |
| `ws_client.py` | 37 | `"ws://localhost:8200"` | str | WS training stream default | `DEFAULT_WS_BASE_URL` |
| `ws_client.py` | 161 | `"ws://localhost:8200"` | str | WS control stream default | (same) |
| `testing/fake_client.py` | 63 | `"http://fake-cascor:8200"` | str | Fake client URL | `FAKE_BASE_URL` |
| `testing/fake_client.py` | 107, 144 | `"0.4.0"` | str | Fake service version | `FAKE_SERVICE_VERSION` |

### 2.2 HTTP & Networking — NOT COVERED

| File | Line | Value | Type | Context | Proposed Constant Name |
|------|------|-------|------|---------|----------------------|
| `client.py` | 34 | `30` | int | Request timeout (sec) | `DEFAULT_REQUEST_TIMEOUT` |
| `client.py` | 45 | `3` | int | Retry count | `DEFAULT_RETRY_COUNT` |
| `client.py` | 46 | `0.5` | float | Backoff factor | `DEFAULT_BACKOFF_FACTOR` |
| `client.py` | 47 | `[502, 504]` | list | Retryable status codes | `RETRYABLE_STATUS_CODES` |
| `client.py` | 51 | `10` | int | Pool max size | `DEFAULT_POOL_MAXSIZE` |
| `client.py` | 80 | `30.0` | float | Ready wait timeout | `DEFAULT_READY_TIMEOUT` |
| `client.py` | 80 | `0.5` | float | Ready poll interval | `DEFAULT_READY_POLL_INTERVAL` |
| `client.py` | 223 | `50` | int | Decision boundary resolution | `DEFAULT_DECISION_BOUNDARY_RESOLUTION` |
| `client.py` | 227 | `5`, `200` | int | Resolution min/max | `MIN_DECISION_BOUNDARY_RESOLUTION`, `MAX_DECISION_BOUNDARY_RESOLUTION` |

### 2.3 HTTP Status Codes — NOT COVERED

| File | Line | Value | Context | Proposed Constant Name |
|------|------|-------|---------|----------------------|
| `client.py` | 344 | `400` | Bad request | `HTTP_400_BAD_REQUEST` |
| `client.py` | 344 | `422` | Validation error | `HTTP_422_UNPROCESSABLE_ENTITY` |
| `client.py` | 346 | `404` | Not found | `HTTP_404_NOT_FOUND` |
| `client.py` | 348 | `409` | Conflict | `HTTP_409_CONFLICT` |
| `client.py` | 350 | `503` | Service unavailable | `HTTP_503_SERVICE_UNAVAILABLE` |

### 2.4 Training Hyperparameter Defaults (`testing/fake_client.py`) — NOT COVERED

| Line | Value | Type | Context | Proposed Constant Name |
|------|-------|------|---------|----------------------|
| 227 | `0.01` | float | Default learning rate | `DEFAULT_LEARNING_RATE` |
| 355, 501 | `1000` | int | Default max epochs | `DEFAULT_MAX_EPOCHS` |
| 533, 559 | `10` | int | Default max hidden units | `DEFAULT_MAX_HIDDEN_UNITS` |
| 561 | `10` | int | Default patience | `DEFAULT_PATIENCE` |
| 563 | `0.01` | float | Correlation threshold | `DEFAULT_CORRELATION_THRESHOLD` |
| 158 | `3600.0` | float | Default uptime (sec) | `FAKE_DEFAULT_UPTIME_SECONDS` |
| 115 | `0.1` | float | Error injection rate | `ERROR_PRONE_ERROR_RATE` |

### 2.5 Scenario Metric Curve Parameters (`testing/scenarios.py`) — NOT COVERED

**Loss curve parameters** (20+ values):
- `initial_loss=2.5`, `decay_rate=0.05`, `noise_scale=0.02`
- `sine_multiplier=0.7`, `exp_multiplier=-0.01`, `min_loss=0.001`
- Two-spiral variants: `initial_loss=2.5`, `decay_rate=0.04`
- Empty scenario variants: `initial_loss=1.5`, `decay_rate=0.03`

**Accuracy curve parameters** (15+ values):
- `midpoint=40.0`, `steepness=0.08`, `ceiling=0.98`
- Two-spiral variants: `midpoint=50.0`, `steepness=0.06`, `ceiling=0.96`
- Empty scenario variants: `midpoint=30.0`, `steepness=0.07`, `ceiling=0.92`

**Validation loss parameters**: `gap_factor=1.15`, `noise_scale=0.01`, `sine_multiplier=1.3`

### 2.6 Network Topology Generation (`testing/scenarios.py`) — NOT COVERED

| Line(s) | Value | Context | Proposed Constant Name |
|---------|-------|---------|----------------------|
| 189 | `-0.5`, `0.1` | Hidden bias base/increment | `HIDDEN_BIAS_BASE`, `HIDDEN_BIAS_INCREMENT` |
| 206 | `0.1`, `100`, `0.5` | Weight scale/hash/center | `HIDDEN_WEIGHT_SCALE`, `WEIGHT_HASH_MODULO`, `WEIGHT_CENTER` |
| 224 | `0.01` | Output bias scale | `OUTPUT_BIAS_SCALE` |
| 235 | `0.05`, `50` | Output weight scale/range | `OUTPUT_WEIGHT_SCALE`, `WEIGHT_RANGE_CENTER` |
| 266 | `0.01` | Default learning rate | `DEFAULT_LEARNING_RATE` |
| 284-291 | Various | Network config defaults | `DEFAULT_CANDIDATE_LEARNING_RATE_MULTIPLIER`, etc. |

### 2.7 Decision Boundary Generation (`testing/scenarios.py`) — NOT COVERED

| Line(s) | Value | Context | Proposed Constant Name |
|---------|-------|---------|----------------------|
| 394 | `50` | Default resolution | `DEFAULT_DECISION_BOUNDARY_RESOLUTION` |
| 415-416 | `-1.5`, `1.5` | Grid bounds | `DECISION_BOUNDARY_MIN`, `DECISION_BOUNDARY_MAX` |
| 439 | `2.0` | Sine complexity | `DECISION_BOUNDARY_COMPLEXITY_SCALE` |
| 471-472 | `2.0`, `0.5`, `1.5`, `0.3` | Phase/scale values | Various |

### 2.8 Worker Simulation (`testing/fake_client.py`) — NOT COVERED

| Line | Value | Context | Proposed Constant Name |
|------|-------|---------|----------------------|
| 856 | `8` | Worker 1 CPU cores | `FAKE_WORKER_1_CPU_CORES` |
| 867 | `4` | Worker 2 CPU cores | `FAKE_WORKER_2_CPU_CORES` |
| 862 | `1.0` | Worker 1 health score | `FAKE_WORKER_PERFECT_HEALTH` |
| 873 | `0.8889` | Worker 2 health score | `FAKE_WORKER_2_HEALTH_SCORE` |
| 925 | `0.9444` | Average health score | `FAKE_WORKERS_AVG_HEALTH_SCORE` |
| 736, 779 | `300`, `60` | Snapshot age (sec) | `FAKE_SNAPSHOT_*_AGE_SECONDS` |

---

## 3. Coverage Summary

| Category | Total | Covered | Not Covered | Priority |
|----------|-------|---------|-------------|----------|
| Service Configuration | 5 | 0 | 5 | **HIGH** |
| HTTP/Networking | 9 | 0 | 9 | **HIGH** |
| HTTP Status Codes | 5 | 0 | 5 | **MEDIUM** |
| Training Defaults | 7 | 0 | 7 | **MEDIUM** |
| Scenario Metrics | 35+ | 0 | 35+ | **MEDIUM** |
| Topology Generation | 10+ | 0 | 10+ | **LOW** |
| Decision Boundary | 8 | 0 | 8 | **LOW** |
| Worker Simulation | 6+ | 0 | 6+ | **LOW** |
| **TOTAL** | **~95** | **0** | **~95** | — |

---

## 4. Remediation Approach

### Recommended: Create `juniper_cascor_client/constants.py`

Organize into logical sections:

1. **Service Configuration** — URLs, ports, version
2. **HTTP Configuration** — timeouts, retries, pool sizes, retryable codes
3. **API Endpoints** — all REST endpoint paths
4. **HTTP Status Codes** — error handling codes
5. **Network Defaults** — learning rates, hidden units, epochs, patience
6. **Scenario Parameters** — loss/accuracy curve params (subsections per scenario)
7. **Topology Constants** — weight scales, bias values
8. **Decision Boundary** — grid bounds, resolution limits
9. **Test Fixtures** — worker simulation data, snapshot ages

**Strengths**: Centralized, comprehensive, easy to maintain
**Weaknesses**: Large file (~95 constants); testing constants mixed with production constants
**Alternative**: Split into `constants.py` (production) and `testing/constants.py` (test fixtures/scenarios)

---

## 5. Files Requiring Modification

| File | Action | Replacements |
|------|--------|-------------|
| `juniper_cascor_client/constants.py` | **NEW** | ~30 production constants |
| `juniper_cascor_client/testing/constants.py` | **NEW** | ~65 testing constants |
| `juniper_cascor_client/client.py` | **MODIFY** | ~20 |
| `juniper_cascor_client/ws_client.py` | **MODIFY** | ~4 |
| `juniper_cascor_client/testing/fake_client.py` | **MODIFY** | ~40 |
| `juniper_cascor_client/testing/scenarios.py` | **MODIFY** | ~50 |

---

## 6. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Scenario output changes | Very Low | Medium | Constants preserve exact values |
| Fake client behavior changes | Very Low | Medium | Run full test suite |
| Breaking downstream consumers | Very Low | High | No public API changes |
| Large constants file | Medium | Low | Split into production/testing constants |
