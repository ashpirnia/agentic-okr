# Architecture

Three roles, three stores, one loop. Diagrams are Mermaid so they render on GitHub, diff in review, and stay in the repo alongside the decisions they illustrate.

**Read the legend.** Only a fraction of this is built. Solid means it exists in v1; dashed means it is designed and deliberately deferred by [ADR-0003](adr/0003-v1-scope.md).

---

## 1. Components and stores

```mermaid
flowchart TB
    subgraph humans [" "]
        direction LR
        GO["👤 Goal owners<br/><i>support leads, heads of product</i>"]
        AD["👤 Agent developers"]
        LD["👤 Leaders"]
    end

    subgraph champion ["CHAMPION — what you meant"]
        CH["Facilitation agent<br/><i>batch critique</i>"]
        VAL["Loader · graph · validator · score"]
    end

    subgraph conductor ["CONDUCTOR — how it is hooked up"]
        AR["Agent registry"]
        MS["Measurement sources<br/><i>keyed by key result</i>"]
        LINT["Wiring lint"]
    end

    subgraph shepherd ["SHEPHERD — what happened"]
        WATCH["Continuous watch"]
        UI["Query interface<br/><i>future</i>"]
    end

    OKRREPO[("OKR repo<br/><b>git · YAML</b><br/><i>owned by the organisation</i>")]
    CSTORE[("Conductor store<br/><i>not designed</i>")]
    SSTORE[("Shepherd store<br/><b>bundled SQLite</b><br/><i>optionally self-hosted</i>")]
    AGENTS["🤖 Deployed agent fleet"]
    SRC["Source systems<br/><i>Zendesk · Datadog · warehouse</i>"]

    GO <--> CH
    CH --> VAL
    VAL <--> OKRREPO
    GO -->|"PR review"| OKRREPO

    AD -.-> AR
    AR -.- CSTORE
    MS -.- CSTORE
    AR -.->|"registers"| AGENTS
    LINT -.->|"reads spec"| OKRREPO
    AR -.-> LINT

    LINT -.->|"lint.failed"| AD

    WATCH -.->|"reads via MCP"| SRC
    MS -.->|"where to read"| WATCH
    OKRREPO -.->|"thresholds"| WATCH
    WATCH -.- SSTORE
    AGENTS -.->|"produce"| SRC
    LD -.-> UI
    UI -.- SSTORE

    WATCH -.->|"guardrail.breached<br/><i>notification</i>"| GO
    WATCH -.->|"anti_target.discovered<br/><i>spec change</i>"| CH

    classDef built fill:#1a7f4b,stroke:#0d5c34,color:#fff
    classDef cut fill:#2b2b2b,stroke:#666,color:#bbb,stroke-dasharray:5 5
    classDef store fill:#1f3a5f,stroke:#14273f,color:#fff
    classDef storecut fill:#2b2b2b,stroke:#666,color:#bbb,stroke-dasharray:5 5
    classDef person fill:#4a3a6b,stroke:#2f2444,color:#fff

    class CH,VAL built
    class AR,MS,LINT,WATCH,UI cut
    class OKRREPO store
    class SSTORE,CSTORE,AGENTS,SRC storecut
    class GO,AD,LD person
```

**Legend:** green = built in v1 · dashed grey = designed, not built · blue = store.

Points worth reading off this diagram:

- **The OKR repo is the only store an organisation owns and sees.** The other two are implementation detail of the roles that own them. Nobody is asked to provision a database ([ADR-0001](adr/0001-git-holds-intent.md)).
- **The Shepherd needs two inputs from two different owners** — thresholds from the Champion's spec, and where-to-read from the Conductor's measurement sources. Either alone is useless, which makes their joint presence a lint the Conductor can run at wiring time.
- **Every spec change routes through the Champion, including the Shepherd's.** When the Shepherd discovers a new gaming move, it does not write to the OKR repo directly — it hands the finding to the Champion, which turns it into a well-formed guardrail and emits a validated PR a human merges. Bypassing the Champion would let unfacilitated, unvalidated spec into the graph, which is the one thing the Champion exists to prevent.
- **Notifications go direct; spec changes go through the Champion.** `guardrail.breached` tells a goal owner something is wrong and needs no facilitation. `anti_target.discovered` changes what the spec says and does.
- **`lint.failed` goes to the agent developer, not the goal owner.** A lint failure means an agent's target does not match the spec; the person who can fix it is the one who wired the agent.
- **v1 is the green box.** Three roles described in the series, one facilitation workflow and a validator built.

---

## 2. Who owns what

The distinction most easily got wrong, and the one this project got wrong twice before writing it down.

```mermaid
flowchart LR
    subgraph I ["INTENT — what you meant"]
        I1["Objectives · key results<br/>Success criteria<br/>Guardrail <i>definitions</i><br/>Anti-targets · restraints<br/>Ownership"]
        I2["<b>Champion</b> · git<br/>Written by a human, deliberately<br/>Reviewed in a PR"]
    end

    subgraph M ["MEASUREMENT CONFIG — how to find out"]
        M1["Agent registry<br/>Agent → key result wiring<br/>KR → MCP reading source"]
        M2["<b>Conductor</b><br/>Written by a developer,<br/>at registration"]
    end

    subgraph O ["OBSERVATION — what happened"]
        O1["Current KR values<br/>KPI readings · time series<br/>Drift alerts"]
        O2["<b>Shepherd</b> · its own store<br/>Written by a machine,<br/>on a schedule"]
    end

    I -.->|"metric identity<br/>is the join key"| M
    M -.->|"metric identity<br/>is the join key"| O

    classDef intent fill:#1a7f4b,stroke:#0d5c34,color:#fff
    classDef config fill:#8a5a1a,stroke:#5c3c11,color:#fff
    classDef obs fill:#1f3a5f,stroke:#14273f,color:#fff
    class I1,I2 intent
    class M1,M2 config
    class O1,O2 obs
```

**The test that decides where a field goes:** would a machine write it on a schedule? Then it is observation and it does not belong in the schema — no exceptions for "just a small number." Does it carry a connection detail or credential? Then it is measurement config and belongs to the Conductor, not in a repo goal owners review.

**A guardrail metric's identity is the join key across all three.** The naming scheme chosen by the guardrail-metrics ADR has to make that three-way join natural.

---

## 3. The loop

Piece 3's argument in one diagram: the bridge is a loop, not a beam. The numbered path is the ticket-resolution example carried all the way round.

```mermaid
sequenceDiagram
    autonumber
    actor Owner as 👤 Goal owner
    participant Ch as Champion
    participant Repo as OKR repo (git)
    actor Dev as 👤 Agent developer
    participant Co as Conductor
    participant Sh as Shepherd
    participant Fleet as 🤖 Agent fleet

    rect rgba(26,127,75,0.12)
    note over Owner,Repo: Built in v1
    Owner->>Ch: Submits draft "resolve tickets in under 4 hours"
    Ch->>Ch: Gap analysis · anti-target generation
    Ch-->>Owner: "What does resolved mean? What would game this?"
    Owner->>Ch: "Fixed, not deflected. Mass-closing would game it."
    Ch->>Repo: Emits validated spec — guardrails, restraints, anti-target
    Owner->>Repo: Reviews and merges the PR
    end

    rect rgba(120,120,120,0.10)
    note over Dev,Fleet: Designed, not built
    Repo--)Co: spec.published
    Co->>Co: Lint — agent target "status = closed"<br/>vs restraint clause
    Co--)Dev: lint.failed — wiring does not match intent
    Dev->>Co: Re-wires the agent to the guardrail
    Co--)Sh: measurement_source.registered — where to read reopen rate
    Repo--)Sh: watch_list.updated — thresholds
    Fleet->>Fleet: Runs. Resolution time drops.
    Sh->>Sh: Week 2 — reopen rate climbing
    Sh--)Owner: guardrail.breached (notification)
    Owner->>Owner: Investigates. Finds agents telling customers<br/>to open a fresh ticket, evading reopen rate.
    Sh--)Ch: anti_target.discovered
    Ch->>Repo: Turns the finding into a validated guardrail, opens a PR
    Owner->>Repo: Merges. The trick is now on the page.
    Repo--)Co: spec.published — re-lint the whole fleet
    end

    note over Owner,Fleet: The next fleet cannot use that trick
```

The property that matters: the loop does not assume the spec was right. It assumes it was incomplete, and converts each discovered gap into a line of specification the next fleet is checked against.

---

## What these diagrams do not show

- **The OKR graph's data model.** Whether a guardrail is a first-class node or an embedded field is decided by the Phase 1 schema ADRs. An ERD is a deliverable of that work, not an input to it.
- **The Conductor and Shepherd store schemas.** Both components are cut from v1; drawing their tables would present speculation as specification.
- **Anything about cycles or quarters.** v1 holds one live graph; history is git history ([ADR-0003](adr/0003-v1-scope.md)).
