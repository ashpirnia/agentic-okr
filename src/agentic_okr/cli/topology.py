"""Printing the resolved graph, so the shape of an organisation's goals is visible at once.

Three views of the same object, because the thing worth seeing is not the same in each.
The **tree** shows what contributes to what, top-level objectives downward. The
**connections** table lists every edge somebody actually wrote, which is where the
cross-team topology lives — the tree hides it, because a key result that supports two
objectives has to be drawn under one of them. The **summary** is the size of the thing.

**The tree is a projection of a graph, and says so.** A key result may support several
objectives (ADR-0006), so it appears under each and is drawn in full only the first time;
after that it is marked as already shown. Without that a repeated subtree would be printed
twice and a `supports` cycle would never terminate. Anything the walk never reaches — a
goal inside a cycle, or one whose only connection points at a goal that does not exist —
is printed at the end rather than silently dropped, because a goal missing from the picture
is exactly the kind of wrong answer that looks like a right one.

**Nothing here validates.** `okr graph` prints what is written, including connections that
do not resolve, which are marked in place and reported properly by `okr validate`.
"""

from typing import Any

from rich.console import Console
from rich.padding import Padding
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from agentic_okr.core import Edge, EdgeKind, Graph, KeyResult, Node, NodeKind

#: What each node kind is drawn as. Two shapes rather than two colours alone, because a
#: screenshot outlives the terminal it was taken in and colour is the first thing lost.
_GLYPHS: dict[NodeKind, str] = {NodeKind.OBJECTIVE: "◆", NodeKind.KEY_RESULT: "•"}

_KIND_STYLES: dict[NodeKind, str] = {NodeKind.OBJECTIVE: "bold cyan", NodeKind.KEY_RESULT: "bold"}

#: How each relation is read aloud. The field names authors write are `supports` and
#: `depends_on`; the second is printed as English because the table is prose, not YAML.
_RELATIONS: dict[EdgeKind, str] = {EdgeKind.SUPPORTS: "supports", EdgeKind.DEPENDS_ON: "depends on"}


# --- On a terminal ---------------------------------------------------------------------


def render(console: Console, graph: Graph) -> None:
    """The whole picture: the tree, what it could not place, the connections, the size."""
    console.print(
        Text.assemble(
            (graph.root.name, "bold"), ("  ", ""), (f"period {graph.marker.period}", "dim")
        )
    )
    console.print()
    _render_tree(console, graph)
    _render_connections(console, graph)
    console.print(Text(_summary(graph), style="dim"))


def _render_tree(console: Console, graph: Graph) -> None:
    """Every top-level objective, with what contributes to it beneath.

    Drawn as one tree per root rather than one tree with a shared stem, because a
    top-level objective is a thing an organisation has several of and a shared root would
    invent a parent nobody wrote.
    """
    drawn: set[str] = set()
    roots = _roots(graph)
    if not roots:
        console.print(Text("No top-level objectives — nothing to draw from.", style="dim"))
        console.print()
    for root in roots:
        tree = Tree(_label(graph, root, repeated=False), guide_style="dim")
        _grow(graph, tree, root, drawn, set())
        console.print(tree)
        console.print()
    _render_unplaced(console, graph, drawn)


def _grow(graph: Graph, tree: Tree, node: Node, drawn: set[str], ancestors: set[str]) -> None:
    """Hang everything that supports `node` beneath it, once each.

    `drawn` spans the whole picture and stops a multi-parent key result being expanded
    under every parent. `ancestors` is this branch only, and is what stops a `supports`
    cycle from recurring forever — a cycle is an error `okr validate` reports, and this
    command has to survive printing one rather than hanging on it.
    """
    drawn.add(node.id)
    for child in _children(graph, node.id):
        repeated = child.id in drawn or child.id in ancestors
        branch = tree.add(_label(graph, child, repeated=repeated))
        if not repeated:
            _grow(graph, branch, child, drawn, ancestors | {node.id})


def _render_unplaced(console: Console, graph: Graph, drawn: set[str]) -> None:
    """Goals the walk never reached, listed rather than quietly left out."""
    unplaced = [node for node in graph if node.id not in drawn]
    if not unplaced:
        return
    console.print(Text("Not reachable from any top-level objective", style="bold yellow"))
    labels = [_label(graph, node, repeated=False) for node in unplaced]
    console.print(Padding(Text("\n").join(labels), (0, 0, 1, 2)))


def _render_connections(console: Console, graph: Graph) -> None:
    """Every connection somebody wrote by hand, with the line it is written on.

    Containment edges are left out: nobody wrote them, there is no line to point at, and
    the tree above already shows them. What is left is the network — the cross-team
    contributions and dependencies that no single file makes visible.
    """
    written = [edge for edge in graph.edges if not edge.implicit]
    if not written:
        console.print(Text("No connections between files — every goal stands alone.", style="dim"))
        console.print()
        return

    table = Table(box=None, show_header=False, padding=(0, 2, 0, 0), pad_edge=False)
    table.add_column("from", no_wrap=True)
    table.add_column("relation", style="dim", no_wrap=True)
    table.add_column("to", no_wrap=True)
    table.add_column("where", style="dim", overflow="fold")
    for edge in sorted(written, key=_connection_order):
        table.add_row(
            Text(edge.source_id),
            _RELATIONS[edge.kind],
            _target(graph, edge),
            str(edge.source),
        )
    console.print(Text("Connections written by hand", style="bold"))
    console.print(Padding(table, (0, 0, 1, 2)))


def _connection_order(edge: Edge) -> tuple[str, int, str]:
    """Grouped by the goal that declared them, since that is the file they live in."""
    return (edge.source_id, 0 if edge.kind is EdgeKind.SUPPORTS else 1, edge.target_id)


def _target(graph: Graph, edge: Edge) -> Text:
    """The other end of a connection, marked when nothing declares it.

    Marked rather than hidden or fixed: this command prints what is written. The full
    explanation, and the failure, belong to `okr validate`.
    """
    if edge.target_id in graph.nodes:
        return Text(edge.target_id)
    return Text.assemble((edge.target_id, "red"), (" (no such goal)", "red dim"))


# --- Labels ------------------------------------------------------------------------------


def _label(graph: Graph, node: Node, *, repeated: bool) -> Text:
    """One node on one line: what it is, what it says, and how it is qualified."""
    label = Text.assemble(
        (f"{_GLYPHS[node.kind]} ", _KIND_STYLES[node.kind]),
        (node.id, _KIND_STYLES[node.kind]),
        ("  ", ""),
        (node.spec.statement, ""),
    )
    if repeated:
        label.append("  (shown above)", style="dim")
        return label
    label.append(f"  {_qualifiers(graph, node)}", style="dim")
    return label


def _qualifiers(graph: Graph, node: Node) -> str:
    """The dim tail: who owns it, whether it is a must-hit, and what it moves.

    An owner is printed by their display name rather than their ID. The ID is the join
    key review routing acts on; the name is what a person reads (ADR-0010).
    """
    owner = graph.owner(node.owner_id)
    parts = [owner.name if owner else f"{node.owner_id} (not declared)", _commitment(graph, node)]
    if isinstance(node.spec, KeyResult):
        parts.extend(_key_result_qualifiers(graph, node.spec))
    return f"({' · '.join(parts)})"


def _commitment(graph: Graph, node: Node) -> str:
    """Whether this is a must-hit, and whether it says so itself.

    A key result with no commitment of its own takes its objective's, so the inherited
    value is what is printed — a reader wants to know whether it is a must-hit, not
    whether the field is filled in. Where it came from is marked, because an inherited
    commitment changes when somebody edits a different goal.
    """
    if node.spec.commitment is not None:
        return node.spec.commitment.value
    parent = graph.node(node.parent_id) if node.parent_id else None
    inherited = parent.spec.commitment if parent is not None else None
    return f"{inherited.value}, inherited" if inherited is not None else "no commitment set"


def _key_result_qualifiers(graph: Graph, spec: KeyResult) -> list[str]:
    """What a key result adds: the number it moves, and what is holding it honest."""
    parts = [spec.type.value]
    if spec.metric is not None and spec.target is not None:
        metric = graph.metric(spec.metric)
        unit = f" {metric.unit}" if metric else ""
        parts.append(f"{spec.metric} → {spec.target:g}{unit}")
    if spec.guardrails:
        parts.append(_count(len(spec.guardrails), "guardrail"))
    if spec.anti_targets:
        parts.append(_count(len(spec.anti_targets), "anti-target"))
    return parts


def _count(number: int, noun: str) -> str:
    return f"{number} {noun}" if number == 1 else f"{number} {noun}s"


def _summary(graph: Graph) -> str:
    written = sum(1 for edge in graph.edges if not edge.implicit)
    return (
        f"{_count(len(graph.goal_files), 'file')} · "
        f"{_count(len(graph.objectives), 'objective')} · "
        f"{_count(len(graph.key_results), 'key result')} · "
        f"{_count(written, 'connection')} written by hand"
    )


# --- Walking -----------------------------------------------------------------------------


def _roots(graph: Graph) -> list[Node]:
    """The goals nothing above them was declared for: the top of each ladder.

    A connection that points at a goal nobody declares does not make its source a root —
    it is a broken connection, and treating it as a top-level goal would draw a picture
    that quietly disagrees with what `okr validate` says about the same repo.
    """
    return [
        node
        for node in graph
        if not any(
            edge.target_id in graph.nodes for edge in graph.outgoing(node.id, EdgeKind.SUPPORTS)
        )
    ]


def _children(graph: Graph, node_id: str) -> list[Node]:
    """Everything that contributes to this goal, in the order it is written in the files.

    Found by looking across the whole graph, because a supporting edge is declared on the
    needy side and never on the parent — which is exactly why this view is worth printing.
    Deduplicated: a key result that both sits inside an objective and names it under
    `supports` has two edges and is one child, and saying so twice is `okr validate`'s job.
    """
    order = _file_order(graph)
    children = {edge.source_id for edge in graph.incoming(node_id, EdgeKind.SUPPORTS)}
    return [graph.nodes[child] for child in sorted(children, key=lambda c: order[c])]


def _file_order(graph: Graph) -> dict[str, int]:
    """Where each goal sits in load order, which is file order — how an author reads them."""
    return {node_id: position for position, node_id in enumerate(graph.nodes)}


# --- For a machine ------------------------------------------------------------------------


def payload(graph: Graph) -> dict[str, Any]:
    """The resolved graph as nodes and edges, for something that is not a person.

    Flat, not nested: the goal topology is a graph and a nested document would have to
    pick one parent per key result, which is the assumption ADR-0006 exists to refuse.
    """
    return {
        "repo": {
            "root": str(graph.root),
            "name": graph.root.name,
            "period": graph.marker.period,
            "schema_version": graph.marker.schema_version,
        },
        "counts": {
            "files": len(graph.goal_files),
            "objectives": len(graph.objectives),
            "key_results": len(graph.key_results),
            "edges": len(graph.edges),
        },
        "nodes": [_node_json(graph, node) for node in graph],
        "edges": [_edge_json(edge) for edge in graph.edges],
    }


def _node_json(graph: Graph, node: Node) -> dict[str, Any]:
    owner = graph.owner(node.owner_id)
    entry: dict[str, Any] = {
        "id": node.id,
        "kind": node.kind.value,
        "statement": node.spec.statement,
        "owner": node.owner_id,
        "owner_name": owner.name if owner else None,
        "commitment": node.spec.commitment.value if node.spec.commitment else None,
        "parent": node.parent_id,
        "file": str(node.source.file),
        "line": node.source.line,
    }
    if isinstance(node.spec, KeyResult):
        entry |= {
            "type": node.spec.type.value,
            "metric": node.spec.metric,
            "target": node.spec.target,
            "guardrails": [g.metric for g in node.spec.guardrails],
            "anti_targets": len(node.spec.anti_targets),
        }
    return entry


def _edge_json(edge: Edge) -> dict[str, Any]:
    return {
        "kind": edge.kind.value,
        "from": edge.source_id,
        "to": edge.target_id,
        "implicit": edge.implicit,
        "origin": edge.origin.value if edge.origin else None,
        "file": str(edge.source.file),
        "line": edge.source.line,
    }
