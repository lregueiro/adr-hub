"""
Intermediate Representation (IR) — the stable contract between pipeline core
and destination plugins.

Defined by ADR-CorePlatform-0004. The IR is markdown-native and MUST NOT leak
destination-native representations (no Confluence storage format, no anchors,
no macros, no nav files). Core produces the IR; plugins consume it.

If you change this module, you are changing the API that every plugin depends
on. Change it deliberately.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# IR data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Section:
    """One body section of an ADR, e.g. '## Context'.

    Attributes:
        name: The section heading text without the leading '## ' (e.g. "Context").
        raw_markdown: The section body as raw markdown, verbatim. Plugins render
            this into their own target format. It is NOT pre-rendered.
        content_hash: Stable hash of raw_markdown. Core computes it; plugins MAY
            use it for change-only writes (Confluence) or ignore it and full-write
            (static site). See ADR-0004.
    """

    name: str
    raw_markdown: str
    content_hash: str


@dataclass(frozen=True)
class BundleNode:
    """A node in the OKF bundle tree, used by plugins to synthesize navigation.

    Mirrors the directory/index.md structure of the bundle. Plugins render this
    into destination-native navigation via render_navigation() — a Confluence
    parent page, an mkdocs.yml nav tree, etc.
    """

    title: str
    concept_id: str | None          # OKF concept id (path without .md); None for dirs
    description: str | None          # from frontmatter/index, for nav labels
    children: tuple["BundleNode", ...] = ()


@dataclass(frozen=True)
class AdrIR:
    """The intermediate representation of a single ADR.

    This is what core hands to every plugin. It carries everything a plugin
    needs and nothing destination-specific.
    """

    concept_id: str                  # OKF concept id, e.g. "cross-boundary/ADR-...-0001"
    source_path: str                 # path within the bundle, e.g. ".../ADR-...-0001.md"
    frontmatter: dict[str, Any]      # complete parsed OKF frontmatter
    sections: tuple[Section, ...]    # ordered body sections
    bundle_tree: BundleNode          # root of the bundle tree (shared across ADRs)

    def section(self, name: str) -> Section | None:
        """Convenience lookup of a section by heading name."""
        for s in self.sections:
            if s.name == name:
                return s
        return None


# ---------------------------------------------------------------------------
# Plugin interface (ADR-0004)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RenderedArtifact:
    """Opaque-to-core output of a plugin's render step.

    Core never inspects `content` — only the owning plugin's sync() understands
    it. `changed_section_names` is an optional hint a plugin may populate so its
    own sync() can do section-level writes; it is plugin-internal.
    """

    content: Any
    changed_section_names: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SyncResult:
    """Outcome of a single ADR sync, for telemetry (Actions run history only).

    Per ADR-0003, sync telemetry never gets written back to the repo. This
    object is logged, not persisted to the bundle.
    """

    plugin: str
    concept_id: str
    action: str                      # "created" | "updated" | "skipped" | "withheld"
    detail: str = ""


class DestinationPlugin(ABC):
    """Interface every sync destination implements (ADR-0004).

    Core calls these methods; it never reaches into a plugin's internals. Adding
    a destination means implementing this interface — core does not change.
    """

    @abstractmethod
    def name(self) -> str:
        """Stable identifier for logs/telemetry, e.g. 'confluence'."""

    def is_enabled(self) -> bool:
        """Level-2 global on/off for this destination.

        Whether this destination is active at all, independent of any per-run
        selection. Default True. A plugin overrides this to read its own config
        (e.g. an env var), so a destination can be globally disabled during
        staged rollout. Level 2 has priority over the per-run --destinations
        filter: a disabled destination never runs, even if explicitly selected.
        """
        return True

    @abstractmethod
    def target_id(self, adr: AdrIR) -> str | None:
        """Resolve the destination address from frontmatter.

        Confluence: the page id. Static site: the file path. Returns None if no
        target is assigned (which typically means the ADR is a draft for this
        destination — see is_publishable).
        """

    @abstractmethod
    def is_publishable(self, adr: AdrIR) -> bool:
        """Per-destination draft gate.

        Confluence: True once the concept is in the destination's mapping. Static
        site: may be always True. An ADR can be publishable to one destination and
        withheld from another. This gate lives in the plugin, NOT in core detection.
        """

    def provision(self, adr: AdrIR) -> str | None:
        """Ensure a destination target exists for this ADR; return its id/handle.

        Called by the provisioning entrypoint (ADR-0007), typically triggered by
        a label. Idempotent: returns the existing target if already provisioned.
        Default is a no-op returning None, for destinations that need no explicit
        provisioning step (e.g. a static site that derives its path from the
        concept id). Confluence overrides this to create a page and record the
        concept -> page mapping.
        """
        return None

    @abstractmethod
    def render(self, adr: AdrIR) -> RenderedArtifact:
        """Render the IR into this destination's native format."""

    @abstractmethod
    def sync(self, rendered: RenderedArtifact, target_id: str) -> SyncResult:
        """Write to the destination. The plugin chooses its write strategy
        (section-incremental for Confluence, full write for a static site)."""

    @abstractmethod
    def render_navigation(self, bundle_tree: BundleNode) -> RenderedArtifact:
        """Render destination-native navigation from the bundle tree.

        Confluence: a parent/landing page. Static site: a nav config file.
        Fed by the bundle tree in the IR (ADR-0004 correction to ADR-0003).
        """