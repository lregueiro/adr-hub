# Contributing an ADR

1. Copy [ADR-TEMPLATE.md](ADR-TEMPLATE.md) into `cross-boundary/` as
   `ADR-CorePlatform-####.md`, using the next free number.
2. Fill in the frontmatter. `type: Architecture Decision Record` is required.
   Leave `confluence_page_id: ~` until the ADR is ready to publish to Confluence
   — that field is the publication gate.
3. Write the body using the template's sections. Keep section headings unchanged:
   the sync pipeline maps them to Confluence anchors by name.
4. Open a PR. Merge requires at least one reviewer from each affected team.
5. On merge, the sync pipeline mirrors published ADRs to Confluence automatically.

## Frontmatter relationships

- `amends` / `amended_by` — a refinement that does not replace the target.
- `supersedes` / `superseded_by` — a replacement; the superseded ADR is retired.
  Only mark an ADR `Superseded` once the replacing ADR is `Accepted`.

Keep both ends of a relationship in sync (if A `amends` B, B lists A in `amended_by`).
