"""Validated domain values for the agent-teams board.

Role and Status are the two orthogonal axes of a Card's routing state. Status
answers where the Card sits in its lifecycle; Role answers whose turn it is.
Changing one never implicitly changes the other -- see ARCHITECTURE.md 9.2.

Both are string enums so they survive ``json.dumps`` unchanged and keep the
CLI's existing JSON envelopes byte-compatible.
"""

from __future__ import annotations

from .errors import AgentTeamsError

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping


class DomainError(AgentTeamsError, ValueError):
    """A value that cannot be interpreted as a domain term."""


def _normalise(value: Any) -> str:
    """Casefold and collapse separators so 'In Progress' == 'in_progress'."""
    return re.sub(r"[\s_-]+", " ", str(value or "").strip()).casefold()


class _ParsedEnum(str, Enum):
    """String enum whose ``str()`` is the wire value, not ``Class.MEMBER``."""

    # Without this, f-strings render 'Role.DEV' instead of 'dev' on Python 3.11+.
    __str__ = str.__str__

    @classmethod
    def parse(cls, value: Any) -> "_ParsedEnum":
        wanted = _normalise(value)
        for member in cls:
            if _normalise(member.value) == wanted:
                return member
        raise DomainError(
            f"unknown {cls.__name__.casefold()} {value!r}; expected one of: "
            + ", ".join(member.value for member in cls)
        )

    @classmethod
    def parse_optional(cls, value: Any) -> "_ParsedEnum | None":
        """Parse, but treat an absent or unrecognised value as unset.

        Board data is untrusted input. A Card carrying a Role option somebody
        added by hand must read as 'no Role', never crash a whole briefing.
        """
        if value in (None, ""):
            return None
        try:
            return cls.parse(value)
        except DomainError:
            return None


class Role(_ParsedEnum):
    """A team seat -- the durable token stored in the Project's Role field."""

    ANALYST = "analyst"
    ARCHITECT = "architect"
    DEV = "dev"
    QA = "qa"
    LEAD = "lead"
    HUMAN = "human"

    @property
    def full_name(self) -> str:
        return _FULL_NAMES[self]


_FULL_NAMES = {
    Role.ANALYST: "System Analyst",
    Role.ARCHITECT: "System Architect",
    Role.DEV: "Developer",
    Role.QA: "Quality Assurance engineer",
    Role.LEAD: "Tech Lead",
    Role.HUMAN: "Human stakeholder / merge authority",
}


class Status(_ParsedEnum):
    """Where a Card sits in the delivery lifecycle."""

    BACKLOG = "Backlog"
    READY = "Ready"
    IN_PROGRESS = "In Progress"
    BLOCKED = "Blocked"
    IN_REVIEW = "In Review"
    DONE = "Done"


class ExecutionShape(_ParsedEnum):
    """A session's relationship to the board for one run."""

    PRODUCER = "producer"
    CONSUMER = "consumer"


ROLES: tuple[str, ...] = tuple(role.value for role in Role)
STATUSES: tuple[str, ...] = tuple(status.value for status in Status)

HANDOFF_MARKER = "<!-- agent-teams:handoff -->"
PR_MARKER = "<!-- agent-teams:pr -->"
SPECIFICATION_MARKER = "<!-- agent-teams:specification -->"
DECOMPOSITION_MARKER = "<!-- agent-teams:decomposition-complete -->"
DECOMPOSED_CHILD_MARKER = "<!-- agent-teams:decomposed-child -->"
CLARIFICATION_MARKER = "<!-- agent-teams:clarification -->"
VERDICT_MARKER = "<!-- agent-teams:verdict -->"
ACCEPTANCE_MARKER = "<!-- agent-teams:acceptance -->"
SPEC_CHANGE_MARKER = "<!-- agent-teams:spec-change-approval -->"


def _one_line(value: Any, limit: int = 500) -> str:
    """Constrain a free-text field so generated Markdown stays unambiguous.

    Handoff comments are parsed as well as read, and Issue bodies are
    untrusted input (ARCHITECTURE.md 12.1). A reason is therefore flattened to
    one line and stripped of every character that carries structure in the
    comment grammar: the bold markers that begin a field, the backticks that
    delimit a seat token, and the HTML comment fences that carry the marker.
    Without this, a reason reading "**Handoff**: `qa` -> `human`" would forge a
    second field that a parser could read in preference to the real one.
    """
    text = re.sub(r"\s+", " ", str(value or "").strip())
    text = text.replace("`", "'")
    text = text.replace("<!--", "(").replace("-->", ")")
    text = text.replace("*", r"\*")
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


@dataclass(frozen=True)
class Card:
    """The normalised join of a GitHub Issue and its Project item."""

    number: int
    repo: str
    title: str = ""
    url: str = ""
    item_id: str | None = None
    status: Status | None = None
    role: Role | None = None
    handoff_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Render the envelope the CLI has always emitted, key order included."""
        return {
            "item_id": self.item_id,
            "number": self.number,
            "repo": self.repo,
            "title": self.title,
            "url": self.url,
            "status": self.status.value if self.status else None,
            "role": self.role.value if self.role else None,
        }

    @property
    def routing_state(self) -> str:
        status = self.status.value if self.status else "-"
        role = self.role.value if self.role else "-"
        return f"({status}, {role})"


@dataclass(frozen=True)
class Handoff:
    """A structured Role change with the context the receiver needs."""

    from_role: Role
    to_role: Role
    reason: str
    needs: str = ""
    artifacts: str = ""

    def render(self) -> str:
        """Render the canonical comment shape from ARCHITECTURE.md 9.4."""
        lines = [
            HANDOFF_MARKER,
            f"**Handoff**: `{self.from_role}` -> `{self.to_role}`",
            f"**Reason**: {_one_line(self.reason) or 'No reason recorded.'}",
        ]
        needs = _one_line(self.needs)
        if needs:
            lines.append(f"**Needs from you**: {needs}")
        artifacts = _one_line(self.artifacts)
        if artifacts:
            lines.append(f"**Artifacts**: {artifacts}")
        return "\n".join(lines)


#: ARCHITECTURE.md 9.6. A pass missing any of these has not reviewed the
#: delivery, whatever its prose claims.
#: ``resource-safety`` was added 2026-09-04 after surveying Alibaba's
#: OpenCodeReview (todo 5 of the 2026-08-28 review). Its default ruleset asks
#: "are resources properly released" and "are there obvious performance
#: problems" as a first-class category; nothing in the previous eight asked
#: either. The team lead's own code-smell examples in that same review -- a
#: connection pool never released until the buffer bursts under load, private
#: state leaked out until it becomes a security hole -- landed in the gap
#: between ``correctness`` (the logic is right) and ``security`` (someone
#: attacks it), which is exactly where exhaustion and leak defects live.
REQUIRED_DIMENSIONS: tuple[str, ...] = (
    "design", "architecture", "correctness", "edge-cases",
    "security", "compatibility", "cross-file", "resource-safety",
    "test-strength",
)

#: Line coverage is execution evidence, not behavioural proof. A pass must
#: carry at least one of these stronger dimensions.
TEST_STRENGTH_DIMENSIONS: tuple[str, ...] = (
    "branch", "scenario", "mutation", "integration", "property", "negative",
)

#: What a finding costs if it ships, ordered worst first. A separate axis from
#: confidence, which says how sure the reviewer is that it is real: a
#: confidence-9 naming nit and a confidence-5 data-loss bug are not comparable
#: on one number, and ranking by confidence alone puts the nit first.
#:
#: The first two are the gate. A finding that would send the Card back to the
#: Developer is what ``fail`` means, so carrying one on a ``pass`` is a
#: contradiction rather than a strong opinion; see
#: ``policy._pass_severity_problems``.
SEVERITIES: tuple[str, ...] = ("critical", "high", "medium", "low")

#: Severities a ``pass`` may not carry.
BLOCKING_SEVERITIES: frozenset[str] = frozenset({"critical", "high"})

#: The lowest confidence a finding may be published at. Below this the skill
#: has always said it belongs in ``limitations`` -- not deleted, which is the
#: failure mode ``references/evidence-and-challenge.md`` warns about, but filed
#: where a reader can see it was considered and not acted on.
MINIMUM_FINDING_CONFIDENCE = 5

#: The closed vocabulary a ``structure``-bundle or ``resource-safety`` finding
#: names itself with. Fowler & Beck's "Bad Smells in Code" catalogue, plus the
#: operational categories from alibaba/open-code-review's default ruleset
#: (Apache-2.0); the prose, the per-dimension grouping, and the entries
#: deliberately excluded are in
#: ``skills/verifying-delivery/references/code-smells.md``, which
#: ``tests/test_findings.py`` checks against this tuple in both directions.
#:
#: Closed on purpose. A finding that says *Shotgun Surgery* can be challenged,
#: deduplicated against another reviewer's wording, and compared to the same
#: defect on the next Card. One that says "this feels wrong" can do none of
#: the three, and a name invented on the spot is worse than no name because it
#: looks shared.
#:
#: Membership is enforced; the pairing with a finding's ``dimension`` is not.
#: The grouping below records which dimension is most likely to notice a
#: smell, not the only one permitted to report it -- a ``design`` pass can
#: legitimately see Duplicated Code.
CODE_SMELLS: tuple[str, ...] = (
    # design -- this unit is the wrong size or shape
    "Mysterious Name",
    "Long Function",
    "Long Parameter List",
    "Large Class",
    "Primitive Obsession",
    "Data Clumps",
    "Temporary Field",
    "Lazy Element",
    "Speculative Generality",
    # architecture -- this belongs somewhere else
    "Feature Envy",
    "Inappropriate Intimacy",
    "Message Chains",
    "Middle Man",
    "Divergent Change",
    "Global Data",
    "Mutable Data",
    # cross-file -- the change had to be smeared
    "Shotgun Surgery",
    "Duplicated Code",
    "Repeated Switches",
    "Parallel Inheritance Hierarchies",
    # resource-safety -- it works, until volume
    "Unreleased Resource",
    "N+1",
    "Unbounded Growth",
    "Whole-payload Read",
    # test-strength -- the tests smell too
    "Assertion-free Test",
    "Mystery Guest",
    "Test Mirrors Implementation",
)


@dataclass(frozen=True)
class Verdict:
    """A Quality Assurance result: evidence, never a merge route.

    Deliberately has no acceptance field and no conversion to
    :class:`Acceptance`. The reviewer supplies evidence; deterministic policy
    chooses the route. A field here through which QA could name its own
    outcome would defeat that separation by construction.
    """

    verdict: str
    card: int
    pull_request: str = ""
    head_sha: str = ""
    design_baseline: tuple[str, ...] = ()
    review_dimensions: tuple[str, ...] = ()
    changed_files: tuple[str, ...] = ()
    design_conformance: tuple[str, ...] = ()
    test_strength: tuple[str, ...] = ()
    checks: tuple[str, ...] = ()
    findings: tuple[str, ...] = ()
    challenges: tuple[str, ...] = ()
    blind_spots: tuple[str, ...] = ()
    limitations: str = ""
    #: What was actually done in a browser: named flows, the invalid input fed
    #: to each field, and the console state after. Required of a pass whose
    #: diff touches user-facing files; see policy.validate_verdict. Structured
    #: rather than prose for the same reason as test_strength -- a sentence
    #: saying "clicked around, looked fine" cannot be checked.
    browser_evidence: Mapping[str, Any] | None = None
    #: Defects whose cause is the specification rather than the code, each one
    #: naming the document, the clause, the observed conflict, and the change
    #: suggested. Added 2026-09-04: before it, QA findings could only travel to
    #: the Developer, so a wrong specification had no route at all and was
    #: repaired by a person editing the document by hand, off the record.
    #:
    #: Advisory in the same sense as ``next_role`` -- it is evidence, not a
    #: route. What it *does* do is make ``evaluate_acceptance`` return
    #: ``protected_change``, which is the existing human lane; QA still cannot
    #: name its own outcome. Structured rather than prose for the same reason
    #: as ``test_strength``: "the spec seems wrong" cannot be acted on, and a
    #: suggestion nobody can diff is not a suggestion.
    spec_change_requests: tuple[Mapping[str, Any], ...] = ()
    next_role: Role | None = None

    VALUES = ("pass", "fail", "blocked")

    #: Every tuple-valued field, so serialisation cannot silently miss one.
    #: ``spec_change_requests`` holds objects rather than strings; it belongs
    #: here anyway, because the point of this tuple is that nothing is missed
    #: on the way to JSON.
    _SEQUENCES = (
        "design_baseline", "review_dimensions", "changed_files",
        "design_conformance", "test_strength", "checks", "findings",
        "challenges", "blind_spots", "spec_change_requests",
    )

    def __post_init__(self) -> None:
        if self.verdict not in self.VALUES:
            raise DomainError(
                f"verdict must be one of {', '.join(self.VALUES)}; got {self.verdict!r}"
            )
        if not str(self.head_sha).strip():
            raise DomainError(
                "a verdict must name the exact Pull Request head it reviewed; "
                "evidence not bound to a commit cannot be checked for staleness"
            )
        if self.verdict == "blocked":
            return
        if not self.checks:
            raise DomainError(
                "a pass or fail verdict requires at least one recorded check; "
                "'looks good' is not a verdict"
            )
        if self.verdict == "pass" and not self.changed_files:
            raise DomainError(
                "a pass must enumerate every changed file it reviewed; an "
                "unenumerated change is an unreviewed change"
            )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "verdict": self.verdict,
            "card": self.card,
            "pull_request": self.pull_request,
            "head_sha": self.head_sha,
        }
        for name in self._SEQUENCES:
            payload[name] = list(getattr(self, name))
        payload["limitations"] = self.limitations
        payload["browser_evidence"] = self.browser_evidence
        payload["next_role"] = self.next_role.value if self.next_role else None
        return payload

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "Verdict":
        return cls(
            verdict=str(raw.get("verdict", "")),
            card=int(raw.get("card", 0)),
            pull_request=str(raw.get("pull_request", "")),
            head_sha=str(raw.get("head_sha", "")),
            limitations=str(raw.get("limitations", "")),
            # Kept exactly as written. Validation is policy's job, and coercing
            # a malformed block here would hide the defect it must report.
            browser_evidence=raw.get("browser_evidence"),
            next_role=Role.parse_optional(raw.get("next_role")),
            **{name: tuple(raw.get(name, ()) or ()) for name in cls._SEQUENCES},
        )


@dataclass(frozen=True)
class Acceptance:
    """A deterministic routing decision. Written by policy, never by a seat."""

    acceptance: str
    head_sha: str
    policy_version: str
    reasons: tuple[str, ...] = ()

    VALUES = ("eligible", "defect", "protected_change")

    def __post_init__(self) -> None:
        if self.acceptance not in self.VALUES:
            raise DomainError(
                f"acceptance must be one of {', '.join(self.VALUES)}; "
                f"got {self.acceptance!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "acceptance": self.acceptance,
            "head_sha": self.head_sha,
            "policy_version": self.policy_version,
            "reasons": list(self.reasons),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "Acceptance":
        return cls(
            acceptance=str(raw.get("acceptance", "")),
            head_sha=str(raw.get("head_sha", "")),
            policy_version=str(raw.get("policy_version", "")),
            reasons=tuple(str(value) for value in raw.get("reasons", ()) or ()),
        )


@dataclass
class MutationLog:
    """Records which steps of a multi-step external mutation actually landed.

    GitHub gives no transaction across Issue creation, Project field writes,
    and comments. When step three fails, the caller must be able to say
    exactly what already happened -- claiming a rollback that never ran is
    worse than reporting the truth.
    """

    completed: list[str] = field(default_factory=list)
    artifacts: dict[str, Any] = field(default_factory=dict)

    def record(self, step: str, **artifacts: Any) -> None:
        self.completed.append(step)
        for key, value in artifacts.items():
            if value is not None:
                self.artifacts[key] = value

    def partial_result(self, failed: str, error: str, recovery: Iterable[str]) -> dict:
        return {
            "ok": False,
            "partial": bool(self.completed),
            "completed": list(self.completed),
            "failed": failed,
            "error": error,
            "recovery": list(recovery),
            **self.artifacts,
        }
