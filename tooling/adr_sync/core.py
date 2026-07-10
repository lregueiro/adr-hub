"""
Pipeline core — destination-agnostic (ADR-0003 detection/parsing, ADR-0004 boundary).

Responsibilities:
  1. Change detection: git diff -> changed .md paths.
  2. OKF filtering: keep only ADR concepts; drop reserved files.
  3. Parse OKF markdown into the IR (frontmatter + hashed sections + bundle tree).

Explicitly NOT here:
  - The publication/draft gate. Under ADR-0004 that is per-plugin (is_publishable),
    not a core detection filter. Core detects every changed ADR; each plugin
    decides whether to sync it. (This supersedes ADR-0003's detection Filter 3.)
  - Any destination-native rendering or writing.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path
from typing import Any

import yaml

from .ir import AdrIR, BundleNode, Section

ADR_TYPE = "Architecture Decision Record"
RESERVED_FILENAMES = {"index.md", "log.md"}

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.DOTALL)
_SECTION_RE = re.compile(r"^##[ \t]+(.+?)[ \t]*$", re.MULTILINE)


# ---------------------------------------------------------------------------
# Change detection
# ---------------------------------------------------------------------------


def changed_markdown_paths(bundle_root: Path, base_ref: str, head_ref: str = "HEAD") -> list[Path]:
    """Return changed .md paths between two git refs (ADR-0003: git diff).

    No timestamp gate — change detection depends only on git and, later, content
    hashing (ADR-0003 decision #3).
    """
    out = subprocess.run(
        ["git", "-C", str(bundle_root), "diff", "--name-only", f"{base_ref}", f"{head_ref}"],
        capture_output=True, text=True, check=True,
    ).stdout
    paths = []
    for line in out.splitlines():
        line = line.strip()
        if line.endswith(".md"):
            paths.append(bundle_root / line)
    return paths


# ---------------------------------------------------------------------------
# OKF parsing
# ---------------------------------------------------------------------------


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError("no parseable YAML frontmatter block")
    fm = yaml.safe_load(m.group(1)) or {}
    body = m.group(2)
    return fm, body


def _hash(s: str) -> str:
    return hashlib.sha256(s.strip().encode("utf-8")).hexdigest()


def _parse_sections(body: str) -> tuple[Section, ...]:
    """Split a markdown body into ordered ## sections, hashing each."""
    matches = list(_SECTION_RE.finditer(body))
    sections: list[Section] = []
    for i, match in enumerate(matches):
        name = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        raw = body[start:end].strip("\n")
        sections.append(Section(name=name, raw_markdown=raw, content_hash=_hash(raw)))
    return tuple(sections)


def is_adr(frontmatter: dict[str, Any]) -> bool:
    return frontmatter.get("type") == ADR_TYPE


def is_reserved(path: Path) -> bool:
    return path.name in RESERVED_FILENAMES


def concept_id_for(bundle_root: Path, path: Path) -> str:
    """OKF concept id: bundle-relative path with .md removed."""
    rel = path.relative_to(bundle_root).as_posix()
    return rel[:-3] if rel.endswith(".md") else rel


def parse_adr(bundle_root: Path, path: Path, bundle_tree: BundleNode) -> AdrIR | None:
    """Parse one file into an AdrIR, or return None if it is not an ADR concept.

    Applies only the destination-agnostic OKF filters (type + reserved name).
    The draft gate is deliberately NOT applied here (ADR-0004).
    """
    if is_reserved(path):
        return None
    text = path.read_text(encoding="utf-8")
    frontmatter, body = _split_frontmatter(text)
    if not is_adr(frontmatter):
        return None
    return AdrIR(
        concept_id=concept_id_for(bundle_root, path),
        source_path=str(path),
        frontmatter=frontmatter,
        sections=_parse_sections(body),
        bundle_tree=bundle_tree,
    )


# ---------------------------------------------------------------------------
# Bundle tree (for plugin navigation synthesis)
# ---------------------------------------------------------------------------


def build_bundle_tree(bundle_root: Path) -> BundleNode:
    """Build the bundle tree from the directory structure and ADR frontmatter.

    Plugins turn this into destination-native navigation (ADR-0004).
    """

    def node_for_dir(directory: Path) -> BundleNode:
        children: list[BundleNode] = []
        for child in sorted(directory.iterdir()):
            if child.is_dir():
                children.append(node_for_dir(child))
            elif child.suffix == ".md" and child.name not in RESERVED_FILENAMES:
                title, desc = _title_and_desc(child)
                children.append(
                    BundleNode(
                        title=title,
                        concept_id=concept_id_for(bundle_root, child),
                        description=desc,
                        children=(),
                    )
                )
        title = "root" if directory == bundle_root else directory.name
        return BundleNode(title=title, concept_id=None, description=None, children=tuple(children))

    return node_for_dir(bundle_root)


def _title_and_desc(path: Path) -> tuple[str, str | None]:
    try:
        fm, _ = _split_frontmatter(path.read_text(encoding="utf-8"))
        return fm.get("title", path.stem), fm.get("description")
    except ValueError:
        return path.stem, None


# ---------------------------------------------------------------------------
# Top-level detection pass
# ---------------------------------------------------------------------------


def detect_changed_adrs(bundle_root: Path, base_ref: str, head_ref: str = "HEAD") -> list[AdrIR]:
    """Full core detection pass: git diff -> OKF filter -> parse to IR.

    Returns every changed ADR concept. Per-destination publishability is decided
    later by each plugin, not here.
    """
    tree = build_bundle_tree(bundle_root)
    results: list[AdrIR] = []
    for path in changed_markdown_paths(bundle_root, base_ref, head_ref):
        if not path.exists():          # deleted file; deletion handling is future work
            continue
        adr = parse_adr(bundle_root, path, tree)
        if adr is not None:
            results.append(adr)
    return results
