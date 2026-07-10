# Sync Pipeline (Phase-1 POC)

This directory is **not part of the OKF bundle**. It holds the Phase-1 sync
pipeline per [ADR-0005](/cross-boundary/ADR-CorePlatform-0005.md).

- `adr_sync/ir.py` — the IR contract between core and plugins (ADR-0004).
- `adr_sync/core.py` — destination-agnostic detection + OKF parsing.
- `adr_sync/sync.py` — orchestrator; wires core to plugins.
- `adr_sync/plugins/confluence.py` — first destination plugin.

**Phase 2:** when a second source repo needs syncing, this package moves to its
own repository (reusable workflow or published action), and this directory is
deleted. Nothing in the Python changes on extraction — only placement and the
root workflow launcher.
