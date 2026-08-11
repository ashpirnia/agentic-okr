"""Completeness scoring tests.

The score is the article's evidence, so the thing being protected is that a reader can
recount it. Three properties carry that:

**The worked example scores 12 of 19.** ADR-0011 states the number, and it is checked here
against the same organisation `test_loader.py` loads. A change to the rubric that moves it
has to be a deliberate edit to both.

**The arithmetic adds up.** Subtotals sum to the roll-up, denominators are four per key
result and one per objective, and nothing is weighted.

**Commitment changes the order and never the number.** The same spec scores the same
whether it is committed or aspirational. That is the property most likely to be broken by
somebody trying to make the score "smarter", so it is asserted directly.
"""

from pathlib import Path

import pytest

from agentic_okr.core import Code, Commitment, load, validate
from agentic_okr.core.score import Dimension, NodeScore, Scorecard, Tally, score
from tests.test_loader import SUPPORT, write_repo

#: What ADR-0011 says the worked example scores. Two key results carrying nothing but
#: success criteria, one carrying everything, one objective that is build-trapped.
WORKED_EXAMPLE = Tally(12, 19)

#: A single objective with one key result, as the smallest thing that can be scored.
#: Written out rather than derived, so a test can vary exactly one field of it.
ONE_GOAL = """
objectives:
  - id: team.objective
    statement: A thing the team wants
    owner: lead
    commitment: {commitment}
    key_results:
      - id: team.key-result
        statement: A number the team will move
        type: metric
        owner: lead
        metric: reopen_rate_7d
        target: 0.05
{fields}
"""

MARKER = "schema_version: 1\nperiod: 2026-Q3\nokr_dir: okrs/\n"
OWNERS = "owners:\n  - id: lead\n    name: Team Lead\n"
METRICS = """
metrics:
  - id: reopen_rate_7d
    definition: Share of resolved tickets reopened within 7 days
    unit: ratio
"""


def one_goal(tmp_path: Path, fields: str = "", commitment: str = "committed") -> Scorecard:
    """Score a repo holding a single objective and key result, with `fields` added to it."""
    for relative, content in {
        "okr.yaml": MARKER,
        "owners.yaml": OWNERS,
        "metrics.yaml": METRICS,
        "okrs/team.yaml": ONE_GOAL.format(commitment=commitment, fields=fields),
    }.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return score(load(tmp_path))


def key_result(card: Scorecard) -> NodeScore:
    """The only key result in a repo built by `one_goal`."""
    return card.objectives[0].key_results[0]


@pytest.fixture
def worked(tmp_path: Path) -> Scorecard:
    """The organisation from docs/GRAPH-BY-EXAMPLE.md, scored."""
    return score(load(write_repo(tmp_path)))


# --- The number in the ADR ---------------------------------------------------------------


def test_the_worked_example_scores_what_the_adr_says(worked: Scorecard) -> None:
    assert worked.tally == WORKED_EXAMPLE


def test_the_documented_example_states_the_number_the_code_produces(worked: Scorecard) -> None:
    """The article's evidence is a number a reader can recount from the published files.

    `docs/GRAPH-BY-EXAMPLE.md` walks the same organisation and prints this score. If the
    rubric changes and that page does not, the walkthrough is teaching a number the tool
    no longer produces — which is the one thing the score cannot afford to do.
    """
    walkthrough = (Path(__file__).parent.parent / "docs" / "GRAPH-BY-EXAMPLE.md").read_text(
        encoding="utf-8"
    )

    assert f"{worked.tally} ({worked.tally.percentage}%)" in walkthrough


def test_the_worked_example_rounds_to_63_percent(worked: Scorecard) -> None:
    assert worked.tally.percentage == 63


def test_every_key_result_is_asked_four_questions_and_every_objective_one(
    worked: Scorecard,
) -> None:
    """The denominators, which are what make the total recountable from the files."""
    for objective in worked.objectives:
        assert objective.objective.tally.total == 1
        assert all(kr.tally.total == 4 for kr in objective.key_results)


def test_the_subtotals_add_up_to_the_roll_up(worked: Scorecard) -> None:
    """Every key result is written inside exactly one objective, so these partition."""
    subtotals = [objective.tally for objective in worked.objectives]

    assert sum(t.passed for t in subtotals) == worked.tally.passed
    assert sum(t.total for t in subtotals) == worked.tally.total


def test_the_build_trapped_objective_is_the_one_with_no_metric_key_result(
    worked: Scorecard,
) -> None:
    trapped = [o.objective.node.id for o in worked.objectives if o.objective.missing]

    assert trapped == ["platform.reliability"]


# --- The four key result checks ----------------------------------------------------------


def test_a_key_result_with_nothing_optional_scores_one_of_four(tmp_path: Path) -> None:
    """K4 passes vacuously with no anti-targets, which is K3's to report. Never twice."""
    scored = key_result(one_goal(tmp_path))

    assert scored.tally == Tally(1, 4)
    assert scored.missing == (
        Dimension.SUCCESS_CRITERIA,
        Dimension.GUARDRAILS,
        Dimension.ANTI_TARGETS,
    )


def test_a_key_result_with_everything_scores_four_of_four(tmp_path: Path) -> None:
    scored = key_result(
        one_goal(
            tmp_path,
            fields="""\
        success_criteria:
          - The underlying issue is fixed
        guardrails:
          - metric: reopen_rate_7d
            must_not_exceed: 0.08
        anti_targets:
          - description: Close tickets without fixing anything
            origin: authored
            restraint: A ticket may not be closed with a boilerplate reply
""",
        )
    )

    assert scored.tally == Tally(4, 4)
    assert scored.missing == ()


def test_an_undefended_anti_target_fails_the_fourth_check(tmp_path: Path) -> None:
    """Named and wholly undefended: no restraint, and nothing watching for it."""
    scored = key_result(
        one_goal(
            tmp_path,
            fields="""\
        anti_targets:
          - description: Close tickets without fixing anything
            origin: authored
""",
        )
    )

    assert Dimension.ANTI_TARGETS not in scored.missing
    assert Dimension.ANTI_TARGETS_DEFENDED in scored.missing


@pytest.mark.parametrize(
    "defence",
    ["            restraint: A ticket may not be closed with a boilerplate reply", ""],
    ids=["restraint", "watched-by"],
)
def test_either_kind_of_defence_satisfies_the_fourth_check(defence: str, tmp_path: Path) -> None:
    """A restraint is checked before an agent runs; a watching metric catches it happening."""
    watched = "" if defence else "            watched_by: [reopen_rate_7d]"
    scored = key_result(
        one_goal(
            tmp_path,
            fields=f"""\
        guardrails:
          - metric: reopen_rate_7d
            must_not_exceed: 0.08
        anti_targets:
          - description: Close tickets without fixing anything
            origin: authored
{defence}{watched}
""",
        )
    )

    assert Dimension.ANTI_TARGETS_DEFENDED not in scored.missing


# --- The one objective check, and its two ways of failing --------------------------------

#: An objective nothing is written inside, which other goals ladder up to. `okr validate`
#: reports this as `W106`; here it is one of the two ways the objective check fails.
EMPTY_OBJECTIVE = """
objectives:
  - id: company.ambition
    statement: The thing everything ladders up to
    owner: lead
    commitment: committed
  - id: team.objective
    statement: A thing the team wants
    owner: lead
    commitment: committed
    supports: [company.ambition]
    key_results:
      - id: team.key-result
        statement: A number the team will move
        type: {type}
        owner: lead
{measure}
"""


def objectives(tmp_path: Path, key_result_type: str, measure: str) -> Scorecard:
    """A repo with an empty objective above one that carries a key result of `type`."""
    for relative, content in {
        "okr.yaml": MARKER,
        "owners.yaml": OWNERS,
        "metrics.yaml": METRICS,
        "okrs/team.yaml": EMPTY_OBJECTIVE.format(type=key_result_type, measure=measure),
    }.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return score(load(tmp_path))


def scored_objective(card: Scorecard, objective_id: str) -> NodeScore:
    return next(o.objective for o in card.objectives if o.objective.node.id == objective_id)


def test_an_empty_objective_and_a_build_trapped_one_both_score_zero_of_one(
    tmp_path: Path,
) -> None:
    """The arithmetic is right for both, which is why only the wording needed fixing."""
    card = objectives(tmp_path, "milestone", "        success_criteria: [Shipped]")

    assert scored_objective(card, "company.ambition").tally == Tally(0, 1)
    assert scored_objective(card, "team.objective").tally == Tally(0, 1)


def test_an_empty_objective_is_not_described_as_a_build_trap(tmp_path: Path) -> None:
    """Two different things to go and do, so two different sentences.

    A build trap measures effort instead of impact; an empty objective measures nothing.
    Telling somebody looking at the second to add 'a key result that moves a number'
    describes the first.
    """
    card = objectives(tmp_path, "milestone", "        success_criteria: [Shipped]")

    assert scored_objective(card, "company.ambition").gaps == (
        "key results — this objective has none",
    )
    assert scored_objective(card, "team.objective").gaps == ("a key result that moves a number",)


def test_both_ways_of_failing_are_the_same_check(tmp_path: Path) -> None:
    """One dimension, two wordings. The rubric stays five checks, not six."""
    card = objectives(tmp_path, "milestone", "        success_criteria: [Shipped]")

    for objective_id in ("company.ambition", "team.objective"):
        assert scored_objective(card, objective_id).missing == (Dimension.NOT_BUILD_TRAPPED,)


def test_an_objective_with_a_metric_key_result_passes_however_it_is_worded(
    tmp_path: Path,
) -> None:
    card = objectives(tmp_path, "metric", "        metric: reopen_rate_7d\n        target: 0.05")

    assert scored_objective(card, "team.objective").gaps == ()


@pytest.mark.parametrize(
    ("key_results", "warned", "dimension_fails"),
    [
        ("", True, True),
        ("milestone", False, True),
        ("metric", False, False),
    ],
    ids=["none", "only-milestones", "a-metric"],
)
def test_the_three_states_of_an_objective_form_a_progression(
    key_results: str, warned: bool, dimension_fails: bool, tmp_path: Path
) -> None:
    """ADR-0011 Amendment 1 states this progression. It is checkable, so it is checked.

    No key results raises the warning and fails the dimension. Adding a milestone clears
    the warning and leaves the dimension failing, now as a build trap. Adding a metric key
    result clears both. The warning and the dimension overlap in one of the three states
    and diverge in the next, which is what makes them worth having separately.
    """
    measures = {
        "milestone": "        success_criteria: [Shipped]",
        "metric": "        metric: reopen_rate_7d\n        target: 0.05",
    }
    goals = LADDERED_OBJECTIVE.format(
        key_results=(
            ""
            if not key_results
            else "    key_results:\n"
            "      - id: company.key-result\n"
            "        statement: Something under it\n"
            f"        type: {key_results}\n"
            "        owner: lead\n" + measures[key_results] + "\n"
        )
    )
    root = write_score_repo(tmp_path, goals)
    graph = load(root)

    report = validate(graph)
    scored = scored_objective(score(graph), "company.ambition")

    assert (Code.OBJECTIVE_WITHOUT_KEY_RESULTS in {v.code for v in report.warnings}) is warned
    assert bool(scored.missing) is dimension_fails
    assert report.ok


#: An objective with a team laddering up to it, so it is never an orphan whatever is or is
#: not written inside it. `{key_results}` is what it carries.
LADDERED_OBJECTIVE = """
objectives:
  - id: company.ambition
    statement: The thing everything ladders up to
    owner: lead
    commitment: committed
{key_results}
  - id: team.objective
    statement: A thing the team wants
    owner: lead
    commitment: committed
    supports: [company.ambition]
    key_results:
      - id: team.key-result
        statement: A number the team will move
        type: metric
        owner: lead
        metric: reopen_rate_7d
        target: 0.05
"""


def write_score_repo(tmp_path: Path, goals: str) -> Path:
    """A minimal repo carrying `goals`, for a test that needs both a report and a score."""
    for relative, content in {
        "okr.yaml": MARKER,
        "owners.yaml": OWNERS,
        "metrics.yaml": METRICS,
        "okrs/team.yaml": goals,
    }.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return tmp_path


# --- Commitment orders the report and touches no number ----------------------------------


@pytest.mark.parametrize("commitment", ["committed", "aspirational"])
def test_an_identical_spec_scores_identically_whatever_it_is_committed_to(
    commitment: str, tmp_path: Path
) -> None:
    """The property ADR-0011 rejected weighting for. Two identical specs, one number."""
    assert one_goal(tmp_path, commitment=commitment).tally == Tally(2, 5)


def test_committed_goals_are_reported_before_aspirational_ones(worked: Scorecard) -> None:
    commitments = [scored.commitment for scored in worked.findings]

    assert commitments == sorted(commitments, key=lambda c: c is not Commitment.COMMITTED)


def test_a_key_result_takes_its_objectives_commitment_when_it_declares_none(
    tmp_path: Path,
) -> None:
    """Severity has to read the effective commitment, not the field as written."""
    scored = key_result(one_goal(tmp_path, commitment="committed"))

    assert scored.commitment is Commitment.COMMITTED


def test_within_one_commitment_the_emptier_goal_comes_first(worked: Scorecard) -> None:
    committed = [scored for scored in worked.findings if scored.commitment is Commitment.COMMITTED]
    gaps = [len(scored.missing) for scored in committed]

    assert gaps == sorted(gaps, reverse=True)


def test_nothing_that_passes_every_check_is_reported_as_a_finding(worked: Scorecard) -> None:
    assert all(scored.missing for scored in worked.findings)
    assert "support.resolution-time" not in {scored.node.id for scored in worked.findings}


# --- Edges -------------------------------------------------------------------------------


def test_an_empty_repo_scores_zero_of_zero(tmp_path: Path) -> None:
    """Not filled in badly. Not filled in at all, which is a different thing to say."""
    for relative, content in {"okr.yaml": MARKER, "owners.yaml": OWNERS}.items():
        (tmp_path / relative).write_text(content, encoding="utf-8")
    (tmp_path / "okrs").mkdir()

    card = score(load(tmp_path))

    assert card.tally == Tally(0, 0)
    assert card.tally.percentage is None
    assert card.findings == ()


def test_scoring_is_deterministic(worked: Scorecard, tmp_path: Path) -> None:
    """The article's number has to be the same on any machine, forever."""
    again = score(load(write_repo(tmp_path / "second")))

    assert again.tally == worked.tally
    assert [s.node.id for s in again.findings] == [s.node.id for s in worked.findings]


def test_a_repo_that_fails_validation_still_scores(tmp_path: Path) -> None:
    """A score is a measurement, never a gate. It does not refuse to count a broken repo."""
    broken = write_repo(tmp_path, support=SUPPORT.replace("platform.api-v2", "platform.api-v-2"))

    assert score(load(broken)).tally == WORKED_EXAMPLE
