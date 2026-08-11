# ADR-0008 — The `okr.yaml` repo marker

**Status:** Accepted
**Date:** 2026-08-07
**Deciders:** Ash, Claude

## Context

An OKR repo needs a file at its root that says "this directory is an OKR repo, and here is how to read it" — the job `pyproject.toml` does for a Python project.

The motivating failure is specific and quiet. Without a marker, `okr validate okrs/support/` reads only that directory. Support's key results reference a company objective living in `okrs/company/`, outside the path given. The validator then either reports dangling references that are not real, or — worse — validates a fragment of the graph and passes. Both are wrong answers that look like right ones, and the second is undetectable from the output.

That matters more than it would in most tools, because [ADR-0006](0006-edge-semantics.md)'s review routing and the future Conductor's lint both sit on this loader. A partial graph does not just produce a bad validation result; it produces a bad *reviewer list*, silently omitting the team a change actually affects.

A second force: the schema is a published contract ([ADR-0002](0002-two-repos.md)). Files conforming to it live in other organisations' repositories, so version identification has to exist from the first commit rather than being retrofitted.

## Decision

**An OKR repo root is the directory containing `okr.yaml`.** The loader finds it by walking up from the working directory, as git does with `.git`.

### Contents

```yaml
schema_version: 1            # required — validated against a supported set
period: 2026-Q3              # required — time-bounds every key result
okr_dir: okrs/               # required — where goal files live
metrics_file: metrics.yaml   # optional — defaults to metrics.yaml
owners_file: owners.yaml     # optional — defaults to owners.yaml (ADR-0010)
```

Four fields plus two optional path overrides, and **nothing else**. Organisation name, team registry, default owner, cadence configuration and notification settings will all be proposed; each is refused until something reads it. This file will attract accretion precisely because it is the obvious place to put anything global.

### Failure behaviour

**No marker found after walking to the filesystem root** is an error. The message names the directories searched and points at `okr init`. The loader never falls back to treating the working directory as a root — that reintroduces exactly the partial-graph failure the marker exists to prevent.

**An explicit path argument overrides the walk-up, but must itself contain a marker.** `okr validate ../acme-okrs` works; `okr validate okrs/support/` does not. There is no supported way to load a subdirectory as though it were a whole graph.

**`schema_version` is matched exactly** against the set of supported versions. v1 supports exactly `1`. Anything else fails with a message naming what was found and what is supported. No coercion, no defaulting, no inference.

**`period` is a non-empty free string.** Not a validated pattern.

`2026-Q3` is the recommended convention, alongside `2026-H1` and `2026-07`, and `okr init` scaffolds it — but organisations run halves, trimesters, thirteen-week cycles and fiscal years that start in April, and a pattern tight enough to be useful would exclude some of them. Nothing parses it: it labels the repo for a human reader, and comparing two periods is string inequality. Validation checks that it is present and non-empty, which is all a schema can honestly assert about a label.

## Consequences

**The whole graph is loaded, always.** Every consumer — the validator, the completeness score, `okr diff`, the reviewer list, the future Conductor lint — operates on a complete graph by construction rather than by the caller having remembered to point at the right directory.

**Working from a subdirectory behaves like git.** Running `okr validate` from inside `okrs/support/` validates the entire repo, which is what `git status` would do and therefore what people will expect.

**Explicit paths serve automation without opening the hole.** CI, cross-repo tooling, and [task 1.15](../../EXECUTION_PLAN.md)'s foreign-repo check all need to point at a root that is not the working directory. Requiring a marker at the target keeps that capability from becoming a documented route to partial validation — which is the form this failure would otherwise take, because people reach for a narrower scope exactly when full validation feels slow or noisy.

**The period is declared once and time-bounds everything.** Doerr defines key results as time-bound; putting the cycle here satisfies that by construction without a deadline field on every key result, and keeps [ADR-0003](0003-v1-scope.md)'s single-cycle cut honest — a repo whose files span two quarters has nowhere to say so.

**Rollover is a single-line change plus new content.** Editing `period` and replacing the goal files is the whole operation. No identifier rewriting, because [ADR-0007](0007-id-scheme-and-layout.md) keeps the period out of IDs.

**Exact version matching means v2 arrives as a hard failure, deliberately.** A v1 tool reading a v2 repo stops with a clear message rather than proceeding on a guess. Whether v2 tools accept v1 repos is a decision for v2, made when there is a real migration to reason about rather than a hypothetical one.

**The marker is a second thing an adopter must understand.** Mitigated by `okr init` generating it, so nobody writes one by hand, and by keeping it to four fields — three of which are self-explanatory.

## Alternatives rejected

**No marker; the CLI takes a directory argument.** One less concept, and every file could carry its own `schema_version`. Rejected because it makes partial-graph validation the default rather than an error: the tool would read whatever it was pointed at and report confidently on a fragment. It also scatters version identification across every file, so a migration that updates thirty files and misses a hundred and seventy leaves a repo with no declared intent about what version it is meant to be.

**Falling back to the working directory when no marker is found.** Convenient for someone who just wants to validate a folder of YAML without ceremony. Rejected because the convenience is indistinguishable from the failure. Someone in the wrong directory gets a pass on an empty or partial graph, and a validator that passes when it should have refused is worse than one that is occasionally annoying.

**Allowing an explicit path to point at any subdirectory.** Useful for iterating on one team's file without validating the whole repo. Rejected because it is a documented, supported route to the exact silent failure this ADR exists to prevent — and it would be reached for under precisely the conditions that make the failure most likely to go unnoticed. If per-team iteration proves genuinely painful, the answer is a filtered *report* over a fully-loaded graph, not a partial load.

**Detecting the root by `.git` instead of a dedicated marker.** No new file at all, and OKR repos are git repos anyway. Rejected because it conflates two things: an OKR repo need not be the whole git repo (an organisation might keep goals in a subdirectory of a larger monorepo), and it would leave `period`, `okr_dir` and `metrics_file` homeless. It would also make the tool silently dependent on git for something unrelated to version control.

**`schema_version` on every file rather than on the marker.** Allows a repo to migrate incrementally, file by file. Rejected because incremental migration is precisely the state that should not be representable: a repo half-migrated between schema versions has no coherent meaning, and nothing declares what it is *supposed* to be. One declaration per repo makes the migration atomic.

**Accepting older schema versions with a warning.** Forward-looking and kinder to adopters mid-migration. Rejected as untestable speculation — no older versions exist, so the code would encode assumptions about a migration path nobody has designed. It is also how a bug that only appears in v2 gets shipped in v1.

**A richer marker — organisation name, team registry, default owner, cadence.** Each is plausibly useful and the marker is the obvious home. Rejected wholesale on [ADR-0005](0005-node-types.md)'s thin-v1 rule: nothing reads any of them. A team registry is the most tempting, since it would let the tool validate that owner strings are real — but ownership resolution belongs with the Conductor, which knows about identity, and duplicating it here would create a second place for it to drift.

> **Refined by [ADR-0010](0010-owner-identity.md).** The rejection of a registry *on the marker* stands; the marker keeps its four fields. But the reasoning conflated two things. Declaring **which owner IDs exist** is vocabulary and belongs in the OKR repo — it now lives in `owners.yaml`, exactly as metric declarations do. Resolving an owner ID to a GitHub team or an email address is identity, and that remains the Conductor's. The marker gains an optional `owners_file` path alongside `metrics_file`.
