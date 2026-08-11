"""Schema tests.

Assertions are on error codes, never on message text: the codes are the published
contract and the sentences are free to improve.

The YAML fragments here are copied from `docs/GRAPH-BY-EXAMPLE.md`. If a change makes one
of them fail, either the document or the schema is now wrong — that is the point of
testing against it.
"""

import pytest
import yaml
from pydantic import ValidationError

from agentic_okr.core import (
    Code,
    Commitment,
    Guardrail,
    KeyResult,
    KeyResultType,
    Objective,
    OwnersFile,
    RepoMarker,
)


def codes_from(error: ValidationError) -> set[str]:
    """The violation codes a failed parse reported."""
    return {e["type"] for e in error.errors()}


def parse(model: type, source: str):
    """Parse a YAML fragment as it would arrive from a file."""
    return model.model_validate(yaml.safe_load(source))


# --- The worked example parses -------------------------------------------------------


def test_support_objective_from_the_worked_example() -> None:
    objective = parse(
        Objective,
        """
        id: support.fast-resolution
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
              - description: Mass-close tickets with a canned reply
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
              - Published and linked from the product's help menu
        """,
    )

    resolution_time, self_serve = objective.key_results
    assert objective.commitment is Commitment.COMMITTED
    assert resolution_time.type is KeyResultType.METRIC
    assert resolution_time.target == 4
    assert resolution_time.anti_targets[0].watched_by == ["reopen_rate_7d"]

    # A milestone key result with no metric and no target is legitimate, not deficient.
    assert self_serve.type is KeyResultType.MILESTONE
    assert self_serve.metric is None
    # It overrides its objective's commitment: a stretch inside a must-hit goal.
    assert self_serve.commitment is Commitment.ASPIRATIONAL


def test_owners_file_from_the_worked_example() -> None:
    owners = parse(
        OwnersFile,
        """
        owners:
          - id: ceo
            name: Chief Executive
          - id: head-of-platform
            name: Head of Platform
            handles:
              github: "@acme/platform"
        """,
    )

    assert owners.owners[0].handles == {}
    assert owners.owners[1].handles == {"github": "@acme/platform"}


# --- Edges ---------------------------------------------------------------------------


def test_edge_shorthand_normalises_to_the_mapping_form() -> None:
    key_result = parse(
        KeyResult,
        """
        id: platform.api-v2
        statement: Ship API v2
        type: milestone
        owner: head-of-platform
        supports: [support.fast-resolution]
        depends_on: [platform.schema]
        """,
    )

    assert key_result.supports[0].target == "support.fast-resolution"
    assert key_result.supports[0].origin is None
    assert key_result.depends_on[0].target == "platform.schema"


# --- Required fields, and blank ones -------------------------------------------------


def test_ownership_is_required_on_both_node_types() -> None:
    with pytest.raises(ValidationError) as objective:
        parse(
            Objective,
            """
            id: platform.reliability
            statement: The platform is dependable enough to build on
            commitment: committed
            """,
        )
    with pytest.raises(ValidationError) as key_result:
        parse(
            KeyResult,
            """
            id: platform.api-v2
            statement: Ship API v2
            type: milestone
            """,
        )

    assert codes_from(objective.value) == {"missing"}
    assert codes_from(key_result.value) == {"missing"}


def test_a_blank_required_field_is_rejected() -> None:
    with pytest.raises(ValidationError) as error:
        parse(
            Objective,
            """
            id: platform.reliability
            statement: "   "
            owner: head-of-platform
            commitment: committed
            """,
        )

    assert codes_from(error.value) == {Code.FIELD_EMPTY}


def test_surrounding_whitespace_is_trimmed_from_a_reference() -> None:
    # Otherwise an owner differing only by a trailing space is a dangling reference
    # nobody can see in a diff.
    key_result = parse(
        KeyResult,
        """
        id: platform.api-v2
        statement: Ship API v2
        type: milestone
        owner: "head-of-platform "
        """,
    )

    assert key_result.owner == "head-of-platform"


def test_a_misspelled_field_is_rejected_rather_than_ignored() -> None:
    with pytest.raises(ValidationError) as error:
        parse(
            KeyResult,
            """
            id: support.resolution-time
            statement: Median ticket resolution time under 4 hours
            type: metric
            owner: head-of-support
            anti_target:
              - description: Mass-close tickets with a canned reply
            """,
        )

    assert codes_from(error.value) == {"extra_forbidden"}


# --- Guardrail thresholds ------------------------------------------------------------


@pytest.mark.parametrize(
    "comparison",
    [
        {},
        {"must_not_exceed": 0.08, "must_not_fall_below": 0.02},
    ],
    ids=["neither", "both"],
)
def test_a_guardrail_states_exactly_one_limit(comparison: dict[str, float]) -> None:
    with pytest.raises(ValidationError) as error:
        Guardrail.model_validate({"metric": "reopen_rate_7d"} | comparison)

    assert codes_from(error.value) == {Code.GUARDRAIL_COMPARISON}


# --- The repo marker -----------------------------------------------------------------


def test_marker_defaults_the_two_optional_paths() -> None:
    marker = parse(
        RepoMarker,
        """
        schema_version: 1
        period: 2026-Q3
        okr_dir: okrs/
        """,
    )

    assert str(marker.metrics_file) == "metrics.yaml"
    assert str(marker.owners_file) == "owners.yaml"


def test_an_unsupported_schema_version_fails_rather_than_being_read_on_a_guess() -> None:
    with pytest.raises(ValidationError) as error:
        parse(
            RepoMarker,
            """
            schema_version: 2
            period: 2026-Q3
            okr_dir: okrs/
            """,
        )

    assert codes_from(error.value) == {Code.SCHEMA_VERSION_UNSUPPORTED}


def test_schema_version_is_never_defaulted_or_inferred() -> None:
    with pytest.raises(ValidationError) as error:
        parse(RepoMarker, "period: 2026-Q3\nokr_dir: okrs/")

    assert codes_from(error.value) == {"missing"}
