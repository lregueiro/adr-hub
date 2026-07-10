"""
Plugin registry — the single place destinations are registered.

Both entrypoints (sync.py, provision.py) build their plugin list from here, so
neither hardcodes a specific destination. Adding a destination is a one-line
change here plus the plugin module — no entrypoint touches required (ADR-0004).
"""

from __future__ import annotations

from .ir import DestinationPlugin
from .plugins.confluence import ConfluencePlugin

# Register destination plugin classes here. To add a destination (e.g. a static
# docs site), implement DestinationPlugin in plugins/ and add its class below.
_PLUGIN_CLASSES = [
    ConfluencePlugin,
    # DocsSitePlugin,   # future (ADR-0004)
]


def build_plugins(dry_run: bool) -> list[DestinationPlugin]:
    """Instantiate all registered destination plugins."""
    return [cls(dry_run=dry_run) for cls in _PLUGIN_CLASSES]