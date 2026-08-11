"""Counting how much of a spec is filled in.

[ADR-0011](../../../docs/adr/0011-completeness-rubric.md), implemented. Four checks on a
key result, one on an objective, and a count of how many passed. That is the whole thing.

**It measures whether a spec is filled in. It is not a judgement about whether the goals
are good ones.** A well-conceived objective can score badly and a worthless one can score
full marks. Every line of output has to survive that distinction being read carelessly,
which is why the number is `12 of 19` and never a grade out of ten: a graded scale implies
weights, weights would have to be defended, and the first person to see a sound objective
score 40% would conclude the tool is wrong about their strategy rather than quiet about it.

**Validation covers what is required; scoring covers what is optional but valuable.** If a
field's absence is illegal it is a validation error and never appears here. Nothing is
both, which is why the rubric is this short.

**Structural, deterministic, and recountable by hand.** No model, no API key, no weights,
and no arithmetic a reader cannot repeat from the YAML in front of them. `success_criteria:
[TBD]` scores as present — a structural check cannot see vacuity, and pretending otherwise
is the model-dependence the ADR rejects. That gap is the Champion's semantic review to
fill, and it is emitted as questions, never as a number, and never merged into this one.

**Commitment level appears in exactly one place: the order findings are reported in.** A
committed key result missing guardrails is more urgent than an aspirational one missing the
same, and scores identically. Severity is presentation. Putting it in the arithmetic would
mean two identical specs scoring differently, which is indefensible.

Nothing here formats for a terminal.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from .graph import Graph, Node
from .models import Commitment, KeyResult, KeyResultType


class Dimension(StrEnum):
    """One check. The values are the rubric's own labels, so a reader can follow the ADR.

    Five, and adding a sixth is a decision about what matters rather than an addition to a
    list: every extra dimension is a weighting choice in disguise, and a longer rubric
    would make the number look more precise while making it less defensible.
    """

    SUCCESS_CRITERIA = "K1"
    GUARDRAILS = "K2"
    ANTI_TARGETS = "K3"
    ANTI_TARGETS_DEFENDED = "K4"
    NOT_BUILD_TRAPPED = "O1"

    @property
    def missing(self) -> str:
        """What to call this when it is absent, as it appears after 'missing:'."""
        return _MISSING[self]


#: How a failed check is named in a report. Short noun phrases, because they are read as a
#: list — "missing: guardrails, anti-targets" — and that phrasing is what makes a
#: before-and-after legible at a glance.
_MISSING: Final[dict[Dimension, str]] = {
    Dimension.SUCCESS_CRITERIA: "success criteria",
    Dimension.GUARDRAILS: "guardrails",
    Dimension.ANTI_TARGETS: "anti-targets",
    Dimension.ANTI_TARGETS_DEFENDED: "a defence on every anti-target",
    Dimension.NOT_BUILD_TRAPPED: "a key result that moves a number",
}


@dataclass(frozen=True, slots=True)
class Check:
    """One dimension, asked of one node, answered."""

    dimension: Dimension
    passed: bool


@dataclass(frozen=True, slots=True)
class Tally:
    """`n of m`, and nothing else. No weights, and no grade.

    A denominator that varies honestly with what applies is the point: an objective is
    asked one question and a key result four, so the two are never averaged into a scale
    whose steps somebody would have to justify.
    """

    passed: int
    total: int

    @property
    def percentage(self) -> int | None:
        """For display only. None when nothing applies, which is not the same as zero."""
        return None if self.total == 0 else round(self.passed / self.total * 100)

    def __add__(self, other: Tally) -> Tally:
        return Tally(self.passed + other.passed, self.total + other.total)

    def __str__(self) -> str:
        return f"{self.passed} of {self.total}"


@dataclass(frozen=True, slots=True)
class NodeScore:
    """One node's checks, and what it is missing."""

    node: Node
    commitment: Commitment
    """Effective, not declared: a key result with none of its own takes its objective's.

    Read only when ordering a report. It is deliberately absent from every count here.
    """

    checks: tuple[Check, ...]

    @property
    def tally(self) -> Tally:
        return Tally(sum(1 for check in self.checks if check.passed), len(self.checks))

    @property
    def missing(self) -> tuple[Dimension, ...]:
        """The dimensions that failed, in rubric order. Naming them is the useful part."""
        return tuple(check.dimension for check in self.checks if not check.passed)


@dataclass(frozen=True, slots=True)
class ObjectiveScore:
    """An objective, its own check, and the key results written inside it.

    Containment rather than the whole supporting subgraph, which matters for one reason:
    every key result is written inside exactly one objective, so these groups partition the
    repo and their totals add up to the roll-up exactly. A reader can recount the number
    from the files. Grouping by supporting edges would count a key result that supports two
    objectives twice, and the arithmetic would stop being checkable by hand.
    """

    objective: NodeScore
    key_results: tuple[NodeScore, ...]

    @property
    def tally(self) -> Tally:
        return sum((kr.tally for kr in self.key_results), self.objective.tally)


@dataclass(frozen=True, slots=True)
class Scorecard:
    """A whole repo's completeness: the roll-up, and every node behind it."""

    objectives: tuple[ObjectiveScore, ...]

    @property
    def tally(self) -> Tally:
        return sum((objective.tally for objective in self.objectives), Tally(0, 0))

    @property
    def nodes(self) -> tuple[NodeScore, ...]:
        """Every scored node, objectives and key results alike, in file order."""
        return tuple(
            scored
            for objective in self.objectives
            for scored in (objective.objective, *objective.key_results)
        )

    @property
    def findings(self) -> tuple[NodeScore, ...]:
        """Everything with something missing, most urgent first.

        The one place commitment level is read. A committed key result missing guardrails
        is the same score as an aspirational one missing guardrails and a more pressing
        gap, so it is reported first — and after commitment, the node missing more comes
        before the node missing less, with file order breaking the remaining ties so the
        report is reproducible.
        """
        order = {scored.node.id: position for position, scored in enumerate(self.nodes)}

        def urgency(scored: NodeScore) -> tuple[int, int, int]:
            return (
                0 if scored.commitment is Commitment.COMMITTED else 1,
                -len(scored.missing),
                order[scored.node.id],
            )

        return tuple(sorted((scored for scored in self.nodes if scored.missing), key=urgency))


def score(graph: Graph) -> Scorecard:
    """Count how much of this repo's spec is filled in.

    Never raises and never fails: a low score is a measurement, not a violation. A repo
    with nothing in it scores `0 of 0`, which is honest — it has not been filled in badly,
    it has not been filled in at all.
    """
    return Scorecard(
        tuple(
            ObjectiveScore(
                _objective_score(graph, objective),
                tuple(
                    _key_result_score(key_result, objective)
                    for key_result in graph.key_results_of(objective.id)
                ),
            )
            for objective in graph.objectives
        )
    )


def _objective_score(graph: Graph, objective: Node) -> NodeScore:
    """The one question asked of an objective: is anything under it a number to move?

    A build trap is an objective made entirely of things to ship. It is a real failure —
    a quarter of delivery with nothing that says whether any of it worked — and it is only
    visible when the key results are read together, which is why it is scored on the
    objective rather than on any one of them.
    """
    key_results = graph.key_results_of(objective.id)
    moves_a_number = any(
        isinstance(node.spec, KeyResult) and node.spec.type is KeyResultType.METRIC
        for node in key_results
    )
    return NodeScore(
        objective,
        _declared_commitment(objective),
        (Check(Dimension.NOT_BUILD_TRAPPED, moves_a_number),),
    )


def _key_result_score(key_result: Node, objective: Node) -> NodeScore:
    """The four questions asked of a key result.

    The fourth is vacuously true when there are no anti-targets, which the third already
    reports. Nothing is penalised twice for one gap.
    """
    spec = key_result.spec
    if not isinstance(spec, KeyResult):  # pragma: no cover — a key result node holds one
        raise TypeError("A key result node must carry a key result")
    return NodeScore(
        key_result,
        spec.commitment or _declared_commitment(objective),
        (
            Check(Dimension.SUCCESS_CRITERIA, bool(spec.success_criteria)),
            Check(Dimension.GUARDRAILS, bool(spec.guardrails)),
            Check(Dimension.ANTI_TARGETS, bool(spec.anti_targets)),
            Check(
                Dimension.ANTI_TARGETS_DEFENDED,
                all(target.restraint or target.watched_by for target in spec.anti_targets),
            ),
        ),
    )


def _declared_commitment(objective: Node) -> Commitment:
    """An objective's commitment. Required by the schema, so the fallback never fires."""
    return objective.spec.commitment or Commitment.ASPIRATIONAL
