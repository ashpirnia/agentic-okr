"""OKRs as code: a machine-readable goal spec, and the agents pointed at it.

`agentic_okr.core` is the schema, loader, graph and validator — a library with no LLM
dependency. `agentic_okr.cli` is the `okr` command, one consumer of that library.
`agentic_okr.champion` is the facilitation agent, and needs the optional `agent` extra.

Nothing is imported here. Importing the CLI from the package root would pull a terminal
renderer into every program that only wanted to read a graph.
"""
