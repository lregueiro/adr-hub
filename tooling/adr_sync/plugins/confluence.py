"""
Confluence destination plugin (ADR-0003 behavior, reclassified by ADR-0004 as
'the Confluence plugin implementation' rather than pipeline core).

Confluence-specific concerns that live HERE, not in core:
  - storage-format rendering
  - section-to-anchor mapping
  - Info Panel rendering of frontmatter (the 'enriched mirror', ADR-0003 #2)
  - section-level incremental writes for comment preservation (ADR-0003)
  - parent-page navigation synthesis (ADR-0004 render_navigation)

This is a SKELETON. render() and sync() contain the structure and the decision
points, with the actual pandoc conversion and REST calls stubbed for the
dry-run pilot (ADR-0003 next step 1).
"""

from __future__ import annotations

import os

from ..ir import AdrIR, BundleNode, DestinationPlugin, RenderedArtifact, SyncResult

# Section -> Confluence anchor map (ADR-0003). Coupled to the ADR template's
# heading structure: if the template's section headings change, update this map.
SECTION_ANCHORS = {
    "Context": "okf-context",
    "Decision": "okf-decision",
    "Consequences": "okf-consequences",
    "Next Steps": "okf-next-steps",
    "Citations": "okf-citations",
}


class ConfluencePlugin(DestinationPlugin):
    def __init__(self, dry_run: bool = True) -> None:
        self.dry_run = dry_run
        self.base_url = os.environ.get("CONFLUENCE_BASE_URL", "")
        self.space_key = os.environ.get("CONFLUENCE_SPACE_KEY", "")
        self.user = os.environ.get("CONFLUENCE_USER", "")
        self.token = os.environ.get("CONFLUENCE_API_TOKEN", "")

    def name(self) -> str:
        return "confluence"

    def target_id(self, adr: AdrIR) -> str | None:
        # Confluence target + publication gate is the confluence_page_id field.
        page_id = adr.frontmatter.get("confluence_page_id")
        return str(page_id) if page_id else None

    def is_publishable(self, adr: AdrIR) -> bool:
        # Draft gate: withhold from Confluence until a page id is assigned.
        return self.target_id(adr) is not None

    def render(self, adr: AdrIR) -> RenderedArtifact:
        """Build the enriched-mirror body: Info Panel from frontmatter + one
        storage-format region per mapped section.

        The Info Panel is the ONLY enrichment; section bodies are the ADR wording
        verbatim (ADR-0003 #2). Section content is converted via pandoc in the
        real implementation; stubbed here.
        """
        info_panel = self._render_info_panel(adr.frontmatter)
        regions: dict[str, str] = {}
        for section in adr.sections:
            anchor = SECTION_ANCHORS.get(section.name)
            if anchor is None:
                continue  # unmapped section; not mirrored
            regions[anchor] = self._md_to_storage(section.raw_markdown)

        content = {"info_panel": info_panel, "regions": regions}
        # changed_section_names is filled at sync time after fetching the remote;
        # left empty here.
        return RenderedArtifact(content=content, metadata={"anchors": list(regions)})

    def sync(self, rendered: RenderedArtifact, target_id: str) -> SyncResult:
        """Fetch current page, hash-compare per section, write only changed
        anchor regions (ADR-0003). If nothing changed, no API write — protects
        inline comments.
        """
        if self.dry_run:
            anchors = rendered.metadata.get("anchors", [])
            return SyncResult(
                plugin=self.name(),
                concept_id="(dry-run)",
                action="skipped",
                detail=f"DRY RUN: would upsert page {target_id}, regions={anchors}",
            )

        # --- real path (stubbed) ---------------------------------------------
        # existing = self._get_page(target_id)
        # existing_regions = self._parse_regions(existing["body"])
        # changed = [a for a, html in rendered.content["regions"].items()
        #            if self._hash(html) != self._hash(existing_regions.get(a, ""))]
        # if not changed:
        #     return SyncResult(self.name(), target_id, "skipped", "no section changed")
        # new_body = self._replace_regions(existing["body"], rendered.content, changed)
        # self._put_page(target_id, new_body, existing["version"] + 1)
        # return SyncResult(self.name(), target_id, "updated", f"sections={changed}")
        raise NotImplementedError("live sync not implemented in skeleton")

    def render_navigation(self, bundle_tree: BundleNode) -> RenderedArtifact:
        """Confluence navigation = a parent/landing page listing child ADRs.

        (ADR-0004: navigation is per-destination; this is Confluence's form.)
        """
        lines = ["<h1>ABC Inc ADR Hub</h1>", "<ul>"]
        self._nav_list(bundle_tree, lines)
        lines.append("</ul>")
        html = "\n".join(lines)
        if self.dry_run:
            return RenderedArtifact(content=html, metadata={"kind": "parent_page", "dry_run": True})
        return RenderedArtifact(content=html, metadata={"kind": "parent_page"})

    # --- helpers -------------------------------------------------------------

    def _nav_list(self, node: BundleNode, lines: list[str]) -> None:
        for child in node.children:
            if child.concept_id:
                desc = f" &mdash; {child.description}" if child.description else ""
                lines.append(f'<li><a href="{child.concept_id}">{child.title}</a>{desc}</li>')
            else:
                lines.append(f"<li><strong>{child.title}</strong><ul>")
                self._nav_list(child, lines)
                lines.append("</ul></li>")

    def _render_info_panel(self, fm: dict) -> str:
        authors = ", ".join(
            a.get("name", "") if isinstance(a, dict) else str(a)
            for a in (fm.get("authors") or [])
        )
        tags = ", ".join(fm.get("tags") or [])
        rows = [
            ("ADR", fm.get("adr_id", "")),
            ("Status", fm.get("status", "")),
            ("Authors", authors),
            ("Tags", tags),
        ]
        body = "".join(f"<p><strong>{k}:</strong> {v}</p>" for k, v in rows if v)
        return f'<ac:structured-macro ac:name="info"><ac:rich-text-body>{body}</ac:rich-text-body></ac:structured-macro>'

    def _md_to_storage(self, markdown: str) -> str:
        # Real implementation shells out to pandoc:
        #   pandoc -f gfm -t <confluence storage> ...
        # Stubbed for the skeleton.
        return f"<!-- storage-format for: -->\n<p>{markdown[:60]}...</p>"
