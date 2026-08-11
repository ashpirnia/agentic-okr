"""What a failed load or a failed validation reports, and how it is carried.

One shape for every problem the tool can find, whether the loader found it while reading
a file or the validator found it while walking the finished graph. A violation carries a
stable code from [`docs/ERROR_CODES.md`](../../../docs/ERROR_CODES.md), a sentence written
for the goal owner reading a pull request, and wherever possible the file and line the
problem is on.

Nothing here formats for a terminal. Rendering belongs to the CLI, so that the Conductor's
lint — which will consume the same violations without a terminal in sight — is not reading
around colour codes to find out what went wrong.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .codes import Code, Severity


@dataclass(frozen=True, slots=True)
class Violation:
    """One problem, with its code, its sentence and where to find it.

    The file path is relative to the OKR repo root, because that is how it appears in a
    pull request and how a goal owner will look for it.
    """

    code: Code
    message: str
    file: Path | None = None
    line: int | None = None

    @property
    def severity(self) -> Severity:
        """Whether this fails the run. Read from the code, never set by the caller."""
        return self.code.severity

    @property
    def location(self) -> str:
        """Where to look, as `okrs/support/2026-q3.yaml:12`. Empty when nothing is known."""
        if self.file is None:
            return ""
        return f"{self.file}:{self.line}" if self.line is not None else str(self.file)

    def __str__(self) -> str:
        where = f"{self.location}: " if self.location else ""
        return f"{where}{self.code.value}: {self.message}"


def sort_violations(violations: Iterable[Violation]) -> list[Violation]:
    """Order a report by file, then line, then code — with unlocated problems first.

    A goal owner fixes a file top to bottom, so a report that reads in that order costs
    them less than one in discovery order. It also makes the output reproducible, which
    is what lets tests compare against golden files.

    Problems with no location are repo-wide, so they lead: a missing `okr.yaml` or an
    unreadable schema version is the reason everything else is wrong.
    """
    return sorted(
        violations,
        key=lambda v: (v.file is not None, str(v.file or ""), v.line or 0, v.code.value),
    )


class LoadError(Exception):
    """The graph could not be built, and here is everything wrong with it.

    Raised rather than returned because there is no partial graph to hand back: an OKR
    repo that half-loads is exactly what [ADR-0008](../../../docs/adr/0008-okr-yaml-marker.md)
    exists to prevent, since a fragment produces dangling references that are not real
    and a reviewer list that silently omits a team.

    It carries *every* problem found, not the first. A support lead fixing their file
    wants the whole list — a loader that stopped at the first unparseable line would turn
    one review cycle into five.
    """

    def __init__(self, violations: Iterable[Violation]) -> None:
        self.violations: tuple[Violation, ...] = tuple(sort_violations(violations))
        super().__init__(self._summary())

    def _summary(self) -> str:
        count = len(self.violations)
        problems = "problem" if count == 1 else "problems"
        lines = [f"Your OKR repo could not be read — {count} {problems} found:"]
        lines.extend(f"  {violation}" for violation in self.violations)
        return "\n".join(lines)
