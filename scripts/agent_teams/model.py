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
from typing import Any, Iterable


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
VERDICT_MARKER = "<!-- agent-teams:verdict -->"


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


@dataclass(frozen=True)
class Verdict:
    """A Quality Assurance result. Read by Producer queue inspection."""

    verdict: str
    card: int
    pull_request: str = ""
    scope: tuple[str, ...] = ()
    checks: tuple[str, ...] = ()
    findings: tuple[str, ...] = ()
    limitations: str = ""
    next_role: Role | None = None

    VALUES = ("pass", "fail", "blocked")

    def __post_init__(self) -> None:
        if self.verdict not in self.VALUES:
            raise DomainError(
                f"verdict must be one of {', '.join(self.VALUES)}; got {self.verdict!r}"
            )
        if not self.checks and self.verdict != "blocked":
            raise DomainError(
                "a pass or fail verdict requires at least one recorded check; "
                "'looks good' is not a verdict"
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
