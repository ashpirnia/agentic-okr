# ADR-0002 — Two repos: the tool and the OKR repo

**Status:** Accepted
**Date:** 2026-08-07
**Deciders:** Ash, Claude

## Context

"OKRs as code" is the project's central claim, and it is ambiguous in a way that matters. It can mean *this repository contains OKRs*, or it can mean *this tool lets your organisation keep its OKRs in a repository of its own*. Only the second is true, and early drafts of the README, `CLAUDE.md` and the execution plan blurred it — each said things like "the goal graph lives in git" without ever saying whose git.

The blur is not cosmetic. A reader arriving at a repo named `agentic-okr` and finding a directory of YAML OKRs will reasonably conclude that adopting the tool means committing their goals here, or forking it. Neither is right, and both are hard to walk back once anyone has done it.

There are two artefacts with almost nothing in common:

| | **The tool** (`agentic-okr`) | **An OKR repo** |
| :--- | :--- | :--- |
| Owner | The maintainers | An adopting organisation |
| Contains | Python: schema, loader, validator, agent | YAML only. No Python. |
| Versioned by | Semver releases | The org's own commit history |
| Changes when | We ship a feature | The org changes what it means |
| Audience | Developers | Goal owners — support leads, heads of product |
| Served by | The Conductor, which agent developers register against | The Champion, which goal owners are facilitated by |
| Lifecycle | Ours | Theirs, and it outlives any version of ours |

The audience row is the one with teeth. The person raising a pull request to add a guardrail is a support lead, not an engineer. If reviewing that PR requires them to be looking at a Python source tree, the "goal changes get reviewed like code" promise quietly fails — not because the mechanism is wrong, but because the people it was for cannot use it.

## Decision

**`agentic-okr` is a tool. An OKR repo is a separate artefact owned by an adopting organisation. The tool reads an OKR repo it is pointed at, and never writes to its own repo at runtime.**

Consequences that follow directly and are binding:

- **One OKR repo is one goal graph.** The tool loads exactly one repo per invocation. Cross-repo references are not supported in v1; an organisation wanting several business units in one graph puts them in one repo, in separate directories.
- **`examples/` in this repo holds fixture OKR repos**, each a complete repo shape including its `okr.yaml` marker. They are the one deliberate overlap. They must never become a special case the loader knows about.
- **Docs, CLI help and error messages say "your OKR repo"**, never a bare "the repo". Where the sentence is about this repository, say "the `agentic-okr` source".
- **User-facing output is written for a goal owner**, not a developer. No Python identifiers, no tracebacks, no `see core/loader.py`. A validation error is read in a PR review by someone who has never opened our source.
- **The tool must run correctly against an OKR repo on any path**, unrelated to its own checkout. This is verified explicitly rather than assumed (plan task 1.15).
- **The tool scaffolds, rather than requiring people to guess the layout.** An `okr init` command creates a valid empty OKR repo. This is the moment the layout gets taught, and it is cheap.

## Consequences

**The `okr.yaml` marker becomes load-bearing rather than decorative.** If OKR repos are foreign directories on arbitrary paths, the tool needs a reliable way to identify one and find its root. ADR-0007 covers the marker; this decision is why it exists.

**Path handling has no safe defaults.** Nothing may resolve relative to the tool's own installation directory, and no fixture may be findable by accident. Bugs of this class are invisible in development — everything works because everything happens to be in one tree — and appear only for the first real adopter. Task 1.15 exists to surface them while the loader is still small.

**Phase 3's demo dataset lives in its own public repo.** It is a real OKR repo owned by a fictional organisation, which is what lets the article link to an actual pull request adding a guardrail the Shepherd discovered. It also means the tool is dogfooded against a foreign repo before anyone else tries it.

**The schema is a published contract, not an internal detail.** Files in other people's repositories conform to it, so `schema_version` and a migration story are obligations rather than nice-to-haves. This is a real cost and it constrains how freely the schema can change after v1 — which is precisely the pressure that keeps it thin.

**Two release cadences to think about.** The tool ships versions; an OKR repo has a history that must keep loading across them. A repo written today should still validate against next year's tool, or fail with a message that says exactly how to migrate.

**Support and documentation split in two.** Developer-facing docs live here; goal-owner-facing guidance is about a repo we do not own and cannot see. Not a v1 problem, but the README already has to serve both readers, which is why it opens with the two-repo table.

**Deferred: multi-repo organisations.** A large org may genuinely want one repo per business unit with key results laddering across them. v1 says no, because cross-repo reference resolution and validation is a substantial problem and nobody has asked for it yet. If it arrives, it arrives as an ADR, not as a quiet loader change.

## Alternatives rejected

**One repo containing both the tool and the OKRs.** Simplest to start, one thing to clone, and the demo is trivial to set up. Rejected because it makes every adopter either fork the tool or commit their goals into someone else's project. Both are wrong, and the second is worse than it sounds: an organisation's goal history is sensitive, it outlives our tool, and it should never have our release cadence imposed on it. This is the alternative that happens by accident if the decision is not written down, which is the reason for writing it down.

**A convention rather than a decision — "obviously they're separate."** Rejected on evidence. It *was* obvious, and it still leaked into three documents inside a week, because the ambiguity lives in the phrase "OKRs as code" itself. Anything that reasserts itself under mild pressure needs to be written, not assumed.

**Ship a template OKR repo as the primary onboarding path.** A GitHub template repo an org clicks "use this template" on. Rejected as the *primary* path because it puts the layout in a place that drifts from the validator, and because a template repo is a second artefact to maintain and version. `okr init` generating the same structure from the code that validates it cannot drift. A template repo remains a reasonable convenience to add later.

**Support cross-repo references in v1.** Would let a large organisation split by business unit immediately. Rejected as premature: it requires resolving references across repositories that may be at different commits, different schema versions, or simply not present, and every one of those is a validation question with no obvious answer. One repo, one graph, until someone has a real problem it does not solve.
