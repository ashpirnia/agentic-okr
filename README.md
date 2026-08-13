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

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for diagrams of the components, the ownership boundary, and the loop — with what is built in v1 marked apart from what is designed and deferred. [docs/GLOSSARY.md](docs/GLOSSARY.md) defines every term, marking standard OKR vocabulary apart from what this project adds. [docs/GRAPH-BY-EXAMPLE.md](docs/GRAPH-BY-EXAMPLE.md) walks a three-team organisation through the whole format — the graph drawn, then the YAML that produces it.

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

## What runs where

"Stored in git" invites a fair objection: if goals live in GitHub, isn't GitHub the database, and isn't claiming platform independence like claiming database independence?

Partly. The distinction that holds is that **the datastore is git, not a git host**. Your OKRs are git objects — the same bytes on GitHub, GitLab, Bitbucket, a bare repo on your own server, or a laptop with no remote at all. That is one format, not a compatibility layer over several.

What *isn't* git is the review workflow. Pull requests, `CODEOWNERS` and reviewer assignment are host features, and this architecture leans on review to turn a declared dependency into an accepted commitment.

| | Depends on | Works on |
| :--- | :--- | :--- |
| Your YAML files | a filesystem | anything |
| History, blame, semantic diff | git | any host, or none |
| `init` · `validate` · `score` · `graph` · `diff` | git | any host, or none |
| Review as the acceptance mechanism | a host with merge requests | GitHub, GitLab, Bitbucket, Gitea, Gerrit — API differs |
| `okr codeowners` output | host-specific format | GitHub and GitLab share syntax; others differ |
| Requesting a reviewer automatically | a host's API | shipped as an editable GitHub Actions example |

So the accurate claim is narrower than "platform agnostic": **your data is portable everywhere; the automation assumes a host with reviews and path-based ownership, and the examples are GitHub.** An organisation on Bitbucket keeps every file and every command, and rewrites roughly forty lines of CI.

That boundary is deliberate and worth defending — no API client lives in this codebase. If that ever changes, this section has to shrink.

## What this is not

- **Not an OKR SaaS.** No web UI, no dashboards, no hosted service. A CLI and a directory of YAML.
- **Not a replacement for human judgment.** The Champion is a facilitator, not an author. It interrogates an objective for its missing success criteria, unstated guardrails and plausible anti-targets, and pushes the owner to supply them. It narrows the gap between what you wrote and what you meant. It does not close it, and any tool claiming otherwise is selling you the problem again.
- **Not a scoring system for whether your OKRs are good.** The completeness score measures whether a spec is *filled in*. Whether the objective is the right one to pursue is your job.
- **Not an integration layer.** No connectors to Viva Goals, Lattice or Workday.

## Status

Early, and pre-alpha. The schema is being designed; nothing here is production-ready and the format is unstable by intention.

**Who v1 is for.** People comfortable with a terminal, git and YAML. Goal owners — heads of support, heads of product — are the people this is ultimately *for*, but they are not expected to hand-write specs, and v1 does not yet give them a way not to. The intended surface is the Champion: a conversation where the agent interrogates an objective and emits the spec, so the owner never opens a file. v1 ships the batch-critique half of that, which still assumes someone can read a YAML pull request. Closing that gap is the first thing after v1, not a detail.

The first milestone is a demoable Champion: a facilitation workflow that takes a vague, human-written OKR set and draws out the success criteria, guardrail metrics and anti-targets its authors were silently assuming.

Roughly in order:

- [ ] v1 OKR schema and YAML loader
- [ ] Graph model and validation (referential integrity across a network of goals, not a tree)
- [ ] Champion facilitation workflow (batch critique)
- [ ] A surface goal owners can actually use — conversational Champion, then a form over git
- [ ] Conductor agent registry and wiring lint
- [ ] Shepherd continuous watch and feedback loop

## Quickstart

Create an OKR repo, write a goal, check it. No API key, no account, no database — this half of the tool needs none of them.

Not on PyPI yet — install it from here. Either line works, and both put an `okr` command on your PATH:

```bash
uv tool install git+https://github.com/ashpirnia/agentic-okr    # also fetches a Python if you need one
pipx install git+https://github.com/ashpirnia/agentic-okr       # if you already have Python 3.12+
```

Then:

```bash
mkdir acme-okrs && cd acme-okrs
okr init                          # asks which cycle these goals cover
```

That scaffolds a repo whose files are almost entirely comments — prose explaining each one, then a commented example to uncomment and edit:

```
acme-okrs/
  okr.yaml                     # schema_version, period, where things live
  metrics.yaml                 # what your organisation measures
  owners.yaml                  # who exists
  okrs/support/2026-q3.yaml    # one team's goals
```

Edit the goal file, then:

```bash
okr validate    # errors and warnings, grouped by file, with locations
okr graph       # the goal graph as a tree, plus every connection written by hand
```

`okr validate` exits non-zero when something needs fixing, so it works as a CI check on a goal repo — which is useful to an organisation with no interest in the agent at all. `--json` on either command gives machine-readable output.

For what a filled-in organisation looks like, see [docs/GRAPH-BY-EXAMPLE.md](docs/GRAPH-BY-EXAMPLE.md): three teams, all five edge shapes, and the YAML behind the diagram.

> Pre-alpha, and the schema is unstable by intention. `schema_version` is checked exactly, so a repo written today will refuse to load against a tool that has moved on rather than being read on a guess. If something looks wrong, `okr --version` prints the commit you are on — worth quoting, since installing from a branch means the version number alone does not identify it.

## The thinking behind it

This repo implements an architecture argued for in a three-part series written for technology leaders:

1. [So Many Agents, Achieving So Little](https://medium.com/@ash.pirnia/so-many-agents-achieving-so-little-adf5ebe71b06) — why AI transformation is an organisational design problem, not a tooling one, and where the Champion, Conductor and Shepherd fit
2. [What Agents Reveal About Your Goals](https://medium.com/generative-ai/what-agents-reveal-about-your-goals-46b92374828b) — the hidden interpretive layer humans supply for free, why Goodhart's law becomes a six-week catastrophe at agent speed, and six diagnostic questions for your own OKR set
3. [Two Banks and a River: Bridging OKRs and Agents](https://medium.com/generative-ai/two-banks-and-a-river-bridging-okrs-and-agents-9fb050c47176) — how the three roles form a loop rather than a beam, and why every drift caught becomes a new line of spec

## Contributing

Not yet set up for outside contributions, but issues and discussion are welcome while the schema is still soft. If you have run OKRs at scale and think the format is missing something — or is carrying a field that would never survive a real quarter — that is exactly the feedback worth having now.

## Licence

Apache 2.0. See [LICENSE](LICENSE).
