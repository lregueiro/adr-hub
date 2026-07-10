"""
Provisioning entrypoint (ADR-0007). Destination-agnostic: builds plugins from the
registry and calls provision() on each. Confluence's provision() creates a page
and records the concept -> page mapping; a static-site plugin's provision() may be
a no-op. Neither this file nor sync.py names a specific destination (ADR-0004).

Provisioning creates targets and records mappings; it does NOT sync content — the
sync pipeline does that on merge.

Usage (from tooling/):
    python -m adr_sync.provision --bundle-root .. --paths cross-boundary/ADR-CorePlatform-0001.md
    python -m adr_sync.provision --bundle-root .. --all
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import core
from .registry import build_plugins, resolve_destinations


def _skip_lines(only) -> list[str]:
    """Explain any requested/registered destination that will NOT run."""
    _, skipped = resolve_destinations(only)
    reasons = {
        "disabled": "skipped — globally disabled",
        "unknown": "skipped — not a registered destination",
        "unselected": "skipped — not selected for this run",
    }
    # Only surface 'disabled' and 'unknown' as noteworthy; 'unselected' is
    # normal when a selection was given.
    return [f"[{name}] {reasons[reason]}"
            for name, reason in sorted(skipped.items())
            if reason in ("disabled", "unknown")]


def _adrs_for_paths(bundle_root: Path, paths: list[str]) -> list:
    tree = core.build_bundle_tree(bundle_root)
    out = []
    for rel in paths:
        p = bundle_root / rel
        if not p.exists():
            continue
        adr = core.parse_adr(bundle_root, p, tree)
        if adr is not None:
            out.append(adr)
    return out


def _all_adrs(bundle_root: Path) -> list:
    tree = core.build_bundle_tree(bundle_root)
    out = []
    for p in bundle_root.rglob("*.md"):
        if "tooling" in p.parts:
            continue
        adr = core.parse_adr(bundle_root, p, tree)
        if adr is not None:
            out.append(adr)
    return out


def run(bundle_root: Path, paths: list[str], provision_all: bool, dry_run: bool,
        only: set[str] | None = None) -> list[str]:
    adrs = _all_adrs(bundle_root) if provision_all else _adrs_for_paths(bundle_root, paths)
    lines: list[str] = []
    # Explain any requested destination that will not run (disabled/unknown).
    lines.extend(_skip_lines(only))
    if not adrs:
        lines.append("No ADRs to provision.")
        return lines

    plugins = build_plugins(dry_run, only=only)
    if not plugins and not any("skipped" in l for l in lines):
        lines.append("No active destinations for this run.")

    for plugin in plugins:
        pname = plugin.name()
        for adr in adrs:
            if dry_run:
                lines.append(f"[{pname}] DRY RUN would ensure target for {adr.concept_id}")
                continue
            target = plugin.provision(adr)
            if target is None:
                lines.append(f"[{pname}] no provisioning needed for {adr.concept_id}")
            else:
                lines.append(f"[{pname}] {adr.concept_id} -> {target}")
    return lines


def main() -> int:
    ap = argparse.ArgumentParser(description="Provision destination targets for ADRs (ADR-0007)")
    ap.add_argument("--bundle-root", default="..", type=Path)
    ap.add_argument("--paths", nargs="*", default=[], help="specific ADR paths (bundle-relative)")
    ap.add_argument("--all", action="store_true", help="provision every ADR in the bundle")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--destinations", default="",
                    help="comma-separated destinations to run (level 1). "
                         "Empty => all enabled. Globally-disabled destinations "
                         "(level 2) never run regardless.")
    args = ap.parse_args()

    only = {d.strip() for d in args.destinations.split(",") if d.strip()} or None
    lines = run(args.bundle_root, args.paths, args.all, args.dry_run, only=only)
    print("=== PROVISIONING (ADR-0007) ===")
    for line in lines:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())