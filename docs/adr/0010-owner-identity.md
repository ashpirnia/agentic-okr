# ADR-0010 — Owner identity

**Status:** Accepted — amended 2026-08-07, see Amendments
**Date:** 2026-08-07
**Deciders:** Ash, Claude

## Context

Two questions, both left ambiguous by earlier decisions and both surfaced by drawing the ERD.

[ADR-0005](0005-node-types.md) Amendment 1 moved ownership onto the key result, so that Doerr's co-owned objectives need no multi-owner field, and noted that an objective "may still carry an owner as the accountable lead." *May* is not a schema.

Separately, `owner` has been an unvalidated free-text string throughout. [ADR-0008](0008-okr-yaml-marker.md) rejected a team registry on the marker, reasoning that "ownership resolution belongs with the Conductor, which knows about identity."

That reasoning conflated two different things, and the consequence is a live defect. [ADR-0006](0006-edge-semantics.md)'s review routing compares the owner of an edge's source against the owner of its target, and dispatches a review request accordingly. If an author writes `head_of_support` in one file and `head-of-support` in another, those are two owners as far as the tool can tell. A cross-team dependency is then routed to nobody, silently, and the commitment lands unreviewed.

The obvious mitigation — warn when an owner string appears exactly once, since real owners own several things — catches a typo made once and fails on a variant used consistently.

## Decision

### `Objective.owner` is required — the executive sponsor

Every objective names a sponsor. Distinct from `KeyResult.owner`, and not merely a coarser version of it:

- The **objective owner** holds the qualitative vision — the *what* and the *why* — and is the **tie-breaker**. When key result owners under one objective disagree about scope or trade-offs, this is who decides.
- The **key result owner** does the work and is accountable for the measurable.

The tie-breaker role is what makes the field required rather than merely useful. A co-owned objective spreads work across teams whose priorities will diverge; an objective with no sponsor has no resolution path when they do. Doerr's co-ownership distributes the *work*, not the authority to settle disputes about it.

The examples reflect this naturally: senior leaders sponsor objectives, department heads and technical leads own the key results beneath them.

### Owners are declared in `owners.yaml` and referenced by ID

```yaml
# owners.yaml
owners:
  - id: head-of-support
    name: Head of Support
  - id: platform
    name: Platform Team
```

An entry carries `id` and `name`. Nothing else.

Every `owner` on an objective or key result must resolve to a declared ID. An unresolvable owner is a **dangling reference** — an error in the same class as a reference to a metric that does not exist.

Path defaults to `owners.yaml` at the repo root, overridable in `okr.yaml` alongside `metrics_file`.

### This refines ADR-0008 rather than contradicting it

ADR-0008 rejected a *team registry on the marker*, and that rejection stands — the marker keeps its four fields. What it got wrong was treating "which owners exist" and "who is `platform` on GitHub" as one thing.

- **Declaring which owner IDs exist** is vocabulary. It belongs in the OKR repo, exactly as metric declarations do.
- **Resolving an owner ID to an identity** — a GitHub team, an email address, a directory entry — remains the Conductor's, and never enters the schema.

This is the same split already drawn for metrics: the repo declares that `reopen_rate_7d` exists and what it means; the Conductor knows where to read it.

## Consequences

**A typo becomes a hard error at authoring time.** Not a heuristic, not a warning with a false-negative rate, not something to tune. `head_of_support` fails to resolve and validation stops, with the same machinery that catches a bad metric reference.

**Review routing gains a reliable join key.** Routing is a v1 feature that acts on owner equality, and it was resting on string comparison of unvalidated free text. That the defect was invisible — a review silently going to nobody rather than to the wrong person — is what makes it worth a file.

**The structural argument that justified `Metric` justifies this.** ADR-0005's test is whether something outside its parent references a thing by ID. Owner is referenced by routing, and by the Conductor later. Having applied that test to metrics and not to owners was an inconsistency, not a decision.

**`okr diff` output becomes readable.** `→ needs review from: Platform Team` rather than `platform`, at the cost of one field.

**A fourth file, and ceremony when someone joins.** Adding a person or team is now an edit before their first objective can reference them. Accepted: it is one line, it is reviewed like everything else, and it is the same trade already made for metrics.

**Owner IDs are a published contract like any other identifier.** Renaming one breaks every reference, loudly. [ADR-0007](0007-id-scheme-and-layout.md)'s reasoning applies unchanged — the ID names the role, not the person currently in it, so `head-of-support` survives the person changing.

**Nothing validates that an owner is a real person or team.** A repo can declare `id: nobody, name: Nobody` and use it everywhere. The schema checks internal consistency, not truth. Truth is the Conductor's, and beyond that it is a review question.

## Alternatives rejected

**Leave `Objective.owner` optional.** Lets a genuinely shared objective avoid naming one lead, which feels right for a co-owned goal. Rejected because routing needs a target for edges pointing at objectives, and that is half the legal edge shapes. Deriving an owner from the objective's key results was considered and is worse: a laddering edge into a company objective would route to whoever owns its key results rather than to the accountable lead, which is a plausible-looking wrong answer.

**Remove `Objective.owner` entirely**, leaving ownership only on key results. Thinnest, and consistent with Amendment 1 having moved ownership down. Rejected for the same routing reason, and because an objective nobody is accountable for is the failure mode OKR systems are supposed to prevent.

**Warn when an owner string appears exactly once.** Cheap, needs no registry and no identity knowledge. Rejected because it only catches a typo made once. An author who writes `head_of_support` four times and `head-of-support` three times produces two plausible-looking owners and no warning — which is the realistic case, since people are consistent with their own mistakes.

**Constrain the ID format and warn on normalisation collisions.** Requiring `^[a-z0-9]+(-[a-z0-9]+)*$` prevents the separator-variance class outright, and flagging two strings that normalise identically catches case differences. Genuinely good, and it kills the motivating example. Rejected as insufficient rather than wrong: a plain misspelling — `head-of-suport` — passes both checks, and it fails in exactly the same silent way. A format constraint remains available as an additional check if declared owners prove not to be enough.

**Fuzzy matching on edit distance.** Would catch misspellings that normalisation misses. Rejected as a heuristic with a tuning problem: `pm-growth` and `pm-growth-2` are one edit apart and legitimately different, so the warning either misses real typos or cries wolf. Declared owners make the question exact.

**Richer owner entries — email, GitHub handle, team membership, manager.** Would let the tool dispatch review requests directly rather than emitting IDs for an adopter's CI to map. Rejected because it binds the schema to a hosting platform, which ADR-0006 Amendment 1 explicitly avoided, and because it is identity resolution wearing a vocabulary costume. An organisation on GitLab or an internal directory would carry fields that mean nothing to them.

**A `kind: person | team` field.** Matters for how a review request is dispatched — an individual and a group are addressed differently. Rejected because nothing in v1 reads it and the distinction is usually evident from the name. It is a field, and fields are cheap to add.

## Amendments

### Amendment 1 · 2026-08-07 — Platform handles, and generated CODEOWNERS

The original decision gave owner entries `id` and `name` only, rejecting a platform handle because it "binds the schema to a hosting platform." That rejection assumed the alternative was harmless. It is not, and the reasoning missed a mechanism worth having.

**Two routing mechanisms, complementary rather than alternative.**

- `CODEOWNERS` matches **paths**: it catches *someone edited your team's file*, which is the ordinary case.
- `okr diff --reviewers` matches **content**: it catches *someone in another team's file made a commitment about you*, which is the case [ADR-0006](0006-edge-semantics.md) Amendment 1 exists for.

Neither covers the other, and both are answering the same question — who owns this? — from one source of truth. That makes generating the first from the graph obviously correct: `CODEOWNERS` otherwise duplicates ownership by hand and rots, which is the drift this ADR was written to eliminate.

**The decision.**

`okr codeowners` prints a `CODEOWNERS` mapping derived from the graph and `owners.yaml`, to **stdout** rather than to a file. An adopter's `CODEOWNERS` may cover paths this tool knows nothing about, so the tool refuses to own the file — redirect it, splice a block, or diff it in CI to detect drift.

Where a file contains work owned by several people, all of them are emitted. `CODEOWNERS` permits multiple owners per path, and joint review rights over a shared file is the correct answer rather than a compromise.

Owner entries gain an **optional `handles` map**:

```yaml
owners:
  - id: platform
    name: Platform Team
    handles:
      github: "@acme/platform"
```

Generic rather than a `github:` field, so GitLab, Bitbucket or an internal system fit the same shape. Optional, so an organisation that never generates `CODEOWNERS` carries nothing meaningless. Unknown keys are ignored rather than rejected.

**Why this reverses the original rejection.** The alternative — the adopter maps owner IDs to handles inside their CI workflow — creates a *second* registry of who exists. If it is missing an entry, the review routes to nobody, silently. That is precisely the failure this ADR eliminated for owner strings, reintroduced one layer up. Having argued that an unvalidated join key drifts, accepting a second unvalidated copy of the same mapping would have been inconsistent.

**Where the boundary now sits.** [ADR-0001](0001-git-holds-intent.md) put measurement configuration with the Conductor, and a handle is superficially similar — an external system's name for something. It is not the same: a review handle carries no credentials, no endpoint, and changes only when the organisation reorganises. It describes who reviews *this repository*, which is a property of the repository rather than of external infrastructure. Metric sources stay with the Conductor; review handles stay here.

**Consequences.**

*One definition of ownership drives both routing paths.* Ownership is stated once, in the spec, and every mechanism that acts on it reads from there.

*`CODEOWNERS` becomes verifiable.* `okr codeowners | diff - CODEOWNERS` in CI fails when the committed file has drifted from the goal graph — a check that was impossible while the file was authored by hand.

*Handles are unvalidated strings.* Nothing confirms `@acme/platform` exists. That is identity resolution, and it stops here by design; a wrong handle is a wrong reviewer, which is visible, rather than a missing one, which is not.
