# Validation error codes

Every violation `okr validate` reports carries a stable code. This is the registry.

## Why codes exist, and what is guaranteed

Codes are a **published contract**. The Conductor will consume validation output to decide whether a spec is safe to lint agents against, and consuming it by matching on message text would break the first time someone improved a sentence.

Three guarantees:

1. **A code's meaning never changes.** If a check's semantics change, it gets a new code.
2. **Retired codes stay reserved.** A number is never reused for a different check.
3. **New checks get new codes**, never a widened existing one.

**Severity is part of the contract.** `E` codes fail the run and exit non-zero. `W` codes are reported and exit zero — they mark things that are legal but usually wrong, and a validator that rejected them would teach people to write false specs to satisfy it.

**Every violation reports a location** — file path, and line where the parser can supply one. Tests assert on codes, never on message text (`CLAUDE.md`).

**Which layer raises a code is an implementation detail; the code is the contract.** Some are enforced by the schema models, some by the validator, and the split is recorded in the build log rather than here. Two consequences worth knowing:

- **`E003` and `E103` are the same underlying violation in different files.** A missing required field is detected by the parser before any of our code runs, so the file being read is what distinguishes them — `E003_MARKER_FIELD_MISSING` in `okr.yaml`, `E103_FIELD_MISSING` in a goal file. Only the caller knows which, so the loader completes the mapping. The same applies to `E102_UNKNOWN_FIELD`.
- **A code may be raised later than you would expect.** The type-conditional rules `E401`–`E403` are computable from a single key result but are the validator's, not the model's: a model raises fatally on the first failure, and a goal owner needs every problem in their file at once with locations.

---

## E0xx — Repo and marker

Failures that stop the graph being loaded at all. See [ADR-0008](adr/0008-okr-yaml-marker.md).

| Code | Meaning |
| :--- | :--- |
| `E001_NO_MARKER` | No `okr.yaml` found after walking up to the filesystem root. Message names the directories searched and points at `okr init`. |
| `E002_MARKER_UNPARSEABLE` | `okr.yaml` is not valid YAML. |
| `E003_MARKER_FIELD_MISSING` | A required marker field is absent: `schema_version`, `period` or `okr_dir`. |
| `E004_SCHEMA_VERSION_UNSUPPORTED` | `schema_version` is not in the supported set. Message names what was found and what is supported. |
| `E005_PERIOD_EMPTY` | `period` is present but empty. Format is otherwise unconstrained. |
| `E006_OKR_DIR_MISSING` | The directory named by `okr_dir` does not exist. |
| `E007_METRICS_FILE_MISSING` | `metrics_file` names a file that does not exist. |
| `E008_OWNERS_FILE_MISSING` | `owners_file` names a file that does not exist. |
| `E009_PATH_HAS_NO_MARKER` | An explicit path argument was given but contains no `okr.yaml`. Loading a subdirectory as though it were a whole graph is never supported. |

## E1xx — Parse and structure

| Code | Meaning |
| :--- | :--- |
| `E101_YAML_UNPARSEABLE` | A file under `okr_dir` is not valid YAML. |
| `E102_UNKNOWN_FIELD` | A field not in the schema. Catches misspellings like `anti_target:` or `guardrail:`, which would otherwise be silently ignored and produce a spec that looks complete and is empty. |
| `E103_FIELD_MISSING` | A required node field is absent — `id`, `statement`, `type`, `owner`, or `commitment` on an objective. |
| `E104_FIELD_EMPTY` | A required field is present but blank. |

## E2xx — Identity and references

See [ADR-0007](adr/0007-id-scheme-and-layout.md), [ADR-0009](adr/0009-guardrails-and-anti-targets.md), [ADR-0010](adr/0010-owner-identity.md).

| Code | Meaning |
| :--- | :--- |
| `E201_DUPLICATE_ID` | Two nodes share an ID. IDs are globally unique across the repo. |
| `E202_DANGLING_EDGE_REF` | A `supports` or `depends_on` target does not resolve. |
| `E203_DANGLING_METRIC_REF` | A `metric` on a key result or guardrail does not resolve to a declared metric. |
| `E204_DANGLING_OWNER_REF` | An `owner` does not resolve to a declared owner. This is the code that catches `head_of_support` where `head-of-support` was declared. |
| `E205_DANGLING_WATCHED_BY_REF` | An anti-target's `watched_by` names a metric that does not exist. |
| `E206_WATCHED_BY_NOT_GUARDED` | `watched_by` names a real metric that is not guarded on *this* key result. A false sense of coverage is worse than none. |

## E3xx — Edges

See [ADR-0006](adr/0006-edge-semantics.md).

| Code | Meaning |
| :--- | :--- |
| `E301_ILLEGAL_EDGE_SHAPE` | An edge connects node types that may not be connected — most commonly `supports` between two key results, which is always `depends_on`. |
| `E302_SELF_REFERENCE` | A node supports or depends on itself. |
| `E303_SUPPORTS_CYCLE` | A cycle in `supports`. A goal contributing to itself, directly or transitively, cannot have its contribution resolved. |
| `E304_REDUNDANT_CONTAINMENT_EDGE` | A key result explicitly lists its containing objective in `supports`. Nesting already materialises that edge, and two representations of one relationship is how they come to disagree. |
| `E305_DEPENDS_ON_NOT_KEY_RESULT` | A `depends_on` target is not a key result. |
| `E306_SUPPORTS_TARGET_INVALID` | A key result's `supports` targets something other than an objective. |

## E4xx — Content rules

See [ADR-0005](adr/0005-node-types.md), [ADR-0009](adr/0009-guardrails-and-anti-targets.md), [ADR-0011](adr/0011-completeness-rubric.md).

| Code | Meaning |
| :--- | :--- |
| `E401_METRIC_KR_WITHOUT_METRIC` | A `type: metric` key result has no `metric` or no `target`. |
| `E402_MILESTONE_KR_WITH_METRIC` | A `type: milestone` key result names a metric or target. |
| `E403_MILESTONE_KR_WITHOUT_CRITERIA` | A `type: milestone` key result has no success criteria. It has no metric, no target and nothing checkable — it asserts nothing at all. |
| `E404_GUARDRAIL_COMPARISON` | A guardrail has neither `must_not_exceed` nor `must_not_fall_below`, or has both. Exactly one is required. |
| `E405_TARGET_NOT_NUMERIC` | `target` is not a number. |

## W1xx — Warnings

Legal, and occasionally correct. Reported; the run still exits zero.

| Code | Meaning |
| :--- | :--- |
| `W101_DEPENDS_ON_CYCLE` | A cycle in `depends_on`. Mutual dependency between teams is real and sometimes legitimately phased. Rejecting it would force people to omit true information to satisfy a validator. |
| `W102_ORPHAN_OBJECTIVE` | An objective that neither supports anything nor is supported by anything, and is not a top-level objective. Usually an unfinished ladder. |
| `W103_ALL_KRS_ASPIRATIONAL` | An objective declared `committed` whose key results all override to `aspirational` — commitment level used as a difficulty dial rather than a claim about ambition. |
| `W104_UNUSED_METRIC` | A metric is declared but nothing targets or guards it. Harmless, but usually a leftover or a typo elsewhere. |
| `W105_UNUSED_OWNER` | An owner is declared but owns nothing. |

---

## What is deliberately *not* an error

**A vacuous field.** `success_criteria: ["TBD"]` passes every check here. Structural validation cannot see meaning, and pretending otherwise would make results model-dependent. That gap is the Champion's semantic review to fill, and [ADR-0011](adr/0011-completeness-rubric.md) keeps the two outputs separate for exactly this reason.

**A missing guardrail or anti-target.** These are legal absences that weaken a spec, which makes them the completeness score's business rather than the validator's. Validation covers what is required; scoring covers what is optional but valuable, and nothing is both.

**A malformed ID.** [ADR-0007](adr/0007-id-scheme-and-layout.md) leaves ID format to the author, so there is no pattern to violate. An inconsistent team prefix is a readability problem, not a correctness one — ownership comes from the `owner` field.

**An ID prefix that disagrees with its directory.** Deliberately unchecked, since coupling identity to location would make reorganisation a breaking change.
