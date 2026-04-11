# Hardcoded Values Refactor Plan — juniper-cascor-client

**Version**: 0.3.0
**Created**: 2026-04-08
**Status**: PLANNING — No source code modifications
**Companion Document**: `HARDCODED_VALUES_ANALYSIS.md`

---

## Phase 1: Constants Infrastructure (Priority: HIGH)

### Step 1.1: Create Production Constants Module

**Task**: Create `juniper_cascor_client/constants.py` (~30 constants)

**Sections**:
1. Service Configuration (base URLs for REST and WebSocket)
2. HTTP Configuration (timeout, retries, backoff, pool size, retryable codes)
3. HTTP Status Codes (400, 404, 409, 422, 503)
4. Decision Boundary (resolution default, min, max)
5. Authentication (header name)

### Step 1.2: Create Testing Constants Module

**Task**: Create `juniper_cascor_client/testing/constants.py` (~65 constants)

**Sections**:
1. Fake Client Configuration (fake URL, version, error rate, uptime)
2. Training Hyperparameters (learning rate, epochs, hidden units, patience, correlation threshold)
3. Loss Curve Parameters (initial loss, decay, noise, per scenario)
4. Accuracy Curve Parameters (midpoint, steepness, ceiling, per scenario)
5. Validation Loss Parameters (gap factor, noise)
6. Network Topology Generation (bias, weight scales, hash modulo)
7. Decision Boundary Generation (grid bounds, complexity, phase shifts)
8. Worker Simulation Data (CPU cores, health scores)
9. Dataset Configuration (spiral points, XOR corners, split ratios)

---

## Phase 2: Source File Refactor (Priority: HIGH)

### Step 2.1: Refactor REST Client

**File**: `client.py` — ~20 replacements

### Step 2.2: Refactor WebSocket Clients

**File**: `ws_client.py` — ~4 replacements

### Step 2.3: Refactor Fake Client

**File**: `testing/fake_client.py` — ~40 replacements

### Step 2.4: Refactor Scenarios

**File**: `testing/scenarios.py` — ~50 replacements (largest file)

---

## Phase 3: Validation (Priority: HIGH)

### Step 3.1: Run Full Test Suite

```bash
pytest tests/ -v
```

### Step 3.2: Pre-commit Hooks
### Step 3.3: Verify Scenario Outputs

Run scenario generation for `two_spiral`, `xor_converged`, and empty scenarios. Verify metric curves, topology, and decision boundary data match pre-refactor.

---

## Phase 4: Documentation & Release (Priority: MEDIUM)

### Step 4.1: Update AGENTS.md
### Step 4.2: Update CHANGELOG.md
### Step 4.3: Create Release Description
