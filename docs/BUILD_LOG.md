# Build log

**Implementation decisions below the ADR threshold**, and the surprises worth remembering.
Written as we go — reconstructed afterwards it would be tidier and less honest.

**What belongs here.** A call you had to make that no ADR settled: where a boundary
between two modules falls, why a field is normalised, a constraint the language or a
library imposed that changed the shape of something. Anything a future implementer would
otherwise have to rediscover, or would "fix" without knowing it was deliberate.

**What does not.** Decisions with consequences beyond the implementation — those are
ADRs, and an entry here that starts to read like one should become one. Definitions
belong in the glossary. Progress belongs nowhere; this is not a changelog.

**The trigger:** if you made a call an ADR did not settle, add an entry in the same
commit. Not afterwards.

*This file was cut in planning and reinstated once implementation began — the reasoning
for cutting it held while only design docs were being written, and broke the moment there
were decisions ADRs are too heavy for.*

---

## The node and edge models — `core/models.py`

ADRs 0005 to 0010 decide the schema, so most of this file was transcription. Five things
were not decided there.

**Error codes ride on pydantic's own error type.** `docs/ERROR_CODES.md` promises stable,
machine-readable codes, and `CLAUDE.md` forbids tests asserting on message text. Pydantic
already carries a `type` on every error, so a model validator raising
`PydanticCustomError("E404_GUARDRAIL_COMPARISON", ...)` puts our code exactly where a
consumer already looks. No parallel exception hierarchy, and `codes.py` is the registry
document in executable form.

Two codes cannot be raised this way, because pydantic detects them before any of our code
runs: a missing field and an unknown one. They arrive as `missing` and `extra_forbidden`.
That turns out to be necessary rather than awkward — a missing field is
`E003_MARKER_FIELD_MISSING` in `okr.yaml` and `E103_FIELD_MISSING` in a goal file, and
only the caller knows which file it was reading. The loader completes the mapping;
`PYDANTIC_ERROR_TYPES` records it.

**Where the model stops and the validator starts.** The models reject only what would be
meaningless in memory: a required string left blank, a guardrail with neither limit and so
no comparison to make. The type-conditional content rules (`E401`–`E403`) were left to the
validator even though they are computable from a single key result, because raising is
fatal and stops at the first failure. A support lead wants every problem in their file at
once, with locations — not the first one, as a stack trace. That is a real constraint on
how much the schema layer should do, and it was not obvious going in.

Filesystem checks (`E006`–`E008`, the paths in `okr.yaml` existing) are the loader's for
the same reason plus an obvious one: a model has no idea where it was parsed from.

**`depends_on` is an edge object, but a thinner one.** ADR-0006 says an edge accepts a
bare ID or a mapping and that `origin` is optional on the edge. Read literally, that gives
dependencies a `cascaded | laddered` field, which is meaningless — provenance there is
about goal hierarchy. So `DependencyEdge` carries `target` and nothing else, while keeping
the shorthand normalisation uniform. If a dependency ever needs to say what it is waiting
for (explicitly deferred in ADR-0006), the shape is already there.

**Required strings are trimmed.** Not in any ADR. `owner: "head-of-platform "` would
otherwise be a dangling reference invisible in a diff — the same class of silent failure
ADR-0010 wrote a whole file to eliminate, arriving through a different door.

**`extra="forbid"` everywhere.** ADR-mandated in effect (`E102` exists), but worth naming
as the single highest-value line in the module: `anti_target:` instead of `anti_targets:`
would otherwise produce a spec that reads as complete in review and asserts nothing.
