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
from rich.text import Text

from agentic_okr.core import (
    Graph,
    LoadError,
    Scaffold,
    ScaffoldRefused,
    create,
    load,
    validate,
)
from agentic_okr.core.scaffold import OKR_DIR

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
    # Markdown, so a command's help reflows into paragraphs. The default treats every
    # newline in a docstring as a line break, which wraps help text at whatever column
    # the source happened to end on and reads as though it were badly formatted.
    rich_markup_mode="markdown",
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

NewPathArgument = Annotated[
    Path | None,
    typer.Argument(
        show_default=False,
        metavar="[PATH]",
        help=(
            "Where to create your OKR repo. Leave it out to create one where you are "
            "standing. The directory is created if it is not there."
        ),
    ),
]

PeriodOption = Annotated[
    str,
    typer.Option(
        prompt="Which cycle do these goals cover (for example 2026-Q3)",
        help=(
            "The cycle this repo covers. One repo holds one live cycle. Anything reads: "
            "2026-Q3, 2026-H1, FY27."
        ),
    ),
]


@app.command("init")
def init_command(path: NewPathArgument = None, period: PeriodOption = ...) -> None:
    """Create a new OKR repo, ready to write your first objective into.

    Writes the marker that makes a directory an OKR repo, somewhere for your goal files
    to live, and a commented example of each thing you will write — one owner, one
    metric, one objective. Nothing is overwritten.
    """
    try:
        scaffold = create(path or Path.cwd(), period)
    except ScaffoldRefused as refused:
        console.print(Text(str(refused), style="bold red"))
        raise typer.Exit(1) from None

    _render_scaffold(scaffold)
    graph = _load_or_exit(scaffold.root, as_json=False)
    result = validate(graph)
    report.render_violations(console, result.violations)
    report.render_summary(console, graph, result)
    console.print()
    console.print(_next_step(scaffold))
    raise typer.Exit(0 if result.ok else 1)


def _render_scaffold(scaffold: Scaffold) -> None:
    """What was written, and what was already there and left alone."""
    console.print(Text.assemble(("Created an OKR repo in ", ""), (str(scaffold.root), "bold")))
    console.print()
    for relative in scaffold.written:
        console.print(Text(f"  {relative}"))
    if scaffold.kept:
        console.print()
        console.print(Text("Already there, so left alone:", style="dim"))
        for relative in scaffold.kept:
            console.print(Text(f"  {relative}", style="dim"))
    console.print()


def _next_step(scaffold: Scaffold) -> Text:
    """The one thing to do next. A scaffold that does not say this is a pile of files."""
    goal_file = next(
        (path for path in (*scaffold.written, *scaffold.kept) if path.parts[0] == OKR_DIR),
        Path(OKR_DIR),
    )
    return Text.assemble(
        ("Next: ", "bold"),
        (f"open {goal_file} and write your first objective, "),
        ("then run 'okr validate'."),
    )


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
