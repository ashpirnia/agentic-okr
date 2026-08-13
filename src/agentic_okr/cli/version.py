"""What `okr --version` prints.

One pasteable line, because the moment it exists to serve is somebody reporting that the
tool did something odd. A bare version number is not enough to act on that: the recommended
install is `git+https://github.com/…`, so two people on `0.1.0` can be on different commits
weeks apart, and the Python they are running is the other thing that turns out to matter.

The commit is not guesswork. A VCS install records it in `direct_url.json` — PEP 610 — and
both `uv tool install` and `pipx install` write one. An install from a wheel or an index has
no such file and simply says less, which is correct rather than a fallback: there is no
commit to name.

Nothing here reads the repo the tool was built from. It reports the *installed*
distribution, which is the thing whose behaviour is being asked about.
"""

import platform
import sys
from importlib.metadata import PackageNotFoundError, distribution
from json import JSONDecodeError, loads
from typing import Any

#: The installed distribution's name, which is not the command's name.
DISTRIBUTION = "agentic-okr"

#: How much of a commit hash to print. Enough to find it, short enough to read out.
COMMIT_LENGTH = 7


def describe() -> str:
    """The version line: what is installed, where it came from, and what is running it."""
    parts = [f"okr {_version()}", *_origin(), f"Python {platform.python_version()}"]
    return " · ".join(parts)


def _version() -> str:
    try:
        return distribution(DISTRIBUTION).version
    except PackageNotFoundError:
        # Running from a source tree that was never installed. Rare, and not worth a
        # crash in the command somebody runs precisely because something is already wrong.
        return "unknown version"


def _origin() -> list[str]:
    """Where this copy came from, when the install recorded it.

    Three cases worth telling apart in a bug report: a commit somebody can check out, a
    working copy whose contents nobody else can reconstruct, and an ordinary install where
    the version number is the whole answer.
    """
    match _direct_url():
        case {"vcs_info": {"commit_id": str(commit)}}:
            return [f"commit {commit[:COMMIT_LENGTH]}"]
        case {"dir_info": {"editable": True}}:
            return ["local checkout"]
        case {"url": str()}:
            return ["installed from a local file"]
        case _:
            return []


def _direct_url() -> dict[str, Any] | None:
    """`direct_url.json` from the installed distribution, if it has one."""
    try:
        recorded = distribution(DISTRIBUTION).read_text("direct_url.json")
    except PackageNotFoundError:
        return None
    if recorded is None:
        return None
    try:
        parsed = loads(recorded)
    except JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def show(value: bool) -> None:
    """Print the version and stop, before any other argument is looked at."""
    if not value:
        return
    print(describe())
    sys.exit(0)
