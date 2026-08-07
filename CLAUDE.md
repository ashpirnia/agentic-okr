# CLAUDE.md

Context for Claude Code working in this repo. These are the invariants — read them before proposing changes, and push back if a request violates one rather than quietly complying.

## What this is

`agentic-okr` is a **tool**. It lets an organisation write its OKRs as machine-readable specs in git, precisely enough that agents can be pointed at them. Three roles sit on top of that spec: the **Champion** helps humans write it, the **Conductor** wires agents to it and lints the connection, the **Shepherd** watches for drift and feeds what it catches back as new spec.

Only the Champion is being built. Conductor and Shepherd exist in this repo as an event contract and a reserved wiring field, nothing more.

## The two repos — read this first

This is the distinction most likely to be got wrong, and it is wrong in a way that is hard to unpick later.

| | **This repo** (`agentic-okr`) | **An OKR repo** |
| :--- | :--- | :--- |
| Owner | Us, the maintainers | An adopting organisation |
| Contains | Python: schema, loader, validator, agent | YAML only. No Python. |
| Versioned by | Semver releases | The org's own commit history |
| Audience | Developers | Goal owners — support leads, heads of product |
| Example | `src/agentic_okr/` | `acme-okrs/okrs/support/2026-q3.yaml` |

**The tool never writes to its own repo at runtime.** It reads an OKR repo it was pointed at. That is the entire relationship between them.

A support lead raising a PR to add a guardrail must never have to look at our `src/` tree. When writing docs, error messages or CLI help, always be explicit about which repo you mean — say "your OKR repo", never a bare "the repo".

`examples/` in this repo is the one deliberate overlap: hand-written OKR sets used as test fixtures. They must be **shaped exactly like a real OKR repo**, marker file and all, or they will quietly encode assumptions no real repo satisfies.

## Invariants

**Git holds intent. The database holds observation.**
This governs the *OKR repo*. Objectives, key results, success criteria, guardrail metric *definitions*, anti-targets, restraint clauses, ownership and links go in YAML under version control. Current KR values, KPI readings, time series and drift alerts do not — they belong in a database that does not exist yet. If a proposed field would be written by a machine on a schedule, it is observation and it does not go in the schema. An OKR repo whose commit log is destroyed by progress numbers within a quarter has lost the only property that made this worth doing.

**Never validate a partial graph.**
An OKR repo root is marked by an `okr.yaml` declaring `schema_version` and `okr_dir`. The loader finds it by walking up from the given path (as git does), then loads the *whole* graph. Validating only the subdirectory a user happened to point at produces phantom dangling references, or worse, silently passes a fragment. Both are wrong answers that look like right ones, and the Conductor will later lint against this loader.

**The schema is thin on purpose.**
A field earns its place only if the Champion can elicit it from a human *today*. Not because the Conductor or Shepherd might need it later. Adding a field is cheap; restructuring one we got wrong means migrating every file in every repo using it. When in doubt, leave it out and note it in the build log. Every field must trace to an ADR in `docs/adr/` — if you find yourself adding one that doesn't, stop and raise it.

**`schema_version` is non-optional, from the first commit.**
Declared once per OKR repo, in `okr.yaml`. The loader validates it against a supported set and fails clearly on mismatch. Never make it default or infer it.

**`core` never imports `champion`.**
`core/` is the schema, loader, graph and validator — a library with no LLM dependency, installable and runnable without an API key. `champion/` is the agent workflow and depends on `core`. The dependency runs one way only. The Conductor's lint will later sit on `core` too, which is the reason for the split.

**The goal topology is a graph, not a tree.**
A key result can support multiple parent objectives. OKRs are created both cascading (top-down) and laddering (bottom-up). Any code, test or example that assumes a single parent is wrong. Referential integrity is not free in flat files — dangling IDs and accidental cycles are the failure mode this project exists to prevent, so validation is a first-class feature, not a nicety.

**Errors carry stable codes.**
Validation violations get machine-readable codes (e.g. `E001_DANGLING_REF`), because the Conductor will consume them later. Never let a validation failure surface as a raw traceback, and never write a test that asserts on error message text — assert on the code.

## Vocabulary

Fixed terms, taken from the published articles. Use them exactly; do not introduce synonyms.

| Term | Means |
| :--- | :---- |
| **OKR repo** | An adopting organisation's goal repo. YAML only, rooted at an `okr.yaml`. Never means *this* repo. |
| **Goal graph** | The resolved in-memory network built from one OKR repo. |
| **Objective** | The qualitative thing you want to achieve. |
| **Key result** | The measurable signal that you are getting there. |
| **Success criterion** | What "done" actually means, written for a reader with no judgment. |
| **Guardrail metric** | A metric that must hold while the key result moves. Definition only in git; readings live elsewhere. |
| **Anti-target** | A one-sentence description of an action that would hit the metric while betraying its spirit. |
| **Restraint clause** | A thing you would never do to hit the number, stated outright. |
| **Wiring** | The link from an agent's goal to the OKR it serves. Conductor's job; reserved and unpopulated here. |
| **Lint** | The Conductor's static, wiring-time check that an agent's target matches the spec's intent. |
| **Watch list** | The set of guardrail metrics the Shepherd monitors. Grows through the loop. |

## Layout

This repo (the tool):

```
src/agentic_okr/
  core/       schema, loader, graph, validation — no LLM dependency
  champion/   facilitation agent (LangGraph) — depends on core
docs/adr/     architecture decision records; every schema field traces to one
examples/     fixture OKR repos, each shaped like a real one
tests/
```

An OKR repo (what a user owns — for reference, we do not ship this):

```
acme-okrs/
  okr.yaml                    # marker: schema_version, okr_dir
  okrs/
    company/2026-q3.yaml
    support/2026-q3.yaml
```

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
okr validate    # load, resolve, validate the whole graph; non-zero exit on violation
okr score       # completeness score with per-dimension breakdown
okr graph       # print the resolved graph
```

## Conventions

- Python 3.14, `uv` for everything. Never invoke `pip` or a bare `python`.
- Ruff config lives in `pyproject.toml` and is authoritative. Do not add a separate linter or formatter.
- Prefer a library function with a thin CLI wrapper over logic living in the CLI. The graph object is the public API; the CLI is one consumer of it.
- Tests assert on error codes and golden files, not on prose.

## Working agreements

- **Follow the ADR.** If `docs/adr/` covers the decision, implement it as written. If it doesn't, or if implementing it reveals the ADR is wrong, stop and say so — do not decide silently in code.
- **Log the surprises.** Design decisions, rejected alternatives and anything unexpected go in `docs/BUILD_LOG.md` as you go. This repo's build is being written up publicly, and reconstructing the log afterwards produces a worse and less honest article.
- **The completeness score measures whether a spec is filled in, not whether the OKR is good.** Do not let that distinction blur in code, output text or docs.
- **Write for the goal owner, not the developer.** Validation errors, CLI help and schema docs are read by a support lead in a PR review, not by us. No Python identifiers, no stack traces, no "see `core/loader.py`".
