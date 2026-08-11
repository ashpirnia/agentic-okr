"""Loader and graph tests.

Assertions are on error codes and on graph structure, never on message text: the codes
are the published contract and the sentences are free to improve.

The repo the happy-path tests load is the organisation from `docs/GRAPH-BY-EXAMPLE.md`,
written out file by file. It carries all five legal edge shapes at once, so a change that
breaks one of them fails here rather than in a demo.
"""

from pathlib import Path

import pytest

from agentic_okr.core import (
    Code,
    EdgeKind,
    Graph,
    LoadError,
    NodeKind,
    RefKind,
    Severity,
    load,
)
from agentic_okr.core.loader import find_root

# --- The worked example, as files ------------------------------------------------------

MARKER = """
schema_version: 1
period: 2026-Q3
okr_dir: okrs/
"""

OWNERS = """
owners:
  - id: ceo
    name: Chief Executive
  - id: cro
    name: Chief Revenue Officer
  - id: head-of-support
    name: Head of Support
    handles:
      github: "@acme/support-leads"
  - id: support-eng-lead
    name: Support Engineering Lead
  - id: head-of-platform
    name: Head of Platform
    handles:
      github: "@acme/platform"
"""

METRICS = """
metrics:
  - id: net_revenue_retention
    definition: Revenue from existing customers this period versus the same cohort a year ago
    unit: ratio
  - id: resolution_time_p50
    definition: Median time from ticket creation to resolution
    unit: hours
  - id: reopen_rate_7d
    definition: Share of resolved tickets reopened by the customer within 7 days
    unit: ratio
  - id: csat
    definition: Mean customer satisfaction rating on post-resolution surveys
    unit: rating_1_5
"""

COMPANY = """
objectives:
  - id: company.retention
    statement: Customers stay because the product earns it
    owner: ceo
    commitment: committed
    key_results:
      - id: company.net-retention
        statement: Net revenue retention reaches 110%
        type: metric
        owner: cro
        metric: net_revenue_retention
        target: 1.10
        success_criteria:
          - Measured on the trailing twelve months, excluding new logos
"""

SUPPORT = """
objectives:
  - id: support.fast-resolution
    statement: Customers get their problems solved, fast
    owner: head-of-support
    commitment: committed
    supports:
      - target: company.net-retention
        origin: cascaded

    key_results:
      - id: support.resolution-time
        statement: Median ticket resolution time under 4 hours
        type: metric
        owner: head-of-support
        metric: resolution_time_p50
        target: 4
        success_criteria:
          - The underlying issue is fixed, not deflected to another queue
        guardrails:
          - metric: reopen_rate_7d
            must_not_exceed: 0.08
          - metric: csat
            must_not_fall_below: 4.2
        anti_targets:
          - description: Mass-close tickets with a canned reply and let the customer chase you
            origin: authored
            restraint: A ticket may not be closed with a boilerplate reply
            watched_by: [reopen_rate_7d]
        depends_on:
          - platform.api-v2

      - id: support.self-serve
        statement: Ship help centre v2
        type: milestone
        owner: support-eng-lead
        commitment: aspirational
        success_criteria:
          - Search returns a relevant article for the top 20 ticket topics
"""

PLATFORM = """
objectives:
  - id: platform.reliability
    statement: The platform is dependable enough to build on
    owner: head-of-platform
    commitment: committed
    supports:
      - target: company.retention
        origin: laddered

    key_results:
      - id: platform.api-v2
        statement: Ship API v2 with per-ticket state transitions
        type: milestone
        owner: head-of-platform
        supports:
          - target: support.fast-resolution
            origin: laddered
        success_criteria:
          - Published, versioned, and documented
"""


def write_repo(root: Path, **overrides: str | None) -> Path:
    """Write the worked example to `root`, replacing or removing named files.

    `write_repo(tmp_path, marker=..., support=None)` writes a repo whose marker differs
    and whose support file is absent — which is how every failure case below is built.
    """
    files = {
        "okr.yaml": MARKER,
        "owners.yaml": OWNERS,
        "metrics.yaml": METRICS,
        "okrs/company/2026-q3.yaml": COMPANY,
        "okrs/support/2026-q3.yaml": SUPPORT,
        "okrs/platform/2026-q3.yaml": PLATFORM,
    }
    named = {
        "marker": "okr.yaml",
        "owners": "owners.yaml",
        "metrics": "metrics.yaml",
        "company": "okrs/company/2026-q3.yaml",
        "support": "okrs/support/2026-q3.yaml",
        "platform": "okrs/platform/2026-q3.yaml",
    }
    for key, content in overrides.items():
        path = named[key]
        if content is None:
            del files[path]
        else:
            files[path] = content

    for relative, content in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    (root / "okrs").mkdir(exist_ok=True)
    return root


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return write_repo(tmp_path)


@pytest.fixture
def graph(repo: Path) -> Graph:
    return load(repo)


def codes_from(error: LoadError) -> set[Code]:
    """The violation codes a failed load reported."""
    return {violation.code for violation in error.violations}


def raises_load(path: Path) -> LoadError:
    with pytest.raises(LoadError) as caught:
        load(path)
    return caught.value


# --- Finding the root ------------------------------------------------------------------


def test_root_is_found_by_walking_up(repo: Path) -> None:
    assert find_root(repo / "okrs" / "support") == repo


def test_working_from_a_subdirectory_loads_the_whole_repo(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Running inside one team's directory validates the entire repo, as git would."""
    monkeypatch.chdir(repo / "okrs" / "support")
    assert set(load().nodes) == set(load(repo).nodes)


def test_no_marker_anywhere_above(tmp_path: Path) -> None:
    with pytest.raises(LoadError) as caught:
        find_root(tmp_path)
    assert codes_from(caught.value) == {Code.NO_MARKER}


def test_a_subdirectory_is_never_loadable_as_a_whole_graph(repo: Path) -> None:
    """The failure ADR-0008 exists for: support references a company objective."""
    assert codes_from(raises_load(repo / "okrs" / "support")) == {Code.PATH_HAS_NO_MARKER}


def test_the_marker_itself_may_be_named(repo: Path) -> None:
    assert load(repo / "okr.yaml").root == repo


def test_a_path_may_be_a_string(repo: Path) -> None:
    assert load(str(repo)).root == repo


# --- The marker ------------------------------------------------------------------------


def test_marker_that_is_not_yaml(tmp_path: Path) -> None:
    error = raises_load(write_repo(tmp_path, marker="period: [2026-Q3\n"))
    assert codes_from(error) == {Code.MARKER_UNPARSEABLE}


def test_marker_missing_a_required_field(tmp_path: Path) -> None:
    error = raises_load(write_repo(tmp_path, marker="schema_version: 1\nokr_dir: okrs/\n"))
    assert codes_from(error) == {Code.MARKER_FIELD_MISSING}


def test_unsupported_schema_version(tmp_path: Path) -> None:
    marker = MARKER.replace("schema_version: 1", "schema_version: 2")
    assert codes_from(raises_load(write_repo(tmp_path, marker=marker))) == {
        Code.SCHEMA_VERSION_UNSUPPORTED
    }


def test_blank_period_is_its_own_code(tmp_path: Path) -> None:
    """The same underlying violation as E104, and the marker's band is more specific."""
    marker = MARKER.replace("period: 2026-Q3", 'period: "  "')
    assert codes_from(raises_load(write_repo(tmp_path, marker=marker))) == {Code.PERIOD_EMPTY}


def test_unknown_marker_field(tmp_path: Path) -> None:
    marker = MARKER + "organisation: Acme\n"
    assert codes_from(raises_load(write_repo(tmp_path, marker=marker))) == {Code.UNKNOWN_FIELD}


def test_okr_dir_that_is_not_there(tmp_path: Path) -> None:
    marker = MARKER.replace("okr_dir: okrs/", "okr_dir: goals/")
    assert codes_from(raises_load(write_repo(tmp_path, marker=marker))) == {Code.OKR_DIR_MISSING}


def test_a_named_metrics_file_that_is_not_there(tmp_path: Path) -> None:
    marker = MARKER + "metrics_file: vocabulary.yaml\n"
    assert codes_from(raises_load(write_repo(tmp_path, marker=marker))) == {
        Code.METRICS_FILE_MISSING
    }


def test_a_named_owners_file_that_is_not_there(tmp_path: Path) -> None:
    marker = MARKER + "owners_file: people.yaml\n"
    assert codes_from(raises_load(write_repo(tmp_path, marker=marker))) == {
        Code.OWNERS_FILE_MISSING
    }


def test_a_defaulted_metrics_file_may_simply_not_exist_yet(tmp_path: Path) -> None:
    """An empty metric vocabulary is legitimate: milestone key results have none.

    Individual references then fail to resolve, which is the validator's to report and
    lands on the line that names the metric.
    """
    graph = load(write_repo(tmp_path, metrics=None))
    assert graph.metrics == {}
    assert graph.metric("resolution_time_p50") is None
    assert graph.owner_of("company.retention") is not None


def test_a_defaulted_owners_file_that_is_absent_is_reported_once(tmp_path: Path) -> None:
    """An empty owner vocabulary is never legitimate, because `owner` is required.

    Letting it load would strand every node in the repo at once — seven here — with
    nothing among the failures naming the cause.
    """
    error = raises_load(write_repo(tmp_path, owners=None))
    assert codes_from(error) == {Code.NO_OWNERS_DECLARED}
    assert len(error.violations) == 1


def test_absent_owners_are_only_reported_when_there_are_goals_to_own(tmp_path: Path) -> None:
    """A repo scaffolded and not yet written has nothing to be missing an owner for."""
    empty = write_repo(tmp_path, owners=None, company=None, support=None, platform=None)
    assert load(empty).owners == {}


def test_an_owners_file_named_and_missing_is_a_different_code(tmp_path: Path) -> None:
    """`E008` is a typo in one line; `E010` is a file nobody has written."""
    marker = MARKER + "owners_file: people.yaml\n"
    assert codes_from(raises_load(write_repo(tmp_path, marker=marker, owners=None))) == {
        Code.OWNERS_FILE_MISSING
    }


# --- Goal files ------------------------------------------------------------------------


def test_goal_file_that_is_not_yaml(tmp_path: Path) -> None:
    error = raises_load(write_repo(tmp_path, support="objectives:\n\t- id: support.x\n"))
    assert codes_from(error) == {Code.YAML_UNPARSEABLE}
    assert error.violations[0].file == Path("okrs/support/2026-q3.yaml")


def test_a_missing_field_reports_the_line_it_should_have_been_on(tmp_path: Path) -> None:
    support = SUPPORT.replace("    owner: head-of-support\n    commitment", "    commitment")
    error = raises_load(write_repo(tmp_path, support=support))
    assert codes_from(error) == {Code.FIELD_MISSING}
    assert error.violations[0].line is not None


def test_a_misspelled_field_is_caught_rather_than_ignored(tmp_path: Path) -> None:
    support = SUPPORT.replace("        anti_targets:", "        anti_target:")
    assert codes_from(raises_load(write_repo(tmp_path, support=support))) == {Code.UNKNOWN_FIELD}


def test_a_target_that_is_not_a_number(tmp_path: Path) -> None:
    support = SUPPORT.replace("target: 4\n", "target: four hours\n")
    assert codes_from(raises_load(write_repo(tmp_path, support=support))) == {
        Code.TARGET_NOT_NUMERIC
    }


def test_a_value_outside_a_fixed_set(tmp_path: Path) -> None:
    support = SUPPORT.replace("commitment: committed", "commitment: quite-keen")
    assert codes_from(raises_load(write_repo(tmp_path, support=support))) == {Code.FIELD_INVALID}


def test_a_blank_required_field(tmp_path: Path) -> None:
    support = SUPPORT.replace("owner: support-eng-lead", 'owner: "   "')
    assert codes_from(raises_load(write_repo(tmp_path, support=support))) == {Code.FIELD_EMPTY}


def test_a_guardrail_with_no_limit(tmp_path: Path) -> None:
    support = SUPPORT.replace("            must_not_exceed: 0.08\n", "")
    assert codes_from(raises_load(write_repo(tmp_path, support=support))) == {
        Code.GUARDRAIL_COMPARISON
    }


def test_every_problem_is_reported_not_the_first(tmp_path: Path) -> None:
    """A support lead fixing their file wants the whole list, in one review cycle."""
    error = raises_load(
        write_repo(
            tmp_path,
            support=SUPPORT.replace("        anti_targets:", "        anti_target:"),
            platform=PLATFORM.replace(
                "    owner: head-of-platform\n    commitment", "    commitment"
            ),
        )
    )
    assert codes_from(error) == {Code.UNKNOWN_FIELD, Code.FIELD_MISSING}
    assert {v.file for v in error.violations} == {
        Path("okrs/support/2026-q3.yaml"),
        Path("okrs/platform/2026-q3.yaml"),
    }


def test_a_report_reads_down_the_files(tmp_path: Path) -> None:
    error = raises_load(
        write_repo(
            tmp_path,
            support=SUPPORT.replace("        anti_targets:", "        anti_target:").replace(
                "        success_criteria:\n          - Search returns",
                "        criteria:\n          - Search returns",
            ),
        )
    )
    lines = [v.line for v in error.violations]
    assert lines == sorted(lines)


def test_duplicate_ids_across_files(tmp_path: Path) -> None:
    platform = PLATFORM.replace("platform.api-v2", "support.self-serve")
    error = raises_load(write_repo(tmp_path, platform=platform))
    assert codes_from(error) == {Code.DUPLICATE_ID}


def test_duplicate_metric_declarations(tmp_path: Path) -> None:
    metrics = METRICS + "  - id: csat\n    definition: Something else\n    unit: rating_1_5\n"
    assert codes_from(raises_load(write_repo(tmp_path, metrics=metrics))) == {Code.DUPLICATE_ID}


def test_duplicate_owner_declarations(tmp_path: Path) -> None:
    owners = OWNERS + "  - id: ceo\n    name: Chief Executive Officer\n"
    assert codes_from(raises_load(write_repo(tmp_path, owners=owners))) == {Code.DUPLICATE_ID}


def test_an_empty_goal_file_is_not_an_error(tmp_path: Path) -> None:
    """A team that has not written their goals yet has not broken the repo."""
    assert "support.resolution-time" not in load(write_repo(tmp_path, support="")).nodes


def test_files_that_are_not_yaml_are_ignored(repo: Path) -> None:
    (repo / "okrs" / "README.md").write_text("# Our goals\n", encoding="utf-8")
    assert Path("okrs/README.md") not in load(repo).goal_files


def test_the_layout_is_not_enforced(tmp_path: Path) -> None:
    """One flat file instead of three directories loads to the same graph (ADR-0007)."""
    flat = write_repo(tmp_path, company=None, support=None, platform=None)
    one_file = COMPANY + SUPPORT.replace("objectives:", "") + PLATFORM.replace("objectives:", "")
    (flat / "okrs" / "everything.yml").write_text(one_file, encoding="utf-8")
    assert set(load(flat).nodes) == {
        "company.retention",
        "company.net-retention",
        "support.fast-resolution",
        "support.resolution-time",
        "support.self-serve",
        "platform.reliability",
        "platform.api-v2",
    }


# --- The graph that comes out ----------------------------------------------------------


def test_the_whole_graph_is_loaded(graph: Graph) -> None:
    assert len(graph) == 7
    assert len(graph.objectives) == 3
    assert len(graph.key_results) == 4
    assert graph.marker.period == "2026-Q3"


def test_nesting_materialises_the_primary_supports_edge(graph: Graph) -> None:
    """Nobody wrote this edge; the loader makes it from containment (ADR-0006)."""
    containment = [
        edge
        for edge in graph.outgoing("support.resolution-time", EdgeKind.SUPPORTS)
        if edge.implicit
    ]
    assert [edge.target_id for edge in containment] == ["support.fast-resolution"]
    assert graph.node("support.resolution-time").parent_id == "support.fast-resolution"


def test_a_key_result_can_have_two_parents(graph: Graph) -> None:
    """The shape that makes this a network rather than a tree."""
    parents = {edge.target_id for edge in graph.outgoing("platform.api-v2", EdgeKind.SUPPORTS)}
    assert parents == {"platform.reliability", "support.fast-resolution"}


def test_an_objective_can_support_a_key_result(graph: Graph) -> None:
    """Doerr's cascade: a parent's key result becomes the child level's objective."""
    edges = graph.outgoing("support.fast-resolution", EdgeKind.SUPPORTS)
    assert [(edge.target_id, edge.implicit) for edge in edges] == [("company.net-retention", False)]
    assert graph.node("company.net-retention").kind is NodeKind.KEY_RESULT


def test_the_shorthand_and_the_mapping_form_agree(tmp_path: Path) -> None:
    """`depends_on: [platform.api-v2]` normalises to the mapping form (ADR-0006)."""
    written_out = SUPPORT.replace(
        "        depends_on:\n          - platform.api-v2",
        "        depends_on:\n          - target: platform.api-v2",
    )
    long_form = load(write_repo(tmp_path, support=written_out))
    assert [(e.source_id, e.target_id) for e in long_form.edges_of_kind(EdgeKind.DEPENDS_ON)] == [
        ("support.resolution-time", "platform.api-v2")
    ]


def test_edge_origin_is_kept(graph: Graph) -> None:
    laddered = graph.outgoing("platform.reliability", EdgeKind.SUPPORTS)[0]
    assert laddered.origin is not None and laddered.origin.value == "laddered"


def test_incoming_edges_are_found_from_the_other_side(graph: Graph) -> None:
    """Nobody declared anything on `support.fast-resolution`; it takes the whole graph."""
    supporters = {edge.source_id for edge in graph.incoming("support.fast-resolution")}
    assert supporters == {"support.resolution-time", "support.self-serve", "platform.api-v2"}


def test_key_results_of_is_containment_only(graph: Graph) -> None:
    contained = {node.id for node in graph.key_results_of("support.fast-resolution")}
    assert contained == {"support.resolution-time", "support.self-serve"}


def test_owners_resolve(graph: Graph) -> None:
    assert graph.owner_of("platform.api-v2").name == "Head of Platform"
    assert graph.owner("head-of-platform").handles == {"github": "@acme/platform"}


def test_metrics_resolve(graph: Graph) -> None:
    assert graph.metric("resolution_time_p50").unit == "hours"


def test_all_three_reference_classes_are_collected(graph: Graph) -> None:
    assert len(graph.references_of(RefKind.OWNER)) == 7
    assert {r.target_id for r in graph.references_of(RefKind.METRIC)} == {
        "net_revenue_retention",
        "resolution_time_p50",
        "reopen_rate_7d",
        "csat",
    }
    assert [r.target_id for r in graph.references_of(RefKind.WATCHED_BY)] == ["reopen_rate_7d"]
    assert {r.target_id for r in graph.references_of(RefKind.EDGE)} == {
        "company.net-retention",
        "company.retention",
        "support.fast-resolution",
        "platform.api-v2",
    }


def test_every_reference_carries_the_line_it_was_written_on(graph: Graph) -> None:
    """So an unresolved one can be pointed at, rather than leaving a reader to search."""
    assert all(reference.source.line is not None for reference in graph.references)
    guardrail = next(
        r for r in graph.references_of(RefKind.METRIC) if r.target_id == "reopen_rate_7d"
    )
    text = (graph.root / guardrail.source.file).read_text(encoding="utf-8").splitlines()
    assert "reopen_rate_7d" in text[guardrail.source.line - 1]


def test_a_dangling_reference_still_produces_a_graph(tmp_path: Path) -> None:
    """Loading answers 'could this be built', not 'is this correct'.

    Resolution is the validator's, and it needs a whole graph to do it against.
    """
    support = SUPPORT.replace("- platform.api-v2", "- platform.api-v3")
    graph = load(write_repo(tmp_path, support=support))
    assert graph.node("platform.api-v3") is None
    assert "platform.api-v3" in {edge.target_id for edge in graph.edges}


def test_a_cycle_still_produces_a_graph(tmp_path: Path) -> None:
    company = COMPANY.replace(
        "    commitment: committed\n",
        "    commitment: committed\n    supports:\n      - platform.reliability\n",
        1,
    )
    graph = load(write_repo(tmp_path, company=company))
    assert "platform.reliability" in {
        edge.target_id for edge in graph.outgoing("company.retention")
    }


# --- Violations ------------------------------------------------------------------------


def test_severity_comes_from_the_code(tmp_path: Path) -> None:
    error = raises_load(write_repo(tmp_path, marker="period: [2026-Q3\n"))
    assert all(v.severity is Severity.ERROR for v in error.violations)


def test_a_violation_locates_itself_relative_to_the_repo_root(tmp_path: Path) -> None:
    support = SUPPORT.replace("        anti_targets:", "        anti_target:")
    violation = raises_load(write_repo(tmp_path, support=support)).violations[0]
    assert violation.location == f"okrs/support/2026-q3.yaml:{violation.line}"
    assert violation.code.value in str(violation)
