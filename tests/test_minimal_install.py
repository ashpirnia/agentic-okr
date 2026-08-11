"""The minimal install stays minimal.

`core` is a library with no LLM dependency: the schema, loader, graph and validator must
install and run without an API key or an Anthropic account, because the Conductor's
wiring lint will later sit on the same loader. Agent dependencies live in the optional
`agent` extra, and the dependency runs one way only — `core` never imports `champion`.

`CLAUDE.md` claimed a test enforced that. None did. It is enforced here.

**Why this is a static check rather than an import.** `import agentic_okr.core` succeeds
whether or not `langgraph` is installed, so in any environment that has the extra — the
main CI job, and most development machines — an import test proves nothing. Reading the
source proves it everywhere. CI runs the import as well, in a job that installs without
extras, which is the other half of the guard.

The rule this protects is easy to break by accident and expensive to notice: a
convenience import at the top of a module is invisible until someone installs without the
extra and the tool will not start.
"""

import ast
import re
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
PACKAGE_ROOT = REPO_ROOT / "src" / "agentic_okr"

#: Distributions the agent extra pulls in transitively. They are not named in
#: `pyproject.toml`, so they cannot be derived, but importing one from `core` breaks the
#: minimal install just as surely as importing `langgraph` does.
TRANSITIVE_AGENT_DEPENDENCIES = frozenset({"anthropic", "langsmith"})


def _distribution_prefix(requirement: str) -> str:
    """The importable name a requirement string is likely to occupy.

    `langgraph-checkpoint-sqlite>=2.0` installs into `langgraph.checkpoint.sqlite`, and
    `langchain-anthropic` into `langchain_anthropic`. Matching on the first segment
    catches both, and catches a sibling package added to the extra later.
    """
    name = re.split(r"[<>=!~\[; ]", requirement, maxsplit=1)[0]
    return name.replace("_", "-").split("-")[0]


def agent_extra_prefixes() -> frozenset[str]:
    """Every import prefix that belongs to the optional `agent` extra."""
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    declared = pyproject["project"]["optional-dependencies"]["agent"]
    return frozenset({_distribution_prefix(r) for r in declared} | TRANSITIVE_AGENT_DEPENDENCIES)


def modules_outside_champion() -> list[Path]:
    """Every module that must import cleanly on a minimal install.

    That is the whole package except `champion/`: the schema, the loader and the CLI all
    have to work for someone who never installed the extra.
    """
    return sorted(p for p in PACKAGE_ROOT.rglob("*.py") if "champion" not in p.parts)


def containing_package(module: Path) -> str:
    """The dotted package a file lives in — the same for `core/models.py` and `core/__init__.py`."""
    return ".".join(module.parent.relative_to(PACKAGE_ROOT.parent).parts)


def module_level_imports(module: Path) -> list[str]:
    """The absolute names a module imports when it is loaded.

    Imports inside a function body are skipped deliberately. Deferring an optional
    dependency into the function that needs it is the supported way to reach the Champion
    from shared code — the rule is about what happens at import time.
    """
    package = containing_package(module)
    imported: list[str] = []
    stack = list(ast.parse(module.read_text()).body)
    while stack:
        node = stack.pop()
        match node:
            case ast.FunctionDef() | ast.AsyncFunctionDef():
                continue
            case ast.Import(names=names):
                imported.extend(alias.name for alias in names)
            case ast.ImportFrom(module=name, level=level):
                base = package.rsplit(".", level - 1)[0] if level else ""
                imported.append(".".join(part for part in (base, name) if part))
            case _:
                stack.extend(ast.iter_child_nodes(node))
    return imported


@pytest.mark.parametrize(
    "module", modules_outside_champion(), ids=lambda p: str(p.relative_to(PACKAGE_ROOT))
)
def test_nothing_outside_champion_imports_an_agent_dependency(module: Path) -> None:
    forbidden = agent_extra_prefixes()

    offenders = [
        name
        for name in module_level_imports(module)
        if name.split(".")[0].split("_")[0] in forbidden
    ]

    assert not offenders, (
        f"{module.relative_to(REPO_ROOT)} imports {offenders} at module level. These come "
        "from the optional 'agent' extra, so this breaks the minimal install. Move the "
        "import inside the function that needs it, or move the code into champion/."
    )


@pytest.mark.parametrize(
    "module", modules_outside_champion(), ids=lambda p: str(p.relative_to(PACKAGE_ROOT))
)
def test_core_never_imports_champion(module: Path) -> None:
    offenders = [
        name for name in module_level_imports(module) if name.startswith("agentic_okr.champion")
    ]

    assert not offenders, (
        f"{module.relative_to(REPO_ROOT)} imports {offenders} at module level. The "
        "dependency runs one way only: champion/ depends on core, never the reverse."
    )


def test_the_schema_loads_in_whatever_environment_this_is() -> None:
    """Cheap on a full install; the actual check in the CI job that installs no extras."""
    import agentic_okr.core  # noqa: F401
