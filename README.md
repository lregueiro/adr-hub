# ABC Inc ADR Hub

Canonical home for ABC Inc architectural decisions, authored as an
[OKF](https://en.wikipedia.org/wiki/Knowledge_representation) knowledge bundle:
markdown files with YAML frontmatter, version-controlled and PR-reviewed.

## The three-layer model (ADR-0001)

- **Source of truth** — this repository.
- **Query layer** — GitHub Copilot Spaces indexes this repo for AI-powered,
  conversational discovery (GitHub-native users).
- **Stakeholder mirror** — Confluence (DSP space), fed by a one-way sync
  pipeline, for non-GitHub stakeholders.

## Repository layout

| Path | Purpose |
|------|---------|
| `index.md`, `log.md` | OKF reserved files (bundle listing + history). |
| `cross-boundary/` | Cross-boundary ADR concepts (ADR-0002). |
| `ADR-TEMPLATE.md` | Authoring template. |
| `architecture.md` | C4 and flow diagrams. |
| `tooling/` | **Not part of the OKF bundle.** Phase-1 POC sync pipeline (ADR-0005). |
| `.github/workflows/` | The sync launcher. |

> **POC note (ADR-0005):** during the proof of concept the pipeline lives here
> under `tooling/`. When a second source repo needs syncing, the pipeline is
> extracted into its own repo/package and this directory is removed, restoring
> the repo to a pure OKF bundle. `tooling/` and `.github/` are marked in
> `.okfignore` as outside the bundle.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Every ADR uses [ADR-TEMPLATE.md](ADR-TEMPLATE.md)
and merges via PR with at least one reviewer per affected team.

## Running the sync pipeline (POC)

```bash
cd tooling
pip install -r requirements.txt
# dry run against the last commit:
python -m adr_sync.sync --bundle-root .. --base-ref HEAD~1 --head-ref HEAD --dry-run
```
