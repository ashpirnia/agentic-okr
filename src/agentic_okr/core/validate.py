"""Asking a finished graph whether it holds together.

The loader answers "could this be read?". This answers "does it make sense?" — the
questions that need a whole graph to answer at all: does every reference resolve, is every
edge a shape the model allows, does anything contribute to itself, is anything stranded.

Three properties shape the module.

**Severity is not a list.** A cycle in `supports` is an error and a cycle in `depends_on`
is a warning that still exits zero (ADR-0006), so a caller needs to know which of the
things it was handed actually fail. `Report` separates them, and the severity is read off
the code rather than decided here.

**The relations are traversed separately.** A path that alternates between `supports` and
`depends_on` is a cycle in neither, because the two mean different things and a mixed
circle asserts nothing incoherent.

**One cause is reported once.** An owner ID renamed in `owners.yaml` breaks every node
that named it — twelve references, one fix — and printing twelve identical failures buries
the one thing worth reading. Unresolved references are therefore grouped by their
*target*: one violation per thing that does not exist, listing every place that expected
it. Three key results with three different mistyped metrics stay three violations, because
they are three fixes.

Nothing here formats for a terminal, and nothing exits. The CLI renders a report; the
Conductor's lint will consume the same objects without a terminal in sight.
"""

from collections import deque
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from itertools import groupby

from .codes import Code, Severity
from .graph import Edge, EdgeKind, Graph, Node, NodeKind, Reference, RefKind, Source
from .models import Commitment, KeyResult, KeyResultType
from .violations import Violation, sort_violations


@dataclass(frozen=True, slots=True)
class Report:
    """Everything validation found, with the errors kept apart from the warnings.

    `okr validate` exits non-zero when `errors` is non-empty and never on `warnings`
    alone. That distinction is part of the published contract rather than a presentation
    choice: a warning marks something legal and occasionally correct, and a validator that
    failed on those would teach people to write false specs to satisfy it.
    """

    violations: tuple[Violation, ...] = ()

    @property
    def errors(self) -> tuple[Violation, ...]:
        return tuple(v for v in self.violations if v.severity is Severity.ERROR)

    @property
    def warnings(self) -> tuple[Violation, ...]:
        return tuple(v for v in self.violations if v.severity is Severity.WARNING)

    @property
    def ok(self) -> bool:
        """Whether the run passes. Warnings do not fail it."""
        return not self.errors

    def __bool__(self) -> bool:
        return self.ok


def validate(graph: Graph) -> Report:
    """Check a loaded graph, and report everything wrong with it.

    Never raises on a bad graph: an invalid OKR repo is an ordinary outcome that a goal
    owner is expected to read and act on, not an exceptional one. The exception the loader
    raises is for a graph that could not be *built* at all.
    """
    violations = [
        *_unresolved_references(graph),
        *_unguarded_watchers(graph),
        *_edge_shapes(graph),
        *_cycles(graph),
        *_content_rules(graph),
        *_orphans(graph),
        *_objectives_without_key_results(graph),
        *_commitment_dials(graph),
        *_unused_declarations(graph),
    ]
    return Report(tuple(sort_violations(violations)))


# --- References ------------------------------------------------------------------------


def _unresolved_references(graph: Graph) -> list[Violation]:
    """Every reference that points at something nobody declared, grouped by target.

    The three vocabularies fail differently — an edge to nothing breaks the graph, a
    metric to nothing breaks the join to measurement, an owner to nothing breaks review
    routing — so each has its own code. What they share is the grouping: the thing that
    does not exist is the fix, and the places expecting it are the symptoms.
    """
    return [
        *_grouped(
            graph,
            RefKind.EDGE,
            Code.DANGLING_EDGE_REF,
            lambda target: target in graph.nodes,
            lambda target, where: (
                f"Nothing in this repo declares '{target}', and it is named as a "
                f"connection {_places(where)}. Either the goal it names was deleted or "
                f"renamed, or the ID is misspelled — a connection to a goal that does not "
                f"exist is the one thing flat files cannot catch on their own."
            ),
        ),
        *_grouped(
            graph,
            RefKind.METRIC,
            Code.DANGLING_METRIC_REF,
            lambda target: target in graph.metrics,
            lambda target, where: (
                f"No metric called '{target}' is declared in "
                f"{graph.marker.metrics_file}, and it is named {_places(where)}. Declare "
                f"it there, or correct the spelling: a metric is declared once so that "
                f"everything measuring it agrees on what is being counted."
            ),
        ),
        *_grouped(
            graph,
            RefKind.OWNER,
            Code.DANGLING_OWNER_REF,
            lambda target: target in graph.owners,
            lambda target, where: (
                f"No owner called '{target}' is declared in {graph.marker.owners_file}, "
                f"and it is named {_places(where)}. Declare them there, or correct the "
                f"spelling — review of a change goes to the owners it affects, and a name "
                f"that resolves to nobody reaches nobody."
            ),
        ),
        *_grouped(
            graph,
            RefKind.WATCHED_BY,
            Code.DANGLING_WATCHED_BY_REF,
            lambda target: target in graph.metrics,
            lambda target, where: (
                f"An anti-target says it is watched by '{target}', and no metric of that "
                f"name is declared in {graph.marker.metrics_file}. It is named "
                f"{_places(where)}. A watching metric that does not exist watches nothing."
            ),
        ),
    ]


def _grouped(
    graph: Graph,
    kind: RefKind,
    code: Code,
    resolves: Callable[[str], bool],
    describe: Callable[[str, Sequence[Reference]], str],
) -> list[Violation]:
    """One violation per unresolvable target, listing every place that expected it.

    The grouping key is the *target*, never the reference site. A per-site error is right
    when the sites are independently fixable and wrong when they share one fix, and an ID
    that was renamed in one place shares one fix across all of them.
    """
    unresolved = [r for r in graph.references_of(kind) if not resolves(r.target_id)]
    violations = []
    for target, group in groupby(sorted(unresolved, key=_reference_order), lambda r: r.target_id):
        where = list(group)
        first = where[0].source
        violations.append(
            Violation(code, describe(target, where), file=first.file, line=first.line)
        )
    return violations


def _reference_order(reference: Reference) -> tuple[str, str, int]:
    """Group by target, and order the places within a group as a reader would fix them."""
    return (reference.target_id, str(reference.source.file), reference.source.line or 0)


def _places(references: Sequence[Reference]) -> str:
    """The locations a grouped violation covers, as a phrase ending a sentence.

    Every location is listed rather than counted. A goal owner renaming an owner ID has to
    visit each one, and a message saying 'in 12 places' sends them searching for the other
    eleven.
    """
    locations = ", ".join(f"{r.from_node_id} ({r.source})" for r in references)
    if len(references) == 1:
        return f"by {locations}"
    return f"by {len(references)} goals: {locations}"


def _unguarded_watchers(graph: Graph) -> list[Violation]:
    """`watched_by` naming a real metric that this key result does not guard.

    A metric that exists but is not guarded here reads as coverage in review and provides
    none, which is worse than an honest gap (ADR-0009). Grouped by key result and metric
    together, because that pair is the fix: adding the one guardrail settles every
    anti-target on the key result that named it.
    """
    violations = []
    seen: set[tuple[str, str]] = set()
    for reference in graph.references_of(RefKind.WATCHED_BY):
        node = graph.node(reference.from_node_id)
        pair = (reference.from_node_id, reference.target_id)
        if node is None or reference.target_id not in graph.metrics or pair in seen:
            continue
        if reference.target_id in _guarded_metrics(node):
            continue
        seen.add(pair)
        violations.append(
            Violation(
                Code.WATCHED_BY_NOT_GUARDED,
                f"'{reference.target_id}' is listed as watching an anti-target on "
                f"'{node.id}', but this key result has no guardrail on it. Nothing would "
                f"stop the move it is supposed to catch. Add a guardrail on "
                f"'{reference.target_id}' here, or remove it from 'watched_by'.",
                file=reference.source.file,
                line=reference.source.line,
            )
        )
    return violations


def _guarded_metrics(node: Node) -> frozenset[str]:
    """The metrics guarded on this key result, or nothing for an objective."""
    if not isinstance(node.spec, KeyResult):
        return frozenset()
    return frozenset(guardrail.metric for guardrail in node.spec.guardrails)


# --- Edges -----------------------------------------------------------------------------


def _edge_shapes(graph: Graph) -> list[Violation]:
    """Whether each edge connects a pair of node kinds the model allows.

    Skips an edge whose target does not resolve: that is already reported once, against
    the thing that does not exist, and a second complaint about the shape of a connection
    to a goal that is not there tells nobody anything.
    """
    violations = []
    for edge in graph.edges:
        source = graph.node(edge.source_id)
        target = graph.node(edge.target_id)
        if source is None or target is None:
            continue

        if edge.source_id == edge.target_id:
            violations.append(
                Violation(
                    Code.SELF_REFERENCE,
                    f"'{source.id}' {edge.kind.value.replace('_', ' ')} itself. A goal "
                    f"cannot contribute to, or wait for, itself.",
                    file=edge.source.file,
                    line=edge.source.line,
                )
            )
            continue

        if edge.kind is EdgeKind.DEPENDS_ON and target.kind is not NodeKind.KEY_RESULT:
            violations.append(
                Violation(
                    Code.DEPENDS_ON_NOT_KEY_RESULT,
                    f"'{source.id}' depends on '{target.id}', which is an objective. A "
                    f"dependency is on the specific key result that has to land first — "
                    f"an objective is never finished in the way something can wait for.",
                    file=edge.source.file,
                    line=edge.source.line,
                )
            )
            continue

        if edge.kind is EdgeKind.SUPPORTS and source.kind is NodeKind.KEY_RESULT:
            violations.extend(_key_result_supports(edge, source, target))
    return violations


def _key_result_supports(edge: Edge, source: Node, target: Node) -> list[Violation]:
    """The two ways a key result's `supports` goes wrong.

    A key result contributes to *objectives* and unblocks *key results*, so `supports`
    between two key results is always the wrong relationship rather than an unusual one
    (ADR-0006). Restating the containing objective is the other: nesting already
    materialises that edge, and two representations of one relationship is how they come
    to disagree.
    """
    if target.kind is NodeKind.KEY_RESULT:
        return [
            Violation(
                Code.ILLEGAL_EDGE_SHAPE,
                f"'{source.id}' supports '{target.id}', and both are key results. A key "
                f"result contributes to an objective; when it cannot finish until another "
                f"key result does, that is 'depends_on'.",
                file=edge.source.file,
                line=edge.source.line,
            )
        ]
    if not edge.implicit and target.id == source.parent_id:
        return [
            Violation(
                Code.REDUNDANT_CONTAINMENT_EDGE,
                f"'{source.id}' is already written inside '{target.id}', so it does not "
                f"list it under 'supports'. Being nested is that connection. Remove the "
                f"line — two ways of saying one thing is how they come to disagree.",
                file=edge.source.file,
                line=edge.source.line,
            )
        ]
    return []


# --- Cycles ----------------------------------------------------------------------------

#: Which code each relation's cycles carry, and the sentence that goes with one. The
#: asymmetry is the decision, not an oversight: a goal contributing to itself cannot have
#: its contribution resolved, while two teams depending on each other is real and
#: sometimes legitimately phased, and a validator that rejected it would teach people to
#: omit true information (ADR-0006).
_CYCLE_RULES: dict[EdgeKind, tuple[Code, str]] = {
    EdgeKind.SUPPORTS: (
        Code.SUPPORTS_CYCLE,
        "These goals contribute to each other in a circle: {path}. A goal that "
        "contributes to itself, directly or through others, cannot have its contribution "
        "worked out. Break the circle by removing one of these connections.",
    ),
    EdgeKind.DEPENDS_ON: (
        Code.DEPENDS_ON_CYCLE,
        "These key results wait on each other in a circle: {path}. That is allowed — "
        "mutual dependency between teams is sometimes real and phased deliberately — but "
        "check it is what you meant, because as written neither side can start.",
    ),
}


def _cycles(graph: Graph) -> list[Violation]:
    """Circular `supports` and circular `depends_on`, each traversed on its own.

    Reported once per circle rather than once per edge in it: every edge in a cycle has
    the same single fix, which is to remove one of them. Self-reference is left out — it
    is a cycle of one and is already reported with its own code, at the line somebody
    wrote.
    """
    violations = []
    for kind, (code, template) in _CYCLE_RULES.items():
        adjacency = _adjacency(graph, kind)
        for component in sorted(_circular_components(adjacency), key=min):
            path = _shortest_cycle(min(component), adjacency, component)
            source = _edge_source(graph, kind, path[0], path[1])
            violations.append(
                Violation(
                    code,
                    template.format(path=" → ".join(path)),
                    file=source.file if source else None,
                    line=source.line if source else None,
                )
            )
    return violations


def _adjacency(graph: Graph, kind: EdgeKind) -> dict[str, list[str]]:
    """One relation's edges, as a map from each node to what it points at.

    Only edges between nodes that both exist: a dangling target is reported once as a
    dangling reference, and following it here would invent a node to put in a cycle.
    Implicit containment edges are included — an objective that supports one of its own
    key results really is a goal contributing to itself.
    """
    adjacency: dict[str, list[str]] = {node_id: [] for node_id in graph.nodes}
    for edge in graph.edges_of_kind(kind):
        if edge.source_id != edge.target_id and edge.target_id in adjacency:
            adjacency[edge.source_id].append(edge.target_id)
    return adjacency


def _circular_components(adjacency: dict[str, list[str]]) -> list[set[str]]:
    """The strongly connected components with more than one node in them.

    Tarjan's algorithm, written iteratively rather than recursively: nothing stops an
    organisation from having a goal chain deeper than the interpreter's stack, and a
    validator that crashed on one would be reporting a bug of ours as a problem with their
    goals.
    """
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[set[str]] = []
    counter = 0

    for root in adjacency:
        if root in index:
            continue
        work: list[tuple[str, int]] = [(root, 0)]
        while work:
            node, position = work[-1]
            if position == 0:
                index[node] = low[node] = counter
                counter += 1
                stack.append(node)
                on_stack.add(node)
            descended = False
            neighbours = adjacency[node]
            while position < len(neighbours):
                neighbour = neighbours[position]
                position += 1
                work[-1] = (node, position)
                if neighbour not in index:
                    work.append((neighbour, 0))
                    descended = True
                    break
                if neighbour in on_stack:
                    low[node] = min(low[node], index[neighbour])
            if descended:
                continue
            work.pop()
            if work:
                low[work[-1][0]] = min(low[work[-1][0]], low[node])
            if low[node] == index[node]:
                component = set()
                while True:
                    popped = stack.pop()
                    on_stack.discard(popped)
                    component.add(popped)
                    if popped == node:
                        break
                if len(component) > 1:
                    components.append(component)
    return components


def _shortest_cycle(start: str, adjacency: dict[str, list[str]], members: set[str]) -> list[str]:
    """The shortest circle through `start` inside a component, for the message.

    A component can hold several overlapping circles. Printing the shortest one keeps the
    sentence readable, and any of them names connections whose removal breaks the circle.
    """
    previous: dict[str, str | None] = {start: None}
    queue = deque([start])
    while queue:
        current = queue.popleft()
        for neighbour in adjacency[current]:
            if neighbour not in members:
                continue
            if neighbour == start:
                path = [current]
                while (parent := previous[path[-1]]) is not None:
                    path.append(parent)
                return [*reversed(path), start]
            if neighbour not in previous:
                previous[neighbour] = current
                queue.append(neighbour)
    return [start]


def _edge_source(graph: Graph, kind: EdgeKind, source_id: str, target_id: str) -> Source | None:
    """Where one edge of a circle was written, so the report points at a line to remove."""
    for edge in graph.outgoing(source_id, kind):
        if edge.target_id == target_id and not edge.implicit:
            return edge.source
    return None


# --- Content rules ---------------------------------------------------------------------


def _content_rules(graph: Graph) -> list[Violation]:
    """What each kind of key result has to carry to assert anything at all.

    Computable from a single key result, and still the validator's rather than the
    schema's: a model raises on the first failure, and a goal owner needs every problem in
    their file at once, each with a line (ADR-0011).
    """
    violations = []
    for node in graph.key_results:
        if isinstance(node.spec, KeyResult):
            violations.extend(_key_result_content(node, node.spec))
    return violations


def _key_result_content(node: Node, spec: KeyResult) -> list[Violation]:
    """The three rules one key result's declared type puts on the rest of its fields."""
    is_milestone = spec.type is KeyResultType.MILESTONE
    problems = []
    if not is_milestone and (spec.metric is None or spec.target is None):
        problems.append(
            (
                Code.METRIC_KR_WITHOUT_METRIC,
                f"'{node.id}' is a metric key result, so it needs both the metric it "
                f"moves and the target that metric should reach. Without them there is no "
                f"number to move. If this is something you ship rather than a number you "
                f"move, its type is 'milestone'.",
            )
        )
    if is_milestone and (spec.metric is not None or spec.target is not None):
        problems.append(
            (
                Code.MILESTONE_KR_WITH_METRIC,
                f"'{node.id}' is a milestone key result, and milestones do not carry a "
                f"metric or a target — a milestone is shipped, not moved. If there is a "
                f"number here, its type is 'metric'.",
            )
        )
    if is_milestone and not spec.success_criteria:
        problems.append(
            (
                Code.MILESTONE_KR_WITHOUT_CRITERIA,
                f"'{node.id}' is a milestone key result with no success criteria. It has "
                f"no metric and no target either, so nothing about it can be checked and "
                f"it asserts nothing at all. Write down what 'done' means to someone who "
                f"will not be in the room.",
            )
        )
    return [
        Violation(code, message, file=node.source.file, line=node.source.line)
        for code, message in problems
    ]


# --- Warnings --------------------------------------------------------------------------


def _connected(graph: Graph, node: Node) -> bool:
    """Whether anything supports this objective, or it supports anything.

    Containment counts, because nesting is itself a supporting edge — which is what makes
    an objective with key results beneath it connected by definition.
    """
    return bool(
        graph.outgoing(node.id, EdgeKind.SUPPORTS) or graph.incoming(node.id, EdgeKind.SUPPORTS)
    )


def _orphans(graph: Graph) -> list[Violation]:
    """An objective connected to nothing in either direction.

    Nothing supports it and it supports nothing — including the key results written inside
    it, whose containment is itself a supporting edge. So a top-level objective with key
    results beneath it is not an orphan; an objective with neither a parent nor anything
    under it is a ladder somebody started and did not finish.
    """
    violations = []
    for node in graph.objectives:
        if _connected(graph, node):
            continue
        violations.append(
            Violation(
                Code.ORPHAN_OBJECTIVE,
                f"'{node.id}' is connected to nothing: it has no key results beneath it, "
                f"nothing contributes to it, and it contributes to nothing. Usually this "
                f"is a ladder somebody started and did not finish.",
                file=node.source.file,
                line=node.source.line,
            )
        )
    return violations


def _objectives_without_key_results(graph: Graph) -> list[Violation]:
    """An objective that other goals ladder up to, with nothing written under it.

    Legal, and sometimes deliberate: a top-level objective can be the point several teams
    aim at, and the work is genuinely in their files rather than in it. What it still lacks
    is any way to tell whether the ambition it states was reached.

    Never raised alongside `W102_ORPHAN_OBJECTIVE`, which covers an objective with no key
    results *and* no connections at all. That is the same absence with more missing around
    it, and its message already says the objective has nothing beneath it — two warnings on
    one line would be one cause reported twice.
    """
    return [
        Violation(
            Code.OBJECTIVE_WITHOUT_KEY_RESULTS,
            f"'{node.id}' has no key results of its own. Other goals ladder up to it, which "
            f"is a legitimate way to use an objective — but nothing written under it says "
            f"whether this objective was reached, so as it stands it states an ambition and "
            f"no way to check it.",
            file=node.source.file,
            line=node.source.line,
        )
        for node in graph.objectives
        if not graph.key_results_of(node.id) and _connected(graph, node)
    ]


def _commitment_dials(graph: Graph) -> list[Violation]:
    """A committed objective whose key results all override to aspirational.

    Legal, and occasionally honest. Usually it is commitment level being used as a
    difficulty dial rather than a claim about ambition: the objective is declared a
    must-hit and then everything that would actually establish it is marked a stretch
    (ADR-0011).
    """
    violations = []
    for objective in graph.objectives:
        if objective.spec.commitment is not Commitment.COMMITTED:
            continue
        key_results = graph.key_results_of(objective.id)
        if not key_results:
            continue
        if any(kr.spec.commitment is not Commitment.ASPIRATIONAL for kr in key_results):
            continue
        violations.append(
            Violation(
                Code.ALL_KRS_ASPIRATIONAL,
                f"'{objective.id}' is committed, and every key result beneath it "
                f"overrides that to aspirational. Nothing under it is a must-hit, so the "
                f"objective's commitment claims something none of its key results do.",
                file=objective.source.file,
                line=objective.source.line,
            )
        )
    return violations


def _unused_declarations(graph: Graph) -> list[Violation]:
    """A metric or an owner declared and never referred to.

    Harmless on its own. Worth saying because the usual cause is a misspelling somewhere
    else: the reference that should have reached this is sitting one line away, spelled
    differently, and reported as dangling.
    """
    used_metrics = {
        reference.target_id
        for kind in (RefKind.METRIC, RefKind.WATCHED_BY)
        for reference in graph.references_of(kind)
    }
    used_owners = {reference.target_id for reference in graph.references_of(RefKind.OWNER)}
    return [
        *_unused(
            graph.metrics,
            used_metrics,
            graph.metric_sources,
            Code.UNUSED_METRIC,
            "'{id}' is declared as a metric, and no key result targets it and no "
            "guardrail watches it. Either something meant to name it is spelled "
            "differently, or this is left over from a previous cycle.",
        ),
        *_unused(
            graph.owners,
            used_owners,
            graph.owner_sources,
            Code.UNUSED_OWNER,
            "'{id}' is declared as an owner and owns nothing. Either something meant to "
            "name them is spelled differently, or this is left over from a previous cycle.",
        ),
    ]


def _unused(
    declared: Iterable[str], used: set[str], sources: dict[str, Source], code: Code, template: str
) -> list[Violation]:
    violations = []
    for declared_id in declared:
        if declared_id in used:
            continue
        source = sources.get(declared_id)
        violations.append(
            Violation(
                code,
                template.format(id=declared_id),
                file=source.file if source else None,
                line=source.line if source else None,
            )
        )
    return violations
