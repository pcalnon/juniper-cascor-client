# Documentation Overview

## Navigation Guide to juniper-cascor-client Documentation

**Version:** 0.1.0
**Status:** Active
**Last Updated:** March 3, 2026
**Project:** Juniper - CasCor Service Client Library

---

## Table of Contents

- [Quick Navigation](#quick-navigation)
- [Document Index](#document-index)
- [Ecosystem Context](#ecosystem-context)
- [Related Documentation](#related-documentation)

---

## Quick Navigation

### I Want To

| Goal | Document | Location |
|------|----------|----------|
| **Install and use the client** | [QUICK_START.md](QUICK_START.md) | docs/ |
| **See the full API reference** | [REFERENCE.md](REFERENCE.md) | docs/ |
| **Understand the project** | [README.md](../README.md) | Root |
| **See development conventions** | [AGENTS.md](../AGENTS.md) | Root |
| **See version history** | [CHANGELOG.md](../CHANGELOG.md) | Root |
| **Quick-reference dev tasks** | [DEVELOPER_CHEATSHEET.md](DEVELOPER_CHEATSHEET.md) | docs/ |
| **Run tests** | [AGENTS.md](../AGENTS.md) | Root |

---

## Document Index

### docs/ Directory

| File | Lines | Type | Purpose |
|------|-------|------|---------|
| **DOCUMENTATION_OVERVIEW.md** | ~120 | Overview | This file -- navigation index |
| **QUICK_START.md** | ~140 | Tutorial | Install, configure, and use in 5 minutes |
| **REFERENCE.md** | ~330 | Reference | Complete REST, WebSocket, exception, and testing reference |

### notes/ Directory

| File | Lines | Type | Purpose |
|------|-------|------|---------|
| **DEVELOPER_CHEATSHEET.md** | ~100 | Cheatsheet | Quick-reference card for common development tasks |

### Root Directory

| File | Lines | Type | Purpose |
|------|-------|------|---------|
| **README.md** | ~200 | Overview | Project overview, features, quick examples |
| **AGENTS.md** | ~200 | Guide | Development conventions, commands, worktree setup |
| **CHANGELOG.md** | ~50 | History | Version history and release notes |

---

## Ecosystem Context

`juniper-cascor-client` provides both synchronous REST and asynchronous WebSocket clients for the juniper-cascor neural network training service. It is a shared dependency consumed by:

- **juniper-canopy** -- Real-time dashboard uses `JuniperCascorClient` for training control and `CascorTrainingStream` for live metric updates
- **juniper-ml** -- Meta-package installs it via `pip install juniper-ml[clients]`

### Dependency Graph

```
juniper-cascor-client ──REST──> juniper-cascor (port 8200)
juniper-cascor-client ──WS────> juniper-cascor (/ws/training, /ws/control)
juniper-canopy ──uses──> juniper-cascor-client
juniper-ml ──meta-package──> juniper-cascor-client
```

### Compatibility

| juniper-cascor-client | juniper-cascor | juniper-canopy | juniper-data |
|-----------------------|----------------|----------------|--------------|
| 0.1.x | 0.3.x | 0.2.x | 0.4.x |

---

## Related Documentation

### Upstream Service

- **juniper-cascor** -- [Training Service](https://github.com/pcalnon/juniper-cascor) (service that this client calls)
- **REST API**: `/v1/` prefix for all endpoints on port 8200
- **WebSocket**: `/ws/training` (metrics stream) and `/ws/control` (command stream)

### Downstream Consumers

- **juniper-canopy** -- [Dashboard](https://github.com/pcalnon/juniper-canopy) (real-time training visualization)

### Meta-Package

- **juniper-ml** -- `pip install juniper-ml[clients]` installs this client automatically

---

**Last Updated:** March 3, 2026
**Version:** 0.1.0
**Maintainer:** Paul Calnon
