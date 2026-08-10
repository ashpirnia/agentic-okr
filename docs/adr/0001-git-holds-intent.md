# ADR-0001 — Git holds intent, the Shepherd's store holds observation

**Status:** Accepted — amended twice on 2026-08-07, see Amendments
**Date:** 2026-08-07
**Deciders:** Ash, Claude

## Context

`agentic-okr` stores an organisation's OKRs as YAML in a git repository. That choice buys versioning, pull requests for goal changes, diffs showing how the graph evolved, and a format anyone can read without our tooling. It is also the project's most quotable idea, so it is worth being precise about its limits.

The limit is this: an OKR system has two write paths, and they behave nothing alike.

**Intent** is what a human meant. Objectives, key results, success criteria, guardrail metric *definitions*, anti-targets, restraint clauses, ownership, links. Low-volume — an objective might be edited a handful of times a quarter. Deliberate — written by a person who thought about it. It benefits from review, because a change to what you meant is exactly the kind of change another human should see before it takes effect.

**Observation** is what happened. Current key result values, KPI readings, the Shepherd's time series, drift alerts. High-volume — a fleet under continuous watch produces readings constantly. Machine-written. Nobody reviews a metric reading; there is nothing to approve.

Put observation in git and the commit log is destroyed inside a quarter. Ten thousand automated commits saying `reopen_rate: 0.081 → 0.082` bury the one commit that says a human added a guardrail because agents found a way to game the goal. The property that made git worth choosing — that the history is a legible record of what the organisation decided — is the first thing lost. Diffs stop being reviewable, blame stops being useful, and the repo becomes a time-series database with terrible query performance.

An earlier draft of this decision said the database "belongs to the adopting org." That framing is wrong and would have been damaging. It reads as a prerequisite — provision Postgres before this works — for a tool whose entire v1 needs no database at all. It is also the wrong locus of ownership.

## Decision

**Intent lives in git. Observation lives in a store owned by the Shepherd.**

What goes in the OKR repo, versioned and reviewed:

- Objectives, key results, success criteria
- Guardrail metric *definitions* — name, definition, direction, threshold, measurement window
- Anti-targets and restraint clauses
- Ownership and links

What never goes in the OKR repo:

- Current key result values and progress percentages
- KPI readings and the Shepherd's time series
- Drift alerts and their resolution state
- Anything a machine writes on a schedule
- Which agents serve a key result, and how a key result is measured — both are Conductor-owned (see Amendments)

**The test:** if a field would be written by a machine on a schedule, it is observation and it does not belong in the schema. No exceptions for "just a small number." A single `current_value` field is how this erodes.

**The Shepherd owns the store.** Its schema, migrations, retention policy and API are the Shepherd's implementation, not the user's responsibility. It ships with bundled SQLite so the default experience requires no provisioning. An organisation running a fleet at scale may point it at their own infrastructure for backup and retention reasons, but *hosting* it is an option they take, not a prerequisite they satisfy. Ownership and hosting are separate questions and this ADR separates them deliberately.

**The store is not a system of record.** Raw KPIs already live in the organisation's source systems — Zendesk, Datadog, the warehouse. The Shepherd keeps its own readings and drift history, which is derived data. We are not asking anyone to build a data warehouse, and no part of this architecture should imply that.

**No store is built in v1.** This ADR reserves the boundary; it does not commission the thing on the far side of it. The Champion reads YAML and writes YAML. The Conductor's lint is static — it compares agent definitions against the spec and needs no readings. Only the Shepherd touches the store, and the Shepherd is phases away.

## Consequences

**The OKR repo stays reviewable.** Its commit log remains what it should be: a legible record of every change to what the organisation meant, each one attributable and each one reviewed. This is the property the whole "OKRs as code" claim rests on.

**A guardrail discovered in production arrives as a pull request**, with the drift evidence attached, and a human merges it. That is the loop from piece 3 made concrete, and it only works because the repo is quiet enough for such a PR to be visible.

**v1 has no persistence and no configuration.** `okr validate` runs against a directory. Nothing to install, nothing to connect. This is a real adoption advantage and it falls out of the boundary rather than being designed for.

**We cannot answer "how is this KR tracking?" from the repo alone**, which is the cost we are accepting. Anyone wanting progress must query the Shepherd's store, and until the Shepherd exists, nobody can. For v1 that is correct: the Champion's job is specification, not tracking, and conflating the two is what produces OKR tools that are really status dashboards.

**Every future schema proposal must pass the machine-written test.** Expect pressure — a `current_value` field looks harmless and would be requested within a week of anyone using this. Refusing it consistently is what keeps the boundary real.

**Joining intent to observation becomes a Shepherd design problem**, one we have deferred rather than solved. The join key is the guardrail metric's identity in the spec, which means metric naming is load-bearing in a way that is not obvious yet. ADR-0008 (guardrail metrics and anti-targets) must not choose a naming scheme that makes this join awkward.

## Alternatives rejected

**Everything in git, including progress.** Simplest possible story, one artefact, one tool, and the "OKRs as code" claim becomes maximally pure. Rejected because it destroys the commit log within a quarter. The purity is exactly what breaks it: git's value is a reviewable history, and a history nobody can read is worse than no history. This is the alternative most likely to be proposed by someone who likes the idea, which is why it is written down here.

**Everything in a database, git optional.** The conventional OKR-tool architecture, and it works — for OKR tools. Rejected because it discards the properties that motivated the project: PRs for goal changes, diffs of how the graph evolved, and a format an organisation owns without depending on us. Without those, this is another OKR SaaS with an agent bolted on.

**Git with progress in separate, gitignored files.** Keeps the two write paths in one directory while sparing the commit log. Rejected because it produces a repo whose working tree does not match its history, breaks the "clone it and you have the whole thing" property, and puts the most operationally sensitive data in the place least likely to be backed up. It also invites exactly the confusion this ADR is trying to prevent.

**The adopting organisation provides the database.** The framing this ADR corrects. Rejected because it converts a phase-3 implementation detail into a day-one adoption prerequisite, and because it misplaces ownership: the schema and lifecycle of the store are the Shepherd's concern, not the user's. Orgs may host it; they should never have to design it.

**Defer the boundary entirely and decide when the Shepherd is built.** Tempting, since nothing in v1 needs a store. Rejected because the schema is being designed now, and a schema designed without this boundary will absorb observation fields by default — they always look reasonable one at a time. The boundary is cheap to state today and expensive to retrofit once files exist in the wild.

## Amendments

### Amendment 1 · 2026-08-07 — A third category: measurement configuration

This ADR originally described two categories, intent and observation, and implied they were exhaustive. They are not. Clarifying the three roles' responsibilities surfaced a third:

**Measurement configuration** — where a key result's current value is obtained. An MCP connection: an API call, a file read, a database query, or a Slack message to a human asking for an update.

It is not intent: nobody *meant* anything by choosing a Zendesk endpoint. It is not observation: no machine writes it on a schedule; a person configures it once and it stays put. It fails both tests and belongs in neither store.

**It is owned by the Conductor, keyed by key result.** The Conductor is the registry of connections — agents, agent-to-goal wiring, and now KR-to-measurement-source. The agent developer supplies it at registration, which is the natural moment, but the record attaches to the key result rather than to the agent. Attaching it to the agent would mean a key result loses its measurement when an agent is deregistered, that two agents serving one goal can carry configs that disagree, and that a human-owned key result cannot be measured at all. That last consequence is disqualifying: piece 1's premise is that OKRs govern human and agent work alike, and measurement that exists only where agents exist can only ever see half the organisation.

**It stays out of the OKR repo.** Connection configuration carries endpoints and credential references. The OKR repo is reviewed by goal owners — support leads and heads of product — and putting infrastructure plumbing in the file they read to understand what a goal means is how that file stops being readable by them.

The three-way boundary is therefore:

| Category | Example | Owner | Written by |
| :--- | :--- | :--- | :--- |
| Intent | "Reopen rate must not exceed 8%" | Champion (git) | A human, deliberately |
| Measurement config | "Reopen rate comes from Zendesk API X" | Conductor | A developer, at registration |
| Observation | "Reopen rate was 8.1% on Tuesday" | Shepherd (its store) | A machine, on a schedule |

The guardrail metric's identity is the join key across all three. The guardrail-metrics ADR must choose a naming scheme that makes a three-way join natural, not just the two-way join noted in the original Consequences.

### Amendment 2 · 2026-08-07 — SQLite reconsidered, and the decision reaffirmed

The original Alternatives section rejected "everything in a database" while describing a *server* database — provisioning, a host, credentials. That was arguing against Postgres. **SQLite has none of those costs**, and rejecting it by association was unfair. It deserves a real hearing, recorded here so that it is a considered alternative rather than an unexamined assumption.

**What SQLite genuinely wins.** A substantial part of the Phase 1 plan simply disappears: foreign keys make dangling references impossible; `UNIQUE` constraints make duplicate IDs impossible; the `okr.yaml` marker becomes unnecessary because the database file is itself the marker; the loader shrinks to a query; migration becomes a solved problem with known tooling, applied to one file rather than to files scattered across adopters' repositories. Graph questions become `SELECT`s rather than traversal code we write, test and maintain. This is not a marginal saving.

**What it cannot do.** A `.db` file is binary. `git diff` shows nothing, no pull request can be reviewed, and `git blame` on a guardrail is impossible.

That is not one lost feature among several. It is the mechanism the series argues for. Piece 3's conclusion is a discovered gaming trick becoming specification: *"A human merges it, and the trick is on the page."* In SQLite there is no page — there is a row, and nobody reviews a row without an interface. Choosing SQLite therefore forces a web UI, reversing [ADR-0003](0003-v1-scope.md)'s cut and placing the project in a category with Viva Goals, Lattice and Perdoo, competing on features rather than on the one property that is actually different.

A second, more practical objection: six teams authoring in the same week is clean parallel work across separate YAML files, and an unresolvable binary merge conflict in a single database file.

**The objection that nearly carried it, and why it does not.** The strongest case against YAML is not technical: goal owners are heads of support and product, not engineers, and neither git nor YAML is a reasonable interface for them. That is true.

But it argues for a *surface*, not for SQLite — because **the UX problem is identical under both**. A support lead cannot edit a `.db` file either. Both options require a conversation, a form, or some other surface between the human and the store. What differs is only what survives once that surface exists: with git, review, diffs, blame and an organisation owning its goals in a format outliving this tool; with SQLite, queries and referential integrity.

UX is therefore neutral between the two, and the decision turns on what is retained rather than on who can read the file. It is also a well-trodden pattern — Netlify CMS, TinaCMS and Contentful's git sync all put a form in front of a git-backed store, and editors in those systems never see the underlying files.

**What this exchange did change.** ADR-0003 justified cutting the web UI as "CLI and YAML is more credible for this audience." That reasoned about the *article's* readers, technical leaders, and not the *tool's* users, who are goal owners. Those are different people and the justification conflated them. The consequence is real and now stated plainly rather than implied: **v1 has no adoption path for a non-technical goal owner.** The intended surface is the conversational Champion, and the interactive interview loop is cut from v1.

**The hybrid, for the record.** YAML remains the source of truth while SQLite becomes a *derived* index the loader builds — gitignored and rebuilt on demand. This keeps review and gains queries. It buys nothing at the scale v1 operates at, where the graph fits comfortably in memory, but it is the shape of the answer if querying ever matters, and it means choosing YAML now forecloses nothing.
