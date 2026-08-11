"""Scaffold tests.

Two things are being protected here, and the second is the reason the first exists.

**`examples/scaffold/` is what `okr init` writes, byte for byte.** An adopter learns the
layout from one of two places — the command, or the examples — and if they disagree one of
them is teaching a shape that does not work. Shipping the example as generated output makes
that drift a test failure instead of somebody's discovery.

**The commented examples are real.** Every scaffolded file that is entirely comments carries
exactly one example, as its last block. Uncommenting all of them has to produce a repo that
loads and validates with nothing to report — otherwise the scaffold is teaching a shape the
validator rejects, which is a worse first experience than no example at all.

**And what the example leaves out is what the file says it leaves out.** The goal file
carries no success criteria, no guardrails and no anti-targets, tells the reader so in
prose, and tells them `okr score` will name the gap. That is a promise made to somebody in
their first five minutes, so it is checked rather than trusted.
"""

from pathlib import Path

import pytest
import yaml

from agentic_okr.core import CURRENT_SCHEMA_VERSION, ScaffoldRefused, create, load, validate
from agentic_okr.core.scaffold import files, slug
from agentic_okr.core.score import Dimension, Tally, score

SHIPPED = Path(__file__).parent.parent / "examples" / "scaffold"

#: The period `examples/scaffold/` was generated with. Read from the example itself rather
#: than written down here, so the two cannot disagree about what is being compared.
SHIPPED_PERIOD = yaml.safe_load((SHIPPED / "okr.yaml").read_text(encoding="utf-8"))["period"]


def relative_files(root: Path) -> set[Path]:
    """Every file in a repo, as paths relative to its root. Hidden files included."""
    return {path.relative_to(root) for path in root.rglob("*") if path.is_file()}


def commented_example(content: str) -> str:
    """The example block at the end of a scaffolded file, with the comment marks removed.

    The rule the scaffold is written to: prose first, then a blank line, then one
    commented example as the final block. Uncommenting is stripping one `#` and one space
    from each line, which is also what a goal owner does to it.
    """
    block = content.strip().split("\n\n")[-1]
    return "\n".join(line.removeprefix("#").removeprefix(" ") for line in block.splitlines())


@pytest.fixture
def created(tmp_path: Path) -> Path:
    """A freshly scaffolded repo, at the same period as the shipped example."""
    return create(tmp_path, SHIPPED_PERIOD).root


# --- The shipped example is the command's output -----------------------------------------


def test_the_example_holds_exactly_the_files_init_writes(created: Path) -> None:
    assert relative_files(created) == relative_files(SHIPPED)


@pytest.mark.parametrize("relative", sorted(relative_files(SHIPPED)), ids=str)
def test_every_file_matches_the_shipped_example(relative: Path, created: Path) -> None:
    """Byte for byte. A wording change in the scaffold has to be committed to both."""
    assert (created / relative).read_text(encoding="utf-8") == (SHIPPED / relative).read_text(
        encoding="utf-8"
    )


def test_the_shipped_example_validates_with_nothing_to_report() -> None:
    """Not merely loadable: no errors and no warnings either.

    A scaffold that opened with a warning would teach that warnings are background noise,
    which is the habit that makes the ones that matter invisible.
    """
    assert validate(load(SHIPPED)).violations == ()


def test_a_new_repo_declares_the_current_schema_version(created: Path) -> None:
    assert load(created).marker.schema_version == CURRENT_SCHEMA_VERSION


# --- The commented examples are real -----------------------------------------------------


def fully_commented(period: str) -> dict[Path, str]:
    """The scaffolded files that carry nothing live — every one of them has an example."""
    return {
        relative: content
        for relative, content in files(period).items()
        if relative.suffix == ".yaml" and yaml.safe_load(content) is None
    }


def test_every_commented_out_file_carries_an_example() -> None:
    """Three of them: the two vocabularies, and the first goal file."""
    assert len(fully_commented(SHIPPED_PERIOD)) == 3


def uncommented(tmp_path: Path) -> Path:
    """A scaffolded repo with every commented example uncommented, as a reader would."""
    root = create(tmp_path, SHIPPED_PERIOD).root
    for relative, content in fully_commented(SHIPPED_PERIOD).items():
        (root / relative).write_text(commented_example(content) + "\n", encoding="utf-8")
    return root


@pytest.mark.parametrize("relative", sorted(fully_commented(SHIPPED_PERIOD)), ids=str)
def test_an_uncommented_example_is_valid_yaml(relative: Path) -> None:
    example = commented_example(fully_commented(SHIPPED_PERIOD)[relative])

    assert isinstance(yaml.safe_load(example), dict)


def test_uncommenting_every_example_produces_a_repo_that_validates(tmp_path: Path) -> None:
    """The claim the scaffold makes to a goal owner, checked end to end.

    They uncomment what we wrote, save, and run `okr validate`. If that reports anything,
    the first thing the tool ever taught them was wrong.
    """
    graph = load(uncommented(tmp_path))

    assert validate(graph).violations == ()
    assert len(graph.objectives) == 1
    assert len(graph.key_results) == 1


def test_the_example_goal_is_missing_exactly_what_the_file_says_it_is(tmp_path: Path) -> None:
    """The scaffold tells a reader to uncomment it and run `okr score`. This is that.

    The example is a goal as most people first write it — a statement, an owner, a metric
    and a target — and it carries none of the half of the schema that makes intent
    explicit. That gap is the thing being taught, so the file says so in prose and this
    checks the prose is true: `okr score` names those three and no others.
    """
    card = score(load(uncommented(tmp_path)))
    key_result = card.objectives[0].key_results[0]

    assert key_result.missing == (
        Dimension.SUCCESS_CRITERIA,
        Dimension.GUARDRAILS,
        Dimension.ANTI_TARGETS,
    )
    assert card.tally == Tally(2, 5)


def test_the_example_goal_is_not_build_trapped(tmp_path: Path) -> None:
    """The one thing the example does get right, so the gap it teaches is a clean one."""
    card = score(load(uncommented(tmp_path)))

    assert card.objectives[0].objective.missing == ()


# --- The period reaches a file and a filename --------------------------------------------


@pytest.mark.parametrize(
    ("period", "expected"),
    [
        ("2026-Q3", "2026-q3"),
        ("2026 H1", "2026-h1"),
        ("FY27/Q1", "fy27-q1"),
        ("  2026-Q3  ", "2026-q3"),
        ("///", "goals"),
    ],
)
def test_a_period_becomes_a_filename(period: str, expected: str) -> None:
    """A period is free text and must never reach a path as typed."""
    assert slug(period) == expected


@pytest.mark.parametrize("period", ["2026: Q3", "*2026", "yes", "2026-Q3"])
def test_a_period_survives_being_written_and_read_back(period: str, tmp_path: Path) -> None:
    """Whatever somebody types at the prompt, the marker has to say it back.

    Pasted into a template unquoted, a colon or a leading asterisk produces a file that is
    not the one we meant to write — and the first thing they would see is a brand new repo
    failing to load.
    """
    root = create(tmp_path, period).root

    assert load(root).marker.period == period.strip()


# --- Refusals ----------------------------------------------------------------------------


def test_an_existing_repo_is_never_written_over(created: Path) -> None:
    with pytest.raises(ScaffoldRefused):
        create(created, SHIPPED_PERIOD)


def test_a_repo_inside_another_repo_is_refused(created: Path) -> None:
    """Two markers in one tree means everything reading the goals stops at the nearer one."""
    nested = created / "teams" / "support"
    nested.mkdir(parents=True)

    with pytest.raises(ScaffoldRefused):
        create(nested, SHIPPED_PERIOD)


def test_a_file_that_is_already_there_is_kept(tmp_path: Path) -> None:
    """Somebody with a .gitignore has it for a reason, and a scaffold is not worth it."""
    (tmp_path / ".gitignore").write_text("secrets/\n", encoding="utf-8")

    scaffold = create(tmp_path, SHIPPED_PERIOD)

    assert Path(".gitignore") in scaffold.kept
    assert Path(".gitignore") not in scaffold.written
    assert (tmp_path / ".gitignore").read_text(encoding="utf-8") == "secrets/\n"
