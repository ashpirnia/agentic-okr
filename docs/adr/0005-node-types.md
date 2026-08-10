# ADR-0005 — Node types and the thin-v1 rule

**Status:** Accepted — amended 2026-08-07, see Amendments
**Date:** 2026-08-07
**Deciders:** Ash, Claude

## Context

The schema is the product. It is also a published contract — [ADR-0002](0002-two-repos.md) established that files conforming to it will live in other organisations' repositories, so a field shipped in v1 is expensive to change and a field omitted is cheap to add.

The first structural question is which concepts are **first-class nodes** — addressable by a stable ID, referenceable from elsewhere, independently meaningful — and which are **embedded fields** on a parent. Getting this wrong is not a rename. Promoting an embedded field to a node later means every adopter's files change shape.

The pressure in the room is to make everything a node. It feels safer, it looks more "proper", and every concept can be argued into deserving its own identity. That pressure is mostly wrong, and it needs a test rather than taste.

## Decision

**The test: a concept is a first-class node if and only if something outside its parent needs to reference it by ID.**

Applying it:

| Concept | Form | Why |
| :--- | :--- | :--- |
| `Objective` | **Node** | Edges connect objectives to each other and to key results |
| `KeyResult` | **Node** | The Conductor wires agents to key results ([ADR-0001](0001-git-holds-intent.md) amendment) |
| `Metric` | **Node** | The join key across git, the Conductor's measurement sources, and the Shepherd's store |
| `Guardrail` | Embedded in `KeyResult` | Nothing references a guardrail by ID |
| `AntiTarget` | Embedded in `KeyResult` | Prose about one key result |
| `Restraint` | Embedded in `KeyResult` | Prose about one key result |
| `SuccessCriterion` | Embedded in `KeyResult` | Prose about one key result |

**A key result declares its type: `milestone` or `metric`.** See Amendments — this supersedes an earlier decision to infer type from whether a metric was present.

**Every `metric:` reference must resolve.** Unresolvable metric references are validation errors in the same class as dangling objective references.

### The thin-v1 rule

A field earns its place only if **the Champion can elicit it from a human today**. Not because the Conductor or Shepherd might need it later; not because it would be tidy; not because another OKR tool has it.

Two supporting rules:

- **Every field traces to an ADR.** A field with no written justification is removed, not grandfathered.
- **When in doubt, leave it out.** Adding a field is a minor version. Restructuring one is a migration for every adopter.

## Consequences

**The inversion is the finding worth remembering.** Intuition says `Guardrail` is a node and `Metric` is a detail. The test says the reverse, and the test is right. A guardrail is *per-key-result*: CSAT may guard three different key results at three different thresholds, so (metric + threshold) belongs to the KR that set it. The shared, externally-referenced thing is the metric identity. Had we followed intuition, the concept with the strongest claim to identity would have been the one without an ID.

**Metric identity becomes validated rather than assumed.** ADR-0001 committed to the metric's identity being the join key across three stores. As an embedded string, `csat` and `CSAT` would silently become two metrics in the Shepherd's store, discoverable only as a gap in a time series months later. As a node reference, it is a validation error at authoring time.

**Referential integrity has real work beyond edges.** Metric references are a second class of cross-reference the loader must resolve, which strengthens the case for the loader being a library first ([plan task 1.7](../../EXECUTION_PLAN.md)) rather than a CLI convenience.

**Hand-writing costs slightly more ceremony.** You define a metric before referencing it. This is a real cost on a small repo and the right cost overall: a shared metric vocabulary is an organisational asset, and forcing metrics to be named and defined once is the discipline this project exists to argue for. "Which metric measures this?" is a Champion question, so it passes the thin-v1 test on its own merits.

**The completeness score gains a strong signal.** A key result with no metric is precisely the "aspiration dressed up as a key result" that piece 2 attacks. Making it scoreable rather than fatal keeps milestone KRs expressible while ensuring the gap is visible.

**Guardrails cannot be shared across key results.** If ten KRs all guard on CSAT, the threshold is repeated ten times. Accepted deliberately: thresholds genuinely differ by context, and a shared guardrail object would need its own identity and override semantics — a node in disguise. If real usage shows thresholds are almost always identical, this is revisited with evidence.

**Deferred to adjacent ADRs, not decided here:** whether key results nest inside objectives in the file or live separately, and where metrics are declared (ID scheme and layout ADR); what `supports` and `ladders_to` mean and how a key result supports multiple parent objectives (edge semantics ADR); the internal fields of a guardrail and an anti-target (guardrail metrics ADR). **Note for the edge ADR:** if key results nest under objectives structurally, a KR has one structural parent plus additional `supports` edges, and those two relationships must not be allowed to disagree.

## Alternatives rejected

**Everything as a node — `Guardrail`, `AntiTarget`, `Restraint`, `SuccessCriterion` all with IDs.** Maximally flexible, and every concept becomes independently addressable, versionable and reusable. Rejected because flexibility nobody uses is complexity everybody pays for. A goal owner writing an anti-target does not want to mint an identifier for a sentence, and nothing in the architecture ever refers to an anti-target by name — the Shepherd's `anti_target.discovered` proposes new prose rather than pointing at existing prose. This is the alternative the room drifts toward by default, which is why the test exists.

**Metric embedded in each guardrail.** Thinner by one node type, and a guardrail reads standalone with nothing to look up. Rejected because it turns the three-store join key into an unvalidated string. The failure is silent and slow: two spellings become two metrics, and nobody notices until a time series has a hole in it.

**Metric embedded, with a validator consistency check** — inline definitions, but the validator rejects two guardrails defining the same metric name differently. Genuinely close, and it gets most of the integrity. Rejected because it is a node in disguise with worse ergonomics: there is no single place to read what a metric means, the "definition" is whichever guardrail you happen to open first, and the Conductor's measurement source would key off a string that exists in n places rather than one.

**Requiring every key result to name a metric.** Maximally strict, and it forces exactly the discipline the series argues for. Rejected because milestone key results are real, and an org that cannot express one will invent a fake metric to satisfy the validator. A fake metric is worse than an admitted milestone: it looks measured, so nothing flags it, and it is precisely the ceremonial KR piece 2 describes teams learning to ignore.

**Separate node types for committed versus aspirational key results.** Doerr distinguishes them and organisations do treat them differently. Rejected for v1 as a field-level concern at most, not a structural one, and nothing in the loop currently behaves differently for the two. It can be added as an optional field the moment something acts on the distinction. *(Note: this is a different axis from the `milestone`/`metric` type added in the Amendments below — commitment level versus output shape. Both are field-level; only the second earned its place in v1.)*

## Amendments

### 2026-08-07 — Alignment with Doerr's OKR structure

Reviewing the model against *Measure What Matters* produced three changes. None disturb the node/embedded split; two are field-level and one reverses a decision made in the original draft.

**1. A key result declares its type: `milestone` or `metric`.** This supersedes "a key result's own metric is optional; its absence lowers the completeness score."

The original treated a metric-less key result as deficient. Doerr treats milestone KRs (binary outputs — "launch the new app") and metric KRs (continuous outcomes — "reach 10,000 daily active users") as two legitimate kinds, and a healthy cycle needs a mix of both. Penalising a milestone for lacking a metric is wrong.

Inferring the type from metric-presence is worse than a field, because it makes two different situations indistinguishable: a deliberate milestone and a metric KR whose author never got round to naming the metric look identical. Completeness scores each type against its own requirements — a milestone needs binary, testable success criteria; a metric KR needs a metric reference and a target.

The field passes the thin-v1 test on its own merits: *"is this something you ship, or a number you move?"* is a Champion question and a clarifying one.

**2. `owner` moves to the key result.** Doerr's co-owned objectives — several teams sharing one objective while each owns different key results — need no special support once ownership sits at the KR level. A co-owned objective is simply an objective whose key results have different owners. This avoids a multi-owner field on `Objective` and the override semantics that would come with it. An objective may still carry an owner as the accountable lead; the KR owner is who is doing the work.

**3. Metric's first-class status is strengthened, not challenged.** Doerr separates KPIs (the dashboard: ongoing business-as-usual health) from OKRs (the roadmap: transformational change), with a KPI entering the OKR graph only when it is broken or needs a step change.

That distinction maps onto the two roles a metric plays here. A metric can be a **key result target** for the team transforming it and a **guardrail** for a team who must not degrade it — CSAT being the obvious case: support's own improvement target, and simultaneously the guardrail on a resolution-time KR. One entity, two roles, referenced from two places. That is the strongest argument yet for it having an identity rather than being redefined inline at each use.

It also implies a discipline the metrics section must keep: it is not a dumping ground for every KPI the organisation tracks. A metric belongs in an OKR repo when a key result targets it or a guardrail watches it, and not otherwise.

**Consequences landing in adjacent ADRs, not here:**

- **Edges must be able to target a key result, not only an objective.** Doerr's cascade turns a parent's key result into the child level's objective. The edge ADR must permit `Objective → KeyResult`.
- **Interlocking key results need a dependency edge**, distinct from `supports`/`ladders_to`. Goal hierarchy and delivery dependency are different relationships with different cycle legality. Piece 1 claims the Champion "knows where the critical dependencies sit", so without this the tool cannot back a published claim. v1 lets a spec *declare* a dependency; *detecting* that a dependency has stalled needs live data and remains the Conductor's job, safely outside v1.
- **The completeness rubric gains an objective-level check for the build trap.** An objective whose key results are all milestones is a to-do list measuring effort rather than impact. This is the first rubric rule that operates on an objective rather than a key result, and it is a strong facilitation prompt: *"you have listed four things you will ship — how will you know any of it worked?"*
