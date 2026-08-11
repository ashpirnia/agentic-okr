"""Stable codes for everything `okr validate` can report.

The registry, with the meaning of each code and the guarantees attached to it, is
[`docs/ERROR_CODES.md`](../../../docs/ERROR_CODES.md). This module is that document in
executable form: the strings here and the rows there must not diverge.

Codes are a published contract — a code's meaning never changes, retired codes stay
reserved, and a new check gets a new code rather than widening an old one. Nothing that
consumes validation output should ever match on message text.

`E` codes fail the run. `W` codes are reported and exit zero.
"""

from enum import StrEnum
from typing import Final


class Severity(StrEnum):
    """Whether a violation fails the run.

    Part of the published contract, not a presentation choice: a consumer deciding
    whether a spec is safe to act on reads this. It is carried by the code itself —
    `E` fails, `W` reports and exits zero — so no caller can grade a violation
    differently from the registry.
    """

    ERROR = "error"
    WARNING = "warning"


class Code(StrEnum):
    """Machine-readable identity of a validation violation."""

    # E0xx — repo and marker. Failures that stop the graph being loaded at all.
    NO_MARKER = "E001_NO_MARKER"
    MARKER_UNPARSEABLE = "E002_MARKER_UNPARSEABLE"
    MARKER_FIELD_MISSING = "E003_MARKER_FIELD_MISSING"
    SCHEMA_VERSION_UNSUPPORTED = "E004_SCHEMA_VERSION_UNSUPPORTED"
    PERIOD_EMPTY = "E005_PERIOD_EMPTY"
    OKR_DIR_MISSING = "E006_OKR_DIR_MISSING"
    METRICS_FILE_MISSING = "E007_METRICS_FILE_MISSING"
    OWNERS_FILE_MISSING = "E008_OWNERS_FILE_MISSING"
    PATH_HAS_NO_MARKER = "E009_PATH_HAS_NO_MARKER"
    NO_OWNERS_DECLARED = "E010_NO_OWNERS_DECLARED"

    # E1xx — parse and structure.
    YAML_UNPARSEABLE = "E101_YAML_UNPARSEABLE"
    UNKNOWN_FIELD = "E102_UNKNOWN_FIELD"
    FIELD_MISSING = "E103_FIELD_MISSING"
    FIELD_EMPTY = "E104_FIELD_EMPTY"
    FIELD_INVALID = "E105_FIELD_INVALID"

    # E2xx — identity and references.
    DUPLICATE_ID = "E201_DUPLICATE_ID"
    DANGLING_EDGE_REF = "E202_DANGLING_EDGE_REF"
    DANGLING_METRIC_REF = "E203_DANGLING_METRIC_REF"
    DANGLING_OWNER_REF = "E204_DANGLING_OWNER_REF"
    DANGLING_WATCHED_BY_REF = "E205_DANGLING_WATCHED_BY_REF"
    WATCHED_BY_NOT_GUARDED = "E206_WATCHED_BY_NOT_GUARDED"

    # E3xx — edges.
    ILLEGAL_EDGE_SHAPE = "E301_ILLEGAL_EDGE_SHAPE"
    SELF_REFERENCE = "E302_SELF_REFERENCE"
    SUPPORTS_CYCLE = "E303_SUPPORTS_CYCLE"
    REDUNDANT_CONTAINMENT_EDGE = "E304_REDUNDANT_CONTAINMENT_EDGE"
    DEPENDS_ON_NOT_KEY_RESULT = "E305_DEPENDS_ON_NOT_KEY_RESULT"
    SUPPORTS_TARGET_INVALID = "E306_SUPPORTS_TARGET_INVALID"

    # E4xx — content rules.
    METRIC_KR_WITHOUT_METRIC = "E401_METRIC_KR_WITHOUT_METRIC"
    MILESTONE_KR_WITH_METRIC = "E402_MILESTONE_KR_WITH_METRIC"
    MILESTONE_KR_WITHOUT_CRITERIA = "E403_MILESTONE_KR_WITHOUT_CRITERIA"
    GUARDRAIL_COMPARISON = "E404_GUARDRAIL_COMPARISON"
    TARGET_NOT_NUMERIC = "E405_TARGET_NOT_NUMERIC"

    # W1xx — warnings. Legal, occasionally correct, reported without failing the run.
    DEPENDS_ON_CYCLE = "W101_DEPENDS_ON_CYCLE"
    ORPHAN_OBJECTIVE = "W102_ORPHAN_OBJECTIVE"
    ALL_KRS_ASPIRATIONAL = "W103_ALL_KRS_ASPIRATIONAL"
    UNUSED_METRIC = "W104_UNUSED_METRIC"
    UNUSED_OWNER = "W105_UNUSED_OWNER"

    @property
    def severity(self) -> Severity:
        """Whether this code fails the run. Carried by the code's own band."""
        return Severity.WARNING if self.value.startswith("W") else Severity.ERROR


#: Codes pydantic raises on its own behalf, mapped to ours. A missing or extra field is
#: detected by the model; which of our codes it becomes depends on the model it was
#: found in, so the loader completes the mapping (a missing marker field is
#: `E003_MARKER_FIELD_MISSING`, a missing node field is `E103_FIELD_MISSING`).
#:
#: Anything not listed becomes `E105_FIELD_INVALID`: a value pydantic could not read as
#: the shape the field declares — a word where a number belongs, or a `commitment`
#: outside the fixed set. The fallback is deliberate, so a pydantic release that adds an
#: error type reports a code rather than escaping as a traceback.
PYDANTIC_ERROR_TYPES: Final = {
    "missing": Code.FIELD_MISSING,
    "extra_forbidden": Code.UNKNOWN_FIELD,
}
