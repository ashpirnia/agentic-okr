"""`okr --version` tests.

The line exists so that a bug report identifies the copy of the tool that produced it.
During an early-testing round the recommended install is `git+https://github.com/…`, so
"0.1.0" on its own is not an answer — two testers on that version can be a fortnight of
commits apart. What is asserted here is that each kind of install says the thing that
distinguishes it.

The install metadata is faked rather than produced. Genuinely covering the VCS branch would
mean installing from GitHub inside a test: slow, networked, and it would assert that `uv`
writes `direct_url.json` correctly, which is not ours to check. What is ours is reading it.
"""

from typing import Any

import pytest
from typer.testing import CliRunner

from agentic_okr.cli import app, version

runner = CliRunner()

#: What `uv tool install git+...` and `pipx install git+...` record. The shape is PEP 610.
FROM_GIT: dict[str, Any] = {
    "url": "https://github.com/ashpirnia/agentic-okr",
    "vcs_info": {"vcs": "git", "commit_id": "f2392116ef16857420bbcb0793432ca996ad88ac"},
}

#: What an editable install of a working copy records — `uv sync`, and every dev machine.
FROM_CHECKOUT: dict[str, Any] = {
    "url": "file:///Users/someone/code/agentic-okr",
    "dir_info": {"editable": True},
}

#: What installing a downloaded wheel records.
FROM_FILE: dict[str, Any] = {"url": "file:///tmp/agentic_okr-0.1.0-py3-none-any.whl"}


@pytest.fixture
def installed(monkeypatch: pytest.MonkeyPatch):
    """Pretend the tool was installed in a particular way."""

    def install(direct_url: dict[str, Any] | None) -> None:
        monkeypatch.setattr(version, "_direct_url", lambda: direct_url)

    return install


def test_a_git_install_names_the_commit(installed) -> None:
    """The case the line exists for: two testers on one version, different commits."""
    installed(FROM_GIT)

    assert "commit f239211" in version.describe()


def test_the_commit_is_short_enough_to_read_out(installed) -> None:
    installed(FROM_GIT)

    assert FROM_GIT["vcs_info"]["commit_id"] not in version.describe()


def test_a_working_copy_says_so(installed) -> None:
    """Nobody else can reconstruct it, and a report from one is worth less. Say it."""
    installed(FROM_CHECKOUT)

    assert "local checkout" in version.describe()


def test_an_installed_file_says_so(installed) -> None:
    installed(FROM_FILE)

    assert "installed from a local file" in version.describe()


def test_an_ordinary_install_claims_no_origin(installed) -> None:
    """An install from an index has no commit to name, so it names none."""
    installed(None)

    described = version.describe()

    assert "commit" not in described
    assert "checkout" not in described


@pytest.mark.parametrize("direct_url", [FROM_GIT, FROM_CHECKOUT, FROM_FILE, None], ids=str)
def test_the_version_and_the_python_are_always_there(direct_url, installed) -> None:
    """Whatever the install, the two things every bug report needs are present."""
    import platform

    installed(direct_url)

    described = version.describe()

    assert described.startswith("okr ")
    assert f"Python {platform.python_version()}" in described


def test_it_is_one_line_so_it_can_be_pasted(installed) -> None:
    installed(FROM_GIT)

    assert "\n" not in version.describe()


# --- Through the command ------------------------------------------------------------------


def test_the_flag_prints_the_line_and_exits_zero() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.output.strip() == version.describe()


def test_the_flag_needs_no_command_after_it() -> None:
    """It is eager, so it answers before Typer objects that no command was named."""
    assert runner.invoke(app, ["--version"]).exit_code == 0


def test_the_flag_needs_no_okr_repo(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Somebody reporting a bug may be standing anywhere, including nowhere useful."""
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(app, ["--version"]).exit_code == 0


def test_the_commands_still_work_with_a_callback_in_front_of_them(tmp_path) -> None:
    """Adding the callback is where a Typer app usually stops routing subcommands."""
    result = runner.invoke(app, ["init", str(tmp_path), "--period", "2026-Q3"])

    assert result.exit_code == 0
