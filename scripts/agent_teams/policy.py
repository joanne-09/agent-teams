"""Pure legality for the agent-teams board.

Nothing here touches GitHub, the filesystem, or the clock. That is deliberate:
authority is the part of the system that most needs to be exhaustively
testable, and a rule that needs a live Project to exercise never gets tested
against its own edges.

Four independent questions live here:

* may this Status move to that Status?        -- LEGAL_TRANSITIONS
* may this seat hand work to that seat?       -- HANDOFF_AUTHORITY
* may this seat take this action at all?      -- ACTION_POLICY
* how much work is in flight?                 -- wip_count

Status and Role are orthogonal (ARCHITECTURE.md 9.2), so a transition check
never consults Role and a handoff check never consults Status.
"""

from __future__ import annotations

from .errors import AgentTeamsError

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping

from .model import Card, Role, Status


class PolicyError(AgentTeamsError):
    """A refusal produced before any external mutation is attempted."""


class IllegalTransition(PolicyError):
    """The requested Status move is not on the state machine."""


class IllegalHandoff(PolicyError):
    """The requested Role change is not on the authority matrix."""


class HandoffCapExceeded(PolicyError):
    """The Card has ping-ponged past its configured handoff budget."""


class ActionForbidden(PolicyError):
    """The acting seat may not take this action."""


# ---------------------------------------------------------------- lifecycle

#: The normal delivery path is Backlog -> Ready -> In Progress -> In Review ->
#: Done. Blocked is an interruption reachable from every live state and
#: returning to any of them, because the recovering seat restores the Card to
#: whatever state it actually left. In Review -> In Progress is the rejection
#: edge; In Review -> Backlog is the "specification defect" route
#: (ARCHITECTURE.md 8.3 governs which of the two Quality Assurance uses).
LEGAL_TRANSITIONS: Mapping[Status, frozenset[Status]] = {
    Status.BACKLOG: frozenset({Status.READY, Status.BLOCKED}),
    Status.READY: frozenset({Status.IN_PROGRESS, Status.BACKLOG, Status.BLOCKED}),
    Status.IN_PROGRESS: frozenset({Status.IN_REVIEW, Status.READY, Status.BLOCKED}),
    Status.IN_REVIEW: frozenset(
        {Status.IN_PROGRESS, Status.DONE, Status.BACKLOG, Status.BLOCKED}
    ),
    Status.BLOCKED: frozenset(
        {Status.BACKLOG, Status.READY, Status.IN_PROGRESS, Status.IN_REVIEW}
    ),
    Status.DONE: frozenset(),
}

#: Statuses that consume active team attention. Blocked is excluded because a
#: blocked Card is waiting on someone else, not occupying a seat.
ACTIVE_STATUSES: frozenset[Status] = frozenset({Status.IN_PROGRESS, Status.IN_REVIEW})


def transition_is_legal(current: Status, target: Status) -> bool:
    return target in LEGAL_TRANSITIONS.get(current, frozenset())


def check_transition(current: Status | None, target: Status) -> None:
    """Raise unless ``current -> target`` is on the state machine."""
    if current is None:
        raise IllegalTransition(
            f"Card has no {Status.__name__}; set one before transitioning to "
            f"{target}"
        )
    if current == target:
        raise IllegalTransition(f"Card is already in {target}")
    if not transition_is_legal(current, target):
        legal = sorted(s.value for s in LEGAL_TRANSITIONS.get(current, frozenset()))
        detail = ", ".join(legal) if legal else "nothing; it is terminal"
        raise IllegalTransition(
            f"{current} -> {target} is not a legal transition; "
            f"from {current} you may reach: {detail}"
        )


# ---------------------------------------------------------------- authority

#: The enforceable organisation chart (ARCHITECTURE.md 4.3). Read the rows and
#: the reporting lines fall out: dev never reaches human because only Quality
#: Assurance opens the merge gate; analyst never reaches dev because nothing is
#: built without passing through the architect.
HANDOFF_AUTHORITY: Mapping[Role, frozenset[Role]] = {
    Role.ANALYST: frozenset({Role.ARCHITECT, Role.LEAD, Role.HUMAN}),
    Role.ARCHITECT: frozenset({Role.ANALYST, Role.DEV, Role.QA, Role.LEAD, Role.HUMAN}),
    Role.DEV: frozenset({Role.ARCHITECT, Role.QA, Role.LEAD}),
    Role.QA: frozenset({Role.ARCHITECT, Role.DEV, Role.LEAD, Role.HUMAN}),
    Role.LEAD: frozenset({Role.ANALYST, Role.ARCHITECT, Role.DEV, Role.QA, Role.HUMAN}),
    Role.HUMAN: frozenset({Role.ANALYST, Role.ARCHITECT, Role.DEV, Role.QA, Role.LEAD}),
}

#: Why a specific edge is missing, so a refusal can teach instead of just deny.
REFUSAL_REASONS: Mapping[tuple[Role, Role], str] = {
    (Role.ANALYST, Role.DEV): (
        "nothing reaches implementation without passing through the architect; "
        "hand to `architect` instead"
    ),
    (Role.ANALYST, Role.QA): (
        "there is no delivery to verify yet; hand to `architect` instead"
    ),
    (Role.DEV, Role.HUMAN): (
        "only the Quality Assurance engineer opens the merge gate; "
        "hand to `qa` instead"
    ),
    (Role.DEV, Role.ANALYST): (
        "route requirement problems through the architect, which is this "
        "seat's technical lead"
    ),
    (Role.QA, Role.ANALYST): (
        "route specification defects through the architect"
    ),
}

DEFAULT_HANDOFF_CAP = 6

#: Where a Card goes when it has exceeded its handoff budget.
CAP_BREACH_TARGET: tuple[Status, Role] = (Status.BLOCKED, Role.LEAD)


def handoff_is_legal(from_role: Role, to_role: Role) -> bool:
    return to_role in HANDOFF_AUTHORITY.get(from_role, frozenset())


def check_handoff(
    from_role: Role,
    to_role: Role,
    handoff_count: int = 0,
    cap: int = DEFAULT_HANDOFF_CAP,
) -> None:
    """Raise unless this seat may hand to that seat, within budget."""
    if from_role == to_role:
        raise IllegalHandoff(f"`{from_role}` cannot hand work to itself")
    if not handoff_is_legal(from_role, to_role):
        reason = REFUSAL_REASONS.get((from_role, to_role))
        legal = ", ".join(sorted(r.value for r in HANDOFF_AUTHORITY.get(from_role, ())))
        detail = f"; {reason}" if reason else f"; `{from_role}` may hand to: {legal}"
        raise IllegalHandoff(f"handoff `{from_role}` -> `{to_role}` is not allowed{detail}")
    if cap > 0 and handoff_count >= cap:
        status, role = CAP_BREACH_TARGET
        raise HandoffCapExceeded(
            f"Card has already been handed off {handoff_count} times, at the "
            f"configured cap of {cap}. This is a signal, not a nuisance: the "
            f"Card is under-specified. Route it to ({status}, {role}) for "
            f"recovery instead of around the loop again."
        )


# ------------------------------------------------------------- seat actions


class ActionClass(str, Enum):
    """What a seat may do with an action."""

    ALLOW = "allow"
    REVIEW = "review"
    REFUSE = "refuse"

    __str__ = str.__str__


@dataclass(frozen=True)
class Decision:
    action: str
    seat: Role
    klass: ActionClass
    note: str = ""

    @property
    def permitted(self) -> bool:
        return self.klass is not ActionClass.REFUSE

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "seat": self.seat.value,
            "class": self.klass.value,
            "note": self.note,
        }


_A, _R, _N = ActionClass.ALLOW, ActionClass.REVIEW, ActionClass.REFUSE

#: The seat-aware action policy (ARCHITECTURE.md 4.4). Values are either a
#: bare class or a (class, constraint-note) pair. A note records a condition
#: this pure layer cannot verify on its own -- Card binding enforces those.
ACTION_POLICY: Mapping[str, Mapping[Role, object]] = {
    "create_requirement_card": {
        Role.ANALYST: _A,
        Role.ARCHITECT: (_A, "when decomposing a durable specification"),
        Role.DEV: _N,
        Role.QA: _N,
        Role.LEAD: _A,
        Role.HUMAN: _A,
    },
    "split_implementation_work": {
        Role.ANALYST: _N,
        Role.ARCHITECT: _A,
        Role.DEV: _N,
        Role.QA: _N,
        Role.LEAD: (_R, "requires a written justification"),
        Role.HUMAN: _A,
    },
    # Readiness is a human lifecycle gate (ARCHITECTURE.md Appendix A.2 decision 6).
    # Every artificial intelligence seat is refused, including `lead`: a
    # review-class pass would have been decorative, because REVIEW is
    # permitted. An agent seat prepares the Card and hands it to `human`.
    "promote_to_ready": {
        Role.ANALYST: _N,
        Role.ARCHITECT: _N,
        Role.DEV: _N,
        Role.QA: _N,
        Role.LEAD: _N,
        Role.HUMAN: _A,
    },
    "claim_card": {
        Role.ANALYST: _N,
        Role.ARCHITECT: (_A, "documentation Cards only"),
        Role.DEV: (_A, "own bound Card only"),
        Role.QA: (_A, "governed verification or test Card only"),
        Role.LEAD: _N,
        Role.HUMAN: _A,
    },
    "write_verdict": {
        Role.ANALYST: _N,
        Role.ARCHITECT: _N,
        Role.DEV: _N,
        Role.QA: (_A, "own bound Card only"),
        Role.LEAD: _N,
        Role.HUMAN: _A,
    },
    "merge_pull_request": {
        Role.ANALYST: _N,
        Role.ARCHITECT: _N,
        Role.DEV: _N,
        Role.QA: _N,
        Role.LEAD: _N,
        Role.HUMAN: _A,
    },
    "transition_card": {
        Role.ANALYST: _A,
        Role.ARCHITECT: _A,
        Role.DEV: (_A, "own bound Card only"),
        Role.QA: (_A, "own bound Card only"),
        Role.LEAD: _A,
        Role.HUMAN: _A,
    },
    "handoff_card": {
        Role.ANALYST: _A,
        Role.ARCHITECT: _A,
        Role.DEV: _A,
        Role.QA: _A,
        Role.LEAD: _A,
        Role.HUMAN: _A,
    },
    "dispatch_session": {
        Role.ANALYST: _N,
        Role.ARCHITECT: _N,
        Role.DEV: _N,
        Role.QA: _N,
        Role.LEAD: _A,
        Role.HUMAN: _A,
    },
    "reconcile_done": {
        Role.ANALYST: _N,
        Role.ARCHITECT: _N,
        Role.DEV: _N,
        Role.QA: _N,
        Role.LEAD: (_R, "reconciliation only, after a confirmed human merge"),
        Role.HUMAN: _A,
    },
}

#: Some Status moves *are* a governed action under another name. Promoting to
#: Ready is the architect's readiness decision, and reaching Done means a human
#: accepted the delivery. Routing them here stops the generic ``transition``
#: command becoming a hole through which a seat takes an action its own row
#: forbids.
_TRANSITION_ACTIONS: Mapping[Status, str] = {
    Status.READY: "promote_to_ready",
    Status.DONE: "reconcile_done",
}


def action_for_transition(target: Status) -> str:
    """The action name that governs moving a Card into ``target``."""
    return _TRANSITION_ACTIONS.get(target, "transition_card")

#: Why an action is closed to agent seats, so a refusal teaches the caller the
#: route that does exist instead of only saying no.
ACTION_REFUSAL_REASONS: Mapping[str, str] = {
    "promote_to_ready": (
        "readiness is the human lifecycle gate. Hand the Card to `human` with "
        "the specification and let them approve it into Ready"
    ),
}

#: Actions no override may ever widen for an artificial intelligence seat.
#: Human merge is the floor the whole governance layer rests on -- if an agent
#: could merge, every other refusal becomes advisory.
HARD_FLOORS: frozenset[str] = frozenset({"merge_pull_request"})


def classify_action(action: str, seat: Role) -> Decision:
    """Return the seat's class for an action, without raising."""
    row = ACTION_POLICY.get(action)
    if row is None:
        raise ActionForbidden(
            f"unknown action {action!r}; known actions: "
            + ", ".join(sorted(ACTION_POLICY))
        )
    entry = row.get(seat, _N)
    if isinstance(entry, tuple):
        klass, note = entry
    else:
        klass, note = entry, ""
    return Decision(action=action, seat=seat, klass=klass, note=note)


def check_action(action: str, seat: Role) -> Decision:
    """Raise unless the seat may take the action. Returns the decision."""
    decision = classify_action(action, seat)
    if decision.klass is ActionClass.REFUSE:
        if action in HARD_FLOORS:
            raise ActionForbidden(
                f"`{seat}` may never {action.replace('_', ' ')}. Only the human "
                f"merge authority can accept a repository change. This floor is "
                f"not overridable by any agent session."
            )
        reason = ACTION_REFUSAL_REASONS.get(action)
        detail = f". {reason}" if reason else ""
        raise ActionForbidden(
            f"`{seat}` ({seat.full_name}) may not "
            f"{action.replace('_', ' ')}{detail}"
        )
    return decision


# -------------------------------------------------------- work in progress


def is_active(status: Status | None) -> bool:
    return status in ACTIVE_STATUSES


def wip_count(cards: Iterable[Card]) -> int:
    """Cards consuming active attention: In Progress plus In Review."""
    return sum(1 for card in cards if is_active(card.status))


def over_wip(cards: Iterable[Card], limit: int) -> bool:
    return limit > 0 and wip_count(cards) > limit
