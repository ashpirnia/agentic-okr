# ADR-0003 — v1 scope and deliberate cuts

**Status:** Accepted
**Date:** 2026-08-07
**Deciders:** Ash, Claude

## Context

This project has an architecture with three roles, an article series describing all three, and one developer. The gap between what is described and what can be built is large enough that without a written scope, every session will relitigate it — and the relitigation will always trend toward building more, because each individual addition looks small and defensible.

There is a second pressure. The v1 deliverable is not just software; it is evidence for a fourth article, *Building the OKR Champion*. That gives the scope a natural boundary — **v1 is what must exist for the article to be honest** — and a natural failure mode, which is building things that demo well but that nobody would run.

The constraint that matters most: the schema is a published contract. ADR-0002 established that files conforming to it will live in other people's repositories. Anything shipped in v1 is expensive to change. Anything cut is cheap to add. This asymmetry should decide every marginal case.

## Decision

**v1 is the Champion's specification half: a schema, a loader, a validator, a completeness score, and a batch-critique facilitation agent. Nothing else.**

### In scope

- The OKR schema and its `okr.yaml` repo marker
- The loader and graph builder, including referential integrity validation
- `okr init`, `okr validate`, `okr score`, `okr graph`
- A batch-critique facilitation agent (LangGraph, Sonnet) that annotates a submitted OKR set
- A hand-written reference example set, and a demo dataset in its own repo
- `docs/EVENTS.md` — definitions only

### Cut, with the reason

**No web UI.** A CLI and a directory of YAML. A UI is where a project like this quietly becomes an OKR tool instead of an argument about goal specification.

*Corrected 2026-08-07:* this cut originally read "for this audience a terminal and a PR diff are more credible than a dashboard." That reasoned about the **article's** readers — technical leaders — not the **tool's** users, who are goal owners: heads of support, heads of product. Those are different people, and neither git nor YAML is a reasonable interface for the second group. The cut stands, but on the honest ground that v1 is a demonstration rather than a product, and with its consequence stated: **v1 has no adoption path for a non-technical goal owner.** The intended surface is the conversational Champion, whose interview loop is also cut from v1. See [ADR-0001](0001-git-holds-intent.md) Amendment 2.

**No observation store, and no progress tracking.** Per ADR-0001, v1 has no Shepherd and therefore nothing that reads or writes metric values. `okr validate` runs against a directory with nothing to install or connect. *Note:* the Champion's LangGraph checkpointing uses SQLite, which is agent-run persistence, not an observation store. The cut is about tracking KR progress, not about all persistence.

**No Conductor and no Shepherd.** They exist as event definitions with named triggers and consumers. This is the cut that most needs to be visible rather than silent: the point is to show the loop is designed, not to imply it is built.

**No multi-cycle support.** One repo holds one live goal graph. Last quarter's OKRs are a previous commit; rolling over is a pull request. Objectives carry no cycle field and no identity across cycles.

**No integrations.** No connectors to Viva Goals, Lattice, Workday or Jira. An organisation that wants its OKRs here writes YAML.

**No multi-tenancy, no access control, no ownership enforcement.** Git already provides authorship, review and permissions. Re-implementing them inside the tool would duplicate what the host platform does better.

**No interactive interview loop.** v1 ships batch critique only: the agent reads a submitted OKR set and annotates it with questions, gaps and proposed anti-targets, and a human answers in their own time. The live interview is the more faithful expression of facilitation and it is deferred deliberately, not abandoned.

**No cross-repo references.** Per ADR-0002, one repo is one graph.

**No registry lifecycle management.** The Champion in the articles is a living registry; v1 is only its authoring half. No cycle rollover, no archiving workflow, no staleness detection.

## Consequences

**The schema stays thin, because there is nothing to make it fat for.** Most speculative fields exist to serve a component that does not exist. With the Conductor and Shepherd explicitly out, the answer to "the Conductor will need this" is that the Conductor is not in v1 and the field can be added when it is.

**ADR-0006 gets substantially simpler.** No cycle in the ID, no carried-forward identity, no question of what makes a Q3 objective the same as its Q2 version. That last one is a genuinely hard modelling problem and cutting it removes the largest source of schema risk in Phase 1.

**Phase 3's evidence changes shape.** With batch critique only, the article's artefacts are annotated specs and the owner's written responses, not live dialogue transcripts. This is less vivid on the page. It still carries the claim that matters — the agent surfaced an anti-target the owner had not written down — and the annotation is arguably better evidence than a transcript, because a reader can see the before and after side by side rather than taking a conversation on trust.

**Batch is a subset of interactive, so nothing is wasted.** The gap analyser, anti-target generator and spec writer are the same nodes in both modes. Adding the interview loop later means adding LangGraph interrupts around existing nodes, not rebuilding them. Had the sequencing gone the other way, the batch mode would have been a stripped-down afterthought.

**Some readers will find v1 underwhelming relative to the articles.** Three roles described, one third of one role built. The README's status section must be honest about this rather than implying more exists. Overclaiming here would undercut the series, which spends its credibility on being straight about what is hard.

**The cuts are dated, not permanent.** Each has a reason attached. When one is revisited, the question is whether the reason still holds — not whether the feature seems useful, which it always will.

## Alternatives rejected

**Build all three roles thinly.** A skeletal Champion, Conductor and Shepherd, so the loop runs end to end and the architecture is demonstrable rather than described. Genuinely tempting: the loop closing is the series' whole thesis, and a working loop would be the strongest possible artefact. Rejected because a thin Shepherd needs live metrics and a thin Conductor needs a real agent registry, so both require infrastructure and integrations that v1 explicitly cuts — and three shallow components would produce a demo that impresses nobody who tries to use it. The Champion is the only role demonstrable standalone, which is why it is first.

**Interactive facilitation first.** Truer to the vision, and the more compelling artefact. Rejected on evidence quality rather than effort: a transcript is hard to present honestly when the same person authored the naive OKR and played the owner being interviewed. Batch critique produces a before-and-after a reader can inspect directly. The vividness gap is real; the credibility gain is worth more.

**Multi-cycle support from the start.** Real organisations run quarterly and will hit this immediately. Rejected because identity-over-time is a hard modelling problem — what makes an objective "the same" across cycles is a question with several defensible answers — and getting it wrong means a migration for every adopter. Git history covers the actual need for v1: you can see what last quarter said by checking out last quarter's commit.

**Ship the schema without the facilitation agent.** Just the format, loader and validator — smaller, faster, and the schema is the part the other two roles depend on. Rejected because the schema alone cannot be evaluated. The test of whether a field earns its place is whether the Champion can elicit it from a human, and without the agent that test cannot be run. The article would also have no evidence: a schema is not a demonstration.

**Leave the Conductor and Shepherd entirely undocumented.** Cleanest possible v1, no speculation at all. Rejected because the loop is the architecture's actual claim, and a repo that shows only the Champion invites the reading that this is a linting tool for YAML goals. Event definitions with named triggers and consumers cost little and make the design legible without implying implementation.
