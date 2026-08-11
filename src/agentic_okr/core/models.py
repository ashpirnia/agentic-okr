"""The OKR schema: the nodes, edges and files an OKR repo is made of.

This module is the published contract. Files conforming to it live in other
organisations' repositories, so a field shipped here is expensive to change and a field
omitted is cheap to add — every field below traces to an ADR in
[`docs/adr/`](../../../docs/adr/), and one that does not belongs nowhere.

**Terms are defined once, in [`docs/GLOSSARY.md`](../../../docs/GLOSSARY.md).** Field
descriptions here say what a field is *for* — what reads it, and what goes wrong without
it. They deliberately do not restate what the term means, because the Champion's prompts
explain the same vocabulary in order to elicit it, and two copies of a definition drift
apart while both halves keep looking correct.

**What these models check, and what they do not.** A model rejects only what would make
the object meaningless in memory: a required string left blank, a guardrail with no
comparison to make. Everything else — dangling references, cycles, illegal edge shapes,
and the content rules that depend on a key result's `type` — belongs to the validator,
which reports every violation it finds with a file and a location rather than stopping at
the first. Raising here would turn a full report into a single exception.

Nothing in this module holds observation. No current values, no readings, no progress:
git holds intent, and a machine writing a field on a schedule is the signal that the
field is in the wrong store (ADR-0001).
"""

from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any, Final, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_core import PydanticCustomError

from .codes import Code

#: Schema versions this release of the tool can read. Matched exactly: an OKR repo
#: declaring anything else fails to load rather than being read on a guess (ADR-0008).
SUPPORTED_SCHEMA_VERSIONS: Final = frozenset({1})

#: What a new OKR repo declares. The newest version this release understands, derived
#: rather than written down twice — a second literal is how `okr init` comes to scaffold
#: a version the loader has moved past.
CURRENT_SCHEMA_VERSION: Final = max(SUPPORTED_SCHEMA_VERSIONS)


def _reject_blank(value: str) -> str:
    """Reject a required string that is present but has nothing in it."""
    stripped = value.strip()
    if not stripped:
        raise PydanticCustomError(
            Code.FIELD_EMPTY.value,
            "This is required, and it cannot be left blank.",
        )
    return stripped


#: A required string with something in it. Surrounding whitespace is trimmed, because a
#: reference that differs from its declaration by a trailing space is a dangling
#: reference nobody can see in a pull request.
Text = Annotated[str, AfterValidator(_reject_blank)]


class Base(BaseModel):
    """Shared configuration for every model in the schema.

    `extra="forbid"` is the load-bearing setting. A misspelled `anti_target:` or
    `guardrail:` would otherwise be silently ignored, leaving a spec that looks complete
    in review and asserts nothing at all.
    """

    model_config = ConfigDict(extra="forbid")


class Commitment(StrEnum):
    """Whether a goal is a must-hit or a stretch. See the glossary.

    Read by the completeness score, which holds a committed goal to a higher bar: a
    committed key result without guardrails is more dangerous than an aspirational one,
    because a committed goal is where the pressure to hit the number at any cost is
    highest (ADR-0005 Amendment 2).
    """

    COMMITTED = "committed"
    ASPIRATIONAL = "aspirational"


class KeyResultType(StrEnum):
    """Whether a key result is something you ship or a number you move. See the glossary.

    Declared rather than inferred from whether a metric is present, so that a deliberate
    milestone and a metric key result whose author never named the metric are
    distinguishable. Each type is then scored against its own requirements
    (ADR-0005 Amendment 1).
    """

    MILESTONE = "milestone"
    METRIC = "metric"


class EdgeOrigin(StrEnum):
    """How a `supports` edge came about. See the glossary for cascading and laddering.

    Provenance, not relationship: both produce the same edge. Nothing in v1 reads this.
    It exists so the cascade/ladder balance stays computable later without a migration,
    since deep top-down cascading is the failure mode worth being able to measure
    (ADR-0006).
    """

    CASCADED = "cascaded"
    LADDERED = "laddered"


class AntiTargetOrigin(StrEnum):
    """Who put an anti-target on the record.

    `proposed` means the Champion suggested it and a human confirmed it — never
    generated and written unattended. The distinction is what lets a reader see which
    lines facilitation actually surfaced, rather than taking the claim on trust
    (ADR-0009).
    """

    AUTHORED = "authored"
    PROPOSED = "proposed"


class SupportsEdge(Base):
    """A child contributing to a parent — the hierarchy edge. See the glossary.

    Always declared on the child, never on the parent. That direction is a concurrency
    decision as much as a modelling one: under the opposite convention every team
    laddering upward would edit leadership's file, making the organisation's most
    important document its most contended one (ADR-0006).

    Accepts either a bare target ID or a mapping, and normalises to the mapping form.
    """

    target: Text = Field(
        description=(
            "The ID of the objective or key result being contributed to. Must resolve; "
            "an unresolvable target is a dangling reference, which is the failure this "
            "project exists to prevent."
        )
    )
    origin: EdgeOrigin | None = Field(
        default=None,
        description=(
            "Optionally, how this connection came about. Unread in v1 — recorded so the "
            "balance of top-down against bottom-up goal setting can be measured later."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _accept_bare_id(cls, data: Any) -> Any:
        """Normalise the authoring shorthand `supports: [company.retention]`."""
        return {"target": data} if isinstance(data, str) else data


class DependencyEdge(Base):
    """A key result that cannot complete until another one does. See the glossary.

    Declared by the blocked key result, because the awareness starts with whoever is
    blocked. There is no acknowledgement field: the provider's commitment is their
    review and merge of the pull request, and a field could assert an agreement no human
    ever gave (ADR-0006).

    Accepts either a bare target ID or a mapping, and normalises to the mapping form.
    """

    target: Text = Field(
        description=(
            "The ID of the key result that must land first. Crossing a team boundary "
            "here is what routes the other team into the review."
        )
    )

    @model_validator(mode="before")
    @classmethod
    def _accept_bare_id(cls, data: Any) -> Any:
        """Normalise the authoring shorthand `depends_on: [platform.api-v2]`."""
        return {"target": data} if isinstance(data, str) else data


class Owner(Base):
    """Someone accountable for a goal, declared once and referenced by ID. See the glossary."""

    id: Text = Field(
        description=(
            "The stable ID every `owner` field refers to. Names the role rather than the "
            "person in it, so it survives someone changing jobs. Declared rather than "
            "free text because review routing compares owners for equality — otherwise "
            "two spellings become two people and a cross-team review reaches neither."
        )
    )
    name: Text = Field(
        description=(
            "How this owner is written in output a human reads: 'needs review from: "
            "Head of Platform' rather than 'head-of-platform'."
        )
    )
    handles: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Optionally, this owner's name in other systems, keyed by platform — "
            '`github: "@acme/platform"`. Used to generate CODEOWNERS so that file '
            "stops being a hand-maintained second copy of who owns what. Unknown keys "
            "are ignored; nothing here is resolved or verified."
        ),
    )


class Metric(Base):
    """A named, defined quantity the organisation measures. See the glossary."""

    id: Text = Field(
        description=(
            "The stable ID a key result targets and a guardrail watches. This is the "
            "join key between what was meant, where the number is read from, and what "
            "was recorded — so the measurement window belongs inside it: "
            "`reopen_rate_7d` and `reopen_rate_30d` are two metrics, not one metric "
            "read two ways."
        )
    )
    definition: Text = Field(
        description=(
            "What is actually counted, in a sentence a reviewer can check a threshold "
            "against. Not where the number comes from — that is measurement "
            "configuration and lives outside your OKR repo."
        )
    )
    unit: Text = Field(
        description=(
            "What the numbers are in: `ratio`, `hours`, `rating_1_5`. Free text, since "
            "organisations measure in things no fixed list would contain. Nothing reads "
            "it; it exists so `must_not_exceed: 0.08` can be understood as 8% by "
            "whoever is approving the change."
        )
    )


class Guardrail(Base):
    """A metric that must hold while a key result moves. See the glossary.

    Embedded in the key result that sets it rather than shared, because the same metric
    legitimately guards several key results at different thresholds. The comparison is
    written out here rather than derived from a direction stored on the metric, so the
    line reads correctly in a pull request without opening a second file (ADR-0009).
    """

    metric: Text = Field(
        description="The ID of the metric being protected. Must resolve to a declared metric."
    )
    must_not_exceed: float | None = Field(
        default=None,
        description="A ceiling: the value may go no higher than this while the key result moves.",
    )
    must_not_fall_below: float | None = Field(
        default=None,
        description="A floor: the value may go no lower than this while the key result moves.",
    )

    @model_validator(mode="after")
    def _exactly_one_comparison(self) -> Self:
        """A guardrail with no comparison, or with both, states nothing checkable."""
        given = (self.must_not_exceed is not None, self.must_not_fall_below is not None)
        if not any(given):
            raise PydanticCustomError(
                Code.GUARDRAIL_COMPARISON.value,
                "A guardrail needs a limit: give either 'must_not_exceed' or "
                "'must_not_fall_below'.",
            )
        if all(given):
            raise PydanticCustomError(
                Code.GUARDRAIL_COMPARISON.value,
                "A guardrail sets one limit, not two. Give either 'must_not_exceed' or "
                "'must_not_fall_below'. Protecting a range means two guardrails.",
            )
        return self


class AntiTarget(Base):
    """A move that would hit the number while betraying its spirit. See the glossary.

    Carries up to two defences, which fail differently and are therefore both worth
    having: a `restraint` is a rule checked against an agent's configuration before
    anything runs, and `watched_by` names metrics that would catch the move while it
    happens. An anti-target with neither is named and wholly undefended — the sharpest
    single check the completeness score makes (ADR-0009 Amendment 1).
    """

    description: Text = Field(
        description=(
            "The move itself, in one sentence: 'mass-close tickets with a canned reply "
            "and let the customer chase you'. What someone would do, not what they are "
            "forbidden from doing."
        )
    )
    origin: AntiTargetOrigin = Field(
        description=(
            "Whether the goal owner wrote this down or the Champion proposed it and a "
            "human confirmed it. This is what shows which risks facilitation surfaced."
        )
    )
    restraint: Text | None = Field(
        default=None,
        description=(
            "Optionally, the rule that forbids the move, stated outright. The static "
            "defence: it is what an agent's configuration is later checked against, "
            "before that agent processes anything."
        ),
    )
    watched_by: list[Text] = Field(
        default_factory=list,
        description=(
            "Optionally, the IDs of metrics that would reveal the move happening. The "
            "dynamic defence. Each must be guarded on this key result — a metric named "
            "here but not guarded is a false sense of coverage, which is worse than an "
            "honest gap."
        ),
    )


class KeyResult(Base):
    """The measurable signal that an objective is being achieved. See the glossary.

    A first-class node: it is the level agents are wired to, so it needs an identity
    something outside this file can reference. What it does *not* carry is any record of
    where it has got to — progress is observation, and a `current_value` field is how an
    OKR repo's commit log gets buried inside a quarter (ADR-0001).
    """

    id: Text = Field(
        description=(
            "The stable ID other files reference. Author-chosen and namespaced by team "
            "— `support.resolution-time` — never by parent objective, since a key "
            "result may support several. Rewording the statement leaves it untouched."
        )
    )
    statement: Text = Field(
        description="What the key result asserts, as a goal owner would say it out loud."
    )
    type: KeyResultType = Field(
        description=(
            "Whether this is something you ship or a number you move. Each kind is "
            "legitimate and each is scored against its own requirements, so a milestone "
            "is never penalised for having no metric."
        )
    )
    owner: Text = Field(
        description=(
            "The ID of whoever does the work and is accountable for the measurable. "
            "Required: this is the join key review routing acts on, and it is what "
            "makes a co-owned objective expressible without a multi-owner field."
        )
    )
    commitment: Commitment | None = Field(
        default=None,
        description=(
            "Optionally, whether this particular key result is a must-hit or a stretch. "
            "When absent it inherits the objective's; when present it overrides, because "
            "a stretch objective can genuinely carry one must-hit key result beneath it."
        ),
    )
    metric: Text | None = Field(
        default=None,
        description=(
            "The ID of the metric this key result moves. Required for a metric key "
            "result and not allowed on a milestone, which has nothing to move."
        ),
    )
    target: float | None = Field(
        default=None,
        description=(
            "The value the metric should reach, in the metric's own unit. Required for "
            "a metric key result and not allowed on a milestone."
        ),
    )
    success_criteria: list[Text] = Field(
        default_factory=list,
        description=(
            "What 'done' means to a reader with no judgment — the interpretation a "
            "human would have supplied silently. A milestone key result needs these: "
            "with no metric and no target, they are the only checkable thing it has."
        ),
    )
    guardrails: list[Guardrail] = Field(
        default_factory=list,
        description=(
            "The metrics that must hold while this one moves. What stops the headline "
            "number being bought at a cost nobody agreed to."
        ),
    )
    anti_targets: list[AntiTarget] = Field(
        default_factory=list,
        description=(
            "The ways this key result could be hit while its spirit is betrayed, named "
            "in advance so the restraint a human would have exercised is written down."
        ),
    )
    supports: list[SupportsEdge] = Field(
        default_factory=list,
        description=(
            "Additional parent objectives this contributes to, beyond the objective it "
            "is written inside. Listing the containing objective here is an error, not "
            "a harmless repetition: two representations of one relationship are how "
            "they come to disagree. Supporting another key result is never right — that "
            "relationship is 'depends_on'."
        ),
    )
    depends_on: list[DependencyEdge] = Field(
        default_factory=list,
        description=(
            "Key results that must land before this one can. Declared here by the "
            "blocked team, which is where the awareness starts; the other team's "
            "agreement is their review of the change."
        ),
    )


class Objective(Base):
    """The qualitative thing a team wants to achieve. See the glossary."""

    id: Text = Field(
        description=(
            "The stable ID other files reference. Author-chosen, namespaced by team, "
            "and decoupled from the statement so rewording costs nothing."
        )
    )
    statement: Text = Field(
        description=(
            "The objective itself — directional and not measurable. What makes it "
            "measurable are the key results beneath it."
        )
    )
    owner: Text = Field(
        description=(
            "The ID of the executive sponsor: who holds the vision, and who breaks ties "
            "when key result owners disagree about scope. Required, because a co-owned "
            "objective spreads work across teams whose priorities will diverge, and one "
            "with no sponsor has no resolution path when they do."
        )
    )
    commitment: Commitment = Field(
        description=(
            "Whether this is a must-hit or a stretch. Required, and inherited by every "
            "key result that does not override it — there is no unset case to interpret."
        )
    )
    supports: list[SupportsEdge] = Field(
        default_factory=list,
        description=(
            "The parent objectives or key results this contributes to, whether it was "
            "handed down or connected upward by the team itself. Empty means this is a "
            "top-level objective."
        ),
    )
    key_results: list[KeyResult] = Field(
        default_factory=list,
        description=(
            "The key results written inside this objective. Containment is itself the "
            "primary supports edge — nobody writes that edge, and it is not restated."
        ),
    )


class RepoMarker(Base):
    """`okr.yaml`: the file that says 'this directory is an OKR repo, and here is how to read it'.

    Found by walking up from the path given, as git does with `.git`. Its existence is
    what stops a subdirectory being validated as though it were the whole graph — which
    reports dangling references that are not real, or silently passes a fragment
    (ADR-0008).

    Four fields and two path overrides, and nothing else. This file will attract every
    global-looking setting anyone proposes; each is refused until something reads it.
    """

    schema_version: int = Field(
        description=(
            "Which version of the OKR schema this repo is written against. Declared once "
            "per repo, so a half-migrated repo is not representable. Matched exactly — "
            "a tool that cannot read this repo stops and says so rather than guessing."
        )
    )
    period: Text = Field(
        description=(
            "The cycle this repo covers — `2026-Q3`, `2026-H1`, `2026-07`. One repo "
            "holds one live cycle, so this time-bounds every key result in it without a "
            "deadline on each one. Nothing parses it: organisations run halves, "
            "trimesters and fiscal years, and it labels the repo for a human reader."
        )
    )
    okr_dir: Path = Field(
        description=(
            "Where the goal files live, relative to this file. Every YAML file beneath "
            "it is loaded — file organisation is convention, not something the tool "
            "enforces, so an organisation can restructure freely."
        )
    )
    metrics_file: Path = Field(
        default=Path("metrics.yaml"),
        description=(
            "Where the shared metric vocabulary lives. One place to read what the "
            "organisation measures, so adding a metric is a reviewable change to that "
            "vocabulary rather than a line buried in one team's file."
        ),
    )
    owners_file: Path = Field(
        default=Path("owners.yaml"),
        description="Where owners are declared. Every `owner` field must resolve to one of them.",
    )

    @field_validator("schema_version")
    @classmethod
    def _supported(cls, value: int) -> int:
        """Refuse a repo written against a schema this release cannot read."""
        if value not in SUPPORTED_SCHEMA_VERSIONS:
            supported = ", ".join(str(v) for v in sorted(SUPPORTED_SCHEMA_VERSIONS))
            raise PydanticCustomError(
                Code.SCHEMA_VERSION_UNSUPPORTED.value,
                "This repo declares schema version {found}, and this version of the tool "
                "reads {supported}. Upgrade the tool, or check the version in okr.yaml.",
                {"found": value, "supported": supported},
            )
        return value


class GoalFile(Base):
    """One file under `okr_dir`, by convention one team's goals for the cycle.

    A team's set is reviewed as a unit, because the properties worth checking — the mix
    of committed and aspirational, of milestone and metric — are only visible together
    (ADR-0007).
    """

    objectives: list[Objective] = Field(
        default_factory=list, description="The objectives declared in this file."
    )


class MetricsFile(Base):
    """`metrics.yaml`: the organisation's shared metric vocabulary.

    Not a dump of every KPI tracked. A metric belongs in an OKR repo when a key result
    targets it or a guardrail watches it, and not otherwise (ADR-0005 Amendment 1).
    """

    metrics: list[Metric] = Field(
        default_factory=list, description="Every metric this repo's goals may refer to."
    )


class OwnersFile(Base):
    """`owners.yaml`: who exists.

    Declared, so that a misspelled owner is a dangling reference rather than a silently
    invented second person that review routing then reaches neither of (ADR-0010).
    """

    owners: list[Owner] = Field(
        default_factory=list, description="Every owner this repo's goals may refer to."
    )
