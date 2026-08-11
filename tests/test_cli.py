"""CLI tests.

The command's contract with a CI job is its exit code, and its contract with a script is
the JSON. Those are what is asserted here, along with the codes printed on a terminal —
never the sentences around them, which are free to improve.

One test does assert on prose, in the negative: that nothing Python-shaped reaches the
page. The reader of this output is a support lead looking at a pull request, and a
traceback or a module path in front of them is the failure this whole layer exists to
prevent — so it is worth a test rather than a convention.
"""

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from agentic_okr.cli import app
from tests.test_loader import SUPPORT, write_repo

runner = CliRunner()

#: A supports cycle, which `okr validate` reports and `okr graph` has to survive drawing.
CYCLE = """
objectives:
  - id: circle.first
    statement: First
    owner: ceo
    commitment: committed
    supports: [circle.second]
  - id: circle.second
    statement: Second
    owner: ceo
    commitment: committed
    supports: [circle.first]
"""


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """The worked example: valid, and quiet."""
    return write_repo(tmp_path)


@pytest.fixture
def dangling(tmp_path: Path) -> Path:
    """A repo whose support team depends on a key result nobody declares."""
    return write_repo(tmp_path, support=SUPPORT.replace("platform.api-v2", "platform.api-v-2"))


@pytest.fixture
def unreadable(tmp_path: Path) -> Path:
    """A repo with a YAML file that does not parse, so no graph can be built at all."""
    return write_repo(tmp_path, support="objectives:\n  - id: x\n   statement: bad indent\n")


def run(*arguments: str, typed: str | None = None) -> Any:
    """Invoke the CLI, failing loudly if anything escaped as an exception.

    `typed` is what somebody enters at a prompt, which is how `okr init` gets a period
    when it was not passed one.
    """
    result = runner.invoke(app, list(arguments), input=typed)
    assert result.exception is None or isinstance(result.exception, SystemExit), (
        f"The command raised instead of reporting:\n{result.output}"
    )
    return result


def payload(*arguments: str) -> dict[str, Any]:
    """The machine output of a command, parsed. Anything but JSON is a broken contract."""
    return json.loads(run(*arguments).output)


#: What must never appear in front of a goal owner. Each one means an internal failure
#: escaped instead of being reported as a sentence with a code beside it.
LEAKS = ("Traceback", "agentic_okr", ".py", "core/", "pydantic", "Error:")


def assert_reads_like_prose(output: str) -> None:
    for leak in LEAKS:
        assert leak not in output, f"{leak!r} leaked into what a goal owner reads:\n{output}"


# --- init --------------------------------------------------------------------------------


def test_init_creates_a_repo_that_validates(tmp_path: Path) -> None:
    """The whole promise of the command, from the outside: scaffold, then check it."""
    assert run("init", str(tmp_path), "--period", "2026-Q3").exit_code == 0
    assert run("validate", str(tmp_path)).exit_code == 0


def test_init_asks_for_the_period_when_it_is_not_given(tmp_path: Path) -> None:
    result = run("init", str(tmp_path), typed="2026-H1\n")

    assert result.exit_code == 0
    assert (tmp_path / "okrs" / "support" / "2026-h1.yaml").is_file()


def test_init_creates_the_directory_it_is_pointed_at(tmp_path: Path) -> None:
    target = tmp_path / "acme-okrs"

    assert run("init", str(target), "--period", "2026-Q3").exit_code == 0
    assert (target / "okr.yaml").is_file()


def test_init_refuses_where_there_is_already_a_repo(repo: Path) -> None:
    result = run("init", str(repo), "--period", "2026-Q3")

    assert result.exit_code == 1
    assert "already" in result.output


def test_init_says_what_to_do_next(tmp_path: Path) -> None:
    """A scaffold that does not say what to do next is a pile of files."""
    result = run("init", str(tmp_path), "--period", "2026-Q3")

    assert "okrs/support/2026-q3.yaml" in result.output
    assert "okr validate" in result.output


# --- validate: the exit code is the contract with CI -------------------------------------


def test_a_valid_repo_exits_zero(repo: Path) -> None:
    assert run("validate", str(repo)).exit_code == 0


def test_an_error_exits_non_zero(dangling: Path) -> None:
    assert run("validate", str(dangling)).exit_code == 1


def test_warnings_alone_do_not_fail_the_run(tmp_path: Path) -> None:
    """`W` codes are reported and exit zero. That is part of the published contract."""
    owners = write_repo(tmp_path).joinpath("owners.yaml")
    owners.write_text(owners.read_text() + "  - id: nobody\n    name: Nobody\n", encoding="utf-8")

    result = run("validate", str(tmp_path))

    assert "W105_UNUSED_OWNER" in result.output
    assert result.exit_code == 0


def test_a_repo_that_cannot_be_read_exits_non_zero(unreadable: Path) -> None:
    result = run("validate", str(unreadable))

    assert "E101_YAML_UNPARSEABLE" in result.output
    assert result.exit_code == 1


def test_a_directory_below_the_root_is_refused(repo: Path) -> None:
    """No supported route to validating a fragment, and the refusal says which code."""
    result = run("validate", str(repo / "okrs" / "support"))

    assert "E009_PATH_HAS_NO_MARKER" in result.output
    assert result.exit_code == 1


def test_a_directory_with_no_repo_above_it_is_refused(tmp_path: Path) -> None:
    result = run("validate", str(tmp_path))

    assert "E009_PATH_HAS_NO_MARKER" in result.output
    assert result.exit_code == 1


def test_the_path_may_be_left_out(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run from inside one team's directory, and the whole repo is checked."""
    monkeypatch.chdir(repo / "okrs" / "support")

    assert run("validate").exit_code == 0


# --- validate: what is on the page -------------------------------------------------------


def test_every_violation_is_printed_with_its_code(dangling: Path) -> None:
    codes = {v["code"] for v in payload("validate", "--json", str(dangling))["violations"]}

    printed = run("validate", str(dangling)).output

    assert codes
    assert all(code in printed for code in codes)


def test_a_violation_is_printed_with_the_line_it_is_on(dangling: Path) -> None:
    lines = [v["line"] for v in payload("validate", "--json", str(dangling))["violations"]]

    printed = run("validate", str(dangling)).output

    assert all(f"line {line}" in printed for line in lines if line is not None)


@pytest.mark.parametrize("command", ["validate", "graph", "score"])
@pytest.mark.parametrize("fixture", ["repo", "dangling", "unreadable"])
def test_nothing_python_shaped_reaches_the_page(
    command: str, fixture: str, request: pytest.FixtureRequest
) -> None:
    """The reader is a goal owner in a pull request, not a developer.

    A traceback, a module path or one of our own identifiers on the page means an
    internal failure escaped instead of being reported as a violation with a code.
    """
    path = request.getfixturevalue(fixture)

    assert_reads_like_prose(run(command, str(path)).output)


def test_nothing_python_shaped_reaches_the_page_when_init_refuses(repo: Path) -> None:
    assert_reads_like_prose(run("init", str(repo), "--period", "2026-Q3").output)
    assert_reads_like_prose(run("init", str(repo / "okrs"), "--period", "2026-Q3").output)


# --- validate: the machine contract ------------------------------------------------------


def test_json_reports_the_run_and_every_violation(dangling: Path) -> None:
    result = payload("validate", "--json", str(dangling))

    assert result["ok"] is False
    assert result["loaded"] is True
    assert result["repo"]["period"] == "2026-Q3"
    assert result["counts"]["errors"] == len(
        [v for v in result["violations"] if v["severity"] == "error"]
    )


def test_json_ok_matches_the_exit_code(repo: Path) -> None:
    assert payload("validate", "--json", str(repo))["ok"] is True
    assert run("validate", "--json", str(repo)).exit_code == 0


def test_json_says_when_it_never_got_to_look(unreadable: Path) -> None:
    """`loaded` is how a consumer tells 'nothing found' apart from 'never checked'."""
    result = payload("validate", "--json", str(unreadable))

    assert result["loaded"] is False
    assert result["repo"] is None
    assert result["counts"]["objectives"] is None
    assert result["counts"]["errors"] == 1


def test_json_is_the_only_thing_printed(repo: Path) -> None:
    """Nothing decorative may share the stream, or a caller cannot parse it."""
    assert run("validate", "--json", str(repo)).output.lstrip().startswith("{")


# --- score -------------------------------------------------------------------------------


def test_score_prints_the_count_and_never_a_grade(repo: Path) -> None:
    """`12 of 19`, and nothing that reads as a mark out of ten."""
    result = run("score", str(repo))

    assert "12 of 19" in result.output
    assert result.exit_code == 0


def test_score_says_what_it_measures(repo: Path) -> None:
    """The distinction the whole feature depends on, printed every run."""
    assert "Not whether the goals are good ones" in run("score", str(repo)).output


def test_score_names_the_specific_misses(repo: Path) -> None:
    """A count of gaps would not tell anybody what to go and write."""
    output = run("score", str(repo)).output

    assert "missing: guardrails, anti-targets" in output


def test_score_never_fails_the_run(dangling: Path) -> None:
    """A score is a measurement, not a gate — even on a repo that fails validation."""
    assert run("score", str(dangling)).exit_code == 0


def test_score_on_a_repo_that_cannot_be_read_exits_non_zero(unreadable: Path) -> None:
    result = run("score", str(unreadable))

    assert "E101_YAML_UNPARSEABLE" in result.output
    assert result.exit_code == 1


def test_score_json_carries_every_check_so_the_total_can_be_recounted(repo: Path) -> None:
    result = payload("score", "--json", str(repo))
    checks = [
        passed
        for objective in result["objectives"]
        for node in (objective, *objective["key_results"])
        for passed in node["checks"].values()
    ]

    assert result["score"] == {"passed": 12, "total": 19, "percentage": 63}
    assert sum(checks) == 12
    assert len(checks) == 19


def test_score_of_a_new_repo_says_there_is_nothing_to_score(tmp_path: Path) -> None:
    """A scaffold scores 0 of 0. That is not the same as scoring badly."""
    run("init", str(tmp_path), "--period", "2026-Q3")

    result = run("score", str(tmp_path))

    assert result.exit_code == 0
    assert "nothing to score" in result.output


# --- graph -------------------------------------------------------------------------------


def test_graph_shows_every_goal(repo: Path) -> None:
    ids = [node["id"] for node in payload("graph", "--json", str(repo))["nodes"]]

    printed = run("graph", str(repo)).output

    assert all(goal_id in printed for goal_id in ids)


def test_graph_shows_the_connections_somebody_wrote(repo: Path) -> None:
    written = [e for e in payload("graph", "--json", str(repo))["edges"] if not e["implicit"]]

    printed = run("graph", str(repo)).output

    assert written
    assert all(f"{edge['file']}:{edge['line']}" in printed for edge in written)


def test_graph_draws_a_key_result_under_each_parent_it_supports(repo: Path) -> None:
    """A key result may support several objectives, so the tree is a projection of a graph."""
    printed = run("graph", str(repo)).output

    assert printed.count("platform.api-v2") >= 2
    assert "shown above" in printed


def test_graph_survives_a_cycle(tmp_path: Path) -> None:
    """A circle is an error `okr validate` reports. Drawing one must not hang or crash."""
    repo = write_repo(tmp_path, company=CYCLE, support=None, platform=None)

    result = run("graph", str(repo))

    assert result.exit_code == 0
    assert "circle.first" in result.output
    assert "circle.second" in result.output


def test_graph_marks_a_connection_pointing_at_nothing(dangling: Path) -> None:
    """`okr graph` prints what is written, including what does not resolve."""
    result = run("graph", str(dangling))

    assert result.exit_code == 0
    assert "platform.api-v-2" in result.output


def test_graph_on_a_repo_that_cannot_be_read_exits_non_zero(unreadable: Path) -> None:
    result = run("graph", str(unreadable))

    assert "E101_YAML_UNPARSEABLE" in result.output
    assert result.exit_code == 1
