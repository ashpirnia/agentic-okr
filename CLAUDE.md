# CLAUDE.md

Context for Claude Code working in this repo. These are the invariants — read them before proposing changes, and push back if a request violates one rather than quietly complying.

## What this is

`agentic-okr` is a **tool**. It lets an organisation write its OKRs as machine-readable specs in git, precisely enough that agents can be pointed at them. Three roles sit on top of that spec: the **Champion** helps humans write it, the **Conductor** wires agents to it and lints the connection, the **Shepherd** watches for drift and feeds what it catches back as new spec.

Only the Champion is being built, and only its specification half. Conductor and Shepherd exist in this repo as an event contract, nothing more. See ADR-0003 for the full list of v1 cuts and why each was made — check it before proposing anything that sounds like scope.

**The three own different things.** Champion: what you meant (git). Conductor: how it is hooked up — the agent registry, agent→key-result wiring, and where each KR's value is read from. Shepherd: what happened (its own store). Each has a different primary audience — goal owners, agent developers, and leaders respectively.

**Wiring points from agents to key results, never the reverse.** The OKR spec has no field listing which agents serve a KR, and adding one is a mistake, not an oversight. Agents are numerous and redeployed constantly; key results are few and slow. Listing agents in the OKR YAML would make every deployment a commit to the goal repo, destroying the commit log exactly as progress numbers would.

## The two repos — read this first

This is the distinction most likely to be got wrong, and it is wrong in a way that is hard to unpick later. See ADR-0002.

| | **This repo** (`agentic-okr`) | **An OKR repo** |
| :--- | :--- | :--- |
| Owner | Us, the maintainers | An adopting organisation |
| Contains | Python: schema, loader, validator, agent | YAML only. No Python. |
| Versioned by | Semver releases | The org's own commit history |
| Audience | Developers | Goal owners — support leads, heads of product |
| Example | `src/agentic_okr/` | `acme-okrs/okrs/support/2026-q3.yaml` |

**The tool never writes to its own repo at runtime.** It reads an OKR repo it was pointed at. That is the entire relationship between them.

A support lead raising a PR to add a guardrail must never have to look at our `src/` tree. When writing docs, error messages or CLI help, always be explicit about which repo you mean — say "your OKR repo", never a bare "the repo".

**`examples/` and `tests/fixtures/` are different things and must never be the same files.**

- **`examples/`** is shipped and read by adopters. Everything in it is something to copy: exemplary specs, a plausible organisation, no field left out that a real goal would carry. Nothing in it may model a mistake.
- **`tests/fixtures/`** exists for coverage. Deliberately bad specs belong here — an anti-target with no defence, a build-trapped objective, a dangling reference — because a check cannot be proven to fire without input that trips it.

The two pull in opposite directions, and the sharpest case shows why: proving K4 works needs an anti-target with *no* defence, and shipping that as an example teaches exactly what the check exists to catch.

Both must be **shaped exactly like a real OKR repo**, marker file and all, or they quietly encode assumptions no real repo satisfies.

## Invariants

**Three stores, three owners.** See ADR-0001.

| Category | Example | Owner |
| :--- | :--- | :--- |
| **Intent** — what you meant | "reopen rate must not exceed 8%" | Champion, in git |
| **Measurement config** — how to find out | "reopen rate comes from Zendesk API X" | Conductor |
| **Observation** — what happened | "reopen rate was 8.1% on Tuesday" | Shepherd, its own store |

Only intent goes in the OKR repo: objectives, key results, success criteria, guardrail metric *definitions*, anti-targets and the restraints nested inside them, and ownership.

**The test:** if a field would be written by a machine on a schedule, it is observation and does not go in the schema. No exceptions for "just a small number" — a single `current_value` field is how this erodes, and it will be requested. If a field carries a connection detail or credential, it is measurement config and belongs to the Conductor. An OKR repo whose commit log is destroyed by progress numbers within a quarter has lost the only property that made this worth doing.

**Never imply the user must provide a database.**
The Shepherd owns its store — schema, migrations, retention — and will ship with bundled SQLite so the default requires no provisioning. An org may host it elsewhere; that is an option, not a prerequisite. It is derived data, not a system of record: the raw KPIs already live in the org's own tools. Nothing in the docs, CLI help or README should suggest otherwise, and v1 needs no persistence at all.

**Never validate a partial graph.**
An OKR repo root is marked by an `okr.yaml` declaring `schema_version`, `period` and `okr_dir`, plus optional `metrics_file` and `owners_file`. The loader finds it by walking up from the given path (as git does), then loads the *whole* graph. An explicit path may override the walk-up but must itself contain a marker — there is no supported way to load a subdirectory as though it were whole. Validating a fragment produces phantom dangling references, or worse, passes silently. Both are wrong answers that look like right ones, and both review routing and the future Conductor lint sit on this loader, so a partial graph produces a wrong *reviewer list* too. See ADR-0008.

**Join keys are declared, never free text.**
Metrics (`metrics.yaml`) and owners (`owners.yaml`) are declared once and referenced by ID; an unresolvable reference is an error in the same class as a dangling edge. Both are join keys — a metric's identity joins git to the Conductor's sources and the Shepherd's readings, an owner's identity drives review routing. Unvalidated strings drift silently: `csat` and `CSAT` become two metrics, `head_of_support` and `head-of-support` become two people and a cross-team review routes to neither. Never accept a bare string where a declared reference belongs. See ADR-0009 and ADR-0010.

**The schema is thin on purpose.**
A field earns its place only if the Champion can elicit it from a human *today*. Not because the Conductor or Shepherd might need it later. Adding a field is cheap; restructuring one we got wrong means migrating every file in every repo using it. When in doubt, leave it out. Every field must trace to an ADR in `docs/adr/` — if you find yourself adding one that doesn't, stop and raise it. See ADR-0005 for the node set and the test that produced it: a concept is a first-class node only if something outside its parent references it by ID.

**`schema_version` is non-optional, from the first commit.**
Declared once per OKR repo, in `okr.yaml`. The loader validates it against a supported set and fails clearly on mismatch. Never make it default or infer it.

**`core` never imports `champion`.**
`core/` is the schema, loader, graph and validator — a library with no LLM dependency, installable and runnable without an API key. `champion/` is the agent workflow and depends on `core`. The dependency runs one way only. The Conductor's lint will later sit on `core` too, which is the reason for the split. Agent dependencies live in the optional `agent` extra. Never add a convenience import that breaks the minimal install. `tests/test_minimal_install.py` reads the source of everything outside `champion/` and fails on a module-level import of the extra or of `champion`; CI runs a second job that installs without extras. An optional dependency reached from shared code goes inside the function that needs it.

**No API client in this codebase.**
The datastore is git, not a git host. Every core command — `init`, `validate`, `score`, `graph`, `diff` — must work against a bare repo with no remote. Host-specific behaviour is confined to two places: output *formats* selected by `--platform`, and editable example workflows under `.github/`. Never add an HTTP call to a hosting platform, never import a platform SDK, and never make a core command depend on a remote existing. The README's portability claim is only true while this holds.

**Nothing leaves the machine by default.**
LangSmith tracing is opt-in via environment variable. Trace payloads carry prompt content, which here is an organisation's OKRs. Never enable it in code, a config default, or a test fixture. Checkpoints go in the OS app-data directory, never the OKR repo. The model is pinned to `claude-sonnet-5` — never substitute an alias, because article evidence has to stay reproducible. See ADR-0004.

**The goal topology is a graph, not a tree.**
A key result can support multiple parent objectives. OKRs are created both cascading (top-down) and laddering (bottom-up). Any code, test or example that assumes a single parent is wrong. Referential integrity is not free in flat files — dangling IDs and accidental cycles are the failure mode this project exists to prevent, so validation is a first-class feature, not a nicety.

Edges are declared on the **needy side**: a child declares what it `supports`, a dependent declares what it `depends_on`, and nothing is ever declared on the parent or provider. Cycles in `supports` are errors; cycles in `depends_on` are warnings that still exit zero, so the validator needs severity levels. See ADR-0006 and ADR-0007.

**Errors carry stable codes.**
[`docs/ERROR_CODES.md`](docs/ERROR_CODES.md) is the registry — 38 codes across six bands, one of them reserved and never raised. It is a **published contract**: a code's meaning never changes, retired codes stay reserved, and new checks get new codes rather than widening an existing one. Severity is part of the contract too — `E` fails and exits non-zero, `W` reports and exits zero.

Never invent a code inline; add it to the registry first. Never let a validation failure surface as a raw traceback. Never write a test that asserts on message text — assert on the code.

## Vocabulary

**[`docs/GLOSSARY.md`](docs/GLOSSARY.md) is the single source for every term.** Read it before writing user-facing text, field docstrings, or agent prompts.

Do not restate a definition here, in the README, in a docstring, or in a prompt. Link to the glossary instead. Definitions copied into four places drift, and the drift that matters is between the Champion's prompt (which explains what an anti-target *is*, in order to elicit one) and the schema's docstring (which says what gets stored). When those disagree the agent elicits the wrong thing, and both halves look correct in isolation.

Use the terms exactly as defined; never introduce a synonym. If a definition needs to change, that is an ADR, not an edit — several are published in the article series.

## Layout

This repo (the tool):

```
src/agentic_okr/
  core/       schema, loader, graph, validation — no LLM dependency
  cli/        the `okr` command (Typer + rich) — one consumer of core, renders only
  champion/   facilitation agent (LangGraph) — depends on core
docs/adr/     architecture decision records; every schema field traces to one
examples/     fixture OKR repos, each shaped like a real one
              scaffold/ is generated — the verbatim output of `okr init`, and a
              test fails if it stops matching, so the two cannot teach different shapes
tests/
```

An OKR repo (what a user owns — for reference, we do not ship this):

```
acme-okrs/
  okr.yaml          # marker: schema_version, period, okr_dir,
                    #   optional metrics_file and owners_file
  metrics.yaml      # declared metric vocabulary — ADR-0009
  owners.yaml       # declared owners, optional platform handles — ADR-0010
  okrs/             # one file per team is the recommended layout,
    company/2026-q3.yaml    #   but the loader is layout-agnostic
    support/2026-q3.yaml
    platform/2026-q3.yaml
```

A worked example with the YAML behind it is in [`docs/GRAPH-BY-EXAMPLE.md`](docs/GRAPH-BY-EXAMPLE.md).

## Commands

```bash
uv sync                      # install, including dev group
uv run pytest                # tests
uv run ruff check .          # lint
uv run ruff format .         # format
uv run pre-commit install    # once, per clone
```

CLI (built in Phase 1, entry point `okr`). Run from anywhere inside an OKR repo — the path argument is optional and defaults to walking up for `okr.yaml`:

```bash
okr init        # scaffold a valid empty OKR repo; prompts for --period
                #   never overwrites, and refuses inside an existing OKR repo
okr validate    # load, resolve, validate the whole graph; non-zero exit on violation
                #   --json  the same report for a machine
okr score       # completeness score: `n of m`, per KR, per objective, repo roll-up
                #   --json  every check by its rubric label, so the total can be recounted
                #   always exits zero — a low score is a measurement, not a failure
okr graph       # print the resolved graph as a tree plus an adjacency view
                #   --json  nodes and edges, flat
okr diff        # graph-level diff between two revisions, rendered in prose
                #   --reviewers  owners affected by cross-boundary edge changes
okr codeowners  # derive a CODEOWNERS mapping; prints to stdout, never writes
```

Exit codes are the contract with CI and only two are used: `0` when nothing failed — warnings are reported and exit zero — and `1` when there is something to fix, whether validation found it or the repo could not be read at all.

Every one of these must work against a bare repo with no remote.

## Conventions

- Python 3.14, `uv` for everything. Never invoke `pip` or a bare `python`.
- Ruff config lives in `pyproject.toml` and is authoritative. Do not add a separate linter or formatter.
- Prefer a library function with a thin CLI wrapper over logic living in the CLI. The graph object is the public API; the CLI is one consumer of it.
- Tests assert on error codes and golden files, not on prose.

## Working agreements

- **Follow the ADR.** `docs/adr/` is the source of truth; this file is a summary of it. If an ADR covers the decision, implement it as written. If it doesn't, or if implementing it reveals the ADR is wrong, stop and say so — do not decide silently in code.
- **If you made a call an ADR didn't settle, log it in the same commit.** [`docs/BUILD_LOG.md`](docs/BUILD_LOG.md) holds implementation decisions below the ADR threshold — where a boundary between modules falls, why a field is normalised, a library constraint that changed a shape. Not afterwards, and not a changelog. The test: would a future implementer otherwise rediscover this, or "fix" it without knowing it was deliberate?
- **This file drifts. Update it in the same commit.** When an ADR lands or is amended, check whether it changed anything stated here — an invariant, the layout, a marker field, a command. Summaries rot silently while every individual ADR stays correct, and a stale invariant is worse than a missing one because it will be believed.
- **The completeness score measures whether a spec is filled in, not whether the OKR is good.** Do not let that distinction blur in code, output text or docs. It is `n of m` and never a grade: no weights, no 0–10, no bar. Commitment level appears in exactly one place — the order findings are reported in — and changes no number. The worked example scores 12 of 19, asserted in `tests/test_score.py` against both ADR-0011 and `docs/GRAPH-BY-EXAMPLE.md`.
- **Write for the goal owner, not the developer.** Validation errors, CLI help and schema docs are read by a support lead in a PR review, not by us. No Python identifiers, no stack traces, no "see `core/loader.py`".
