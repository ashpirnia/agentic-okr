"""The OKR schema, loader, graph and validator.

A library with no LLM dependency: installable and runnable without an API key. The
Champion depends on this; this never depends on the Champion, because the Conductor's
wiring lint will later sit on the same loader.

The way in is `load`, which returns a `Graph`, and then `validate`, which reports
everything wrong with it. Everything downstream — the completeness score, `okr diff`, the
CLI — reads the graph rather than the files.
"""

from .codes import Code, Severity
from .graph import Edge, EdgeKind, Graph, Node, NodeKind, Reference, RefKind, Source
from .loader import find_root, load
from .models import (
    SUPPORTED_SCHEMA_VERSIONS,
    AntiTarget,
    AntiTargetOrigin,
    Commitment,
    DependencyEdge,
    EdgeOrigin,
    GoalFile,
    Guardrail,
    KeyResult,
    KeyResultType,
    Metric,
    MetricsFile,
    Objective,
    Owner,
    OwnersFile,
    RepoMarker,
    SupportsEdge,
)
from .validate import Report, validate
from .violations import LoadError, Violation, sort_violations

__all__ = [
    "SUPPORTED_SCHEMA_VERSIONS",
    "AntiTarget",
    "AntiTargetOrigin",
    "Code",
    "Commitment",
    "DependencyEdge",
    "Edge",
    "EdgeKind",
    "EdgeOrigin",
    "GoalFile",
    "Graph",
    "Guardrail",
    "KeyResult",
    "KeyResultType",
    "LoadError",
    "Metric",
    "MetricsFile",
    "Node",
    "NodeKind",
    "Objective",
    "Owner",
    "OwnersFile",
    "RefKind",
    "Reference",
    "Report",
    "RepoMarker",
    "Severity",
    "Source",
    "SupportsEdge",
    "Violation",
    "find_root",
    "load",
    "sort_violations",
    "validate",
]
