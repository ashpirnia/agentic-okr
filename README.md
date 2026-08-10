# agentic-okr

**OKRs as code: a machine-readable goal spec, plus the agent architecture that keeps AI work pointed at it.**

## The premise

Give a senior team an OKR like *"improve customer experience"* and they get on with it. Give the same OKR to an agent and something uncomfortable surfaces: you never defined what it meant. The team was filling in the gap. They never told you, and you never noticed.

That gap is not a capability or budget problem. Your goals were written for a human reader who supplies judgment and restraint for free. Agents supply neither — they take the words and run. A support team with a four-hour resolution target *could* mass-close tickets with "please reopen if this persists." Mostly they don't. That restraint is not in the metric; it is in them.

`agentic-okr` treats the goal spec as the missing layer. OKRs get written down precisely enough that something without judgment can follow them, and they are stored as code so they can be reviewed, diffed, and inherited by the next team and the next quarter.

On top of that spec sit three roles:

- the **Champion** helps humans write the spec and holds it
- the **Conductor** wires each agent to the OKR it is meant to serve, and lints the connection before anything runs
- the **Shepherd** watches for the drift the wiring could not predict, and feeds what it catches back into the spec

The three form a loop, not a beam. A spec you write once will be wrong; the loop assumes that and turns being wrong into the mechanism that makes the next crossing safer.

## What a spec looks like

> **Illustrative only.** The schema is actively being designed and this shape *will* change. Do not build against it yet. Follow [the execution plan](#status) for when v1 lands.

```yaml
# okrs/support/2026-q3.yaml
id: support.resolution-time
objective: Customers get their problems solved, fast
owner: head-of-support
supports: [company.retention]

key_results:
  - id: support.resolution-time.p50
    statement: Median ticket resolution time under 4 hours
    success_criteria:
      - The underlying issue is fixed, not deflected to another queue
      - Applies to all inbound tickets except billing disputes

    guardrails:
      - metric: reopen_rate_7d
        must_not_exceed: 0.08
      - metric: csat
        must_not_fall_below: 4.2

    restraints:
      - A ticket may not be closed with a boilerplate
        "please reopen if this persists"

    anti_targets:
      - Mass-close tickets with a canned reply and let the
        customer chase you
```

The `anti_targets` field is the sharpest instrument here, and it comes straight from a diagnostic in [piece 2](https://medium.com/generative-ai/what-agents-reveal-about-your-goals-46b92374828b): *for each key result, can you write down in one sentence the action that would technically hit the metric but violate the spirit?* If you can, your team has been silently restraining themselves — and that restraint will not be in the agents you deploy against the same target. Writing it down is how it gets inherited.

That piece has five more questions worth running against your own OKR set. They need no tooling and will surface uncomfortable things.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for diagrams of the components, the ownership boundary, and the loop — with what is built in v1 marked apart from what is designed and deferred.

## Two repos, not one

This distinction matters, so it is worth being explicit:

| | **This repo** (`agentic-okr`) | **Your OKR repo** |
| :--- | :--- | :--- |
| Owner | Us, the maintainers | Your organisation |
| Contains | Python: schema, loader, validator, agent | YAML only. No Python. |
| Audience | Developers | Goal owners |

You do not put your OKRs here. You create your own repo, and this tool reads it:

```
acme-okrs/
  okr.yaml                    # marks the repo root; pins the schema version
  okrs/
    company/2026-q3.yaml
    support/2026-q3.yaml
```

A support lead raising a PR to add a guardrail should never have to look at our source tree.

## Why intent lives in git

The spec format is the product. Everything else is built on top of it.

Two write paths, deliberately kept apart:

- **Intent lives in git.** Objectives, key results, success criteria, guardrail metric definitions, anti-targets and ownership are low-volume, deliberate, and benefit from review. A change to what you meant should be a pull request with a diff someone reads.
- **Observation lives in the Shepherd's store.** Current metric values, KPI readings and drift signals are high-volume and machine-written. They have no business in version control — a goal repo whose commit log is buried under progress numbers has lost the only property that made this worth doing.

You do not have to provide a database. The Shepherd owns its own store and will ship with bundled SQLite; hosting it elsewhere is an option for organisations running at scale, never a prerequisite. It holds derived readings, not a system of record — your raw KPIs stay where they already are. And v1 needs no persistence at all: `okr validate` runs against a directory with nothing to install or connect. See [ADR-0001](docs/adr/0001-git-holds-intent.md).

The practical payoff: when the Shepherd discovers that agents found a way to game a goal, the new guardrail arrives as a PR with the evidence attached. A human merges it, and the trick is on the page for every fleet that follows.

## What this is not

- **Not an OKR SaaS.** No web UI, no dashboards, no hosted service. A CLI and a directory of YAML.
- **Not a replacement for human judgment.** The Champion is a facilitator, not an author. It interrogates an objective for its missing success criteria, unstated guardrails and plausible anti-targets, and pushes the owner to supply them. It narrows the gap between what you wrote and what you meant. It does not close it, and any tool claiming otherwise is selling you the problem again.
- **Not a scoring system for whether your OKRs are good.** The completeness score measures whether a spec is *filled in*. Whether the objective is the right one to pursue is your job.
- **Not an integration layer.** No connectors to Viva Goals, Lattice or Workday.

## Status

Early, and pre-alpha. The schema is being designed; nothing here is production-ready and the format is unstable by intention.

The first milestone is a demoable Champion: a facilitation workflow that takes a vague, human-written OKR set and draws out the success criteria, guardrail metrics and anti-targets its authors were silently assuming.

Roughly in order:

- [ ] v1 OKR schema and YAML loader
- [ ] Graph model and validation (referential integrity across a network of goals, not a tree)
- [ ] Champion facilitation workflow
- [ ] Conductor agent registry and wiring lint
- [ ] Shepherd continuous watch and feedback loop

## Quickstart

*Coming with the v1 schema.* It will be: create an OKR repo, write one objective, run `okr validate`.

## The thinking behind it

This repo implements an architecture argued for in a three-part series written for technology leaders:

1. [So Many Agents, Achieving So Little](https://medium.com/@ash.pirnia/so-many-agents-achieving-so-little-adf5ebe71b06) — why AI transformation is an organisational design problem, not a tooling one, and where the Champion, Conductor and Shepherd fit
2. [What Agents Reveal About Your Goals](https://medium.com/generative-ai/what-agents-reveal-about-your-goals-46b92374828b) — the hidden interpretive layer humans supply for free, why Goodhart's law becomes a six-week catastrophe at agent speed, and six diagnostic questions for your own OKR set
3. [Two Banks and a River: Bridging OKRs and Agents](https://medium.com/generative-ai/two-banks-and-a-river-bridging-okrs-and-agents-9fb050c47176) — how the three roles form a loop rather than a beam, and why every drift caught becomes a new line of spec

## Contributing

Not yet set up for outside contributions, but issues and discussion are welcome while the schema is still soft. If you have run OKRs at scale and think the format is missing something — or is carrying a field that would never survive a real quarter — that is exactly the feedback worth having now.

## Licence

Apache 2.0. See [LICENSE](LICENSE).
