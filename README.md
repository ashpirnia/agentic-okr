# agentic-okr

**OKRs as code: a machine-readable goal spec, plus the agent architecture that keeps AI work pointed at it.**

## The premise

Organisations are deploying agents faster than they can say what those agents are for. The local wins are real, but ask what all of it adds up to at the organisational level and the answer is usually a shrug. That is not a capability gap or a budget gap, it is a design gap: the goals were written for a human reader who supplies judgment and restraint for free, and agents supply neither. `agentic-okr` treats the goal spec as the missing layer. OKRs get written down precisely enough that something without judgment can follow them, and they are stored as code so they can be reviewed, diffed, and inherited by the next team and the next quarter. On top of that spec sit three roles: the **Champion** helps humans write the spec and holds it, the **Conductor** wires each agent to the OKR it is meant to serve and lints the connection before anything runs, and the **Shepherd** watches for the drift the wiring could not predict and feeds what it catches back into the spec as a new line of specification.

## Why the goal graph lives in git

The spec format is the product. Everything else in this repo is built on top of it.

Two write paths, deliberately kept apart:

- **Intent lives in git.** Objectives, key results, success criteria, guardrail metrics, anti-targets and ownership are low-volume, deliberate, and benefit from review. A change to what you meant should be a pull request with a diff someone reads.
- **Observation lives in a database.** Current metric values, KPI readings and drift signals are high-volume and machine-written. They have no business in version control.

The practical payoff: when the Shepherd discovers that agents found a way to game a goal, the new guardrail arrives as a PR with the evidence attached. A human merges it, and the trick is on the page for every fleet that follows.

## Status

Early. The schema is being designed and nothing is production-ready. The first milestone is a demoable Champion: a facilitation workflow that takes a vague, human-written OKR set and draws out the success criteria, guardrail metrics and anti-targets its authors were silently assuming.

Roadmap, roughly in order:

- [ ] v1 OKR schema and YAML loader
- [ ] Graph model and validation (referential integrity across a network of goals, not a tree)
- [ ] Champion facilitation workflow
- [ ] Conductor agent registry and wiring lint
- [ ] Shepherd continuous watch and feedback loop

## The thinking behind it

This repo is the implementation of a series written for technology leaders:

1. [So Many Agents, Achieving So Little](<url>) — why AI transformation is an organisational design problem, not a tooling one
2. [The second piece](<url>) — the hidden interpretive layer humans supply for free, and what happens when they stop
3. [Two Banks and a River: Bridging OKRs and Agents](<url>) — how the Champion, Conductor and Shepherd form a loop rather than a beam

## Contributing

Not yet set up for outside contributions, but issues and discussion are welcome while the schema is still soft. If you have run OKRs at scale and think the format is missing something, that is exactly the feedback worth having now.

## Licence

Apache 2.0. See [LICENSE](LICENSE).
