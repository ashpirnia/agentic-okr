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

---

## The validator — `core/validate.py`

ADR-0006 decides the edge rules and ADR-0011 the three type-conditional ones, so the
checks themselves were transcription. What was not settled:

**`validate` returns a report; it never raises.** The loader raises, because a repo that
cannot be *built* has no object to hand back. An invalid repo does — invalidity is the
ordinary outcome a goal owner is expected to read and act on, and making it an exception
would force every consumer, including the future Conductor lint, to use `try` for the
normal path. `Report` keeps errors and warnings apart rather than handing back one list
with a severity to filter on, because the one question every caller asks is whether to
exit non-zero.

**Grouping is by the reference's target, uniformly across all four classes.** The build
log's earlier note — one cause producing N identical failures is reported as the cause —
needed a concrete rule. The rule is: the thing that does not exist is the fix, and the
places expecting it are symptoms. One renamed owner ID is one violation listing twelve
locations; three key results with three differently mistyped metrics are three violations,
because they are three fixes. Every location is listed in the message rather than counted,
since the reader has to visit each one and "in 12 places" sends them searching for the
other eleven.

`E206_WATCHED_BY_NOT_GUARDED` is the exception that proves the rule: it is grouped by key
result *and* metric together, because the fix is one guardrail on one key result, which
settles every anti-target there that named it.

**A dangling target suppresses the shape and cycle checks on that edge.** Otherwise a
misspelled ID reports twice — once as a goal that does not exist, once as a connection to
the wrong kind of thing — and the second is an artefact of the first.

**Cycles are reported per strongly connected component, not per edge or per elementary
cycle.** Every edge in a circle has the same single fix, and a component with several
overlapping circles would otherwise produce a combinatorial pile of violations saying one
thing. The message prints the shortest circle through the component's lowest ID, which is
readable and still names connections whose removal breaks it. Tarjan is written
iteratively: nothing stops a goal chain being deeper than the interpreter's stack, and a
crash there would report a bug of ours as a problem with somebody's goals.

Implicit containment edges are included in the traversal, which is what makes an objective
that supports one of its own key results a cycle — as it should be, since nesting is
itself a supporting edge. Self-loops are excluded, because `E302_SELF_REFERENCE` already
reports them at the line somebody wrote.

**`W102_ORPHAN_OBJECTIVE` counts containment as a connection.** The registry says an
orphan is an objective that neither supports nor is supported by anything "and is not a
top-level objective", which needs a rule for telling those two apart. Containment is that
rule: an objective with key results beneath it has incoming supporting edges and is never
an orphan, so what the warning catches is an objective with no parent and nothing under it
— an unfinished ladder.

**`E306_SUPPORTS_TARGET_INVALID` is not raised, and `E301_ILLEGAL_EDGE_SHAPE` covers its
case.** The two registry rows describe one situation. `E306` is "a key result's `supports`
targets something other than an objective", and with two node kinds in the schema the only
such target is another key result — which is exactly what `E301`'s row names as its
commonest case. `E301` was chosen because the registry row spells the case out. `E306`
stays reserved and unraised; it is not retired, because the pair is worth resolving
deliberately rather than by deleting a published code. Flagged rather than decided
silently, per the working agreements.

---

## The CLI — `cli/`, `cli/report.py`, `cli/topology.py`

ADR-0003 names the commands and ADR-0008 decides where the root comes from, so the
argument handling was transcription. What was not settled:

**Two exit codes, not three.** The obvious third — one for "invalid", another for "could
not be read" — was rejected. A CI job asks one question, and every non-zero code it does
not recognise it treats as failure anyway; a second failure code is a distinction only
somebody debugging the tool would use, and the person the output is for is not that.
`0` is nothing-to-fix, warnings included, and `1` is everything else.

**A failed load renders exactly like a failed validation.** Both are lists of violations
with codes and locations, and at the moment of reading them the difference between an
unparseable file and an undeclared metric is not one the reader acts on differently. Only
the closing line differs, and it has to: after a load failure the silence about everything
else is not a pass, so the summary says nothing else could be checked. Machine output
carries the same distinction as `loaded`, which is how a consumer tells "nothing found"
from "never looked" — the counts it never got to make are null rather than zero.

**Rendering lives in `cli/`, and the report objects stay clean.** `core` builds
violations; nothing in it knows about a terminal. The split is what lets the future
Conductor lint consume the same objects, and it is also why `Violation.__str__` is not
what the CLI prints — a one-line form is for a log, and the report is a table.

**The console is fixed at 100 columns when nothing is asking.** Rich falls back to 80 for
a pipe, which folds a file path across two lines in the one place a reader has to read it
exactly. A terminal is still measured. The side effect is that piped output is
deterministic, which is what makes the CLI tests possible without stripping widths.

**`okr graph`'s tree is a projection, and the projection is the interesting part.** The
goal topology is a graph, so a tree has to pick one parent per node. A key result
supporting two objectives is therefore drawn under each and expanded only the first time,
marked "shown above" after that. Two guards, not one: a repo-wide `drawn` set stops the
duplicate expansion, and a per-branch `ancestors` set stops a `supports` cycle recurring
forever. The cycle guard is load-bearing — a cycle is an error `okr validate` reports, and
the command a person reaches for to *see* the cycle must not hang on it.

Anything the walk never reaches is printed under its own heading rather than dropped: a
goal missing from the picture is the kind of wrong answer that looks like a right one.
That covers goals inside a cycle and goals whose only connection points at nothing.

**The adjacency table lists only edges somebody wrote.** Containment edges are excluded —
nobody wrote them, there is no line to point at, and the tree above already shows them.
What is left is the cross-team network, which is exactly what no single file makes visible
and what the tree flattens away.

**`okr graph` does not validate, and shows what does not resolve.** A connection pointing
at a goal nobody declares is printed and marked in place, and the command still exits
zero. Making it fail would give two commands one job, and hiding the edge would draw a
picture that quietly disagrees with what `okr validate` says about the same repo.

**A key result's inherited commitment is printed, not the empty field.** The label shows
`committed, inherited` rather than "inherited" or a blank, because the reader's question
is whether the goal is a must-hit, not whether the field is filled in. Where it came from
is still marked, since an inherited commitment changes when somebody edits a different
goal.

**The entry point moved to `agentic_okr.cli:main`, and the package root imports nothing.**
Under the old `agentic_okr:main`, importing `agentic_okr.core` would execute the package
root and pull a terminal renderer into every program that only wanted to read a graph.

---

## The scaffold — `core/scaffold.py`, `examples/scaffold/`

ADR-0002 decides that `okr init` is where the layout gets taught and why it is generated
rather than kept as a template repo; ADR-0007 decides the layout it teaches. What was not
settled:

**The scaffold lives in `core`, not in the CLI.** It is the layout, expressed as code, and
the property that makes it worth generating — that it cannot drift from the validator — only
holds if it sits beside the validator. The CLI writes nothing itself; it calls `create` and
renders what came back. This is also the only place the tool writes files, and it writes
them into somebody else's repo, never its own.

**`okr init`'s refusals carry no error code.** Every other failure the tool prints carries
one from the registry, so this is a deliberate exception. That registry is what
`okr validate` reports and what the Conductor will consume; nothing consumes the reason a
directory could not be scaffolded. Extending a published contract to cover a command's own
mechanics would add a promise with no reader, and the guarantee that a code's meaning never
changes is worth more when the set stays small. `ScaffoldRefused` carries a sentence.

**Refusing to init inside an existing repo is the same decision as ADR-0008's marker walk,
seen from the other end.** Two markers in one tree means anything reading the goals stops at
the nearer one and silently reads part of an organisation — the partial graph the marker
exists to prevent. The message names the outer root and points at its `okrs/` directory,
because the thing the person actually wanted is a team file in the repo they already have.

**Existing files are kept, never overwritten, and only `okr.yaml` refuses outright.** A
`.gitignore` somebody already wrote is theirs. So `create` reports written and kept
separately, and the CLI prints both.

**Init validates what it wrote and prints the result.** One line, from the same renderer
`okr validate` uses. It costs a load and it makes the claim checkable at the moment it is
made rather than in a test the adopter never sees. The exit code follows the validation, so
the only way `okr init` exits non-zero having written files is if a file it kept is the
problem — which is exactly when somebody needs to know.

**The scaffold is mostly comments, and the examples are the last block of each file.** That
placement is a convention the tests depend on: for every scaffolded file that has nothing
live in it, the final blank-line-separated block is a commented example, and uncommenting
it must yield a repo that loads and validates silently. The three examples are therefore
mutually consistent — the owner the goal file names is the owner `owners.yaml` declares, and
the metric it targets is the one `metrics.yaml` declares. Anything else would teach a
dangling reference as the starting shape.

**Guardrails and anti-targets are left out of the scaffold**, despite being the point of the
tool. A scaffold showing every optional field teaches that writing a goal here means filling
in twenty; those two are what the Champion elicits in conversation, and `examples/` plus
`docs/GRAPH-BY-EXAMPLE.md` are where a reader sees a full one. Flagged because it looks like
an omission and is not.

**The period is written by the YAML writer, not pasted into a template.** It is free text
from a prompt, and a colon or a leading asterisk in it would produce a marker that is not
the file we meant to write — with the failure landing on somebody's brand new repo. It is
also slugified before it reaches a filename, for the same reason in the other direction.

**`examples/scaffold/` is generated output, committed.** The test asserts it byte for byte
against a fresh `create`, so changing the scaffold's wording means regenerating it in the
same commit. The period it was generated with is read out of its own `okr.yaml` rather than
duplicated in the test.

**The reference examples this was meant to be checked against do not exist yet.** The brief
was that the scaffold and the reference repos must not disagree, and today `examples/` holds
only the scaffold — the worked three-team organisation lives in `docs/GRAPH-BY-EXAMPLE.md`
and in `tests/test_loader.py` as strings. The vocabulary was kept deliberately identical
(`support.fast-resolution`, `support.resolution-time`, `resolution_time_p50`,
`head-of-support`) so that when that repo does land under `examples/`, the two already
agree. Worth doing properly: the fixture strings in `test_loader.py` should become that
example repo, read from disk.

**CLI help is rendered as markdown.** Typer's default treats every newline in a docstring as
a line break, so help text wrapped at whatever column the source line happened to end on and
read as though it had been formatted badly. `rich_markup_mode="markdown"` reflows
paragraphs. Noted because it looks like a styling preference and is not — the docstrings are
help text a goal owner reads.
