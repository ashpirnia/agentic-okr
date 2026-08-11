# ADR-0011 — Completeness scoring rubric

**Status:** Accepted — amended 2026-08-07, see Amendments
**Date:** 2026-08-07
**Deciders:** Ash, Claude

## Context

The completeness score is the article's evidence. The claim is that a raw OKR scores poorly and a Champion-processed one scores well, which means the number has to be defensible rather than vibes — a reader should be able to recount it, and a sceptic should not be able to dismiss it as an arbitrary weighting.

It also carries a risk the project cannot afford. If the score looks like a judgment about whether an OKR is *good*, then the tool is quietly claiming to evaluate strategy, and the first person who scores a well-conceived objective at 40% will conclude the tool is wrong. It measures whether a spec is **filled in**. Nothing more.

## Decision

### The organising principle

**Validation covers what is required. Scoring covers what is optional but valuable.**

If a field's absence is illegal, it is a validation error and never appears in the score. If its absence is legal but weakens the spec, it is a scored dimension. Nothing is both.

This keeps the score from double-counting things the validator already refuses, and it is why the rubric below is short.

### Two artefacts, deliberately separate

**`okr score` is structural and deterministic.** Every check is computable from the graph. It lives in `core`, runs without an API key, and produces the same answer for the same input on any machine, forever.

**The Champion separately emits semantic review** — whether a success criterion is actually testable, whether an anti-target is plausible, whether a guardrail threshold is meaningful. That output is **questions, never a number.**

The two are never merged. A reader can verify the score by hand; the semantic review is an agent's opinion and is labelled as one.

### The rubric

**Key result — four checks:**

| | Check |
| :-- | :--- |
| K1 | At least one success criterion |
| K2 | At least one guardrail |
| K3 | At least one anti-target |
| K4 | Every anti-target has at least one defence — a `restraint` or a `watched_by` |

K4 is vacuously satisfied when there are no anti-targets, which K3 already catches. It never double-penalises.

**Objective — one check:**

| | Check |
| :-- | :--- |
| O1 | Not build-trapped — at least one key result of `type: metric` |

### Presentation: `n of m`, never a curated scale

Reported per key result, per objective, and as a repo roll-up: `3 of 4 (75%)`.

No weights. Denominators vary honestly with what applies. A reader can recount every number by hand.

**The report orders findings by severity, and severity is where commitment level lives.** Both committed and aspirational key results should carry guardrails; what differs is how much the gap matters. So the score stays `3 of 4` and the report says *"missing guardrails — this is a committed key result, where that gap matters most."* Severity is presentation, not arithmetic.

### Two new validation errors this ADR creates

**A milestone key result with no success criteria is invalid.** It has no metric, no target, and now nothing checkable — it asserts nothing at all. That is the ceremonial key result piece 2 describes teams learning to ignore, and it is better refused than scored low and merged.

**An objective declared `committed` whose key results all override to `aspirational` is a warning.** Legal, and occasionally honest, but usually commitment level being used as a difficulty dial rather than a claim about ambition. Reported, exits zero.

## Consequences

**The score is reproducible, and that is its whole value as evidence.** A reader can clone the demo repo, run `okr score`, and get the number printed in the article. A model-dependent score could not survive that, and "the agent thought it improved" is a weaker claim than "here is a count you can check."

**`okr score` needs no API key.** It sits in `core` alongside the validator, which means the widest possible audience — an organisation with no interest in the agent can still run it in CI on their goal repo.

**The rubric is short, and that is intentional.** Four checks plus one. Every additional dimension is a weighting decision in disguise, and a longer list would make the number look more precise while making it less defensible.

**`success_criteria: [TBD]` scores as present.** The structural score cannot see vacuity, and pretending otherwise would be the model-dependence this ADR rejects. This is exactly the gap the Champion's semantic review exists to fill, and stating the limit plainly is better than a score that quietly overclaims.

**The two artefacts must stay visibly distinct in output.** If a report interleaves "3 of 4 checks" with "this success criterion looks untestable," a reader will take both as equally hard facts. Phase 2 must keep them separated and labelled.

**Type-awareness largely resolved into validation rather than scoring.** A metric key result must have a metric and target; a milestone must have success criteria. Both are now required, so neither is scored. What looked like a scoring requirement was a validation requirement wearing the wrong hat.

**"Scope bounded" was dropped as a dimension.** Scope is expressed *as* a success criterion — "applies to all inbound tickets except billing disputes" — so it is not structurally separable from K1. Counting criteria and declaring two to mean "bounded" would be arbitrary precision.

**A perfect score means a spec is filled in, not that the goal is worth pursuing.** This must never blur in code, CLI output, documentation or the article. The most likely place it blurs is a chart.

## Alternatives rejected

**Include LLM judgment in the score.** Would catch `TBD`, vacuous criteria and implausible anti-targets — the things a structural check is blind to. Rejected because it makes the article's central number irreproducible and model-dependent: a reader could not verify it, and a future model version would silently change it. "Sonnet rated this 8" is a weaker claim than "eight of nine checks pass, count them yourself." The judgment is still valuable, which is why it is kept as questions rather than discarded.

**A curated 0–10 score.** Matches the phrasing already used when discussing the project, and a 10-point scale is intuitive. Rejected because ten points implies weighting choices we would have to justify — why is a missing guardrail worth two points and a missing anti-target worth one? — and because a graded scale invites precisely the "is this OKR good?" misreading the score must not make. `8 of 9` says what it means.

**Per-dimension output with no aggregate.** The most honest option: just the list of what is missing, no number to misuse. Rejected because the before-and-after comparison is the article's evidence and "these four things are missing" does not go in a chart. The aggregate is retained, but as a count rather than a grade.

**Weighting dimensions by importance.** Anti-targets are arguably worth more than success criteria, since they are the hardest thing to elicit. Rejected because the weights would be invented, unfalsifiable, and the first thing a sceptical reader attacks. Severity ordering in the report gets the same emphasis without putting a judgment inside the arithmetic.

**Scoring commitment level directly** — for instance, requiring anti-targets on committed key results and merely scoring them on aspirational ones. Rejected because both genuinely need them; the difference is consequence, not requirement. Encoding it as a different denominator would mean a committed key result and an aspirational one with identical specs scored differently, which is indefensible.

**Making the objective's owner or commitment a scored dimension.** Both are required by ADR-0010 and ADR-0005, so their absence is already a validation error. Including them would double-count and inflate every score by two.

## Amendments

### Amendment 1 · 2026-08-07 — "Nothing is both" governs errors, not warnings

The organising principle reads: *if a field's absence is illegal, it is a validation error and never appears in the score; if its absence is legal but weakens the spec, it is a scored dimension. Nothing is both.*

Implementing `W106_OBJECTIVE_WITHOUT_KEY_RESULTS` exposed that the sentence never contemplated warnings. An objective with no key results is *legal* — a top-level objective can be an aggregation point for teams laddering to it — so it is a warning rather than an error, and it is also the reason the objective's one scored check fails.

**The principle scopes to errors.** "Nothing is both" means nothing is both a validation *error* and a scored dimension, because that is where double-counting would occur: the score would inflate by re-counting things the validator already refuses. Warnings mark things that are legal, which is the same category scoring covers, so an overlap there is not double-counting — it is two artefacts answering different questions about one absence. The validator asks whether the graph holds together; the score asks how much is written down.

**The constraint that keeps this from spreading: a warning may coincide with an existing dimension failing. It may never add a dimension.** Adding an `O2` for "has any key results" would have asked every objective two questions instead of one, changing every denominator and moving the roll-up — to express something that is not a second requirement. The rubric stays at four key-result checks and one objective check.

**Where a warning and a dimension do coincide, the wording must differ.** Same check, same `0 of 1`, different sentence, because the reader has a different thing to go and do:

```
◆ company.north-star    0 of 1  committed   missing: key results — this objective has none
◆ platform.reliability  0 of 1  committed   missing: a key result that moves a number
```

The stable identity a consumer matches on remains the dimension; only the phrase shown to a human varies.

**The three states form a progression**, which is the check working as intended rather than a coincidence: no key results raises the warning and fails the dimension; adding a milestone key result clears the warning and leaves the dimension failing as a build trap; adding a metric key result clears both.
