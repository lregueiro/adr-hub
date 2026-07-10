---
type: Architecture Decision Record
title: "Plugin-Based Sync Architecture with Destination-Agnostic Intermediate Representation"
description: "Restructure the sync pipeline around a markdown-native intermediate representation so new sync destinations are added as plugins without changing pipeline core."
tags: [core-platform, knowledge-management, sync-pipeline, plugin-architecture, extensibility]
timestamp: 2026-07-10T00:00:00Z
okf_version: "0.1"

# ADR extensions
adr_id: ADR-CorePlatform-0004
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

[ADR-CorePlatform-0003](/cross-boundary/ADR-CorePlatform-0003.md) specifies a sync pipeline with Confluence as the destination. Confluence-specific concerns — storage-format rendering, section-to-anchor mapping, Info Panel rendering of frontmatter, section-level incremental writes for comment preservation, and parent-page navigation synthesis — are currently embedded in the pipeline itself.

We want to add new sync destinations (e.g. a static documentation site) without rewriting the pipeline each time. This requires separating destination-agnostic work (detecting change, parsing OKF) from destination-specific work (rendering to a target format, writing to a target system).

To avoid designing an abstraction against a single example — which risks overfitting to Confluence — a second destination was used as a design foil: a **static documentation site**. It is deliberately the opposite of Confluence on the two seams that matter:

- **Rendering.** Confluence discards raw frontmatter and re-renders it as a macro; most static-site generators (MkDocs, Docusaurus, Hugo) consume raw markdown *with frontmatter intact*. Opposite directions.
- **Write strategy.** Confluence requires section-level incremental writes because destructive rewrites orphan inline comments; a static site has no comments and is regenerated wholesale. Opposite strategies.

Testing the boundary against this foil surfaced one genuine correction (navigation synthesis is destination-shaped, not universal — see Decision) and otherwise left the interface stable, which is evidence the boundary is sound rather than Confluence-specific.

## Decision

Restructure the pipeline so that **pipeline core produces a destination-agnostic intermediate representation (IR)**, and **destination plugins consume the IR** to render and write. Adding a destination means writing a plugin; it never requires changing core.

### The core / plugin boundary

- **Pipeline core (shared, destination-agnostic):**
  - Change detection — git diff, OKF filters, section content hashing (unchanged from ADR-0003).
  - OKF parsing — frontmatter and body-into-sections.
  - Produces the IR. Contains no destination-native concepts (no storage format, no anchors, no macros, no nav files).

- **Destination plugin (per destination):**
  - Renders IR sections into the destination's native format.
  - Resolves the destination address and publication gate from frontmatter.
  - Writes to the destination, choosing its own write strategy (incremental or full).
  - Renders navigation for the destination from the bundle tree.

### The intermediate representation (the stable contract)

The IR is **markdown-native**. For each ADR it carries:

- Parsed OKF frontmatter (complete — plugins select the fields they need, including per-destination target/gate fields).
- Body as an ordered list of sections: \`{ name, raw_markdown, content_hash }\`.
- The bundle tree (derived from \`index.md\` and directory structure) for navigation synthesis.

The IR must never leak destination-native representations. Confluence storage format, anchors, and Info Panels are Confluence-*plugin* concerns, not IR concerns. Core offers section hashes; it does not impose their use — a plugin may use them for incremental writes or ignore them for full writes.

### The plugin interface

\`\`\`
Plugin:
  name()                          -> identifier for logs / telemetry
  target_id(adr_ir)               -> destination address from frontmatter
                                     (Confluence: page id;  docs site: file path)
  is_publishable(adr_ir)          -> per-destination draft gate
                                     (Confluence: confluence_page_id not null;
                                      docs site: may be always true)
  render(adr_ir)                  -> destination-native artifact from IR sections
                                     (Confluence: storage format;
                                      docs site: markdown passthrough)
  sync(rendered, target_id)       -> write; strategy is the plugin's choice
                                     (Confluence: section-incremental;
                                      docs site: full write)
  render_navigation(bundle_tree)  -> destination-native navigation
                                     (Confluence: parent page;
                                      docs site: nav config e.g. mkdocs.yml)
\`\`\`

### Per-destination frontmatter targeting

Each plugin reads its own target and gate field, so an ADR can be published to one destination while withheld from another:

\`\`\`yaml
# destination targeting — each plugin reads its own
confluence_page_id: "123456789"    # confluence: target + publication gate
docs_site_path: ~                   # docs site: withheld (draft) until path assigned
\`\`\`

### Relationship to ADR-0003

This ADR **amends** ADR-0003. The Confluence-specific behavior described in ADR-0003 — storage-format rendering, section-to-anchor mapping, Info Panel, section-incremental writes, and parent-page synthesis — is reclassified as **the Confluence plugin implementation**, not pipeline-core behavior. The change-detection and OKF-parsing behavior in ADR-0003 remains core.

One correction that the docs-site foil surfaced is folded back into ADR-0003: navigation/index synthesis is destination-shaped, so it moves from a core step to the plugin \`render_navigation\` responsibility, fed by the bundle tree in the IR.

## Consequences

**Benefits:**

- New destinations are added as plugins against a stable IR contract; core is untouched.
- The same IR serves opposite destinations — a comment-preserving incremental writer (Confluence) and a full-overwrite writer (static site) — with no special-casing in core.
- Per-destination publication gates let an ADR go to one destination while withheld from another.
- The boundary was validated against a deliberately opposite second destination, reducing the risk of a Confluence-shaped abstraction.

**Tradeoffs and risks:**

- **The IR is validated by design against the docs site but not yet proven by a second running plugin.** Until a second plugin actually ships, the IR contract should be treated as provisional — the first real second implementation may surface a field the IR is missing. This is an accepted, explicitly-recorded limitation.
- A plugin layer adds indirection over a single hard-coded destination. For a one-destination deployment this is overhead; it pays off only as destinations are added.
- The plugin interface is now a maintained API surface. Interface changes ripple to all plugins, so it should change deliberately.

## Next Steps

1. Extract the Confluence behavior from the ADR-0003 pipeline into the first plugin implementing this interface, leaving change-detection and OKF-parsing in core.
2. Define the IR as a concrete, documented data structure (the stable API between core and plugins).
3. Build a static-docs-site plugin as the second implementation to convert the provisional IR contract into a proven one; record any IR fields it forces to be added.
4. Document the plugin-authoring guide (how to implement the interface) in the repo.

## Citations

[1] [ADR-CorePlatform-0003 — Confluence Sync Pipeline](/cross-boundary/ADR-CorePlatform-0003.md)
[2] [ADR-CorePlatform-0002 — Hub Repo and Spaces Aggregation Model](/cross-boundary/ADR-CorePlatform-0002.md)
