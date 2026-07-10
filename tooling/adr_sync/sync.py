"""
Sync entrypoint — wires pipeline core to destination plugins.

Flow (ADR-0003 + ADR-0004):
  1. core.detect_changed_adrs()  -> IR for every changed ADR (destination-agnostic)
  2. for each plugin, for each ADR:
       - plugin.is_publishable()?  (per-destination draft gate, ADR-0004)
       - plugin.render() -> plugin.sync()
  3. plugin.render_navigation() once per plugin from the bundle tree
  4. log every SyncResult to stdout (Actions run history only; ADR-0003 #6 —
     the pipeline is a consumer and never writes back to the repo).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import core
from .ir import SyncResult
from .registry import build_plugins, resolve_destinations


def run(bundle_root: Path, base_ref: str, head_ref: str, dry_run: bool,
        only: set[str] | None = None) -> list[SyncResult]:
    adrs = core.detect_changed_adrs(bundle_root, base_ref, head_ref)
    plugins = build_plugins(dry_run, only=only)
    results: list[SyncResult] = []

    # Explain any requested destination that will not run (disabled/unknown).
    _, skipped = resolve_destinations(only)
    for name, reason in sorted(skipped.items()):
        if reason == "disabled":
            results.append(SyncResult(name, "(destination)", "skipped", "globally disabled"))
        elif reason == "unknown":
            results.append(SyncResult(name, "(destination)", "skipped", "not a registered destination"))

    if not adrs:
        print("No changed ADR concepts detected.")

    for plugin in plugins:
        pname = plugin.name()
        for adr in adrs:
            if not plugin.is_publishable(adr):
                results.append(SyncResult(pname, adr.concept_id, "withheld",
                                          "no target assigned / draft for this destination"))
                continue
            target = plugin.target_id(adr)
            rendered = plugin.render(adr)
            result = plugin.sync(rendered, target)
            # carry the concept id through for telemetry
            results.append(SyncResult(pname, adr.concept_id, result.action, result.detail))

        # Navigation once per plugin, from the shared bundle tree.
        tree = adrs[0].bundle_tree if adrs else core.build_bundle_tree(bundle_root)
        nav = plugin.render_navigation(tree)
        results.append(SyncResult(pname, "(navigation)", "rendered",
                                  f"kind={nav.metadata.get('kind')}"))

    return results


def main() -> int:
    ap = argparse.ArgumentParser(description="OKF ADR -> destinations sync")
    ap.add_argument("--bundle-root", default=".", type=Path)
    ap.add_argument("--base-ref", required=True, help="git ref to diff against (e.g. HEAD~1)")
    ap.add_argument("--head-ref", default="HEAD")
    ap.add_argument("--dry-run", action="store_true", default=False)
    ap.add_argument("--destinations", default="",
                    help="comma-separated destinations to run (level 1). "
                         "Empty => all enabled. Globally-disabled destinations "
                         "(level 2) never run regardless.")
    args = ap.parse_args()

    only = {d.strip() for d in args.destinations.split(",") if d.strip()} or None
    results = run(args.bundle_root, args.base_ref, args.head_ref, args.dry_run, only=only)

    print("\n=== SYNC TELEMETRY (Actions run history only) ===")
    for r in results:
        print(f"[{r.plugin}] {r.action.upper():9} {r.concept_id}  {r.detail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())