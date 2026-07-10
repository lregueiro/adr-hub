# ABC Inc ADR Hub

Knowledge bundle for ABC Inc architectural decisions. Conforms to OKF v0.1.

All documents in this bundle are repo-backed and version-controlled. The Copilot Space indexes this repository as a read-only query source — no documents are authored in the Space itself.

Layer model:
- **Source of truth:** this repository
- **Query layer:** GitHub Copilot Spaces (indexes this repo)
- **Stakeholder mirror:** Confluence DSP space (fed by one-way sync pipeline)

See [architecture.md](architecture.md) for C4 and flow diagrams of how the components interact.

# Cross-Boundary ADRs

Decisions that span multiple ABC Inc repositories or teams.

* [ADR-CorePlatform-0001](cross-boundary/ADR-CorePlatform-0001.md) - Adopt Copilot Spaces as the query layer, the ADR hub repo as source of truth, and Confluence as the stakeholder mirror.
* [ADR-CorePlatform-0002](cross-boundary/ADR-CorePlatform-0002.md) - Cross-boundary ADRs are authored in this hub repo; Copilot Spaces is a query-only layer. Amends ADR-0001.
* [ADR-CorePlatform-0003](cross-boundary/ADR-CorePlatform-0003.md) - One-way Confluence sync pipeline using git diff and content hashing, preserving stakeholder comments.
* [ADR-CorePlatform-0004](cross-boundary/ADR-CorePlatform-0004.md) - Plugin-based sync architecture with a destination-agnostic intermediate representation. Amends ADR-0003.
* [ADR-CorePlatform-0005](cross-boundary/ADR-CorePlatform-0005.md) - Pipeline lives in the hub repo for the POC; extracted to a reusable/published form at scale. Amends ADR-0003.

# Contributing

New ADRs must use the [ADR template](ADR-TEMPLATE.md). All ADRs are merged via pull request with at least one reviewer from each affected team.

See \`CONTRIBUTING.md\` for the full authoring guide.
