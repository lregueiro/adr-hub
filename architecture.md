# Architecture Overview

Visual overview of the ABC Inc ADR knowledge system, from the widest
(C4 container) view down to the detailed component integrations and runtime
flows. Diagrams are standard Mermaid and render in GitHub, in Confluence (via a
Mermaid macro), and on static docs sites.

Traceability: the structures below implement the decisions recorded in
[ADR-0001](cross-boundary/ADR-CorePlatform-0001.md) (three-layer model),
[ADR-0002](cross-boundary/ADR-CorePlatform-0002.md) (hub repo),
[ADR-0003](cross-boundary/ADR-CorePlatform-0003.md) (sync pipeline), and
[ADR-0004](cross-boundary/ADR-CorePlatform-0004.md) (plugin architecture).

---

## 1. C4 Container Overview

The whole system: producers author into the OKF bundle (the source of truth),
which feeds both the Copilot Spaces query layer and the sync pipeline. The
pipeline mirrors to Confluence for non-GitHub stakeholders. The static docs site
is a future plugin (dashed).

```mermaid
graph TB
    subgraph people[" "]
        eng["👤 Engineer / Architect<br/><i>authors ADRs</i>"]
        agent["🤖 Enrichment Agent<br/><i>drafts ADRs, opens PRs</i>"]
        stakeholder["👤 Non-GitHub Stakeholder<br/><i>reads + comments</i>"]
        ghuser["👤 GitHub-native Contributor<br/><i>queries decisions</i>"]
    end

    subgraph system["ADR Knowledge System"]
        hub[("📚 core-platform-adr-hub<br/><b>OKF Bundle — Source of Truth</b><br/>markdown + YAML frontmatter")]
        spaces["🔍 GitHub Copilot Spaces<br/><b>Query Layer</b><br/>AI aggregation, no self-hosted docs"]
        pipeline["⚙️ Sync Pipeline<br/><b>GitHub Actions</b><br/>core + destination plugins"]
    end

    subgraph external["External Destinations"]
        confluence["📄 Confluence Cloud<br/><b>Stakeholder Mirror</b><br/>DSP space"]
        docsite["🌐 Static Docs Site<br/><i>future plugin</i>"]
    end

    eng -->|"PR"| hub
    agent -->|"PR (human-reviewed)"| hub
    hub -->|"indexed by"| spaces
    ghuser -->|"conversational query"| spaces
    hub -->|"push triggers"| pipeline
    pipeline -->|"one-way sync"| confluence
    pipeline -.->|"one-way sync (future)"| docsite
    stakeholder -->|"reads"| confluence
    stakeholder -->|"comments"| confluence

    classDef sot fill:#1f6feb,stroke:#0d1117,color:#fff,stroke-width:2px
    classDef query fill:#8250df,stroke:#0d1117,color:#fff,stroke-width:2px
    classDef pipe fill:#1a7f37,stroke:#0d1117,color:#fff,stroke-width:2px
    classDef dest fill:#9a6700,stroke:#0d1117,color:#fff,stroke-width:2px
    classDef future fill:#6e7781,stroke:#0d1117,color:#fff,stroke-width:1px,stroke-dasharray: 4 3
    class hub sot
    class spaces query
    class pipeline pipe
    class confluence dest
    class docsite future
```

---

## 2. C4 Component — Sync Pipeline Internals

Inside the pipeline: the core/plugin boundary from ADR-0004. Everything on the
core (green) side is destination-agnostic and produces the IR; plugins consume
the IR. Nothing destination-specific crosses back into core.

```mermaid
graph TB
    trigger["📥 Push to main<br/><i>GitHub Actions trigger</i>"]

    subgraph core["Pipeline Core — destination-agnostic"]
        detect["🔎 Detection<br/>core.detect_changed_adrs()<br/><i>git diff + OKF filter</i>"]
        parse["📋 OKF Parser<br/>parse_adr() + _parse_sections()<br/><i>frontmatter + hashed sections</i>"]
        tree["🌳 Bundle Tree Builder<br/>build_bundle_tree()"]
    end

    ir{{"📦 AdrIR<br/><b>Intermediate Representation</b><br/>frontmatter · sections[name,md,hash] · bundle_tree<br/><i>markdown-native · the stable contract</i>"}}

    subgraph plugins["Destination Plugins"]
        confluence["📄 ConfluencePlugin<br/>render → storage format + Info Panel<br/>sync → section-incremental writes<br/>render_navigation → parent page"]
        docsite["🌐 DocsSitePlugin<br/><i>future — proves the IR</i><br/>render → markdown passthrough<br/>sync → full write"]
    end

    entry["🎯 sync.run()<br/><i>wires core → plugins</i>"]
    telemetry["📊 Telemetry<br/><i>Actions run history only<br/>never writes back to repo</i>"]

    trigger --> detect
    detect --> parse
    parse --> ir
    tree --> ir
    ir --> entry
    entry -->|"is_publishable? render → sync"| confluence
    entry -.->|"future"| docsite
    confluence --> telemetry
    docsite -.-> telemetry

    classDef coreCls fill:#1a7f37,stroke:#0d1117,color:#fff,stroke-width:2px
    classDef irCls fill:#1f6feb,stroke:#0d1117,color:#fff,stroke-width:3px
    classDef pluginCls fill:#8250df,stroke:#0d1117,color:#fff,stroke-width:2px
    classDef futureCls fill:#6e7781,stroke:#0d1117,color:#fff,stroke-width:1px,stroke-dasharray: 4 3
    classDef ioCls fill:#9a6700,stroke:#0d1117,color:#fff,stroke-width:2px
    class detect,parse,tree coreCls
    class ir irCls
    class confluence pluginCls
    class docsite futureCls
    class trigger,entry,telemetry ioCls
```

---

## 3. Sync Flow — Detection to Write

Per-ADR runtime interaction between core, the IR, and a plugin. Note the
`is_publishable` gate and the section hash-compare that yields either a
section-level write or a no-op that keeps Confluence comments safe.

```mermaid
sequenceDiagram
    autonumber
    participant GA as GitHub Actions
    participant Core as Pipeline Core
    participant IR as AdrIR
    participant Plugin as ConfluencePlugin
    participant Conf as Confluence Cloud

    GA->>Core: run(bundle_root, base_ref, HEAD)
    Core->>Core: git diff base..HEAD → changed .md
    Core->>Core: filter type == "ADR", drop index/log.md
    Core->>Core: parse frontmatter + hash sections
    Core->>IR: build AdrIR (frontmatter, sections, bundle_tree)
    Core-->>GA: [AdrIR, ...]

    loop for each AdrIR
        GA->>Plugin: is_publishable(adr)?
        alt confluence_page_id is set
            Plugin-->>GA: true
            GA->>Plugin: render(adr)
            Plugin->>IR: read frontmatter + sections
            Plugin->>Plugin: Info Panel + section→anchor storage format
            Plugin-->>GA: RenderedArtifact
            GA->>Plugin: sync(rendered, page_id)
            Plugin->>Conf: GET page (current body + version)
            Conf-->>Plugin: existing sections
            Plugin->>Plugin: hash-compare per section
            alt some sections changed
                Plugin->>Conf: PUT only changed anchors (version+1)
                Conf-->>Plugin: 200 OK
                Plugin-->>GA: SyncResult(updated)
            else nothing changed
                Plugin-->>GA: SyncResult(skipped) — comments safe
            end
        else no page_id (draft)
            Plugin-->>GA: false
            GA->>GA: SyncResult(withheld)
        end
    end

    GA->>Plugin: render_navigation(bundle_tree)
    Plugin-->>GA: parent page artifact
    GA->>GA: log telemetry (run history only)
```

---

## 4. Detection & Draft-Gate Flow

The decision tree for what gets synced. The OKF filters live in core; the draft
gate lives in the plugin (ADR-0004) — visually downstream of core.

```mermaid
flowchart TD
    start(["Push to main"]) --> diff["git diff base..HEAD"]
    diff --> loop{"for each<br/>changed .md"}

    loop --> exists{"file exists?<br/>(not deleted)"}
    exists -->|no| skip1["skip<br/><i>deletion = future work</i>"]
    exists -->|yes| reserved{"reserved name?<br/>index.md / log.md"}
    reserved -->|yes| skip2["skip<br/><i>not an ADR concept</i>"]
    reserved -->|no| istype{"frontmatter<br/>type == ADR?"}
    istype -->|no| skip3["skip<br/><i>other OKF concept</i>"]
    istype -->|yes| buildir["build AdrIR<br/><i>parse + hash sections</i>"]

    buildir --> perplugin{"for each<br/>plugin"}
    perplugin --> gate{"plugin.is_publishable?<br/><i>per-destination gate</i>"}

    gate -->|"no target /<br/>draft"| withheld["WITHHELD<br/><i>gate lives in plugin,<br/>NOT core — ADR-0004</i>"]
    gate -->|"target set"| render["render → sync"]
    render --> hashcmp{"any section<br/>content changed?"}
    hashcmp -->|no| skipped["SKIPPED<br/><i>no write, comments safe</i>"]
    hashcmp -->|yes| updated["UPDATED<br/><i>write changed anchors only</i>"]

    withheld --> tel["telemetry →<br/>run history"]
    skipped --> tel
    updated --> tel

    classDef skipCls fill:#6e7781,stroke:#0d1117,color:#fff
    classDef goodCls fill:#1a7f37,stroke:#0d1117,color:#fff
    classDef gateCls fill:#8250df,stroke:#0d1117,color:#fff
    classDef writeCls fill:#1f6feb,stroke:#0d1117,color:#fff
    class skip1,skip2,skip3,withheld,skipped skipCls
    class buildir goodCls
    class gate,perplugin gateCls
    class updated,render writeCls
```

---

## 5. End-to-End Knowledge Flow

Producers to consumers, with the one-way boundary made explicit: stakeholder
comments live in Confluence and deliberately do not flow back (a recorded
tradeoff of one-way sync).

```mermaid
flowchart LR
    subgraph produce["✍️ Produce"]
        human["👤 Engineer"]
        bot["🤖 Enrichment Agent"]
    end

    pr{{"Pull Request<br/><i>human review gate</i>"}}

    subgraph truth["📚 Source of Truth"]
        hub["core-platform-adr-hub<br/><b>OKF Bundle</b>"]
        idx["index.md<br/><i>bundle tree</i>"]
    end

    subgraph consume["📖 Consume"]
        direction TB
        spaces["🔍 Copilot Spaces<br/><i>AI query — GitHub users</i>"]
        pipe["⚙️ Sync Pipeline"]
        conf["📄 Confluence<br/><i>read — stakeholders</i>"]
        comments["💬 Stakeholder<br/>comments"]
    end

    human --> pr
    bot --> pr
    pr -->|"merge"| hub
    hub --- idx
    hub -->|"indexed"| spaces
    hub -->|"push triggers"| pipe
    pipe -->|"one-way<br/>enriched mirror"| conf
    conf -.->|"comments preserved<br/>across syncs"| comments
    comments -.->|"stay in Confluence<br/><i>one-way: don't flow back</i>"| conf

    classDef prod fill:#9a6700,stroke:#0d1117,color:#fff,stroke-width:2px
    classDef sot fill:#1f6feb,stroke:#0d1117,color:#fff,stroke-width:2px
    classDef cons fill:#8250df,stroke:#0d1117,color:#fff,stroke-width:2px
    classDef gate fill:#1a7f37,stroke:#0d1117,color:#fff,stroke-width:2px
    class human,bot prod
    class hub,idx sot
    class spaces,conf,comments cons
    class pipe,pr gate
```
