"""Creating a valid empty OKR repo, and teaching the layout while doing it.

This is the one place the tool writes files, and it writes them into somebody else's
repository — never its own. It is also the moment an adopting organisation learns what an
OKR repo looks like ([ADR-0002](../../../docs/adr/0002-two-repos.md)), which is why the
scaffold is generated here rather than kept as a template repo somewhere: a template is a
second artefact to maintain, and it drifts from the validator silently. Generated from the
same package that validates it, it cannot.

**The files are mostly comments, and that is the point.** What is written live is the
minimum that makes the repo loadable: the marker, and the directories. Everything else is
one commented example of the smallest useful thing — one owner, one metric, one objective
with one key result. Uncommenting all of them yields a repo that validates, which is a
property `tests/test_scaffold.py` checks rather than a claim made here.

**Minimal on purpose.** A scaffold showing every optional field teaches that the schema is
fatter than it is, and a goal owner reading it would conclude that writing an OKR here
means filling in twenty fields. It does not. Guardrails and anti-targets are the point of
this tool and are still left out of the scaffold — they are what the Champion elicits in
conversation, and the reference repos under `examples/` are where a reader sees a full one.

Nothing here prints. `okr init` is a caller.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

from .loader import MARKER_NAME, find_root
from .models import CURRENT_SCHEMA_VERSION
from .violations import LoadError

#: Where goal files go, relative to the marker. The loader reads every YAML file beneath
#: this, whatever it is called — the structure below is a recommendation (ADR-0007).
OKR_DIR = "okrs"

#: The team directory the first goal file goes in. Support is the running example
#: throughout the documentation, so a reader moving between the two sees one vocabulary
#: rather than two. It is meant to be renamed, and the file says so.
EXAMPLE_TEAM = "support"


class ScaffoldRefused(Exception):
    """A repo could not be created here, with a sentence saying why.

    Deliberately not a `Violation` with a registry code. That registry is what
    `okr validate` reports and what the Conductor will consume, and nothing consumes the
    reason a directory could not be scaffolded — extending a published contract to cover
    a command's own mechanics would add a promise with no reader.
    """


@dataclass(frozen=True, slots=True)
class Scaffold:
    """What `create` did: what it wrote, and what it found already there and left alone."""

    root: Path
    written: tuple[Path, ...]
    kept: tuple[Path, ...]
    """Files that already existed. Never overwritten — somebody wrote them on purpose."""


def create(root: Path, period: str) -> Scaffold:
    """Write a valid empty OKR repo into `root`, and say what was written.

    Refuses rather than merges when there is already an OKR repo here or above here: two
    markers in one tree means the loader finds the nearer one and silently reads half an
    organisation's goals, which is the partial-graph failure ADR-0008 exists to prevent.

    Existing files are kept, not overwritten. Somebody who already has a `.gitignore` has
    it for a reason, and a scaffold is not worth losing it over.
    """
    target = root.resolve()
    _refuse_if_inside_a_repo(target)

    written, kept = [], []
    for relative, content in files(period).items():
        destination = target / relative
        if destination.exists():
            kept.append(relative)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
        written.append(relative)
    return Scaffold(target, tuple(written), tuple(kept))


def _refuse_if_inside_a_repo(target: Path) -> None:
    """Stop if `target`, or anything above it, is already an OKR repo root."""
    try:
        existing = find_root(target)
    except LoadError:
        return
    if existing == target:
        raise ScaffoldRefused(
            f"There is already an OKR repo here: {target} has an {MARKER_NAME} in it. "
            f"Nothing has been changed. Run 'okr validate' to check the one you have."
        )
    raise ScaffoldRefused(
        f"{target} is already inside an OKR repo — the one rooted at {existing}. One repo "
        f"holds one set of goals, and a second repo nested inside the first would hide "
        f"part of it: anything reading your goals stops at the nearest {MARKER_NAME} and "
        f"would never see the rest. Add your team's file under {existing / OKR_DIR} instead."
    )


# --- What gets written -------------------------------------------------------------------


def files(period: str) -> dict[Path, str]:
    """Every file a new OKR repo starts with, as relative paths and their contents.

    Returned rather than written so the same content can be checked without a filesystem,
    and so `examples/scaffold/` can be proved identical to what a real run produces.
    """
    return {
        Path(MARKER_NAME): _marker(period),
        Path("metrics.yaml"): METRICS,
        Path("owners.yaml"): OWNERS,
        Path(OKR_DIR) / EXAMPLE_TEAM / f"{slug(period)}.yaml": GOALS,
        Path(".gitignore"): GITIGNORE,
    }


def slug(period: str) -> str:
    """A period as a filename: `2026-Q3` becomes `2026-q3`.

    A period is free text — organisations run halves, trimesters and fiscal years — so
    anything that is not a letter or a digit becomes a hyphen rather than reaching a path.
    """
    reduced = "".join(character if character.isalnum() else "-" for character in period.lower())
    return "-".join(part for part in reduced.split("-") if part) or "goals"


def _marker(period: str) -> str:
    """`okr.yaml`, the only scaffolded file with anything live in it."""
    return f"""\
# This file marks the root of your OKR repo.
#
# Anything reading your goals walks up from wherever it was run until it finds this
# file, then loads everything beneath it — the whole set, never part of one. That is
# what stops one team's directory being checked on its own and passing, while the
# connection it made to another team's goal quietly points at nothing.

# Which version of the OKR schema this repo is written against. Checked exactly: a
# tool that cannot read this repo says so rather than guessing.
schema_version: {CURRENT_SCHEMA_VERSION}

# The cycle these goals cover. One repo holds one live cycle, which is what puts every
# key result in it inside a time box without a deadline on each one. Nothing parses
# this — halves, quarters, trimesters and fiscal years are all fine.
{_field("period", period)}

# Where your goal files live, relative to this file. Every YAML file beneath it is
# loaded, whatever it is called.
okr_dir: {OKR_DIR}/

# Your metrics and owners are read from metrics.yaml and owners.yaml beside this file.
# Add 'metrics_file:' or 'owners_file:' here only if you want them somewhere else.
"""


def _field(name: str, value: str) -> str:
    """One YAML line, quoted by the YAML writer rather than by us.

    `period` is whatever somebody typed at a prompt. Pasting it into a template unquoted
    would let a colon or a leading asterisk produce a marker that is not the file we meant
    to write — and the first thing they would see is their brand new repo failing to load.
    """
    return yaml.safe_dump({name: value}, default_flow_style=False, allow_unicode=True).strip()


#: `owners.yaml`. Entirely commented: an OKR repo with no goals in it yet has nobody to
#: declare, and a placeholder owner would be a name that resolves to a person who does not
#: exist. The example is the last block in the file, which is the shape the scaffold test
#: relies on to prove that uncommenting it produces something that validates.
OWNERS = """\
# Everyone who can own a goal, declared here once and referred to by ID everywhere else.
#
# Declared rather than typed out each time, because review of a change goes to the
# owners it affects: 'head-of-support' and 'head_of_support' would quietly become two
# people, and a review that should reach one of them would reach neither. An owner ID
# that nothing here declares is an error, which is the whole point of the file.
#
# Name the role rather than the person in it, so an ID survives somebody changing jobs.

# owners:
#   - id: head-of-support
#     name: Head of Support
"""

#: `metrics.yaml`. Also entirely commented, and legitimately empty for longer than
#: `owners.yaml` is: a repo whose key results are all milestones has no metrics at all.
METRICS = """\
# The quantities your goals are allowed to talk about, declared here once and referred
# to by ID everywhere else.
#
# This ID is the join between what you meant, where the number is read from, and what
# was recorded — so 'csat' and 'CSAT' becoming two different metrics is a failure worth
# catching. A metric ID that nothing here declares is an error.
#
# The measurement window belongs in the ID: reopen_rate_7d and reopen_rate_30d are two
# metrics, not one metric read two ways.
#
# A repo whose key results are all things you ship, rather than numbers you move, has
# no metrics to declare. Leaving this file empty is fine.

# metrics:
#   - id: resolution_time_p50
#     definition: Median time from ticket creation to resolution
#     unit: hours
"""

#: The first goal file. One objective, one key result, and only the fields that are
#: required — a scaffold showing everything the schema allows teaches that writing a goal
#: here means filling in twenty fields, and it does not.
GOALS = """\
# One team's goals for this cycle, reviewed together as a set.
#
# Rename this directory to one of your teams. One file per team is a recommendation and
# nothing enforces it — every YAML file under okrs/ is loaded whatever it is called —
# but a team's goals are worth reading as a unit, because the balance between what is
# committed and what is a stretch only shows up when you can see them together.
#
# The IDs are yours to choose, and other files refer to them, so they are namespaced by
# team rather than by the objective above them: a key result can contribute to more
# than one objective, and it should not have to be renamed when it does.

# objectives:
#   - id: support.fast-resolution
#     statement: Customers get their problems solved, fast
#     owner: head-of-support
#     commitment: committed
#     key_results:
#       - id: support.resolution-time
#         statement: Median ticket resolution time under 4 hours
#         type: metric
#         owner: head-of-support
#         metric: resolution_time_p50
#         target: 4
"""

#: `.gitignore`. Short, because there is genuinely nothing of ours to ignore — and saying
#: so is worth the two lines. Nothing the tool does writes into an OKR repo: the Champion's
#: checkpoints go to the operating system's application data directory, and no command
#: caches anything here (ADR-0004).
GITIGNORE = """\
# Nothing that reads your OKRs writes anything back into this repo — no caches, no
# state, no generated files. So there is nothing of the tool's to ignore here.
#
# What is left is the usual local clutter.

.DS_Store
Thumbs.db
*.swp
.idea/
.vscode/
"""
