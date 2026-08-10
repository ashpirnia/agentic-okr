# ADR-0006 — Edge semantics: hierarchy and dependency

**Status:** Accepted — amended 2026-08-07, see Amendments
**Date:** 2026-08-07
**Deciders:** Ash, Claude

## Context

[ADR-0005](0005-node-types.md) established which concepts are nodes. This one establishes what connects them, which is the decision that makes the result a graph rather than a tree.

Four requirements arrive from earlier work:

- Piece 1 distinguishes **cascading** (top-down) from **laddering** (bottom-up), and both must be expressible. A key result may support several parent objectives.
- Doerr's cascade turns a parent's *key result* into the child level's *objective*, so an edge must be able to target a key result.
- Doerr's **interlocking key results** — one team's key result committing to unblock another's — are a different relationship from goal hierarchy.
- Doerr warns that deep top-down cascading stifles agility. Measuring the cascade/ladder balance must not be foreclosed.

Getting the direction convention wrong is a repo-wide rename later, and getting the edge *types* wrong is worse than that.

## Decision

### Two edge types

**`supports`** — a child contributes to a parent. The hierarchy relation, covering both cascading and laddering.

**`depends_on`** — a key result cannot complete until another key result does. The delivery relation.

Cascading and laddering are **not** separate edge types. The relationship they produce is identical — a child contributes to a parent — and only the provenance differs. Encoding provenance as a type would conflate what is true with how we got here. Provenance is an optional `origin: cascaded | laddered` field on the edge.

### The direction convention

**Every edge is declared on the needy side. Nothing is ever declared on the parent or the provider.**

A child declares what it `supports`. A dependent declares what it `depends_on`.

### Acceptance is a pull request, not a field

There is no acknowledgement field, no `accepted: true`, no mutual declaration. The pull request that adds `depends_on: platform.api-v2` is reviewed by platform's owner, who merges or declines. A schema field would only duplicate what review already establishes — worse, it would let a spec claim agreement that no human ever gave.

**This requires review routing that git does not provide by default.** See Amendment 1: `CODEOWNERS` matches file paths, and a cross-team edge is a content change inside the *declaring* team's file. Without routing, the reviewer who must accept is never asked.

### Legal shapes

| Edge | From | To | |
| :--- | :--- | :--- | :--- |
| `supports` | Objective | Objective | Laddering between levels |
| `supports` | Objective | KeyResult | The cascade — a parent's KR becomes a child's objective |
| `supports` | KeyResult | Objective | A key result serving one or more parent objectives |
| `supports` | KeyResult | KeyResult | **Illegal** — that relationship is `depends_on` |
| `depends_on` | KeyResult | KeyResult | Interlocking key results |

### Nesting is an edge

A key result nested inside an objective has that objective as its primary `supports` edge, materialised by the loader rather than written by the author. An explicit `supports` list adds **additional** parents.

The two cannot contradict each other because the containing objective is never restated. Listing it explicitly is an **error**, not a redundant no-op — silently accepting it would leave two representations of one relationship.

### Cycles

**A cycle in `supports` is an error.** A goal contributing to itself, directly or transitively, is incoherent: no attribution of contribution can be resolved. Self-reference is always an error.

**A cycle in `depends_on` is a warning.** Mutual dependency between two teams is real and sometimes legitimately phased — "you give us the API, we give you the schema." Blocking it would force teams to omit true information to satisfy a validator, which is worse than seeing it. The validator reports it prominently and exits successfully.

The two relations are checked **separately**. A path that alternates between `supports` and `depends_on` is not a cycle in either.

### No weights

An edge carries no weight, percentage or contribution share. They invite false precision — a number nobody can derive and everybody will argue about — and nothing in the architecture consumes one.

### Authoring shorthand

An edge accepts either a bare ID or a mapping. `supports: [company.retention]` and `supports: [{target: company.retention, origin: laddered}]` are both valid; the loader normalises to the mapping form.

## Consequences

**Adding a team's OKR never requires editing leadership's file.** Under the opposite convention, every team laddering to a company objective would raise a PR against the same file, making the organisation's most important document its most contended one. Directionality here is a concurrency decision as much as a modelling one.

**An unaccepted cascade is invisible.** If leadership decides an objective cascades to support but support has not added the edge, the graph does not show it. This is deliberate: it makes acceptance real rather than assumed, and it is the same property that makes laddering meaningful. It also means the graph reflects what teams have signed up to, not what was announced — which is the more useful thing to lint against.

**A blocked team can raise a dependency without permission.** The awareness usually starts with whoever is blocked. They open the PR; the provider merges or declines. Under a provider-declared convention the blocked team would have nowhere to put the information until someone else agreed.

**Cycle rules diverge by relation, and that divergence is the point.** Treating both alike would have meant either permitting incoherent goal hierarchies or forbidding honest statements of mutual dependency. The asymmetry follows from the relations meaning different things.

**The loader materialises edges rather than only reading them.** Nesting produces an implicit `supports` edge, and shorthand normalises to the mapping form. The in-memory graph is therefore not a transliteration of the YAML, which reinforces the graph object being the public API and the file format being an authoring surface ([plan task 1.7](../../EXECUTION_PLAN.md)).

**Two authoring forms mean a normalisation step and two documented shapes.** Accepted because [task 1.14](../../EXECUTION_PLAN.md) hand-writes the reference examples, and a schema that is tiring to write by hand is a schema that will be filled in badly.

**The cascade/ladder balance stays computable** without anything in v1 computing it. `origin` is optional and unread; it exists so that Doerr's warning about deep cascading can be checked later without a migration.

**Deferred:** whether a dependency carries a description of what is actually needed. `depends_on: platform.api-v2` states that a key result is blocked, not what it is waiting for. Nothing in v1 reads such a field, and the target key result's own statement usually says it. Revisit if the demo dataset shows the reference alone reading as ambiguous.

## Alternatives rejected

**`supports` and `ladders_to` as two edge types.** The obvious reading of piece 1, which names both. Rejected because they describe the same resulting relationship from two authoring directions. Two types would force every consumer — validator, lint, future Conductor — to handle both identically everywhere, and would make the graph's shape depend on who happened to create a connection. Provenance is real and worth keeping, which is what `origin` is for; it is metadata about how an edge came to exist, not a different kind of edge.

**Edges declared on the parent.** Leadership's objective lists the teams beneath it, which reads naturally top-down and gives one place to see everything hanging off a goal. Rejected on concurrency and on ownership: it makes the company objective file a merge-contention hotspot, and it means a team cannot ladder to a goal without write access to leadership's file. The child-declares convention lets teams connect themselves.

**Edges in a separate manifest file.** All relationships in one place, easy to visualise, and no relationship data mixed into goal definitions. Rejected because it separates a fact from the thing it is a fact about: reviewing a team's OKR change would require reading two files, and the manifest becomes the contention hotspot the parent-declares option was rejected for.

**`unblocks`, declared on the providing key result.** More faithful to Doerr, for whom an interlocking key result is a commitment the provider makes — declaring it *is* the commitment. Genuinely close. Rejected because it leaves a blocked team with nowhere to record a dependency until the provider agrees, and because the commitment it captures is available anyway through PR review, which is a stronger signal than a self-declared field.

**Both directions, validated for agreement.** Each side declares and the validator requires them to match. The strongest possible commitment signal. Rejected for doubling the authoring burden and creating a failure class — two teams disagreeing — with no resolution rule that is not arbitrary.

**Cycles in `depends_on` as errors.** Consistent with `supports`, one rule for all edges, and a circular dependency usually does mean neither party can start. Rejected because it makes phased interdependence unexpressible, and because a validator that rejects true statements teaches people to write false ones.

**Edge weights or contribution percentages.** Would let the future Conductor apportion how much of an objective's progress each key result explains. Rejected as false precision: the number cannot be derived from anything, it would be negotiated politically, and no consumer exists. Adding it later is a field, which is cheap.

## Amendments

### Amendment 1 · 2026-08-07 — Cross-boundary edges need review routing

The original decision claimed "acceptance is a pull request." That claim was aspirational, and the gap is worth recording precisely because the mechanism it assumed sounds like it already exists.

**The gap.** `CODEOWNERS` matches **file paths**. A cross-team edge is a *content* change inside the declaring team's own file. When Product-1 adds `depends_on: platform.api-v2` to `okrs/product-1/2026-q3.yaml`, the only path touched is Product-1's, so GitHub requests review from Product-1 alone. They approve their own pull request and merge, and the graph now asserts a commitment Platform never saw. The relationship that most needed a counterparty is the one review never reaches.

**This is not specific to dependencies.** Any edge crossing an ownership boundary has it, including `supports`. If a Product-1 key result begins supporting a Platform objective, Platform is equally uninformed. The problem is cross-boundary edges as a class.

**Nor does reversing direction solve it.** Under `unblocks`, Platform declares in Platform's file and Product-1 goes unrouted — the same problem, mirrored. What `unblocks` genuinely offers is that a provider-declared commitment needs no counterparty approval at all, since the dependent is the beneficiary. That was under-weighted in the original decision and is acknowledged here. It does not change the outcome, because `supports` needs routing regardless, so the mechanism must exist either way.

**A distinction the original conflated.** Doerr's interlocking key result is a **provider-side commitment**. What `depends_on` records is a **dependent-side claim**. The claim becomes a commitment only when someone from the target's team reviews and merges it. Routing is what converts one into the other, which is why it is load-bearing rather than a convenience.

**The decision.** The tool ships a command that resolves changed edges to the owners they affect:

```
okr reviewers --base main
→ platform    product-1.kr-1 depends_on platform.api-v2
```

It loads the graph at both revisions, diffs the edge sets, and for every added or changed edge whose target has a different owner than its source, prints that owner. The loader already builds the graph and knows every node's owner, so this is a comparison and a print on top of existing machinery.

**Identity mapping stays out of scope.** The command emits owner IDs exactly as the spec spells them — `platform`, not `@acme/platform`. Putting hosting-platform handles into the OKR schema would bind the goal format to GitHub, leaving organisations on GitLab or internal tooling with a field that means nothing to them. Adopters map owner IDs to their own identity system in their own CI. An example workflow ships as a template they edit, not as an integration: no API client lives in this codebase, which is what keeps it on the right side of [ADR-0003](0003-v1-scope.md)'s no-integrations cut.

**Consequence.** Without this command the architecture's review story is decorative, and the demo could describe cross-team acceptance but never show it. With it, "goal changes are reviewed by the people they affect" becomes a property of the system rather than a convention an adopter is asked to remember.
