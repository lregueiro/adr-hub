"""
Plugin registry — the single place destinations are registered, plus the
two-level destination filtering both entrypoints share.

Filtering precedence (level 2 has priority over level 1):
  Level 2 — global enable/disable (plugin.is_enabled()): a destination that is
            globally disabled NEVER runs, even if explicitly selected.
  Level 1 — per-run selection (--destinations): choose among the ENABLED
            destinations for this invocation. Absent => all enabled destinations.

Adding a destination is a one-line change here plus the plugin module — no
entrypoint touches required (ADR-0004).
"""

from __future__ import annotations

from .ir import DestinationPlugin
from .plugins.confluence import ConfluencePlugin

_PLUGIN_CLASSES = [
    ConfluencePlugin,
    # DocsSitePlugin,   # future (ADR-0004)
]


def known_destinations() -> set[str]:
    """All registered destination names, regardless of enabled state."""
    return {cls().name() for cls in _PLUGIN_CLASSES}


def resolve_destinations(only: set[str] | None = None) -> tuple[set[str], dict[str, str]]:
    """Work out which destinations will run and why others won't.

    Returns (will_run, skipped) where:
      will_run  = names that pass both level 2 (enabled) and level 1 (selected)
      skipped   = {name: reason} for every requested-or-registered destination
                  that will NOT run, with reason in:
                    'disabled'   — globally off (level 2, priority)
                    'unknown'    — not a registered destination
                    'unselected' — enabled but not in the --destinations selection

    This lets callers (entrypoints/workflows) explain *why* nothing happened,
    e.g. "confluence skipped — globally disabled".
    """
    registered = {cls().name(): cls() for cls in _PLUGIN_CLASSES}
    skipped: dict[str, str] = {}

    # Unknown requested names (level 1 asked for something not registered).
    if only:
        for name in only:
            if name not in registered:
                skipped[name] = "unknown"

    will_run: set[str] = set()
    for name, plugin in registered.items():
        if not plugin.is_enabled():           # level 2 has priority
            skipped[name] = "disabled"
            continue
        if only is not None and name not in only:
            skipped[name] = "unselected"
            continue
        will_run.add(name)
    return will_run, skipped


def build_plugins(dry_run: bool, only: set[str] | None = None) -> list[DestinationPlugin]:
    """Instantiate destination plugins, applying level-2 then level-1 filters.

    Args:
        dry_run: passed to each plugin.
        only: level-1 per-run selection (plugin names). None => all enabled.

    Returns the plugins that are BOTH enabled (level 2) AND selected (level 1).
    """
    will_run, _ = resolve_destinations(only)
    return [cls(dry_run=dry_run) for cls in _PLUGIN_CLASSES if cls().name() in will_run]