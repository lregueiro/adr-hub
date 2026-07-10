---
type: Architecture Decision Record
title: "ADR Knowledge Base for ABC Inc Using GitHub Copilot Spaces"
description: "Adopt GitHub Copilot Spaces as the query layer for ABC Inc ADRs, with the ADR hub repo as source of truth and Confluence as the stakeholder mirror."
tags: [core-platform, knowledge-management, copilot-spaces, confluence]
timestamp: 2026-07-10T00:00:00Z
okf_version: "0.1"

# ADR extensions
adr_id: ADR-CorePlatform-0001
status: Accepted
authors:
  - name: "Vamsi"
    role: "Tech Strategy"
supersedes: ~
superseded_by: ~
amended_by: ADR-CorePlatform-0002
confluence_page_id: 720897
---

## Context

ABC Inc manages architectural decisions across multiple repositories with no unified discovery layer. Architectural knowledge is fragmented: decisions that affect more than one repository are difficult to find, cross-boundary context is lost, and new contributors must piece together rationale from disparate sources.

Tech Strategy independently maintains ADRs in Confluence to serve stakeholders without GitHub access — a gap that emerged because GitHub-native tooling is not accessible to all decision stakeholders (e.g., product managers, architects, and business stakeholders who operate outside of GitHub).

Options considered:

1. **Continue with per-repository ADRs in Confluence** (current Tech Strategy approach) — no cross-repo aggregation, GitHub-native teams must context-switch to Confluence to find decisions.
2. **Centralize all ADRs in a single dedicated GitHub repository** — aggregates content but still excludes non-GitHub users, and cross-boundary ADRs lack proximity to source code.
3. **Use GitHub Copilot Spaces as a knowledge aggregation layer** — indexes ADRs from across ABC Inc repositories and keeps content evergreen as repositories evolve. Confluence remains the stakeholder-facing surface for non-GitHub users, fed by an automated sync pipeline.

**Access consideration:** Copilot Spaces sharing is scoped to GitHub accounts — organization-owned spaces can be shared with org members (admin/editor/viewer roles), and individual-owned spaces can be made public via link. There is no mechanism for non-GitHub users to interact with a Space directly. This constraint shapes the roles below.

## Decision

Adopt the following three-layer model for ABC Inc architectural decisions:

- **Source of truth:** the `core-platform-adr-hub` repository (and repo-specific `docs/adr/` paths). All ADRs are authored here as OKF-conformant markdown, version-controlled and PR-reviewed. See [ADR-CorePlatform-0002](/cross-boundary/ADR-CorePlatform-0002.md).
- **Query layer:** GitHub Copilot Spaces, which indexes the repositories above and provides AI-powered aggregation and conversational discovery for GitHub-native users.
- **Stakeholder mirror:** Confluence (DSP space), fed by an automated one-way sync pipeline from the source of truth, serving non-GitHub stakeholders.

**Governing principle:** The Copilot Space is a query layer only. It must never be the sole owner of a document — every document queryable in the Space must have a repository-backed source.

## Consequences

**Benefits:**

- ADRs across ABC Inc repositories become discoverable and AI-queryable in a single location, reducing context-switching and cross-repo knowledge gaps.
- Repo-sourced content stays evergreen as repositories evolve, avoiding staleness common to manually maintained wikis.
- Copilot Chat grounded in the Space allows GitHub-native contributors to query decision history conversationally.
- Non-GitHub stakeholders gain read access to all ADRs via the Confluence mirror.

**Tradeoffs and risks:**

- **Read access for non-GitHub stakeholders is solved** by the Confluence sync pipeline. **AI-query access for non-GitHub users remains unsolved** — they can read decisions in Confluence but cannot use the Space's conversational query capability, which requires a GitHub account. This is a known, accepted limitation rather than a blocker.
- Copilot Spaces is a relatively new feature. Dependency on it as a query layer introduces tooling risk if the feature set or access policies change at the GitHub platform level.
- Adoption requires ABC Inc contributors who use the Space to have Copilot licenses (any tier), which may require coordination with license administrators.

## Next Steps

1. Create the \`adr-hub\` repository — see [ADR-CorePlatform-0002](/cross-boundary/ADR-CorePlatform-0002.md).
2. Design and pilot the Confluence sync pipeline — see [ADR-CorePlatform-0003](/cross-boundary/ADR-CorePlatform-0003.md).
3. Monitor GitHub's roadmap for non-GitHub access to Copilot Spaces; revisit the AI-query-access limitation if the platform capability changes.

## Citations

[1] [GitHub Copilot Spaces — concepts](https://docs.github.com/en/copilot/concepts/context/spaces)
[2] [GitHub Copilot Spaces — collaborate with others](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/copilot-spaces/collaborate-with-others)
[3] [Tech Strategy Confluence ADR space](https://cawiki.atlassian.net/wiki/spaces/DSP/folder/5397283275)
[4] [ADR-CorePlatform-0002 — Hub Repo and Spaces Aggregation Model](/cross-boundary/ADR-CorePlatform-0002.md)
[5] [ADR-CorePlatform-0003 — Confluence Sync Pipeline](/cross-boundary/ADR-CorePlatform-0003.md)

