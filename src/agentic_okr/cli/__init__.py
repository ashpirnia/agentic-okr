"""The `okr` command line.

A thin wrapper, deliberately. Every command here loads the graph through `core` and hands
it to something that renders it; no command decides anything about an OKR repo on its own.
The graph is the public API and this is one consumer of it — the future Conductor lint is
another, and it will have no terminal at all.

**Run it from anywhere inside an OKR repo.** The path argument is optional and the root is
found by walking up for `okr.yaml`, as git does. A path may be given, and must then be the
repo root: there is no way to check one team's directory on its own, because its goals
reference goals outside it (ADR-0008).

**Exit codes are the contract with CI.** `0` when nothing failed — warnings are reported
and do not fail a run, per the error registry. `1` when there is something to fix, whether
validation found it or the repo could not be read at all. Nothing else is used, so a
non-zero exit always means the same thing.

**Every message is written for a goal owner reviewing a pull request.** No Python names, no
tracebacks: a load that fails comes back as violations with codes, and they are printed the
same way validation's are.
"""

import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from agentic_okr.core import Graph, LoadError, load, validate

from . import report, topology

#: How wide the report is when nothing is there to ask. A terminal is measured; a pipe,
#: a log file or a pull request comment gets this. Wider than rich's own fallback of 80,
#: because a violation message is a sentence and a file path is long, and the alternative
#: is a path folded across two lines in the one place somebody has to read it exactly.
PIPED_WIDTH = 100

app = typer.Typer(
    name="okr",
    help="Check and read the OKRs in your OKR repo.",
    no_args_is_help=True,
    add_completion=False,
)

#: Where a human-readable report goes. Machine output bypasses this entirely — rich would
#: wrap and colour JSON, and something parsing it is not reading a terminal.
console = Console(width=None if sys.stdout.isatty() else PIPED_WIDTH)

PathArgument = Annotated[
    Path | None,
    typer.Argument(
        show_default=False,
        metavar="[PATH]",
        help=(
            "Your OKR repo's root — the directory holding okr.yaml. "
            "Leave it out to use the repo you are standing in."
        ),
    ),
]

JsonOption = Annotated[
    bool,
    typer.Option("--json", help="Print the result as JSON instead, for another tool to read."),
]


@app.command("validate")
def validate_command(path: PathArgument = None, as_json: JsonOption = False) -> None:
    """Check that your OKRs hold together, and report everything that does not.

    Every connection has to point at a goal that exists, every metric and owner has to be
    one your repo declares, and nothing may contribute to itself. Exits non-zero if
    anything needs fixing, so it can gate a pull request.
    """
    graph = _load_or_exit(path, as_json=as_json)
    result = validate(graph)

    if as_json:
        print(report.as_json(report.checked_payload(graph, result)))
    else:
        report.render_header(console, graph)
        report.render_violations(console, result.violations)
        report.render_summary(console, graph, result)

    raise typer.Exit(0 if result.ok else 1)


@app.command("graph")
def graph_command(path: PathArgument = None, as_json: JsonOption = False) -> None:
    """Show how your goals connect: what supports what, and who is waiting on whom.

    Prints what is written, without checking it. A connection pointing at a goal nobody
    declares is shown and marked; `okr validate` is what explains it and fails on it.
    """
    graph = _load_or_exit(path, as_json=as_json)
    if as_json:
        print(report.as_json(topology.payload(graph)))
    else:
        topology.render(console, graph)


def _load_or_exit(path: Path | None, *, as_json: bool) -> Graph:
    """Read the whole OKR repo, or report why it could not be read and stop.

    A repo that cannot be read is reported in the same shape as one that fails
    validation, because at the moment of reading them the difference between an
    unparseable file and an undeclared metric is not one the reader cares about.
    """
    try:
        return load(path)
    except LoadError as failure:
        if as_json:
            print(report.as_json(report.unreadable_payload(failure.violations)))
        else:
            report.render_unreadable(console, failure.violations)
        raise typer.Exit(1) from None


def main() -> None:
    """The `okr` entry point."""
    app()
