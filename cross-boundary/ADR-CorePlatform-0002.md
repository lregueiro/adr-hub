---
type: Architecture Decision Record
title: "Cross-Boundary ADR Hub Repository with Copilot Spaces as Query-Only Layer"
description: "Cross-boundary ADRs are authored in a dedicated hub repo; Copilot Spaces operates as a query-only layer with no self-hosted documents."
tags: [core-platform, knowledge-management, copilot-spaces, adr-hub]
timestamp: 2026-07-10T00:00:00Z
okf_version: "0.1"

# ADR extensions
adr_id: ADR-CorePlatform-0002
status: Proposed
authors:
  - name: "Vamsi"
    role: "Tech Strategy"
supersedes: ~
superseded_by: ~
amends: ADR-CorePlatform-0001
confluence_page_id: ~
---

## Context

[ADR-CorePlatform-0001](/cross-boundary/ADR-CorePlatform-0001.md) established GitHub Copilot Spaces as the query layer for ABC Inc architectural decisions. An early proposal was to author cross-boundary ADRs (those spanning multiple repositories or teams) directly within the Copilot Space as uploaded documents.

During design review, this approach was identified as incompatible with the Confluence sync pipeline. Documents uploaded directly into a Copilot Space exist only within GitHub's Copilot infrastructure — they have no repository presence, produce no GitHub events, and are not visible to GitHub Actions or the Confluence GitHub App. This means:

- The sync pipeline cannot detect changes to Space-hosted documents and cannot mirror them to Confluence.
- Space-hosted documents are invisible to any automation layer outside of Copilot itself.
- Non-GitHub stakeholders would have no path to view cross-boundary ADRs, since those decisions never reach the Confluence mirror.

A further concern is durability. A document that exists only inside Copilot Spaces cannot be diffed, reviewed via pull request, meaningfully version-controlled, or recovered if Spaces access is lost — an unacceptable property for architectural decision records, which are meant to be durable.

## Decision

This ADR **amends** [ADR-CorePlatform-0001](/cross-boundary/ADR-CorePlatform-0001.md) by specifying where cross-boundary ADRs are authored. It does not replace ADR-0001; the three-layer model (repo as source of truth, Spaces as query layer, Confluence as mirror) remains fully in force.

No ADR document will be authored or stored directly within the Copilot Space. Cross-boundary ADRs will be authored as OKF-conformant markdown files in a dedicated repository: **`core-platform-adr-hub`**. This repository will be:

- The canonical home for all ADRs that span multiple ABC Inc repositories or teams.
- Added as a source in the Copilot Space alongside individual repository ADR paths, so cross-boundary ADRs are fully discoverable and AI-queryable within the Space.
- Subject to the same GitHub Actions sync pipeline as repository-level ADRs, mirroring content to Confluence (DSP space) automatically on merge.
- Governed by the same PR-based review process as code — no ADR is merged without at least one reviewer from each affected team.

The Copilot Space source configuration will be:

\`\`\`
Sources indexed by Copilot Space:
  - core-platform-adr-hub/          (cross-boundary ADRs)
  - repo-a/docs/adr/                (repo-specific ADRs)
  - repo-b/docs/adr/
  - [additional repos as onboarded]
\`\`\`

**Governing principle (reaffirmed from ADR-0001):** The Copilot Space must never be the sole owner of a document. Every document queryable in the Space must have a repository-backed source. This principle applies permanently — it is not a pilot constraint.

## Consequences

**Benefits:**

- All ADRs, regardless of scope, are repo-backed, version-controlled, PR-reviewed, and recoverable. No document exists only inside Copilot infrastructure.
- The sync pipeline applies uniformly to all ADRs. There is no special-case handling for cross-boundary documents — one pipeline, one trigger model.
- Confluence receives a complete mirror of all ADRs (both repo-specific and cross-boundary) without manual steps.
- The Copilot Space remains a clean, purpose-scoped tool: AI-powered query and discovery, not a document store.
- Non-GitHub stakeholders gain read visibility into cross-boundary ADRs via Confluence, which was not achievable under the Space-hosted document approach.

**Tradeoffs and risks:**

- Contributors authoring cross-boundary ADRs must use \`core-platform-adr-hub\` rather than the more convenient Space upload flow. This requires clear onboarding guidance.
- The \`core-platform-adr-hub\` repo introduces a new repository to maintain — access controls, branch protection, and CODEOWNERS must be configured at inception.
- As the number of indexed repositories grows, the Copilot Space source list requires active curation. A process for onboarding new repos into the Space must be defined.

## Next Steps

1. Create the \`l0002-adr-hub\` repository with branch protection, CODEOWNERS, and an initial README defining scope and contribution process.
2. Add \`core-platform-adr-hub\` as a source in the Copilot Space (replacing any uploaded documents from ADR-0001 prototyping).
3. Pilot the GitHub Actions sync pipeline against \`core-platform-adr-hub\` — see [ADR-CorePlatform-0003](/cross-boundary/ADR-CorePlatform-0003.md).
4. Define the process for onboarding new ABC Inc repositories into the Copilot Space source list.
5. Document the governing principle ("Space never owns documents") in the repo README and Copilot Space instructions.

## Citations

[1] [ADR-CorePlatform-0001 — ADR Knowledge Base Using Copilot Spaces](/cross-boundary/ADR-CorePlatform-0001.md)
[2] [ADR-CorePlatform-0003 — Confluence Sync Pipeline](/cross-boundary/ADR-CorePlatform-0003.md)
[3] [GitHub Copilot Spaces — concepts](https://docs.github.com/en/copilot/concepts/context/spaces)

