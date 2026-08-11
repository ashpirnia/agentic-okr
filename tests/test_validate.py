"""Validation tests.

Assertions are on error codes, on counts and on severity — never on message text. The
codes are the published contract; the sentences are free to improve.

The repos here are deliberately tiny. `test_loader.py` checks the worked example from
`docs/GRAPH-BY-EXAMPLE.md` loads; what these check is one broken thing at a time, and a
fixture carrying five teams would make it ambiguous which of them the violation came from.
The worked example is still validated once, as the proof that a correct repo is silent.
"""

from collections.abc import Iterable
from pathlib import Path

from agentic_okr.core import Code, Report, Severity, Violation, load, validate
from tests.test_loader import write_repo

# --- A repo with one of everything and nothing wrong -------------------------------------

MARKER = """
schema_version: 1
period: 2026-Q3
okr_dir: okrs/
"""

OWNERS = """
owners:
  - id: lead
    name: Team Lead
"""

METRICS = """
metrics:
  - id: reopen_rate_7d
    definition: Share of resolved tickets reopened by the customer within 7 days
    unit: ratio
"""

GOALS = """
objectives:
  - id: team.quality
    statement: Customers get answers that hold
    owner: lead
    commitment: committed
    key_results:
      - id: team.reopens
        statement: Fewer tickets come back
        type: metric
        owner: lead
        metric: reopen_rate_7d
        target: 0.05
"""


#: The same objective with a second key result, and a line inserted between them. Used by
#: every test whose subject is a relationship between two key results.
TWO_KEY_RESULTS = """
objectives:
  - id: team.quality
    statement: Customers get answers that hold
    owner: lead
    commitment: committed
    key_results:
      - id: team.a
        statement: One
        type: metric
        owner: lead
        metric: reopen_rate_7d
        target: 0.05
{extra}      - id: team.b
        statement: Two
        type: metric
        owner: lead
        metric: reopen_rate_7d
        target: 0.07
"""

#: Two objectives, with a line inserted into the first one's key result.
TWO_OBJECTIVES = """
objectives:
  - id: team.quality
    statement: Customers get answers that hold
    owner: lead
    commitment: committed
    key_results:
      - id: team.reopens
        statement: Fewer tickets come back
        type: metric
        owner: lead
        metric: reopen_rate_7d
        target: 0.05
{extra}  - id: team.other
    statement: Something else worth doing
    owner: lead
    commitment: committed
    key_results:
      - id: team.other-kr
        statement: Ship the thing
        type: milestone
        owner: lead
        success_criteria: [Published and documented]
"""


def write(root: Path, goals: str = GOALS, owners: str = OWNERS, metrics: str = METRICS) -> Path:
    """A one-file OKR repo, so a test names exactly the thing it is breaking."""
    for relative, content in {
        "okr.yaml": MARKER,
        "owners.yaml": owners,
        "metrics.yaml": metrics,
        "okrs/team/2026-q3.yaml": goals,
    }.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return root


def report_for(root: Path) -> Report:
    return validate(load(root))


def codes(violations: Iterable[Violation]) -> list[Code]:
    return [violation.code for violation in violations]


def check(root: Path, goals: str, **files: str) -> Report:
    """Write a repo whose goal file is `goals`, and validate it."""
    return report_for(write(root, goals, **files))


# --- Nothing wrong -----------------------------------------------------------------------


def test_a_correct_repo_reports_nothing(tmp_path: Path) -> None:
    assert check(tmp_path, GOALS).violations == ()


def test_the_worked_example_is_valid(tmp_path: Path) -> None:
    """The organisation from GRAPH-BY-EXAMPLE.md, carrying all five legal edge shapes."""
    assert report_for(write_repo(tmp_path)).violations == ()


# --- Unresolved references, reported by cause --------------------------------------------


def test_one_missing_goal_referenced_twice_is_one_error(tmp_path: Path) -> None:
    """An objective deleted out from under its supporters: N symptoms, one fix."""
    goals = """
objectives:
  - id: team.quality
    statement: Customers get answers that hold
    owner: lead
    commitment: committed
    supports: [company.gone]
    key_results:
      - id: team.reopens
        statement: Fewer tickets come back
        type: metric
        owner: lead
        metric: reopen_rate_7d
        target: 0.05
        supports: [company.gone]
"""
    assert codes(check(tmp_path, goals).errors) == [Code.DANGLING_EDGE_REF]


def test_a_renamed_owner_is_one_error_however_many_goals_named_it(tmp_path: Path) -> None:
    """Twelve references, one fix. Reporting each would bury the one line to change."""
    owners = "owners:\n  - id: team_lead\n    name: Team Lead\n"
    report = check(tmp_path, GOALS, owners=owners)
    assert codes(report.errors) == [Code.DANGLING_OWNER_REF]


def test_the_grouped_error_names_every_place_that_expected_it(tmp_path: Path) -> None:
    """Grouping must not cost a reader the locations — they have to visit each one."""
    owners = "owners:\n  - id: team_lead\n    name: Team Lead\n"
    message = check(tmp_path, GOALS, owners=owners).errors[0].message
    assert "team.quality" in message and "team.reopens" in message


def test_three_different_mistyped_metrics_are_three_errors(tmp_path: Path) -> None:
    """Three targets, three fixes. Grouping is by what is missing, not by what failed."""
    goals = """
objectives:
  - id: team.quality
    statement: Customers get answers that hold
    owner: lead
    commitment: committed
    key_results:
      - id: team.a
        statement: One
        type: metric
        owner: lead
        metric: reopen_rate
        target: 0.05
      - id: team.b
        statement: Two
        type: metric
        owner: lead
        metric: reopenrate7d
        target: 0.05
      - id: team.c
        statement: Three
        type: metric
        owner: lead
        metric: REOPEN_RATE_7D
        target: 0.05
"""
    report = check(tmp_path, goals)
    assert codes(report.errors) == [Code.DANGLING_METRIC_REF] * 3


def test_one_mistyped_metric_named_twice_is_one_error(tmp_path: Path) -> None:
    goals = """
objectives:
  - id: team.quality
    statement: Customers get answers that hold
    owner: lead
    commitment: committed
    key_results:
      - id: team.a
        statement: One
        type: metric
        owner: lead
        metric: reopen_rate
        target: 0.05
      - id: team.b
        statement: Two
        type: metric
        owner: lead
        metric: reopen_rate
        target: 0.05
"""
    assert codes(check(tmp_path, goals).errors) == [Code.DANGLING_METRIC_REF]


def test_a_dangling_edge_is_not_also_reported_as_a_bad_shape(tmp_path: Path) -> None:
    """A connection to a goal that is not there has one problem, not two."""
    goals = GOALS.replace(
        "        target: 0.05\n",
        "        target: 0.05\n        depends_on: [nobody.here]\n",
    )
    assert codes(check(tmp_path, goals).errors) == [Code.DANGLING_EDGE_REF]


# --- watched_by --------------------------------------------------------------------------

WATCHING = """
objectives:
  - id: team.quality
    statement: Customers get answers that hold
    owner: lead
    commitment: committed
    key_results:
      - id: team.reopens
        statement: Fewer tickets come back
        type: metric
        owner: lead
        metric: reopen_rate_7d
        target: 0.05
        anti_targets:
          - description: Close tickets with a canned reply and let the customer chase you
            origin: authored
            watched_by: [{watched}]
"""


def test_watched_by_a_metric_that_does_not_exist(tmp_path: Path) -> None:
    report = check(tmp_path, WATCHING.format(watched="no_such_metric"))
    assert codes(report.errors) == [Code.DANGLING_WATCHED_BY_REF]


def test_watched_by_a_real_metric_that_is_not_guarded_here(tmp_path: Path) -> None:
    """A false sense of coverage is worse than an honest gap."""
    report = check(tmp_path, WATCHING.format(watched="reopen_rate_7d"))
    assert codes(report.errors) == [Code.WATCHED_BY_NOT_GUARDED]


def test_watched_by_a_metric_guarded_here_is_fine(tmp_path: Path) -> None:
    goals = WATCHING.format(watched="reopen_rate_7d").replace(
        "        anti_targets:",
        "        guardrails:\n          - metric: reopen_rate_7d\n"
        "            must_not_exceed: 0.08\n        anti_targets:",
    )
    assert check(tmp_path, goals).violations == ()


# --- Edge shapes -------------------------------------------------------------------------


def test_a_goal_that_supports_itself(tmp_path: Path) -> None:
    goals = GOALS.replace(
        "    commitment: committed\n", "    commitment: committed\n    supports: [team.quality]\n"
    )
    assert codes(check(tmp_path, goals).errors) == [Code.SELF_REFERENCE]


def test_a_key_result_that_depends_on_itself(tmp_path: Path) -> None:
    goals = GOALS.replace(
        "        target: 0.05\n", "        target: 0.05\n        depends_on: [team.reopens]\n"
    )
    assert codes(check(tmp_path, goals).errors) == [Code.SELF_REFERENCE]


def test_a_key_result_supporting_a_key_result(tmp_path: Path) -> None:
    """Always the wrong relationship: what the author means is depends_on."""
    goals = TWO_KEY_RESULTS.format(extra="        supports: [team.b]\n")
    assert codes(check(tmp_path, goals).errors) == [Code.ILLEGAL_EDGE_SHAPE]


def test_a_key_result_restating_the_objective_it_is_written_inside(tmp_path: Path) -> None:
    goals = GOALS.replace(
        "        target: 0.05\n", "        target: 0.05\n        supports: [team.quality]\n"
    )
    assert codes(check(tmp_path, goals).errors) == [Code.REDUNDANT_CONTAINMENT_EDGE]


def test_a_key_result_supporting_another_objective_is_legal(tmp_path: Path) -> None:
    """Laddering. A key result may support more than one parent — the graph is not a tree."""
    goals = TWO_OBJECTIVES.format(extra="        supports: [team.other]\n")
    assert check(tmp_path, goals).violations == ()


def test_depending_on_an_objective(tmp_path: Path) -> None:
    goals = TWO_OBJECTIVES.format(extra="        depends_on: [team.other]\n")
    assert codes(check(tmp_path, goals).errors) == [Code.DEPENDS_ON_NOT_KEY_RESULT]


# --- Cycles ------------------------------------------------------------------------------


def test_a_cycle_in_supports_is_an_error(tmp_path: Path) -> None:
    goals = """
objectives:
  - id: team.a
    statement: One
    owner: lead
    commitment: committed
    supports: [team.b]
  - id: team.b
    statement: Two
    owner: lead
    commitment: committed
    supports: [team.a]
"""
    report = check(tmp_path, goals, metrics="metrics: []\n")
    assert codes(report.errors) == [Code.SUPPORTS_CYCLE]


def test_a_cycle_is_reported_once_however_many_goals_are_in_it(tmp_path: Path) -> None:
    """Every connection in a circle has the same single fix: remove one of them."""
    goals = """
objectives:
  - id: team.a
    statement: One
    owner: lead
    commitment: committed
    supports: [team.b]
  - id: team.b
    statement: Two
    owner: lead
    commitment: committed
    supports: [team.c]
  - id: team.c
    statement: Three
    owner: lead
    commitment: committed
    supports: [team.a]
"""
    report = check(tmp_path, goals, metrics="metrics: []\n")
    assert codes(report.errors) == [Code.SUPPORTS_CYCLE]


def test_an_objective_supporting_its_own_key_result_is_a_cycle(tmp_path: Path) -> None:
    """Nesting is itself a supporting edge, so this closes a circle of two."""
    goals = GOALS.replace(
        "    commitment: committed\n", "    commitment: committed\n    supports: [team.reopens]\n"
    )
    assert Code.SUPPORTS_CYCLE in codes(check(tmp_path, goals).errors)


def test_a_cycle_in_depends_on_is_a_warning_that_still_passes(tmp_path: Path) -> None:
    """Mutual dependency is sometimes real and phased. Rejecting it teaches people to lie."""
    goals = TWO_KEY_RESULTS.format(extra="        depends_on: [team.b]\n").replace(
        "        target: 0.07\n", "        target: 0.07\n        depends_on: [team.a]\n"
    )
    report = check(tmp_path, goals)
    assert codes(report.warnings) == [Code.DEPENDS_ON_CYCLE]
    assert report.errors == ()
    assert report.ok


def test_a_path_alternating_between_the_two_relations_is_not_a_cycle(tmp_path: Path) -> None:
    """The relations are traversed separately, so a mixed circle is a cycle in neither."""
    goals = """
objectives:
  - id: team.a
    statement: One
    owner: lead
    commitment: committed
    supports: [team.kr-b]
    key_results:
      - id: team.kr-a
        statement: Move the number
        type: metric
        owner: lead
        metric: reopen_rate_7d
        target: 0.05
  - id: team.b
    statement: Two
    owner: lead
    commitment: committed
    key_results:
      - id: team.kr-b
        statement: Ship the thing
        type: milestone
        owner: lead
        success_criteria: [Published and documented]
        depends_on: [team.kr-a]
"""
    assert check(tmp_path, goals).violations == ()


# --- Content rules -----------------------------------------------------------------------


def test_a_metric_key_result_with_no_metric(tmp_path: Path) -> None:
    goals = GOALS.replace("        metric: reopen_rate_7d\n", "")
    assert codes(check(tmp_path, goals).errors) == [Code.METRIC_KR_WITHOUT_METRIC]


def test_a_metric_key_result_with_no_target(tmp_path: Path) -> None:
    goals = GOALS.replace("        target: 0.05\n", "")
    assert codes(check(tmp_path, goals).errors) == [Code.METRIC_KR_WITHOUT_METRIC]


def test_a_milestone_that_names_a_metric(tmp_path: Path) -> None:
    goals = GOALS.replace("type: metric", "type: milestone").replace(
        "        target: 0.05\n", "        target: 0.05\n        success_criteria: [Shipped]\n"
    )
    assert codes(check(tmp_path, goals).errors) == [Code.MILESTONE_KR_WITH_METRIC]


def test_a_milestone_with_no_success_criteria(tmp_path: Path) -> None:
    """No metric, no target and nothing checkable — it asserts nothing at all."""
    goals = (
        GOALS.replace("type: metric", "type: milestone")
        .replace("        metric: reopen_rate_7d\n", "")
        .replace("        target: 0.05\n", "")
    )
    report = check(tmp_path, goals, metrics="metrics: []\n")
    assert codes(report.errors) == [Code.MILESTONE_KR_WITHOUT_CRITERIA]


# --- Warnings ----------------------------------------------------------------------------


def test_an_objective_connected_to_nothing(tmp_path: Path) -> None:
    goals = (
        GOALS
        + """  - id: team.stranded
    statement: Something nobody finished wiring up
    owner: lead
    commitment: committed
"""
    )
    report = check(tmp_path, goals)
    assert codes(report.warnings) == [Code.ORPHAN_OBJECTIVE]
    assert report.ok


def test_a_top_level_objective_with_key_results_is_not_an_orphan(tmp_path: Path) -> None:
    """Containment is a supporting edge, which is what distinguishes the two."""
    assert check(tmp_path, GOALS).warnings == ()


def test_a_committed_objective_whose_key_results_all_override_to_aspirational(
    tmp_path: Path,
) -> None:
    goals = GOALS.replace(
        "        target: 0.05\n", "        target: 0.05\n        commitment: aspirational\n"
    )
    report = check(tmp_path, goals)
    assert codes(report.warnings) == [Code.ALL_KRS_ASPIRATIONAL]
    assert report.ok


def test_one_key_result_inheriting_the_objectives_commitment_is_not_a_dial(
    tmp_path: Path,
) -> None:
    goals = TWO_KEY_RESULTS.format(extra="        commitment: aspirational\n")
    assert check(tmp_path, goals).warnings == ()


def test_a_metric_nothing_targets_or_guards(tmp_path: Path) -> None:
    metrics = METRICS + "  - id: csat\n    definition: Mean satisfaction rating\n    unit: rating\n"
    report = check(tmp_path, GOALS, metrics=metrics)
    assert codes(report.warnings) == [Code.UNUSED_METRIC]


def test_an_owner_who_owns_nothing(tmp_path: Path) -> None:
    owners = OWNERS + "  - id: nobody\n    name: Nobody In Particular\n"
    report = check(tmp_path, GOALS, owners=owners)
    assert codes(report.warnings) == [Code.UNUSED_OWNER]


# --- Severity ----------------------------------------------------------------------------


def test_severity_comes_from_the_code_not_the_caller(tmp_path: Path) -> None:
    goals = (
        GOALS.replace(
            "    commitment: committed\n",
            "    commitment: committed\n    supports: [company.gone]\n",
            1,
        )
        + """  - id: team.stranded
    statement: Something nobody finished wiring up
    owner: lead
    commitment: committed
"""
    )
    report = check(tmp_path, goals)
    assert {v.severity for v in report.errors} == {Severity.ERROR}
    assert {v.severity for v in report.warnings} == {Severity.WARNING}
    assert not report.ok


def test_every_violation_says_where_to_look(tmp_path: Path) -> None:
    """A goal owner reading a pull request needs the file, and a line where there is one."""
    goals = GOALS.replace("        target: 0.05\n", "        supports: [team.quality]\n")
    for violation in check(tmp_path, goals).violations:
        assert violation.file is not None
        assert violation.line is not None
