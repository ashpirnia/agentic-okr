"""The resolved goal graph: the public API everything else is built on.

The validator, the completeness score, `okr diff` and the future Conductor lint all read
this object, never the YAML. That is the whole point of the split — the file format is an
authoring surface, and the graph is what the tool reasons about.

**The graph is not a transliteration of the files.** Three things happen on the way in
([ADR-0006](../../../docs/adr/0006-edge-semantics.md)): a key result nested inside an
objective gains its containing objective as an implicit `supports` edge, the bare-ID
authoring shorthand becomes a mapping, and every reference — to a node, a metric or an
owner — is collected with the file and line it was written on so that whatever fails to
resolve can be pointed at.

**What the graph does not promise is that it is valid.** A graph exists only if it could
be *built*: the files parsed, the fields were the right shapes, and every ID is unique.
Dangling references, illegal edge shapes, cycles and orphans are all representable here
and are the validator's to report — they are questions about a whole graph, and answering
them needs one.
"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from .models import EdgeOrigin, KeyResult, Metric, Objective, Owner, RepoMarker


class NodeKind(StrEnum):
    """What a node is. Values are the words a goal owner would use, since they are
    printed in violation messages and in `okr diff` output."""

    OBJECTIVE = "objective"
    KEY_RESULT = "key result"


class EdgeKind(StrEnum):
    """Which relation an edge expresses. See [ADR-0006](../../../docs/adr/0006-edge-semantics.md).

    Values match the field names authors write, so a message about an edge names the
    line it came from.
    """

    SUPPORTS = "supports"
    DEPENDS_ON = "depends_on"


class RefKind(StrEnum):
    """Which vocabulary a reference points into.

    Three classes, and each has its own dangling-reference code because each fails
    differently: an edge to nothing breaks the graph, a metric to nothing breaks the
    join to measurement, an owner to nothing breaks review routing.
    """

    EDGE = "edge"
    METRIC = "metric"
    OWNER = "owner"
    WATCHED_BY = "watched_by"


@dataclass(frozen=True, slots=True)
class Source:
    """Where something was written: a path relative to the OKR repo root, and a line.

    Relative because that is how the file appears in a pull request. The line is
    best-effort — YAML gives one for anything written down, but not for an edge the
    loader materialised from nesting, which points at the key result instead.
    """

    file: Path
    line: int | None = None

    def __str__(self) -> str:
        return f"{self.file}:{self.line}" if self.line is not None else str(self.file)


@dataclass(frozen=True, slots=True)
class Node:
    """One objective or key result, with its identity, its spec and where it lives."""

    id: str
    kind: NodeKind
    spec: Objective | KeyResult
    source: Source
    parent_id: str | None = None
    """The objective this key result is written inside, if it is one.

    Containment is the primary `supports` edge, so this is the same fact the implicit
    edge carries. It is kept here as well because two consumers need it directly: the
    completeness score walks an objective's own key results, and the check that catches a
    key result restating its container needs to know what its container is.
    """

    @property
    def owner_id(self) -> str:
        """Who is accountable. Present on both node kinds, and required on both."""
        return self.spec.owner


@dataclass(frozen=True, slots=True)
class Edge:
    """A connection between two nodes, always declared on the needy side.

    `target_id` is a string rather than a node because an edge may not resolve — that is
    a dangling reference, the failure this project exists to catch, and it has to be
    representable in order to be reported.
    """

    kind: EdgeKind
    source_id: str
    target_id: str
    source: Source
    origin: EdgeOrigin | None = None
    implicit: bool = False
    """True for the `supports` edge materialised from nesting, which nobody wrote.

    Consumers distinguish these: `okr diff` should not announce a containment edge as a
    new cross-team commitment, and an error message must not tell someone to fix a line
    that does not exist in their file.
    """


@dataclass(frozen=True, slots=True)
class Reference:
    """One place a declared vocabulary is referred to, and where that was written.

    Collected during the load so the validator can resolve all three classes uniformly
    and report each unresolved one at its own line, rather than naming the node and
    leaving a reader to search the file for which of five metrics was misspelled.
    """

    kind: RefKind
    target_id: str
    from_node_id: str
    source: Source


@dataclass(frozen=True, slots=True, eq=False)
class Graph:
    """A whole OKR repo, loaded and resolved.

    Always whole. There is no supported way to build one of these from a subdirectory,
    because a fragment produces phantom dangling references and a reviewer list that
    silently omits the team a change affects
    ([ADR-0008](../../../docs/adr/0008-okr-yaml-marker.md)).
    """

    root: Path
    """The directory containing `okr.yaml`. Every other path here is relative to it."""

    marker: RepoMarker
    nodes: dict[str, Node]
    edges: tuple[Edge, ...]
    references: tuple[Reference, ...]
    metrics: dict[str, Metric]
    owners: dict[str, Owner]
    metric_sources: dict[str, Source] = field(default_factory=dict)
    owner_sources: dict[str, Source] = field(default_factory=dict)
    goal_files: tuple[Path, ...] = ()
    """Every file under `okr_dir` that was read, in load order. Relative to the root."""

    # --- Nodes ------------------------------------------------------------------------

    def node(self, node_id: str) -> Node | None:
        """The node with this ID, or None if nothing declares it."""
        return self.nodes.get(node_id)

    @property
    def objectives(self) -> tuple[Node, ...]:
        return tuple(n for n in self.nodes.values() if n.kind is NodeKind.OBJECTIVE)

    @property
    def key_results(self) -> tuple[Node, ...]:
        return tuple(n for n in self.nodes.values() if n.kind is NodeKind.KEY_RESULT)

    def key_results_of(self, objective_id: str) -> tuple[Node, ...]:
        """The key results written inside this objective, in file order.

        Containment only. A key result that supports this objective from another team's
        file is a `supports` edge and is found through `incoming`.
        """
        return tuple(n for n in self.nodes.values() if n.parent_id == objective_id)

    # --- Edges ------------------------------------------------------------------------

    def outgoing(self, node_id: str, kind: EdgeKind | None = None) -> tuple[Edge, ...]:
        """Edges declared by this node — what it supports, what it depends on."""
        return tuple(
            e for e in self.edges if e.source_id == node_id and (kind is None or e.kind is kind)
        )

    def incoming(self, node_id: str, kind: EdgeKind | None = None) -> tuple[Edge, ...]:
        """Edges pointing at this node. Nobody declared these on it; they were declared
        on the needy side, which is why they can only be found by looking across the
        whole graph."""
        return tuple(
            e for e in self.edges if e.target_id == node_id and (kind is None or e.kind is kind)
        )

    def edges_of_kind(self, kind: EdgeKind) -> tuple[Edge, ...]:
        """Every edge of one relation.

        The relations are traversed separately — a path alternating between `supports`
        and `depends_on` is a cycle in neither (ADR-0006).
        """
        return tuple(e for e in self.edges if e.kind is kind)

    # --- Declared vocabulary ----------------------------------------------------------

    def metric(self, metric_id: str) -> Metric | None:
        return self.metrics.get(metric_id)

    def owner(self, owner_id: str) -> Owner | None:
        return self.owners.get(owner_id)

    def owner_of(self, node_id: str) -> Owner | None:
        """The declared owner of a node, or None if the node or the owner is unknown.

        Review routing compares these for equality, which is the reason owners are
        declared at all: two spellings of one person route a cross-team review to
        neither ([ADR-0010](../../../docs/adr/0010-owner-identity.md)).
        """
        node = self.nodes.get(node_id)
        return None if node is None else self.owners.get(node.owner_id)

    def references_of(self, kind: RefKind) -> tuple[Reference, ...]:
        return tuple(r for r in self.references if r.kind is kind)

    # --- Convenience ------------------------------------------------------------------

    def __iter__(self) -> Iterator[Node]:
        return iter(self.nodes.values())

    def __len__(self) -> int:
        return len(self.nodes)
