---
type: Architecture Decision Record
title: "Confluence Sync Pipeline for OKF ADR Bundle"
description: "One-way GitHub Actions pipeline mirroring OKF-conformant ADRs to Confluence, using git diff and content hashing to sync only changed sections while preserving stakeholder comments."
tags: [core-platform, knowledge-management, confluence, sync-pipeline, ci-cd]
timestamp: 2026-07-10T00:00:00Z
okf_version: "0.1"

# ADR extensions
adr_id: ADR-CorePlatform-0003
status: Proposed
authors:
  - name: "Vamsi"
    role: "Tech Strategy"
supersedes: ~
superseded_by: ~
amends: ~
amended_by: [ADR-CorePlatform-0004, ADR-CorePlatform-0005]
confluence_page_id: ~
---

## Context

[ADR-CorePlatform-0001](/cross-boundary/ADR-CorePlatform-0001.md) designates Confluence as the stakeholder mirror for ABC Inc ADRs, and [ADR-CorePlatform-0002](/cross-boundary/ADR-CorePlatform-0002.md) establishes \`core-platform-adr-hub\` as the OKF-conformant source of truth. This ADR specifies the pipeline that mirrors the repo to Confluence.

Requirements established during design:

- **One-way sync.** GitHub is the source of truth; Confluence is a mirror. No content flows back from Confluence to the repo.
- **Enriched mirror.** ADR section bodies map exactly to Confluence page body content; the OKF frontmatter is additionally rendered as a Confluence Info Panel for at-a-glance metadata. "Exact wording on the sections" and "enriched with a metadata panel" are both true.
- **Comment preservation.** Stakeholders add inline and page-level comments in Confluence. These must survive syncs. Confluence inline comments are anchored to text ranges by marker ID and are orphaned if their anchor text changes, so the pipeline must avoid rewriting unchanged content.
- **No reliance on human discipline** for change detection. An earlier design gated syncs on a hand-authored \`timestamp\` frontmatter field; this was rejected because a forgotten timestamp bump would silently skip a real content change.
- **Target:** Confluence Cloud, DSP space.

## Decision

Implement a GitHub Actions pipeline triggered on push to \`main\`, structured in three stages: detection, transformation, and sync.

### Change detection — git diff + content hash (no timestamp gate)

Detection is driven entirely by git and content hashing. There is **no** \`timestamp\`-based gate — change detection must not depend on any hand-authored field.

\`\`\`
Push to main
      |
      v
git diff against previous commit  ->  list of changed .md paths
      |
      v
Filter 1: OKF frontmatter type == "Architecture Decision Record"
Filter 2: not a reserved OKF filename (index.md, log.md)
Filter 3: confluence_page_id is not null   (null => unpublished draft, skip)
      |
      v
Eligible ADRs -> Stage 2
\`\`\`

The \`confluence_page_id: ~\` convention remains the publication gate: an ADR can be merged and indexed by the Space while still withheld from Confluence until a page ID is assigned. This is an intentional editorial control, not a change-detection mechanism.

### Transformation — section-to-anchor mapping

Each ADR body section is converted independently (markdown to Confluence storage format via \`pandoc\`) and mapped to a named Confluence anchor:

\`\`\`
OKF Section        ->   Confluence Anchor
-----------------------------------------------
frontmatter        ->   okf-metadata     (rendered as Info Panel macro)
## Context         ->   okf-context
## Decision        ->   okf-decision
## Consequences    ->   okf-consequences
## Next Steps      ->   okf-next-steps
## Citations       ->   okf-citations
\`\`\`

The section body content is mirrored verbatim. The frontmatter is the only enrichment — surfaced as an Info Panel showing \`status\`, \`adr_id\`, \`authors\`, and \`tags\` — and is never mixed into section prose.

### Sync — hash-compared, section-level writes

\`\`\`
For each eligible ADR:
  Fetch current Confluence page body (GET content/{confluence_page_id})
  Parse existing body into named anchor sections
  For each section:
    hash(incoming converted content) vs hash(existing section content)
    if different -> queue section for replacement
  If no sections queued -> no API write (page and all comments untouched)
  If sections queued:
    replace only changed anchor sections in the page body
    increment page version
    PUT content/{confluence_page_id}
\`\`\`

The content hash is the authoritative change signal. Because only genuinely changed sections are rewritten, inline comment anchors on unchanged sections are preserved. Page-level comments are stored separately by Confluence and always survive.

### Index synthesis

The pipeline synthesizes a Confluence parent/landing page from the bundle's \`index.md\`, giving non-GitHub stakeholders navigation across ADRs. This is the one case where a reserved OKF file drives Confluence output: \`index.md\` is not synced as an ADR, but is transformed into the parent page under which individual ADR pages are nested. \`log.md\` is not synced.

> **Amended by [ADR-CorePlatform-0004](/cross-boundary/ADR-CorePlatform-0004.md).** Navigation synthesis is destination-shaped, not universal — a Confluence parent page and a static-site nav config are rendered differently from the same input. Under the plugin architecture, index synthesis is a plugin responsibility (\`render_navigation\`, fed by the bundle tree in the IR), not a core pipeline step. The behavior described here is now specifically the *Confluence plugin's* navigation rendering.

### Sync telemetry — Actions run history only

The pipeline is a **consumer** of the OKF bundle and never writes back to the repository. Sync operation records (what changed, what was pushed, what was skipped) live in the GitHub Actions run history. The pipeline does not write to \`log.md\` — that file is reserved for human- and agent-authored knowledge history, a different audience and lifecycle from machine sync telemetry. If durable, queryable sync history is later required (e.g. for audit), it will be promoted to a dedicated machine log at that point — never merged into \`log.md\`.

### Configuration

All configuration lives in GitHub Actions secrets and variables. There is no committed pipeline config file; ADR-specific configuration (\`confluence_page_id\`) is read from OKF frontmatter.

\`\`\`
Secrets (sensitive):
  CONFLUENCE_USER          service account email
  CONFLUENCE_API_TOKEN     Atlassian API token

Variables (non-sensitive):
  CONFLUENCE_BASE_URL      https://cawiki.atlassian.net
  CONFLUENCE_SPACE_KEY     DSP
\`\`\`

## Consequences

**Benefits:**

- Change detection depends only on git and content hashes — no hand-authored field can cause a silent skip.
- Stakeholder comments survive syncs because unchanged sections are never rewritten.
- Confluence stakeholders get both faithful ADR content and an at-a-glance metadata panel, plus a synthesized index page for navigation.
- The pipeline stays a pure consumer — no write-back, no retrigger loop, clean separation between knowledge history and sync telemetry.
- Agent-authored and human-authored ADRs flow through the identical path; the pipeline does not distinguish them.

**Tradeoffs and risks:**

- Section-level diffing is more complex to implement than a full-page replace. The anchor-mapping logic must stay aligned with the ADR template's section structure; a template change requires a pipeline update.
- Inline comments anchored to text *within* a section that genuinely changes will still be orphaned — comment preservation holds at section granularity, not line granularity. This is inherent to Confluence's anchoring model and accepted.
- Sync telemetry is only as durable as GitHub Actions log retention until/unless a dedicated machine log is later added.
- \`pandoc\` markdown-to-storage-format conversion may need per-macro tuning for tables and code blocks during the pilot.

## Next Steps

1. Build the GitHub Actions workflow and sync script skeleton, running in dry-run mode (all stages execute, no Confluence writes).
2. Manually create Confluence pages for ADR-0001 and ADR-0002 in DSP, populate their \`confluence_page_id\`, and merge to trigger the first live sync.
3. Validate comment preservation: add a test comment in Confluence, make a minor edit to one section of one ADR, merge, and confirm only that section updates and the comment survives.
4. Validate index synthesis produces a usable parent page.
5. Promote from pilot to additional repositories once validated.

## Citations

[1] [ADR-CorePlatform-0001 — ADR Knowledge Base Using Copilot Spaces](/cross-boundary/ADR-CorePlatform-0001.md)
[2] [ADR-CorePlatform-0002 — Hub Repo and Spaces Aggregation Model](/cross-boundary/ADR-CorePlatform-0002.md)
[3] [Confluence Cloud REST API — content](https://developer.atlassian.com/cloud/confluence/rest/v2/)
