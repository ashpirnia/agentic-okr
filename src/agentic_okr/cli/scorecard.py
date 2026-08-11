"""Printing a completeness score without letting it read as a grade.

The number is `12 of 19`, and a reader can recount it from the files. Everything here works
to keep it that way: no bar, no letter, no colour running red-to-green across a scale, and
a sentence under the total saying what it counts. A chart is the most likely place the
distinction blurs ([ADR-0011](../../../docs/adr/0011-completeness-rubric.md)), and a
progress bar is a chart.

Two sections, doing different jobs. **What is missing** is ordered by severity and is what
somebody acts on — it is the only place commitment level appears, and it names the specific
gaps rather than counting them, because "missing: guardrails, anti-targets" is what makes a
before-and-after legible. **Where the number comes from** is in file order and is what
somebody recounts: every objective, its own check, its key results, and a subtotal that
adds up.
"""

from typing import Any

from rich.console import Console
from rich.padding import Padding
from rich.table import Table
from rich.text import Text

from agentic_okr.core import Commitment, Graph, NodeKind
from agentic_okr.core.score import Dimension, NodeScore, ObjectiveScore, Scorecard, Tally

#: What the score is, in one line, under the total. It is here because the alternative —
#: a reader taking `12 of 19` as a verdict on their strategy — is the single failure this
#: feature has to avoid, and it costs one line to say so every time.
MEANING = "How much of your spec is written down. Not whether the goals are good ones."

_GLYPHS: dict[NodeKind, str] = {NodeKind.OBJECTIVE: "◆", NodeKind.KEY_RESULT: "•"}


def render(console: Console, graph: Graph, card: Scorecard) -> None:
    """The whole scorecard: the total, what is missing, and where the number came from."""
    console.print(
        Text.assemble(
            (graph.root.name, "bold"), ("  ", ""), (f"period {graph.marker.period}", "dim")
        )
    )
    console.print()

    if not card.objectives:
        console.print(Text("There is nothing to score yet — this repo has no goals in it."))
        return

    console.print(Text(str(card.tally), style="bold"), _percentage(card.tally, style="bold"))
    console.print(Text(MEANING, style="dim"))
    console.print()
    _render_missing(console, card)
    _render_breakdown(console, card)


def _render_missing(console: Console, card: Scorecard) -> None:
    """What is not written down, most pressing first."""
    if not card.findings:
        console.print(Text("Nothing is missing. Every check passes.", style="bold green"))
        console.print()
        return

    table = Table(box=None, show_header=False, padding=(0, 2, 0, 0), pad_edge=False)
    table.add_column("goal", no_wrap=True)
    table.add_column("score", no_wrap=True, justify="right")
    table.add_column("commitment", no_wrap=True)
    table.add_column("missing", overflow="fold")
    for scored in card.findings:
        table.add_row(
            _name(scored),
            Text(str(scored.tally), style="dim"),
            _commitment(scored),
            _missing(scored),
        )
    console.print(Text("What is missing", style="bold"))
    console.print(Padding(table, (0, 0, 1, 2)))


def _render_breakdown(console: Console, card: Scorecard) -> None:
    """Every objective and key result, in file order, with subtotals that add up.

    This is the section that makes the roll-up checkable: an objective's own score plus
    its key results' is its subtotal, and the subtotals are the total.
    """
    table = Table(box=None, show_header=False, padding=(0, 2, 0, 0), pad_edge=False)
    table.add_column("goal", no_wrap=True)
    table.add_column("score", no_wrap=True, justify="right")
    table.add_column("percent", no_wrap=True, justify="right")
    table.add_column("subtotal", style="dim", overflow="fold")
    for objective in card.objectives:
        table.add_row(
            _name(objective.objective),
            Text(str(objective.objective.tally)),
            _percentage(objective.objective.tally),
            _subtotal(objective),
        )
        for key_result in objective.key_results:
            table.add_row(
                Text("  ").append_text(_name(key_result)),
                Text(str(key_result.tally)),
                _percentage(key_result.tally),
                "",
            )
    console.print(Text("Where the number comes from", style="bold"))
    console.print(Padding(table, (0, 0, 1, 2)))


def _name(scored: NodeScore) -> Text:
    kind = scored.node.kind
    return Text.assemble((f"{_GLYPHS[kind]} ", "dim"), (scored.node.id, ""))


def _percentage(tally: Tally, style: str = "dim") -> Text:
    """A percentage, for reading at a glance. The count beside it is the real number."""
    percentage = tally.percentage
    return Text("" if percentage is None else f"({percentage}%)", style=style)


def _subtotal(objective: ObjectiveScore) -> str:
    """What this objective and everything written inside it contribute to the total."""
    if not objective.key_results:
        return ""
    return f"{objective.tally} with its key results"


def _commitment(scored: NodeScore) -> Text:
    """The one place commitment level appears, and it changes no number.

    A committed goal missing guardrails scores exactly what an aspirational one missing
    guardrails scores. What it gets is this word, and a place nearer the top.
    """
    committed = scored.commitment is Commitment.COMMITTED
    return Text(scored.commitment.value, style="yellow" if committed else "dim")


def _missing(scored: NodeScore) -> Text:
    """The specific gaps, named. A count would not tell anybody what to go and write.

    Read off the checks rather than the dimensions, because one check can fail for two
    reasons a reader would act on differently — an objective with only milestones and an
    objective with nothing at all both fail `O1`, and are not the same thing to fix.
    """
    return Text(f"missing: {', '.join(scored.gaps)}")


# --- For a machine ----------------------------------------------------------------------

#: Every dimension, so a consumer reading `checks` can label them without a lookup table
#: of its own. Kept here rather than in `core` because naming is presentation.
RUBRIC: dict[str, str] = {dimension.value: dimension.missing for dimension in Dimension}


def payload(graph: Graph, card: Scorecard) -> dict[str, Any]:
    """The scorecard for something that is not a person.

    Every check is named by its rubric label — `K1`, `O1` — and carries its own pass or
    fail, so a consumer can recount the total rather than trusting it.
    """
    return {
        "repo": {
            "root": str(graph.root),
            "name": graph.root.name,
            "period": graph.marker.period,
        },
        "score": _tally(card.tally),
        "meaning": MEANING,
        "rubric": RUBRIC,
        "objectives": [
            {
                **_node(objective.objective),
                "subtotal": _tally(objective.tally),
                "key_results": [_node(key_result) for key_result in objective.key_results],
            }
            for objective in card.objectives
        ],
    }


def _node(scored: NodeScore) -> dict[str, Any]:
    return {
        "id": scored.node.id,
        "score": _tally(scored.tally),
        "commitment": scored.commitment.value,
        "checks": {check.dimension.value: check.passed for check in scored.checks},
        "missing": [dimension.value for dimension in scored.missing],
        "missing_names": list(scored.gaps),
    }


def _tally(tally: Tally) -> dict[str, int | None]:
    return {"passed": tally.passed, "total": tally.total, "percentage": tally.percentage}
