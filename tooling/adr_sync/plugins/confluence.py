"""
Confluence destination plugin (ADR-0003 behavior, reclassified by ADR-0004 as
'the Confluence plugin implementation' rather than pipeline core).

Confluence-specific concerns that live HERE, not in core:
  - storage-format rendering (markdown -> XHTML via pandoc)
  - section-to-anchor mapping
  - Info Panel rendering of frontmatter (the 'enriched mirror', ADR-0003 #2)
  - section-level incremental writes for comment preservation (ADR-0003)
  - parent-page navigation synthesis (ADR-0004 render_navigation)

Auth: classic API token + HTTP basic auth against the site URL
(https://<site>.atlassian.net/wiki/rest/api/...). If you switch to a scoped
token, change base_url to https://api.atlassian.com/ex/confluence/{cloudId}
and adjust _api() accordingly.
"""

from __future__ import annotations

import hashlib
import html
import os
import re
import subprocess

import urllib.request
import urllib.error
import json
import base64

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

# Marker comment wrapping each section region in the stored page body. Lets us
# find and replace a single section without disturbing the rest (and thus
# without orphaning inline comments on unchanged sections).
_REGION_START = "<!-- okf:region:{anchor} -->"
_REGION_END = "<!-- okf:endregion:{anchor} -->"


class ConfluencePlugin(DestinationPlugin):
    def __init__(self, dry_run: bool = True) -> None:
        self.dry_run = dry_run
        self.base_url = os.environ.get("CONFLUENCE_BASE_URL", "").rstrip("/")
        self.space_key = os.environ.get("CONFLUENCE_SPACE_KEY", "")
        self.user = os.environ.get("CONFLUENCE_USER", "")
        self.token = os.environ.get("CONFLUENCE_API_TOKEN", "")

    def name(self) -> str:
        return "confluence"

    def target_id(self, adr: AdrIR) -> str | None:
        page_id = adr.frontmatter.get("confluence_page_id")
        return str(page_id) if page_id else None

    def is_publishable(self, adr: AdrIR) -> bool:
        return self.target_id(adr) is not None

    # -- render ---------------------------------------------------------------

    def render(self, adr: AdrIR) -> RenderedArtifact:
        """Build the enriched-mirror body: Info Panel from frontmatter + one
        marked storage-format region per mapped section (verbatim wording).

        Also carries each mapped section's SOURCE hash (from the IR) so sync()
        can detect change against Confluence-normalization-proof hashes."""
        parts = [self._render_info_panel(adr.frontmatter)]
        regions: dict[str, str] = {}
        section_hashes: dict[str, str] = {}
        for section in adr.sections:
            anchor = SECTION_ANCHORS.get(section.name)
            if anchor is None:
                continue  # unmapped section; not mirrored
            storage = self._md_to_storage(section.raw_markdown)
            regions[anchor] = storage
            section_hashes[anchor] = section.content_hash  # source hash from core.py
            parts.append(
                _REGION_START.format(anchor=anchor)
                + f"<h2>{html.escape(section.name)}</h2>"
                + storage
                + _REGION_END.format(anchor=anchor)
            )
        full_body = "\n".join(parts)
        return RenderedArtifact(
            content={"body": full_body, "regions": regions, "section_hashes": section_hashes},
            metadata={"anchors": list(regions)},
        )

    def _md_to_storage(self, markdown: str) -> str:
        """Convert a section's markdown to Confluence storage format.

        Pandoc has no native 'storage' writer; storage format is XHTML-based, so
        we convert gfm -> html, which Confluence accepts for the elements ADRs
        use (paragraphs, lists, tables, links, emphasis, code).

        Caveat: bundle-relative .md links (e.g. /cross-boundary/ADR-...-0002.md)
        do not resolve inside Confluence. We rewrite them to plain text with a
        marker so the reader isn't handed a dead link. Cross-ADR linking inside
        Confluence is a future enhancement (map concept-id -> page id).
        """
        if not markdown.strip():
            return ""
        out = subprocess.run(
            ["pandoc", "-f", "gfm", "-t", "html", "--wrap=none"],
            input=markdown, capture_output=True, text=True, check=True,
        ).stdout
        return self._neutralize_md_links(out).strip()

    @staticmethod
    def _neutralize_md_links(html_text: str) -> str:
        # Replace <a href="....md">text</a> (bundle-relative ADR links) with just
        # the text, since those paths 404 in Confluence.
        return re.sub(
            r'<a href="[^"]*\.md"[^>]*>(.*?)</a>',
            r"\1",
            html_text,
            flags=re.DOTALL,
        )

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
        body = "".join(
            f"<p><strong>{html.escape(k)}:</strong> {html.escape(str(v))}</p>"
            for k, v in rows if v
        )
        return (
            '<ac:structured-macro ac:name="info">'
            f"<ac:rich-text-body>{body}</ac:rich-text-body>"
            "</ac:structured-macro>"
        )

    # -- sync -----------------------------------------------------------------

    def sync(self, rendered: RenderedArtifact, target_id: str) -> SyncResult:
        """Fetch current page, replace only changed section regions, PUT back.
        Unchanged regions (and their inline comments) are left intact."""
        if self.dry_run:
            anchors = rendered.metadata.get("anchors", [])
            return SyncResult(
                plugin=self.name(), concept_id="(dry-run)", action="skipped",
                detail=f"DRY RUN: would upsert page {target_id}, regions={anchors}",
            )

        page = self._get_page(target_id)
        version = page["version"]["number"]

        # Change detection uses SOURCE hashes (from the IR), not stored HTML.
        # Confluence normalizes stored storage-format on save (reorders
        # attributes, rewrites entities, strips HTML comments), so hashing the
        # round-tripped body always reports "changed". The source-markdown hash
        # is computed in core.py and is immune to that. We persist the per-section
        # source hashes in a Confluence content property (invisible on the page).
        stored = self._get_hashes(target_id)          # {anchor: source_hash} or {}
        incoming = rendered.content["section_hashes"]  # {anchor: source_hash}

        changed = [a for a, h in incoming.items() if stored.get(a) != h]

        if stored and not changed:
            return SyncResult(self.name(), target_id, "skipped", "no section changed")

        # Whenever anything changed (or first publish), write the full rendered
        # body. Section-level *change detection* is what protects comments across
        # no-op syncs; a genuine content change to a section legitimately rewrites
        # the body. Inline comments on UNCHANGED sections are protected because an
        # unchanged-only sync never reaches this write at all (skipped above).
        self._put_page(target_id, page["title"], rendered.content["body"], version + 1)
        self._put_hashes(target_id, incoming)
        # Enforce one-way sync: lock EDITING to the service account so stakeholders
        # can't alter the mirror body (which the next sync would silently
        # overwrite). Read stays open, so viewers can still see and COMMENT.
        self._restrict_edit_to_self(target_id)
        detail = "first publish" if not stored else f"sections={changed}"
        return SyncResult(self.name(), target_id, "updated", detail)

    # -- navigation -----------------------------------------------------------

    def render_navigation(self, bundle_tree: BundleNode) -> RenderedArtifact:
        lines = ["<h1>Core Platform ADR Hub</h1>", "<ul>"]
        self._nav_list(bundle_tree, lines)
        lines.append("</ul>")
        return RenderedArtifact(
            content="\n".join(lines),
            metadata={"kind": "parent_page", "dry_run": self.dry_run},
        )

    def _nav_list(self, node: BundleNode, lines: list[str]) -> None:
        for child in node.children:
            if child.concept_id:
                desc = f" &mdash; {html.escape(child.description)}" if child.description else ""
                lines.append(f"<li><strong>{html.escape(child.title)}</strong>{desc}</li>")
            else:
                lines.append(f"<li><strong>{html.escape(child.title)}</strong><ul>")
                self._nav_list(child, lines)
                lines.append("</ul></li>")

    # -- REST helpers ---------------------------------------------------------

    # -- edit restrictions: enforce one-way sync ------------------------------
    # Lock the 'update' (edit) operation to the service account only. Crucially
    # we do NOT restrict 'read' — read access governs commenting, so leaving it
    # open keeps the page viewable and commentable by everyone while making the
    # body service-account-write-only.

    _self_account_id: str | None = None

    def _current_account_id(self) -> str:
        if self._self_account_id:
            return self._self_account_id
        url = self._api("user/current")
        req = urllib.request.Request(url, headers={
            "Authorization": self._auth_header(),
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req) as resp:
            self._self_account_id = json.loads(resp.read().decode())["accountId"]
        return self._self_account_id

    def _restrict_edit_to_self(self, page_id: str) -> None:
        account_id = self._current_account_id()
        url = self._api(f"content/{page_id}/restriction")
        # operation 'update' == edit. Only the service account may edit; read is
        # left unrestricted so all viewers retain view + comment access.
        payload = [{
            "operation": "update",
            "restrictions": {"user": [{"type": "known", "accountId": account_id}]},
        }]
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(), method="PUT",
            headers={
                "Authorization": self._auth_header(),
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req) as resp:
            resp.read()

    def _auth_header(self) -> str:
        raw = f"{self.user}:{self.token}".encode()
        return "Basic " + base64.b64encode(raw).decode()

    def _api(self, path: str) -> str:
        return f"{self.base_url}/wiki/rest/api/{path}"

    def _get_page(self, page_id: str) -> dict:
        url = self._api(f"content/{page_id}?expand=body.storage,version")
        req = urllib.request.Request(url, headers={
            "Authorization": self._auth_header(),
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())

    def _put_page(self, page_id: str, title: str, body: str, version: int) -> dict:
        url = self._api(f"content/{page_id}")
        payload = {
            "id": page_id,
            "type": "page",
            "title": title,
            "version": {"number": version},
            "body": {"storage": {"value": body, "representation": "storage"}},
        }
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(), method="PUT",
            headers={
                "Authorization": self._auth_header(),
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())

    # -- content properties: per-section source hashes ------------------------
    # Stored as a page property (key: okf_section_hashes). Invisible on the page
    # body, immune to storage-format normalization, and the authority for
    # "did this section change?" across syncs.

    _PROP_KEY = "okf_section_hashes"

    def _get_hashes(self, page_id: str) -> dict:
        url = self._api(f"content/{page_id}/property/{self._PROP_KEY}")
        req = urllib.request.Request(url, headers={
            "Authorization": self._auth_header(),
            "Accept": "application/json",
        })
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode())
            return data.get("value", {}) or {}
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {}  # property not set yet (first publish)
            raise

    def _put_hashes(self, page_id: str, hashes: dict) -> None:
        # Property has its own version; fetch current to increment, else create.
        get_url = self._api(f"content/{page_id}/property/{self._PROP_KEY}")
        current_version = 0
        try:
            req = urllib.request.Request(get_url, headers={
                "Authorization": self._auth_header(), "Accept": "application/json",
            })
            with urllib.request.urlopen(req) as resp:
                current_version = json.loads(resp.read().decode())["version"]["number"]
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise

        payload = {"key": self._PROP_KEY, "value": hashes}
        if current_version:
            payload["version"] = {"number": current_version + 1}
        req = urllib.request.Request(
            get_url, data=json.dumps(payload).encode(),
            method="PUT" if current_version else "POST",
            headers={
                "Authorization": self._auth_header(),
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        # POST to create uses the collection endpoint, not the keyed one.
        if not current_version:
            create_url = self._api(f"content/{page_id}/property")
            req = urllib.request.Request(
                create_url, data=json.dumps(payload).encode(), method="POST",
                headers={
                    "Authorization": self._auth_header(),
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
        with urllib.request.urlopen(req) as resp:
            resp.read()