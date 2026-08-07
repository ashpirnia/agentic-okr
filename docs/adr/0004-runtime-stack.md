# ADR-0004 — Agent runtime stack

**Status:** Accepted
**Date:** 2026-08-07
**Deciders:** Ash, Claude

## Context

Phase 2 builds the Champion's facilitation agent. Choosing its stack during Phase 2 would turn a build phase into a research phase, so it is settled now, before the schema work that precedes it.

The choice is mostly uncontroversial — it is the stack we already know, and familiarity is worth more here than a marginally better fit. What is *not* uncontroversial is everything around the choice: where state lands, what leaves the machine, and whether output can be reproduced. Those are the parts a stack decision usually leaves implicit and later regrets.

Two constraints from earlier decisions shape this:

- **`core` must stay installable without an API key** (`CLAUDE.md`). The schema, loader and validator are the foundation the Conductor will later sit on, and they have no business requiring an LLM. Anyone should be able to `okr validate` with no account anywhere.
- **The tool writes only spec to a user's OKR repo** (ADR-0002). Agent state is not spec.

## Decision

**Stack:** LangGraph for the workflow, Claude Sonnet via `langchain-anthropic`, SQLite for checkpointing, LangSmith for tracing.

**Agent dependencies are an optional group.** `pip install agentic-okr` gets the schema, loader, validator and CLI. `pip install agentic-okr[agent]` adds the LangGraph stack. A test asserts that `core` imports cleanly with the agent group absent, so the boundary is enforced rather than intended.

**LangSmith tracing is off by default and opt-in.** Enabled by environment variable only. Our development environment sets it; a fresh install does not.

**Checkpoints live in the OS application-data directory**, not in the OKR repo and not in the working directory. Overridable by environment variable.

**The model is pinned to an exact identifier — `claude-sonnet-5` — never an alias.** The pinned ID is recorded alongside any agent output kept as evidence.

**The API key comes from the environment only.** `ANTHROPIC_API_KEY`, never a config file, never a CLI flag that lands in shell history.

**LangSmith project name:** `agentic-okr`.

## Consequences

**Adopters send nothing to a third party unless they choose to.** This is the consequence that most needed to be deliberate. Trace payloads contain prompt content, and prompt content here is an organisation's OKRs — often the most strategically sensitive documents they have. Defaulting tracing on would have shipped that decision invisibly, because it is invisible *to us*: our own config wants tracing on, so the wrong default would never surface in development. The README states plainly what is sent when tracing is enabled.

**Agent state stays out of the goal repo.** A checkpoint database in an OKR repo would sit in front of goal owners reviewing pull requests, and would depend on an ignore rule `okr init` must get right every time. Putting it in the app-data directory removes the failure mode instead of documenting it.

**Article evidence is reproducible.** A reader can run the demo against the same pinned model and get comparable output. Against a drifting alias they could not, and the evidence would quietly expire — the piece's central artefact is agent output, so this is not a small property.

**Model upgrades become explicit events.** Moving off `claude-sonnet-5` means changing a pin, which means re-running the demo dataset and checking whether the article's claims still hold. That is friction, and it is the right friction.

**Two install paths to keep working.** `core`-only and `[agent]` both need testing, and CI must cover the minimal install or the boundary will erode the first time someone adds a convenience import.

**LangGraph's interrupt support is unused in v1** but is the reason it stays the right choice. ADR-0003 cuts the interview loop; adding it later means wrapping existing nodes in interrupts rather than migrating frameworks.

## Alternatives rejected

**Direct Anthropic SDK, no framework.** Fewer dependencies, less magic, and full control of the loop — a serious option for a workflow this small. Rejected because the interview loop is deferred rather than abandoned, and LangGraph's interrupt and checkpoint handling is precisely what that will need. Hand-rolling resumable human-in-the-loop state is a real project, and it would be built worse.

**Tracing on by default.** Better observability for anyone trying the tool, and easier for us to debug reported issues. Rejected because it makes a privacy decision on the adopter's behalf about their most sensitive documents, silently. An adopter discovering after the fact that their goal specs were sent to a third party is the kind of surprise that ends a project's credibility, and no amount of debugging convenience is worth it.

**Agent dependencies as required, not optional.** One install path, one thing to test, no import-boundary maintenance. Rejected because it would mean nobody can validate a goal repo without an Anthropic account. The validator is the piece with the widest possible audience — a CI check on a goal repo is useful to organisations with no interest in the agent at all — and gating it behind an API key would cut that audience off for no benefit.

**Model alias rather than a pinned ID.** Automatic access to improvements without touching config. Rejected because the article's evidence is agent output, and evidence that cannot be reproduced is not evidence. Silent model drift would also mean behaviour changes we did not choose and could not date.

**Checkpoints in the OKR repo, gitignored.** State sits next to the specs it concerns, which is convenient when debugging. Rejected because it puts agent internals in a repository owned by goal owners and reviewed by non-developers, and because it depends on an ignore rule being correct in every repo `okr init` ever creates. The failure is silent when it happens.
