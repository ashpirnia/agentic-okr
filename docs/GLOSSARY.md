# Glossary

The canonical definitions for this project. Everything else — `CLAUDE.md`, the README, the architecture docs, the schema's field docstrings, and the Champion's facilitation prompts — refers here rather than restating.

That rule exists for one specific failure. The Champion has to explain what an anti-target *is* in order to elicit one. If the agent's prompt and the schema's docstring drift apart, the agent starts eliciting something subtly different from what the schema stores, and both halves look fine in isolation.

**Notation:**

- 📖 **Standard OKR vocabulary.** Used as the OKR literature uses it, principally John Doerr's *Measure What Matters*. If our usage narrows or sharpens the standard meaning, that is stated.
- ⚙️ **Specific to this project.** Introduced by the article series or by the implementation.

---

## The goal structure

### 📖 Objective

The qualitative thing you want to achieve. Ambitious, directional, and not itself measurable — "customers get their problems solved, fast."

Objectives exist at every level of an organisation, not only the top. A first-class node in the schema.

### 📖 Key result

The measurable, **time-bound** signal that you are achieving an objective. Where the objective is directional, the key result is testable. Doerr's formulation: specific and time-bound, aggressive yet realistic.

Time-bounding is satisfied at the repository level rather than per key result — an OKR repo declares a single `period` and holds one live graph, so every key result in it is bound by that cycle. A key result with no deadline is not a key result; it is a wish.

A first-class node, and the level at which agents are wired to goals. Two kinds, on two independent axes — **output shape** (`type`) and **commitment level** (`commitment`):

### 📖 Metric key result

A continuous, numerical target: "median ticket resolution time under 4 hours." An *outcome*. Declared as `type: metric`, and requires a metric reference and a target value.

### 📖 Milestone key result

A binary, project-shaped achievement: "launch the new onboarding flow." An *output*. Declared as `type: milestone`, and requires testable success criteria instead of a metric.

Milestone key results are legitimate, not deficient. But an objective built only from them measures effort rather than impact — see **build trap**.

### 📖 Committed

A goal essential to the business, expected to be fully achieved. Doerr's expected score is 1.0; missing it is a failure. *"Meet the compliance deadline."*

Committed goals are where the pressure to hit the number at any cost is highest, which makes them the goals most in need of guardrails, restraint clauses and anti-targets. Completeness scoring holds them to a higher bar for exactly that reason.

### 📖 Aspirational

A moonshot that stretches the team, expected to land around 0.7. Reaching 1.0 means it was not ambitious enough.

Commitment level is a claim about *ambition*, not a difficulty dial to turn down when a goal starts looking hard. An objective whose key results all override to aspirational is a signal, not a plan.

Declared on the objective (required) and optionally overridden on a key result — a stretch objective can legitimately carry one must-hit key result beneath it.

### 📖 Cascading

Top-down goal setting: a leadership objective breaks down into objectives for the level below. In the cascade, a key result at one level frequently becomes the *objective* of the level beneath it.

**A failure mode at depth, not a neutral structure.** Doerr is explicit that strict multi-level cascading is a relic of slow management: it takes months to plan, and it strips teams of the ownership that makes goals work. Healthy organisations limit top-down cascades to leave room for laddering.

### 📖 Laddering

Bottom-up goal setting: a team or individual defines their own objective and connects it upward to the higher-level goal it supports. Doerr advocates roughly half of an organisation's OKRs emerging this way.

Healthy structures use both cascading and laddering, which is what makes the result a network rather than a pyramid.

### ⚙️ Goal graph

The resolved network of objectives and key results built from one OKR repo. A *graph*, not a tree: a key result may support several parent objectives, and contributions arrive from unexpected corners of the organisation.

### 📖 Co-owned objective

One objective shared by several teams, each owning different key results under it. Requires no special support here — ownership sits on the key result, so a co-owned objective is simply one whose key results have different owners.

### 📖 Interlocking key results

A declared dependency where one team's key result commits to unblocking another's. Cross-functional work made explicit rather than left implicit and siloed.

Declared as `depends_on` by the blocked key result. The provider's commitment comes from reviewing and merging the pull request, not from a field in the schema.

### ⚙️ Supports

The hierarchy edge: a child objective or key result contributes to a parent. Covers both cascading and laddering, which produce the same relationship and differ only in provenance — recorded, when it matters, in an optional `origin` field.

Always declared on the child. A key result nested inside an objective supports it implicitly; an explicit list adds further parents.

---

## Making intent explicit

These are the Champion's instruments — the fields that capture what a human reader would have supplied for free.

### ⚙️ Success criterion

What "done" actually means, written for a reader with no judgment. For "resolve tickets in under four hours": *the underlying issue is fixed, not deflected to another queue.*

### ⚙️ Guardrail metric

A metric that must hold while a key result moves. Carries a direction and a threshold: *reopen rate within 7 days must not exceed 8%.*

Guardrails are embedded in the key result that sets them, because the same metric may guard several key results at different thresholds. Only the metric *definition* lives in git; readings live in the Shepherd's store.

### ⚙️ Restraint clause

The rule forbidding a named anti-target, stated outright: *a ticket may not be closed with a boilerplate "please reopen if this persists."*

Named restraint because it makes visible the self-restraint humans supply silently and agents do not.

**A restraint is one of an anti-target's two defences, not a thing in its own right.** It is written as a field on the anti-target it forbids. The other defence is a watching metric. See **anti-target** for how the two differ.

*Refinement on piece 3, which introduced restraint clauses and anti-targets as separate instruments. In practice authors wrote the same sentence twice — once as a prediction, once as a prohibition — so the implementation nests one inside the other.*

### ⚙️ Anti-target

A one-sentence description of an action that would technically hit the metric while betraying its spirit: *mass-close tickets with a canned reply and let the customer chase you.*

The sharpest instrument here. Its diagnostic form, from piece 2: *for each key result, can you write down in one sentence the action that would technically hit the metric but violate the spirit?* If you can, your team has been silently restraining themselves — and that restraint will not be in the agents you deploy against the same target.

Carries an `origin` recording whether the owner authored it or the Champion proposed it and a human confirmed.

**An anti-target names a move. It carries up to two defences against it:**

| | **Restraint** | **Watching metric** |
| :--- | :--- | :--- |
| Is a | rule | measurement |
| Catches the move | on paper, before anything runs | in the numbers, while it runs |
| Checked by | the Conductor's lint, against an agent's configuration | the Shepherd, against live readings |
| Fails when | an agent finds a different route to the same move | the damage has already started |

An anti-target with **neither** is named but wholly undefended — the sharpest single check the completeness score makes. One missing is a gap; both missing is a worry written down and nothing more.

### ⚙️ Metric

A named, defined quantity the organisation measures: `reopen_rate_7d`, "share of resolved tickets reopened within 7 days," direction lower-is-better.

A first-class node, because a metric's identity is the join key across all three stores — git, the Conductor's measurement sources, and the Shepherd's readings. The same metric may be a key result target for the team transforming it and a guardrail for the team protecting it.

Not every KPI belongs here. A metric enters an OKR repo when a key result targets it or a guardrail watches it, and not otherwise.

**The measurement window is part of the identity**, not a separate field: `reopen_rate_7d` and `reopen_rate_30d` are two metrics, because the Shepherd reads two different series and must tell them apart by identity alone.

### ⚙️ Interpretive layer

The judgment and restraint humans silently supply when reading a goal — deciding what it means in context, and how hard to push a proxy without violating its spirit. Invisible because it was universal. Agents do not supply it, which is what makes it necessary to write down.

---

## The three roles

### ⚙️ Champion

The role that holds **what you meant**. Facilitates goal owners into specifying objectives well, and owns the OKR spec in git. Every spec change routes through it, including changes the Shepherd proposes.

### ⚙️ Conductor

The role that holds **how it is hooked up**. The registry of every agent deployed, the wiring from each agent to the key result it serves, and where each metric's value is read from. Works with agent developers at deployment time.

### ⚙️ Shepherd

The role that holds **what happened**. Reads metric values continuously, watches for divergence between the headline number and its guardrails, and proposes spec changes when it finds a gaming move nobody wrote down. Works with leaders.

### ⚙️ Wiring

The link from an agent's goal to the key result it is meant to serve. Owned by the Conductor and pointed from the agent to the key result, never the reverse — agents are numerous and redeployed constantly, key results are few and slow.

### ⚙️ Lint

The Conductor's static, wiring-time check that an agent's declared target matches the spec's intent — run before the agent processes anything. Piece 3 calls it the cheapest check in the system.

### ⚙️ Watch list

The set of guardrail metrics the Shepherd monitors for a key result. Not chosen once: it grows each time the loop catches a divergence nobody anticipated.

### ⚙️ Drift

Divergence between what a goal said and what it meant, visible in behaviour rather than in the text. The headline metric looks pristine while the outcome it stood for decays.

---

## Storage and structure

### ⚙️ OKR repo

An adopting organisation's goal repository: YAML only, rooted at an `okr.yaml` marker, owned and versioned by them. Never refers to the `agentic-okr` source repository.

### ⚙️ Owner

Declared once in `owners.yaml` and referenced by ID everywhere else. Both objectives and key results require one, and they mean different things:

| | **Objective owner** | **Key result owner** |
| :--- | :--- | :--- |
| Is the | executive sponsor | person doing the work |
| Holds | the qualitative vision — the *what* and *why* | the measurable |
| Also | **breaks ties** when KR owners disagree | — |

The tie-breaker role is why the objective's owner is required. A co-owned objective spreads work across teams whose priorities will diverge, and one with no sponsor has no resolution path when they do.

Declared rather than free text because owner identity is the join key review routing acts on — unvalidated strings let `head_of_support` and `head-of-support` become two people, and a cross-team review route to neither. Same reasoning that made **metric** a declared thing.

An ID names the role, not the person currently in it, so it survives someone changing jobs.

An optional `handles` map carries platform names — `github: "@acme/platform"` — used to generate `CODEOWNERS`. Deeper identity resolution, such as email or directory lookup, stays with the Conductor.

### ⚙️ Period

The cycle an OKR repo covers, declared once in `okr.yaml` — for example `2026-Q3`. One repo holds one live graph, so the period time-bounds every key result in it. Last cycle is a previous commit; rolling over is a pull request.

### ⚙️ Intent / measurement config / observation

The three-way ownership boundary. **Intent** is what you meant, lives in git, written by a human deliberately. **Measurement config** is how to find out, owned by the Conductor, written by a developer at registration. **Observation** is what happened, owned by the Shepherd, written by a machine on a schedule.

### ⚙️ Completeness score

A measure of whether a spec is *filled in* — success criteria present and testable, guardrails present, anti-targets present, ownership set, type-appropriate fields supplied.

It does not claim the objective is a good one to pursue. That distinction must not blur in code, output text or docs.

### 📖 Build trap

Relying exclusively on milestone key results, turning the framework into a to-do list that measures effort instead of impact. Guarded against by an objective-level check: an objective whose key results are all milestones is flagged.

---

## Where these come from

The terms marked ⚙️ are introduced or sharpened in the article series:

1. [So Many Agents, Achieving So Little](https://medium.com/@ash.pirnia/so-many-agents-achieving-so-little-adf5ebe71b06) — the three roles, the goal graph
2. [What Agents Reveal About Your Goals](https://medium.com/generative-ai/what-agents-reveal-about-your-goals-46b92374828b) — the interpretive layer, the anti-target diagnostic
3. [Two Banks and a River](https://medium.com/generative-ai/two-banks-and-a-river-bridging-okrs-and-agents-9fb050c47176) — restraint clauses, wiring, the lint, the watch list, drift

A definition here should not contradict a published one. If it needs to, that is a decision worth an ADR, not an edit.
