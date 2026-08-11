"""Rendering a validation report for the person who has to fix it.

The reader is a goal owner looking at a pull request, not a developer. That single fact
decides everything here: violations are grouped by file and ordered as somebody would work
down one, the code is printed beside each line because the code is the published contract,
and nothing that leaks out of Python — a type name, a module path, a traceback — ever
reaches the page.

**A repo that could not be read renders the same way as one that failed validation.** Both
are lists of violations with codes and locations, and the difference between "this file is
not valid YAML" and "this metric is not declared" is not a difference the reader cares
about at the moment they are reading it. Only the closing summary differs, because only
there does it matter that nothing else could be checked.

Nothing here decides an exit code. That belongs to the command, so that this module can be
called by anything that wants a report on a terminal.
"""

import json
from collections.abc import Iterable, Sequence
from itertools import groupby
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.padding import Padding
from rich.table import Table
from rich.text import Text

from agentic_okr.core import Graph, Report, Severity, Violation

#: How each severity is coloured and named. The words are the contract's own — an `E`
#: fails the run and a `W` does not — so they are worth printing rather than implying
#: with a colour somebody's terminal may not show.
_STYLES: dict[Severity, str] = {Severity.ERROR: "bold red", Severity.WARNING: "bold yellow"}

#: The heading for problems with no file to point at: a missing marker, an unreadable
#: schema version, an owners file nobody has written yet.
_REPO_WIDE = "Your OKR repo, as a whole"


# --- On a terminal ---------------------------------------------------------------------


def render_header(console: Console, graph: Graph) -> None:
    """Which repo was checked, and for which cycle."""
    console.print(
        Text.assemble(
            (graph.root.name, "bold"),
            ("  ", ""),
            (f"period {graph.marker.period}", "dim"),
        )
    )
    console.print()


def render_violations(console: Console, violations: Sequence[Violation]) -> None:
    """Every problem, grouped by the file it is in and ordered as a reader would fix them.

    Already sorted by the time it arrives — unlocated problems first, then by file and
    line — so the grouping is a run-length pass rather than a re-sort.
    """
    for file, group in groupby(violations, key=lambda v: v.file):
        console.print(Text(str(file) if file is not None else _REPO_WIDE, style="bold"))
        console.print(Padding(_table(list(group)), (0, 0, 1, 2)))


def _table(violations: Sequence[Violation]) -> Table:
    """One file's problems, three columns wide: where, which code, and what is wrong."""
    table = Table(box=None, show_header=False, padding=(0, 2, 0, 0), pad_edge=False)
    table.add_column("where", style="dim", no_wrap=True, justify="right")
    table.add_column("code", no_wrap=True)
    table.add_column("what", overflow="fold")
    for violation in violations:
        table.add_row(
            "" if violation.line is None else f"line {violation.line}",
            Text(violation.code.value, style=_STYLES[violation.severity]),
            Text(violation.message),
        )
    return table


def render_summary(console: Console, graph: Graph, report: Report) -> None:
    """The closing line: what has to be fixed, what is worth a look, and what was checked."""
    console.print(Text.assemble(*_verdict(report), (f" {_scope(graph)}", "dim")))


def render_unreadable(console: Console, violations: Sequence[Violation]) -> None:
    """A repo that could not be read at all, and therefore was not checked.

    Said plainly at the end, because a reader who has just been handed one YAML error
    would otherwise take the silence on everything else as a pass.
    """
    console.print(Text("Your OKR repo could not be read.", style=_STYLES[Severity.ERROR]))
    console.print()
    render_violations(console, violations)
    console.print(
        Text.assemble(
            *_verdict(Report(tuple(violations))),
            (" Nothing else could be checked until this is fixed.", "dim"),
        )
    )


def _verdict(report: Report) -> list[tuple[str, str]]:
    """The count of what was found, phrased by whether any of it fails the run."""
    errors, warnings = len(report.errors), len(report.warnings)
    aside = f", and {_count(warnings, 'thing')} worth a look" if warnings else ""
    if errors:
        return [(f"{_count(errors, 'problem')} to fix{aside}.", _STYLES[Severity.ERROR])]
    if warnings:
        return [
            (
                f"Nothing to fix, but {_count(warnings, 'thing')} worth a look.",
                _STYLES[Severity.WARNING],
            )
        ]
    return [("No problems found.", "bold green")]


def _count(number: int, noun: str) -> str:
    return f"{number} {noun}" if number == 1 else f"{number} {noun}s"


def _scope(graph: Graph) -> str:
    """What was looked at, so that a clean run says what it actually covered."""
    return (
        f"Checked {_count(len(graph.objectives), 'objective')} and "
        f"{_count(len(graph.key_results), 'key result')} "
        f"across {_count(len(graph.goal_files), 'file')}."
    )


# --- For a machine ----------------------------------------------------------------------


def as_json(payload: dict[str, Any]) -> str:
    """One place that decides how machine output is shaped, so both commands agree."""
    return json.dumps(payload, indent=2, sort_keys=False)


def checked_payload(graph: Graph, report: Report) -> dict[str, Any]:
    """A finished validation run, for something that is not a person.

    `ok` mirrors the exit code exactly: warnings are reported and do not fail the run,
    which is part of the published contract rather than a presentation choice.
    """
    return {
        "ok": report.ok,
        "loaded": True,
        "repo": _repo(graph),
        "counts": _counts(report.errors, report.warnings, graph),
        "violations": [_violation(v) for v in report.violations],
    }


def unreadable_payload(violations: Sequence[Violation]) -> dict[str, Any]:
    """A repo that could not be read, in the same shape as one that could.

    The keys never change, so a consumer reads `loaded` to find out whether the nulls
    mean 'nothing found' or 'never looked'.
    """
    errors = [v for v in violations if v.severity is Severity.ERROR]
    warnings = [v for v in violations if v.severity is Severity.WARNING]
    return {
        "ok": False,
        "loaded": False,
        "repo": None,
        "counts": _counts(errors, warnings, None),
        "violations": [_violation(v) for v in violations],
    }


def _repo(graph: Graph) -> dict[str, Any]:
    return {
        "root": str(graph.root),
        "name": graph.root.name,
        "period": graph.marker.period,
        "schema_version": graph.marker.schema_version,
    }


def _counts(
    errors: Iterable[Violation], warnings: Iterable[Violation], graph: Graph | None
) -> dict[str, int | None]:
    """Null rather than zero for what a failed load never got far enough to count."""
    unknown: dict[str, int | None] = {"files": None, "objectives": None, "key_results": None}
    return {
        "errors": len(list(errors)),
        "warnings": len(list(warnings)),
        **(unknown if graph is None else goal_counts(graph)),
    }


def _violation(violation: Violation) -> dict[str, Any]:
    return {
        "code": violation.code.value,
        "severity": violation.severity.value,
        "message": violation.message,
        "file": _path(violation.file),
        "line": violation.line,
    }


def _path(path: Path | None) -> str | None:
    """Paths cross the boundary as strings, relative to the OKR repo root as everywhere."""
    return None if path is None else str(path)


def goal_counts(graph: Graph) -> dict[str, int | None]:
    """Shared by both commands' machine output, so the two never disagree on a total."""
    return {
        "files": len(graph.goal_files),
        "objectives": len(graph.objectives),
        "key_results": len(graph.key_results),
    }
