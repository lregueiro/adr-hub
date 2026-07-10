---
type: Architecture Decision Record
title: "Sync Pipeline Placement and Packaging: In-Repo POC, Extracted at Scale"
description: "The sync pipeline lives inside the hub repo for the POC, and is extracted into a reusable/published form once a second source repo requires it."
tags: [core-platform, knowledge-management, sync-pipeline, ci-cd, packaging]
timestamp: 2026-07-10T00:00:00Z
okf_version: "0.1"

# ADR extensions
adr_id: ADR-CorePlatform-0005
status: Proposed
authors:
  - name: "Vamsi"
    role: "Tech Strategy"
supersedes: ~
superseded_by: ~
amends: ADR-CorePlatform-0003
confluence_page_id: ~
---

## Context

The sync pipeline (Python core + destination plugins, [ADR-CorePlatform-0003](/cross-boundary/ADR-CorePlatform-0003.md), [ADR-CorePlatform-0004](/cross-boundary/ADR-CorePlatform-0004.md)) is a code project. ADR-0003 implicitly assumed the GitHub Actions workflow lives in the hub repo but never decided where the Python package itself lives. This matters because the hub repo is an OKF *knowledge* bundle, not a code repository, and mixing tooling into it works against the bundle's "pure, portable, cat-readable knowledge" property.

The GitHub Actions workflow interacts with the Python only as a thin launcher: it prepares the environment (checkout, Python, pandoc, secrets) and makes a single subprocess call (\`python -m adr_sync.sync ...\`), passing CLI arguments in and receiving an exit code plus stdout telemetry back. All core/IR/plugin interaction happens inside that one Python process. Because the coupling is this narrow, *where* the Python lives is a placement decision independent of *how* it works.

Three placement options were considered:

- **A — In the hub repo.** \`adr_sync/\` and the workflow sit alongside the ADRs. Simplest wiring; single repo; workflow triggers directly on hub pushes. But the bundle is no longer pure knowledge, and a workflow living only in the hub cannot see pushes in *other* source repos.
- **B — Separate pipeline repo, consumed as a reusable workflow / composite action.** Hub and other source repos reference it via \`uses: your-org/adr-sync-pipeline@vN\`. Keeps the bundle clean; one implementation referenced from many repos; independently versioned. More moving parts.
- **C — Published package or container / Marketplace Action.** Repos invoke a pinned version in ~10 lines of YAML. Cleanest consumption at scale; most upfront packaging and release work.

[ADR-CorePlatform-0002](/cross-boundary/ADR-CorePlatform-0002.md) plans for multiple source repos (the hub plus repo-a, repo-b, …) feeding the system. That makes Option A unsuitable as the *end state*: a pipeline living only in the hub cannot sync ADRs authored in other repos' \`docs/adr/\` paths. However, the pilot ([ADR-0003](/cross-boundary/ADR-CorePlatform-0003.md)) is scoped to the hub repo alone, where A is the fastest path with no external dependency.

## Decision

Adopt a two-phase placement:

- **Phase 1 — Proof of concept: Option A.** The pipeline (\`adr_sync/\` and the workflow) lives inside \`core-platform-adr-hub\`. This is an explicit, temporary POC choice to prove the mechanism end-to-end in one repo with zero external moving parts. During this phase the hub repo is knowingly *bundle + tooling*, accepted as a POC compromise.

- **Phase 2 — Scale: Option B or C.** When a second source repo needs syncing (or the POC is validated and promoted to a supported service), the pipeline is extracted into its own repository and consumed as a reusable workflow (B) or published package/container (C). The hub repo then retains only a thin workflow stub referencing the external pipeline, and returns to being a clean OKF bundle.

**Migration trigger (explicit):** the arrival of the second source repo, per ADR-0002, is the signal to move from Phase 1 to Phase 2. Reaching that trigger before extracting means copying the workflow per repo — the rework Phase 2 exists to avoid.

## Consequences

**Benefits:**

- Fastest possible path to a working POC — one repo, one workflow, no packaging or publishing overhead.
- The decision and its migration trigger are recorded, so the Phase 1 compromise is deliberate and time-bound rather than an accidental permanent state.
- Nothing in the Python (\`core.py\`, \`sync.py\`, plugins) changes between phases — only placement and the workflow launcher change, because the CI/Python boundary is a single subprocess call.

**Tradeoffs and risks:**

- During Phase 1 the hub repo is not a pure OKF bundle; it contains a Python project and CI config. Consumers/agents traversing the bundle must ignore the tooling paths. This is an accepted, temporary POC cost.
- If Phase 1 is allowed to persist past the migration trigger, per-repo workflow duplication and drift will accumulate. The trigger must be acted on, not just documented.
- Extraction (Phase 2) is deferred work, not free — it is the cost consciously traded for POC speed now.

## Next Steps

1. For the POC, place \`adr_sync/\` and \`.github/workflows/adr-sync.yml\` in \`core-platform-adr-hub\`; keep tooling paths clearly separated from bundle content (e.g. a top-level \`tooling/\` or \`.pipeline/\` directory) to ease later extraction and minimise bundle-traversal noise.
2. Add a \`.okfignore\`-style convention or document in the README which paths are tooling vs. bundle, so consumers can skip tooling.
3. When the second source repo appears, extract the pipeline to \`adr-sync-pipeline\` and convert to a reusable workflow (B); revisit C if consumption spreads beyond a few repos.
4. On extraction, reduce the hub's workflow to a stub that references the external pipeline, restoring the hub to a clean OKF bundle.

## Citations

[1] [ADR-CorePlatform-0002 — Hub Repo and Spaces Aggregation Model](/cross-boundary/ADR-CorePlatform-0002.md)
[2] [ADR-CorePlatform-0003 — Confluence Sync Pipeline](/cross-boundary/ADR-CorePlatform-0003.md)
[3] [ADR-CorePlatform-0004 — Plugin-Based Sync Architecture](/cross-boundary/ADR-CorePlatform-0004.md)
[4] [GitHub reusable workflows](https://docs.github.com/en/actions/using-workflows/reusing-workflows)
