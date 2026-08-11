# Example OKR repos

Each directory here is a whole OKR repo, shaped exactly as one an organisation would own —
marker file and all. They are what an adopter reads to find out what a repo looks like, and
they are used as fixtures, so a change that breaks the shape breaks a test.

Nothing here is part of the tool. `src/agentic_okr/` is the tool; these are examples of the
thing it reads. See [ADR-0002](../docs/adr/0002-two-repos.md) for why that distinction is
worth keeping sharp.

| | |
| :--- | :--- |
| [`scaffold/`](scaffold/) | Exactly what `okr init` writes, for period `2026-Q3`. Generated, not hand-written — `tests/test_scaffold.py` fails if it stops matching the command's output byte for byte, so the two cannot teach different shapes. |

To see a repo with goals in it, read
[`docs/GRAPH-BY-EXAMPLE.md`](../docs/GRAPH-BY-EXAMPLE.md), which walks a three-team
organisation and the YAML behind it.
