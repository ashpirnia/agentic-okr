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

---

## The loader and the graph — `core/loader.py`, `core/graph.py`, `core/violations.py`

ADR-0008 decides root detection and failure behaviour, ADR-0007 layout-agnosticism,
ADR-0006 what the loader materialises. Eight things they do not decide.

**A failed load raises; it does not return a half-graph.** The alternative — returning a
graph plus a violation list — would put a partial graph into the hands of every consumer,
which is the exact failure ADR-0008 exists to prevent, arriving through the front door
instead of through a subdirectory argument. So `LoadError` carries *every* violation
found rather than the first, which keeps the "one review cycle, not five" property that
made a violation list attractive in the first place.

**Where loading stops and validating starts.** A graph exists if it could be *built*:
files parsed, fields the right shapes, IDs unique. Everything that needs a finished graph
to answer — dangling references, edge shapes, cycles, orphans — is the validator's, and
is representable in a loaded graph on purpose. The one that looks misplaced is
`E201_DUPLICATE_ID` for nodes, which the loader raises: with two nodes under one ID there
is no index to build, and every reference to it would resolve to whichever was read last.
The same code for metrics and owners is raised in the same place for the same reason.

**Line numbers come from a second look at the same parse.** `yaml.safe_load` discards
positions, and a loader that annotated the data with them would push `__line__` keys into
models set to `extra="forbid"`. So the file is composed to a node tree and constructed
from it in one pass, the tree is kept, and pydantic's error path
(`objectives.0.key_results.1.target`) is walked down it. `_line_at` reports the deepest
point it reached, so a violation about a field the file does not contain still lands on
the object that should have contained it. For a value that is itself a block it reports
the *key's* line, because someone told to look at `guardrails:` wants that line and not
its first item.

**Anything pydantic rejects that no code covers is `E105_FIELD_INVALID`**, added to the
registry here. `commitment: quite-keen` had no code — the E1xx band covered missing,
unknown and blank, and `E405` covered exactly one wrong type. Rather than widen `E104`
(forbidden) or let the error escape as a traceback (also forbidden), the band gained the
general case and `E405` stays the specific one. It is a fallback as well as a code, so a
future pydantic release that adds an error type reports something a consumer can match on
instead of crashing.

**A defaulted vocabulary file that is absent is not `E007`/`E008`.** Read literally, those
force every repo to carry both files from its first commit. The distinction drawn instead:
naming a path explicitly and being wrong is a typo in one line and is reported; leaving
the default and not having written the file is a repo mid-adoption. `okr_dir` is required,
so it is always checked.

**The two vocabularies are not symmetric, which the first cut of this got wrong.** They
look alike — same shape, same join-key argument, adjacent lines in the marker — and were
therefore given the same treatment, which was right for one of them. An absent
`metrics.yaml` is ordinary: a repo made entirely of milestone key results declares no
metrics, and a reference to one that is missing is reported at the line naming it. Owners
have no such case, because `owner` is required on every objective and every key result. An
absent `owners.yaml` therefore strands *every* node at once — seven in a small three-team
repo — and hands a reader a wall of identical failures with nothing in it naming the
cause. Hence `E010_NO_OWNERS_DECLARED`, added to the registry: said once, up front,
instead. It is checked after the goal files are read rather than beside the other marker
paths, since whether it matters depends on there being goals to own — a scaffolded, empty
repo is not yet wrong.

The general shape, worth keeping in mind for the validator: **one cause that produces N
identical failures should be reported as the cause, not as the N failures.** A per-item
error is right when the items are independently fixable, and wrong when they all have one
fix.

**Violations are one shape for the loader and the validator both**, in `violations.py`,
with severity read off the code rather than set by whoever raised it. No caller can grade
a violation differently from the registry. Nothing there formats for a terminal — the
Conductor's lint will consume the same objects without one.

**The graph exposes edges as strings, not resolved node pairs.** An edge to a node that
does not exist has to be representable, or the failure this project exists to catch could
not be reported. `graph.node(id)` returning `None` is the resolution step, and it is the
caller's to take.

**References are collected during the load, not rediscovered afterwards.** Three classes
— edges, metrics, owners — each recorded with the file and line it was written on.
Walking the models again later would be simpler, but the line is only available while the
YAML node tree is in hand, and without it an unresolved metric can name the key result and
not the line, leaving a reader to work out which of five guardrails was misspelled.

---

## Guarding the minimal install — `tests/test_minimal_install.py`

`CLAUDE.md` asserted that a test proved `core` imports without the `agent` extra. No such
test existed, and the CI workflow installed with `--all-extras`, so the minimal path had
never once been exercised.

**The obvious test proves nothing.** `import agentic_okr.core` succeeds whether or not
`langgraph` is installed. On any machine that has the extra — every developer's, and the
main CI job — an import test passes while the rule is being broken. So the guard reads the
source: an AST walk over everything outside `champion/`, failing on a module-level import
of an agent distribution or of `champion`. That fails everywhere, immediately, in the same
run as the change that broke it. The CI job that installs without extras is the second
half rather than the whole of it: it catches what static reading cannot, such as a
dependency arriving through a transitive import.

That job asserts `import langgraph` *fails* before it asserts anything else. Without that,
a change to the install step would silently turn the job into a duplicate of the main one
— a green check proving nothing, which is worse than no job.

**Function-level imports are deliberately allowed.** The rule is about what happens at
import time, and deferring an optional dependency into the function that needs it is how
shared code will eventually reach the Champion. A blanket ban would have no escape hatch
and would be worked around rather than obeyed.

**The forbidden list is derived from `pyproject.toml`, not hardcoded**, so adding a
package to the `agent` extra extends the guard automatically. Two transitive packages
(`anthropic`, `langsmith`) are named explicitly, since nothing declares them and importing
one from `core` breaks the install just as surely.

Also removed here: the CI step that tolerated pytest's exit code 5. It existed because no
tests were collected during bootstrap. Tests exist now, so it had stopped protecting
anything and started hiding a total collection failure.
