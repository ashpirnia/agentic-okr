# ADR-0007 — ID scheme and OKR repo layout

**Status:** Accepted
**Date:** 2026-08-07
**Deciders:** Ash, Claude

## Context

[ADR-0005](0005-node-types.md) settled which concepts have identity. This one settles what that identity looks like and where the files live.

Both decisions are constrained by something unusual: **this is a layout for a repository we do not own.** [ADR-0002](0002-two-repos.md) established that an OKR repo belongs to an adopting organisation, so anything decided here is a recommendation the tool validates and scaffolds, not a structure it can enforce. It also has to survive an organisation restructuring it to suit themselves.

Two forces pull against each other. IDs appear in pull request diffs, validation errors and `okr diff` output, so they must be readable by someone who is not a developer. But they are also referenced from other files, so they must be stable — every rename is a cascade of edits, and a broken reference is a validation failure in somebody else's directory.

## Decision

### IDs are author-chosen slugs, decoupled from the statement

`support.resolution-time`. Not derived from the objective's text, and not generated.

The ID names the *thing*; the statement describes it. Rewording "Median ticket resolution time under 4 hours" to "Half of tickets resolved within 4 hours" leaves the ID untouched. Only re-conceiving what the key result fundamentally *is* would justify a new ID — and at that point it is arguably a different key result.

### Namespaced by team, never by parent objective

`support.resolution-time`, not `support.fast-resolution.resolution-time`.

[ADR-0006](0006-edge-semantics.md) permits a key result to support several parent objectives. Encoding one parent into the ID privileges it arbitrarily and makes the identifier misleading the moment a second `supports` edge is added.

The team segment is a flat namespace by convention. It earns its place at review time: `depends_on: platform.api-v2` reads as a boundary crossing at a glance, which is precisely what ADR-0006's review routing acts on.

### Globally unique across the repo

No relative resolution, no `file:id` qualifiers, no scoping rules. A reference is a string that either resolves or does not. Moving a file never breaks a reference, and duplicate detection is a set membership check.

### No cycle or period in the ID

The period lives once on `okr.yaml` per [ADR-0003](0003-v1-scope.md)'s single-cycle cut. An ID that encoded `2026-q3` would have to be rewritten in full at every rollover, turning a routine event into a repo-wide rename.

### The loader is layout-agnostic

It walks `okr_dir` and reads every YAML file it finds. File organisation is convention enforced by `okr init`, not a rule enforced by the parser.

**Recommended layout**, which `okr init` scaffolds:

```
acme-okrs/
  okr.yaml              # schema_version, period, okr_dir
  metrics.yaml          # the shared metric vocabulary
  okrs/
    company/2026-q3.yaml
    support/2026-q3.yaml
    platform/2026-q3.yaml
```

**One file per team.** A team's OKR set is reviewed as a unit, and the balance properties Doerr cares about — a healthy mix of committed and aspirational, of milestone and metric — are only assessable when they can be seen together.

### Metrics live in one place

`metrics.yaml` at the repo root by default, with the path overridable in `okr.yaml`. A shared vocabulary should be visibly shared: one place to read what the organisation measures, and adding a metric becomes a reviewable change to that vocabulary rather than a line buried in one team's file.

### The loader does not check that an ID prefix matches its directory

An objective with ID `support.fast-resolution` may live in `okrs/platform/`. This is not validated.

Coupling identity to path would mean a reorganisation breaks every ID in the affected directory — the same class of coupling ADR-0006 rejected when it declined to encode structure into edges.

## Consequences

**Renaming is loud, and that is the correct behaviour.** Changing an ID breaks every reference to it, and the validator reports each as a dangling reference with a file and location. There is no silent partial rename. The cost is a manual sweep; the benefit is that a half-completed rename cannot reach `main`.

**Reorganisations do not break IDs, but they do make them stale.** If Support merges into Customer Experience, `support.resolution-time` still resolves and still validates — it just names a team that no longer exists. This is deliberate: a false name is recoverable at leisure, whereas a repo that fails to load during a reorg is not.

**Cross-team references are visible without tooling.** A reviewer reading `depends_on: platform.api-v2` sees the boundary immediately. This matters because ADR-0006's routing is a machine acting on the same fact, and a human should be able to verify what the machine concluded.

**Layout-agnosticism means the recommendation carries no enforcement.** An organisation can restructure freely, and `okr validate` will keep working. The risk is drift: adopters diverging into layouts we never tested. Accepted, because the alternative is dictating structure in a repository we explicitly do not own.

**`metrics.yaml` is a potential contention point.** Every metric addition touches one file, which is the merge-hotspot problem ADR-0006 rejected parent-declared edges to avoid. Accepted here because metric additions are rare compared with OKR edits, and because a shared vocabulary genuinely *should* be a shared, reviewed artefact. Revisit if real usage shows contention; a `metrics/` directory is the natural escape hatch.

**Nothing prevents an inconsistent team prefix.** A key result owned by platform can carry a `support.` prefix, and validation will pass. The prefix is a readability convention, not a fact the tool derives — ownership comes from the `owner` field, which is what routing and scoring actually read.

## Alternatives rejected

**Opaque or generated IDs — UUIDs, hashes, sequential numbers.** Perfectly stable across renames and reorganisations, and they make the rename problem vanish entirely. Rejected because `depends_on: 7f3a9b2e` tells a pull request reviewer nothing, and every error message, diff and prose rendering would need a lookup to become meaningful. Stability is worth less here than legibility: the review path is the mechanism the whole architecture depends on, and the goal owner reading a diff is not going to resolve identifiers by hand.

**IDs derived from the statement text.** Zero authoring effort — slugify "Median ticket resolution time under 4 hours" and move on. Rejected because it couples identity to phrasing, so every wording improvement becomes a repo-wide rename. It would actively discourage the editing that the Champion exists to encourage.

**Hierarchical IDs encoding the parent objective.** Reads beautifully and makes lineage obvious without traversal. Rejected because ADR-0006 permits multi-parent key results, so the ID would assert a structure the graph contradicts. It also means moving a key result between objectives renames it, which discourages exactly the restructuring that facilitation produces.

**Period in the ID, as `support.2026-q3.resolution-time`.** Makes cycle explicit at every reference and would help if multi-cycle support ever arrives. Rejected because every rollover becomes a repo-wide rename of every identifier, converting a routine quarterly event into a migration. ADR-0003 put the period on `okr.yaml` for the same reason.

**IDs unique per file, with qualified references.** Shorter local IDs, less collision pressure, and a team could name a key result `resolution-time` without a prefix. Rejected because references would then depend on file paths, so moving a file breaks every reference to its contents — reintroducing exactly the fragility that global uniqueness removes.

**Validating that an ID prefix matches its directory.** Would catch copy-paste errors where a key result lands in the wrong team's file. Rejected because it couples identity to location, making reorganisation a breaking change. The error it catches is minor and visible in review; the coupling it introduces is permanent.

**One file per objective.** Smallest possible diffs, and no merge conflicts between people editing different objectives within one team. Genuinely close. Rejected as the *recommendation* because a team's set has properties only visible together — the commitment mix, the build-trap check, whether the whole quarter is coherent. Since the loader is agnostic, an organisation preferring this can simply do it.

**Declining to recommend a layout at all.** Most honest about not owning the adopter's repository. Rejected because `okr init` has to scaffold something, and whatever it scaffolds becomes the de facto standard. Better to choose deliberately and say why than to let the first example decide by accident.
