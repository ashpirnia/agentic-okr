"""Reading an OKR repo into a graph.

The entry point is `load`. Point it at anywhere inside an OKR repo — or nowhere, and it
uses the working directory — and it finds the root, reads every file, and returns the
whole graph or raises with everything wrong with it.

**It is a library first and a CLI second.** The Conductor's wiring lint will sit on this
function, so nothing here prints, exits, or knows a terminal exists.

Three rules shape the module.

**The graph is always whole.** The root is found by walking up for `okr.yaml`, as git
does with `.git`. There is no way to load a subdirectory: validating a fragment reports
dangling references that are not real, or passes silently, and both are wrong answers
that look like right ones (ADR-0008).

**Nothing surfaces as a traceback.** Every failure a real repo can produce — no marker, a
tab in someone's YAML, a schema version from a future release, a word where a number
belongs — becomes a `Violation` with a code and, where the parser can supply one, a line.
The reader is a support lead in a pull request, not us.

**Every problem is reported, not the first.** Reading continues past a file that fails,
and the collected violations are raised together. A loader that stopped at the first bad
line would turn one review cycle into five.
"""

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from .codes import Code
from .graph import Edge, EdgeKind, Graph, Node, NodeKind, Reference, RefKind, Source
from .models import (
    GoalFile,
    KeyResult,
    MetricsFile,
    Objective,
    OwnersFile,
    RepoMarker,
)
from .violations import LoadError, Violation

#: The file whose presence makes a directory an OKR repo root.
MARKER_NAME = "okr.yaml"

#: What counts as a goal file under `okr_dir`. Everything else beneath it is ignored, so
#: an organisation can keep a README or a diagram alongside their goals.
GOAL_FILE_SUFFIXES = frozenset({".yaml", ".yml"})

#: Every code the registry defines, for recognising the ones our own models raise.
_REGISTERED_CODES = frozenset(code.value for code in Code)

#: A step along a path into a parsed document: a mapping key or a sequence index.
type Step = str | int


# --- Finding the root ------------------------------------------------------------------


def find_root(start: Path | None = None) -> Path:
    """The OKR repo root containing `start`, found by walking up for `okr.yaml`.

    Raises `LoadError` with `E001_NO_MARKER` if the filesystem root is reached first.
    There is deliberately no fallback to treating `start` as a root: the convenience
    would be indistinguishable from the failure it hides, and someone standing in the
    wrong directory would get a pass on an empty graph.
    """
    origin = (start or Path.cwd()).resolve()
    searched = [origin, *origin.parents]
    for directory in searched:
        if (directory / MARKER_NAME).is_file():
            return directory
    raise LoadError(
        [
            Violation(
                Code.NO_MARKER,
                f"This does not look like an OKR repo: there is no {MARKER_NAME} in "
                f"{origin}, or in any of the {len(searched) - 1} directories above it, "
                f"up to {searched[-1]}. Run 'okr init' to start one.",
            )
        ]
    )


def _root_from_explicit_path(path: Path) -> Path:
    """The root for a path the caller named, which must itself carry the marker.

    An explicit path overrides the walk-up but never widens what can be loaded:
    `okr validate ../acme-okrs` works, `okr validate okrs/support/` does not. Allowing
    the second would be a documented route to the partial-graph failure the marker exists
    to prevent — reached for exactly when full validation feels slow, which is when a
    wrong answer is least likely to be noticed.
    """
    resolved = path.resolve()
    if resolved.is_file() and resolved.name == MARKER_NAME:
        return resolved.parent
    if (resolved / MARKER_NAME).is_file():
        return resolved
    raise LoadError(
        [
            Violation(
                Code.PATH_HAS_NO_MARKER,
                f"There is no {MARKER_NAME} in {resolved}, so this is not the root of an "
                f"OKR repo. Point at the root instead — one team's directory cannot be "
                f"checked on its own, because its goals reference goals outside it.",
            )
        ]
    )


# --- YAML, with lines ------------------------------------------------------------------


def _parse_yaml(
    path: Path, relative: Path, unparseable: Code
) -> tuple[Any, yaml.Node | None, Violation | None]:
    """Read one YAML file into data, the node tree its lines come from, and any problem.

    Composed and constructed in a single pass. The node tree is kept because pydantic
    reports a problem as a path through the data — `objectives.0.key_results.1.target` —
    and only the tree knows what line that path was written on.

    A parse failure is returned rather than raised so the caller can carry on to the next
    file and report every problem at once.
    """
    reader = yaml.SafeLoader(path.read_text(encoding="utf-8"))
    try:
        node = reader.get_single_node()
        data = None if node is None else reader.construct_document(node)
    except yaml.YAMLError as error:
        return None, None, _yaml_violation(error, relative, unparseable)
    finally:
        reader.dispose()
    return data, node, None


def _yaml_violation(error: yaml.YAMLError, relative: Path, code: Code) -> Violation:
    """Turn a YAML parser's complaint into a violation with a line."""
    mark = getattr(error, "problem_mark", None)
    problem = getattr(error, "problem", None) or "it could not be read"
    return Violation(
        code,
        f"This file is not valid YAML: {problem}. Check the indentation, and that any "
        f"colon inside a sentence is quoted.",
        file=relative,
        line=None if mark is None else mark.line + 1,
    )


def _line_at(node: yaml.Node | None, path: Sequence[Step]) -> int | None:
    """The line a path through a document was written on, as best the parser can say.

    Walks as far down the path as the tree allows and reports the deepest point reached,
    so a problem with a field the file does not contain still lands on the object that
    should have contained it. Where a value is itself a block, the *key's* line is
    reported: someone told to look at `guardrails:` wants that line, not its first item.
    """
    current = node
    line = None if current is None else current.start_mark.line + 1
    for step in path:
        match current, step:
            case yaml.SequenceNode(), int() if step < len(current.value):
                current = current.value[step]
                line = current.start_mark.line + 1
            case yaml.MappingNode(), str():
                for key, value in current.value:
                    if key.value == step:
                        anchor = value if isinstance(value, yaml.ScalarNode) else key
                        current, line = value, anchor.start_mark.line + 1
                        break
                else:
                    return line
            case _:
                return line
    return line


# --- Model complaints, as violations ---------------------------------------------------


def _violations_from(
    error: ValidationError,
    relative: Path,
    node: yaml.Node | None,
    *,
    in_marker: bool = False,
) -> list[Violation]:
    """Everything pydantic objected to, as violations with codes and lines.

    Our own model validators already raise registry codes, so those pass straight
    through. The two pydantic detects before our code runs — a missing field and an
    unknown one — are mapped here, because which code a missing field becomes depends on
    the file it was found in and only the caller knows that. Anything else is a value
    that is not the shape its field declares.
    """
    violations = []
    for detail in error.errors():
        location = [step for step in detail["loc"] if isinstance(step, str | int)]
        code = _code_for(str(detail["type"]), location, in_marker=in_marker)
        violations.append(
            Violation(
                code,
                _message_for(code, str(detail["msg"]), location),
                file=relative,
                line=_line_at(node, location),
            )
        )
    return violations


def _code_for(error_type: str, location: Sequence[Step], *, in_marker: bool) -> Code:
    """The registry code for one thing pydantic objected to.

    The same underlying violation carries a different code depending on the file it was
    found in: a required field absent from `okr.yaml` is `E003`, and absent from a goal
    file is `E103`. `period` left blank is the same story one level down.
    """
    field = location[-1] if location else None
    if error_type in _REGISTERED_CODES:
        code = Code(error_type)
        if in_marker and code is Code.FIELD_EMPTY and field == "period":
            return Code.PERIOD_EMPTY
        return code
    match error_type:
        case "missing":
            return Code.MARKER_FIELD_MISSING if in_marker else Code.FIELD_MISSING
        case "extra_forbidden":
            return Code.UNKNOWN_FIELD
        case _ if field == "target":
            return Code.TARGET_NOT_NUMERIC
        case _:
            return Code.FIELD_INVALID


def _message_for(code: Code, detail: str, location: Sequence[Step]) -> str:
    """A sentence for a goal owner. No Python names, no type errors, no stack traces."""
    field = str(location[-1]) if location else "this"
    match code:
        case Code.FIELD_MISSING | Code.MARKER_FIELD_MISSING:
            return f"'{field}' is required, and this one does not have it."
        case Code.UNKNOWN_FIELD:
            return (
                f"'{field}' is not a field in the OKR schema. Check the spelling: a "
                f"field the schema does not know is ignored, which leaves a goal that "
                f"reads as complete in review and asserts nothing."
            )
        case Code.PERIOD_EMPTY:
            return (
                "'period' names the cycle this repo covers — '2026-Q3', '2026-H1', "
                "'2026-07'. It cannot be left blank."
            )
        case Code.TARGET_NOT_NUMERIC:
            return "'target' has to be a number, in the unit its metric is measured in."
        case _:
            return f"'{field}' could not be read: {detail}."


# --- The marker ------------------------------------------------------------------------


def _load_marker(root: Path) -> RepoMarker:
    """Read `okr.yaml`. Nothing else can be attempted until this succeeds."""
    relative = Path(MARKER_NAME)
    data, node, problem = _parse_yaml(root / MARKER_NAME, relative, Code.MARKER_UNPARSEABLE)
    if problem is not None:
        raise LoadError([problem])
    try:
        return RepoMarker.model_validate(data if data is not None else {})
    except ValidationError as error:
        raise LoadError(_violations_from(error, relative, node, in_marker=True)) from None


def _declared_dir(root: Path, marker: RepoMarker) -> Path:
    """The directory the goal files live in, checked to exist."""
    resolved = root / marker.okr_dir
    if resolved.is_dir():
        return resolved
    raise LoadError(
        [
            Violation(
                Code.OKR_DIR_MISSING,
                f"'okr_dir' in {MARKER_NAME} points at a directory that is not there: "
                f"'{marker.okr_dir}'. That is where your goal files live. Paths are "
                f"relative to the {MARKER_NAME} beside them.",
                file=Path(MARKER_NAME),
            )
        ]
    )


def _declared_file(root: Path, marker: RepoMarker, attribute: str, code: Code) -> Path | None:
    """One of the marker's optional file paths, checked to exist.

    Naming a path and being wrong is a typo, and is reported here. Leaving the default
    and not having written the file is a different situation, and returns None — what
    that means then depends on which vocabulary it was, because the two are not
    symmetric. See `_check_owners_exist`.
    """
    declared: Path = getattr(marker, attribute)
    resolved = root / declared
    if resolved.is_file():
        return resolved
    if attribute not in marker.model_fields_set:
        return None
    raise LoadError(
        [
            Violation(
                code,
                f"'{attribute}' in {MARKER_NAME} points at a file that is not there: "
                f"'{declared}'. Paths are relative to the {MARKER_NAME} beside them.",
                file=Path(MARKER_NAME),
            )
        ]
    )


def _check_owners_exist(
    marker: RepoMarker, owners_path: Path | None, nodes: int
) -> Violation | None:
    """A repo with goals in it but no `owners.yaml` at all, which is never right.

    The two vocabularies look alike and fail differently, so an absent default is treated
    differently in each. A repo with no metrics is ordinary — one made entirely of
    milestone key results has none to declare — and a reference to a metric that is not
    there is then reported at the line that names it.

    Owners have no such case: `owner` is required on every objective and every key
    result. With no `owners.yaml`, every one of them dangles at once — seven in a small
    three-team repo — and a reader is handed a wall of identical failures with nothing in
    it naming the cause. This says the cause once instead.

    Deliberately not the same as `E008`: that is a path somebody named and got wrong,
    which is a typo in one line, and this is a file nobody has written yet.
    """
    if owners_path is not None or nodes == 0:
        return None
    return Violation(
        Code.NO_OWNERS_DECLARED,
        f"This repo has goals in it, but there is no '{marker.owners_file}' declaring "
        f"who owns them. Every objective and key result names an owner, and each of "
        f"those names has to resolve to someone declared there. Create it, or point "
        f"'owners_file' in {MARKER_NAME} at where your owners are declared.",
    )


# --- The declared vocabularies ---------------------------------------------------------


def _load_declarations(
    path: Path | None,
    relative: Path,
    model: type[MetricsFile] | type[OwnersFile],
    key: str,
    noun: str,
    violations: list[Violation],
) -> tuple[dict[str, Any], dict[str, Source]]:
    """Read `metrics.yaml` or `owners.yaml` into an index keyed by ID.

    The two files are the same shape doing the same job — declaring a vocabulary so that
    a reference into it either resolves or is reported, rather than silently becoming a
    second metric or a second person (ADR-0009, ADR-0010).

    Anything declared twice is reported rather than quietly resolved: whichever copy won
    would be arbitrary, and the loser's definition is what somebody was reading when they
    wrote a threshold against it.
    """
    if path is None:
        return {}, {}
    data, node, problem = _parse_yaml(path, relative, Code.YAML_UNPARSEABLE)
    if problem is not None:
        violations.append(problem)
        return {}, {}
    try:
        parsed = model.model_validate(data if data is not None else {})
    except ValidationError as error:
        violations.extend(_violations_from(error, relative, node))
        return {}, {}

    index: dict[str, Any] = {}
    sources: dict[str, Source] = {}
    for position, declared in enumerate(getattr(parsed, key)):
        source = Source(relative, _line_at(node, (key, position)))
        if declared.id in index:
            violations.append(
                Violation(
                    Code.DUPLICATE_ID,
                    f"There is already a {noun} called '{declared.id}', declared at "
                    f"{sources[declared.id]}. Each one is declared once, and referred to "
                    f"by that ID everywhere else.",
                    file=relative,
                    line=source.line,
                )
            )
            continue
        index[declared.id] = declared
        sources[declared.id] = source
    return index, sources


# --- The goal files --------------------------------------------------------------------


def _goal_files(okr_dir: Path) -> list[Path]:
    """Every goal file under `okr_dir`, in a stable order.

    The loader is layout-agnostic: it reads what it finds rather than enforcing a
    structure, so an organisation can reorganise their own repo freely (ADR-0007).
    """
    return sorted(p for p in okr_dir.rglob("*") if p.is_file() and p.suffix in GOAL_FILE_SUFFIXES)


class _Builder:
    """Accumulates nodes, edges and references as the goal files are read.

    A class rather than a pile of parameters because four collections are filled in step
    with each other, and threading them separately through the objective and key result
    walks is how a node comes to be added without its references.
    """

    def __init__(self) -> None:
        self.nodes: dict[str, Node] = {}
        self.edges: list[Edge] = []
        self.references: list[Reference] = []
        self.violations: list[Violation] = []

    def read_file(self, relative: Path, parsed: GoalFile, doc: yaml.Node | None) -> None:
        """Walk one file's objectives, and the key results written inside them."""
        for position, objective in enumerate(parsed.objectives):
            self._read_objective(relative, doc, ("objectives", position), objective)

    # --- Nodes ------------------------------------------------------------------------

    def _add(self, node: Node) -> bool:
        """Register a node, reporting a clash rather than overwriting one.

        IDs are globally unique across the repo, so this is a set membership check
        (ADR-0007). A duplicate stops the load rather than waiting for the validator:
        with two nodes under one ID there is no index to build, and every reference to it
        would silently resolve to whichever copy happened to be read last.
        """
        existing = self.nodes.get(node.id)
        if existing is not None:
            self.violations.append(
                Violation(
                    Code.DUPLICATE_ID,
                    f"'{node.id}' is already used by the {existing.kind} at "
                    f"{existing.source}. Every objective and key result needs its own "
                    f"ID, because that ID is what other files reference.",
                    file=node.source.file,
                    line=node.source.line,
                )
            )
            return False
        self.nodes[node.id] = node
        return True

    def _read_objective(
        self,
        relative: Path,
        doc: yaml.Node | None,
        path: tuple[Step, ...],
        objective: Objective,
    ) -> None:
        node = Node(
            objective.id, NodeKind.OBJECTIVE, objective, Source(relative, _line_at(doc, path))
        )
        if not self._add(node):
            return
        self._read_owner(node)
        self._read_supports(relative, doc, path, node)
        for position, key_result in enumerate(objective.key_results):
            self._read_key_result(
                relative, doc, (*path, "key_results", position), key_result, objective.id
            )

    def _read_key_result(
        self,
        relative: Path,
        doc: yaml.Node | None,
        path: tuple[Step, ...],
        key_result: KeyResult,
        parent_id: str,
    ) -> None:
        source = Source(relative, _line_at(doc, path))
        node = Node(key_result.id, NodeKind.KEY_RESULT, key_result, source, parent_id=parent_id)
        if not self._add(node):
            return
        self._read_owner(node)

        # Nesting *is* the primary supports edge, materialised here rather than written
        # by an author (ADR-0006). It is marked implicit so that nothing downstream
        # reports it as a line somebody could go and change.
        self.edges.append(Edge(EdgeKind.SUPPORTS, node.id, parent_id, source, implicit=True))

        self._read_supports(relative, doc, path, node)
        self._read_dependencies(relative, doc, path, node, key_result)
        self._read_metrics(relative, doc, path, node, key_result)

    # --- References -------------------------------------------------------------------

    def _read_owner(self, node: Node) -> None:
        """Both node kinds require an owner, and both are resolved the same way."""
        self.references.append(Reference(RefKind.OWNER, node.owner_id, node.id, node.source))

    def _read_supports(
        self, relative: Path, doc: yaml.Node | None, path: tuple[Step, ...], node: Node
    ) -> None:
        """The `supports` edges written on a node, beyond any it gains from nesting."""
        for position, edge in enumerate(node.spec.supports):
            source = Source(relative, _line_at(doc, (*path, "supports", position)))
            self.edges.append(
                Edge(EdgeKind.SUPPORTS, node.id, edge.target, source, origin=edge.origin)
            )
            self.references.append(Reference(RefKind.EDGE, edge.target, node.id, source))

    def _read_dependencies(
        self,
        relative: Path,
        doc: yaml.Node | None,
        path: tuple[Step, ...],
        node: Node,
        key_result: KeyResult,
    ) -> None:
        for position, edge in enumerate(key_result.depends_on):
            source = Source(relative, _line_at(doc, (*path, "depends_on", position)))
            self.edges.append(Edge(EdgeKind.DEPENDS_ON, node.id, edge.target, source))
            self.references.append(Reference(RefKind.EDGE, edge.target, node.id, source))

    def _read_metrics(
        self,
        relative: Path,
        doc: yaml.Node | None,
        path: tuple[Step, ...],
        node: Node,
        key_result: KeyResult,
    ) -> None:
        """The three places a key result names a metric, each recorded at its own line.

        `watched_by` is kept apart from the other two because it fails in its own way: a
        metric that exists but is not guarded here is a false sense of coverage, which
        the validator reports separately from one that does not exist at all.
        """
        if key_result.metric is not None:
            self.references.append(
                Reference(
                    RefKind.METRIC,
                    key_result.metric,
                    node.id,
                    Source(relative, _line_at(doc, (*path, "metric"))),
                )
            )
        for position, guardrail in enumerate(key_result.guardrails):
            self.references.append(
                Reference(
                    RefKind.METRIC,
                    guardrail.metric,
                    node.id,
                    Source(relative, _line_at(doc, (*path, "guardrails", position, "metric"))),
                )
            )
        for position, anti_target in enumerate(key_result.anti_targets):
            for watched, metric_id in enumerate(anti_target.watched_by):
                where = (*path, "anti_targets", position, "watched_by", watched)
                self.references.append(
                    Reference(
                        RefKind.WATCHED_BY,
                        metric_id,
                        node.id,
                        Source(relative, _line_at(doc, where)),
                    )
                )


# --- The entry point -------------------------------------------------------------------


def load(path: Path | str | None = None) -> Graph:
    """Read the OKR repo containing `path` — or the working directory — into a graph.

    An explicit `path` may name a repo root or its `okr.yaml`. It may not name a
    subdirectory, because there is no supported way to load part of a graph.

    A graph comes back when the repo could be *built*: the files parsed, the fields are
    the shapes the schema declares, and every ID is unique. That is not the same as
    valid — dangling references, illegal edge shapes, cycles and orphans are all
    representable here, because they are questions about a finished graph and answering
    them needs one. `okr validate` asks them of this object.

    Raises `LoadError`, carrying every problem found rather than the first.
    """
    root = _root_from_explicit_path(Path(path)) if path is not None else find_root()
    marker = _load_marker(root)
    okr_dir = _declared_dir(root, marker)
    metrics_path = _declared_file(root, marker, "metrics_file", Code.METRICS_FILE_MISSING)
    owners_path = _declared_file(root, marker, "owners_file", Code.OWNERS_FILE_MISSING)

    builder = _Builder()
    metrics, metric_sources = _load_declarations(
        metrics_path, marker.metrics_file, MetricsFile, "metrics", "metric", builder.violations
    )
    owners, owner_sources = _load_declarations(
        owners_path, marker.owners_file, OwnersFile, "owners", "owner", builder.violations
    )

    goal_files: list[Path] = []
    for goal_file in _goal_files(okr_dir):
        relative = goal_file.relative_to(root)
        goal_files.append(relative)
        data, doc, problem = _parse_yaml(goal_file, relative, Code.YAML_UNPARSEABLE)
        if problem is not None:
            builder.violations.append(problem)
            continue
        try:
            parsed = GoalFile.model_validate(data if data is not None else {})
        except ValidationError as error:
            builder.violations.extend(_violations_from(error, relative, doc))
            continue
        builder.read_file(relative, parsed, doc)

    # Checked after the files are read rather than beside the other marker paths,
    # because whether an absent owners.yaml matters depends on there being goals to own.
    no_owners = _check_owners_exist(marker, owners_path, len(builder.nodes))
    if no_owners is not None:
        builder.violations.append(no_owners)

    if builder.violations:
        raise LoadError(builder.violations)

    return Graph(
        root=root,
        marker=marker,
        nodes=builder.nodes,
        edges=tuple(builder.edges),
        references=tuple(builder.references),
        metrics=metrics,
        owners=owners,
        metric_sources=metric_sources,
        owner_sources=owner_sources,
        goal_files=tuple(goal_files),
    )
