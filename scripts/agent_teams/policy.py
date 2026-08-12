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

import re
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping

from .model import (
    Acceptance, Card, REQUIRED_DIMENSIONS, Role, Status,
    TEST_STRENGTH_DIMENSIONS, Verdict,
)


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
    "publish_specification": {
        Role.ANALYST: _N,
        Role.ARCHITECT: _A,
        Role.DEV: _N,
        Role.QA: _N,
        Role.LEAD: _N,
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
    # Retained only as an emergency destructive cleanup command. Routine stale
    # sessions resume the remote claim branch automatically without reopening
    # readiness or involving a human.
    "release_claim": {
        Role.ANALYST: _N,
        Role.ARCHITECT: _N,
        Role.DEV: _N,
        Role.QA: _N,
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
    # Not a seat action at all. Arming automated merge is a *consequence* of
    # an eligible acceptance result, never something a session requests. The
    # row exists so "no seat may request it" is an assertion in the test
    # suite rather than an absence nobody notices going missing.
    "request_automated_merge": {role: _N for role in Role},
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
        Role.LEAD: (_R, "reconciliation only, after a confirmed merge"),
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
    "release_claim": (
        "deleting a claim branch is emergency destructive cleanup. Routine "
        "interrupted work must resume the existing remote branch; if deletion "
        "is truly required, report the evidence to `human`"
    ),
    "request_automated_merge": (
        "merging is not a seat action. Publish a complete verdict for the "
        "current head, then run `accept`; deterministic policy decides the "
        "route and only an eligible result reaches the merge controller"
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


# ----------------------------------------------------------- protected paths


def glob_to_regex(pattern: str) -> "re.Pattern[str]":
    """Translate a path glob, including ``**``, to an anchored regex.

    ``fnmatch`` has no ``**`` and treats ``*`` as spanning separators, so a
    protected-path rule written with it would silently fail to match nested
    files. This translator is small enough to test on its own, which is
    exactly why it is not inlined into the matcher.
    """
    parts: list[str] = []
    index = 0
    text = str(pattern).replace("\\", "/")
    while index < len(text):
        char = text[index]
        if text.startswith("**/", index):
            parts.append("(?:.*/)?")
            index += 3
        elif text.startswith("**", index):
            parts.append(".*")
            index += 2
        elif char == "*":
            parts.append("[^/]*")
            index += 1
        elif char == "?":
            parts.append("[^/]")
            index += 1
        else:
            parts.append(re.escape(char))
            index += 1
    return re.compile("^" + "".join(parts) + "$")


def path_matches(path: str, pattern: str) -> bool:
    return bool(glob_to_regex(pattern).match(str(path).replace("\\", "/")))


def protected_matches(
    changed_paths: Iterable[str], protected_paths: Mapping[str, Iterable[str]]
) -> dict[str, tuple[str, ...]]:
    """Protected category -> the exact paths that tripped it.

    The category answers *what kind of authority* the change reaches; the
    paths answer *which files to look at*. An escalation carrying only the
    category makes the human open the diff to find out what it meant, so both
    are reported.
    """
    paths = [str(path).replace("\\", "/") for path in changed_paths]
    matched: dict[str, set[str]] = {}
    for category, patterns in protected_paths.items():
        hits = {
            path
            for pattern in patterns
            for path in paths
            if path_matches(path, pattern)
        }
        if hits:
            matched[category] = hits
    return {
        category: tuple(sorted(hits))
        for category, hits in sorted(matched.items())
    }


def classify_protected(
    changed_paths: Iterable[str], protected_paths: Mapping[str, Iterable[str]]
) -> tuple[str, ...]:
    """Which protected categories this change touches, sorted and unique."""
    return tuple(protected_matches(changed_paths, protected_paths))


# ---------------------------------------------------------------- acceptance

#: Identifies the code that made an acceptance decision. Deliberately not
#: configuration: a repository must not be able to claim a decision was made
#: by a policy it did not run.
ACCEPTANCE_POLICY_VERSION = "1"

# GitHub reports a check with no conclusion while it is queued or running.
# Those states are neither proof of success nor a development defect: the
# coordinator waits and re-reads them instead of bouncing the Card to dev.
TRANSIENT_CHECK_STATES: frozenset[str] = frozenset({
    "", "NONE", "NULL", "EXPECTED", "PENDING", "QUEUED", "IN_PROGRESS",
    "REQUESTED", "WAITING",
})


def validate_verdict(
    verdict: Verdict, live_head_sha: str, live_changed_files: Iterable[str]
) -> list[str]:
    """Every reason this verdict cannot be acted on. Empty means usable.

    Stage 1 of two. Reported all at once rather than first-defect-wins, so a
    Quality Assurance session learns everything it must redo in one pass.

    A refusal here is not a route. Stale or incomplete evidence is not a code
    defect and must not push the Card into the Developer lane; the correct
    recovery is re-reviewing the current head.
    """
    problems: list[str] = []
    if verdict.head_sha != live_head_sha:
        problems.append(
            f"verdict reviewed head {str(verdict.head_sha)[:12]} but the Pull "
            f"Request head is now {str(live_head_sha)[:12]}; a new commit "
            f"invalidates the evidence. Re-review the current head."
        )
    if verdict.verdict != "pass":
        return problems

    missing = [d for d in REQUIRED_DIMENSIONS if d not in verdict.review_dimensions]
    if missing:
        problems.append(
            "pass is missing required review dimensions: " + ", ".join(missing)
        )
    if verdict.blind_spots:
        problems.append(
            "pass leaves an unresolved blind spot: " + "; ".join(verdict.blind_spots)
        )
    unreviewed = sorted(
        {str(path) for path in live_changed_files} - set(verdict.changed_files)
    )
    if unreviewed:
        problems.append(
            "pass does not enumerate every changed file; unreviewed: "
            + ", ".join(unreviewed)
        )
    problems.extend(_test_strength_problems(verdict.test_strength))
    return problems


def acceptance_wait_reasons(
    verdict: Verdict, pr_facts: Mapping[str, object], config
) -> tuple[str, ...]:
    """Transient conditions that should be monitored, never routed as defects."""
    if verdict.verdict != "pass" or not config.required_checks:
        return ()

    checks = dict(pr_facts.get("checks", {}) or {})
    terminal_failures = [
        name for name in config.required_checks
        if name in checks
        and str(checks.get(name, "")).strip().upper() != "SUCCESS"
        and str(checks.get(name, "")).strip().upper()
        not in TRANSIENT_CHECK_STATES
    ]
    if terminal_failures:
        return ()
    pending = [
        name for name in config.required_checks
        if name not in checks
        or str(checks.get(name, "")).strip().upper() in TRANSIENT_CHECK_STATES
    ]
    reasons: list[str] = []
    if pending:
        reasons.append("required checks still pending: " + ", ".join(pending))

    mergeable_state = str(pr_facts.get("mergeable_state", "")).strip().upper()
    if mergeable_state in {"", "UNKNOWN"}:
        reasons.append("GitHub is still calculating mergeability")
    return tuple(reasons)


#: The minimum a falsification note must say to be checkable: what was broken
#: and which named test caught it. Shorter than this is an assertion, not
#: evidence.
_MIN_FALSIFICATION_WORDS = 5


def _test_strength_problems(entries: Iterable[object]) -> list[str]:
    """Why this test-strength evidence does not establish tested behaviour.

    Structured rather than free text, and deliberately so. The rule this
    replaced searched free prose for one of six words, which meant "NO branch
    coverage was measured" satisfied it -- the token was present. A check that
    a token appears is exactly the error it was meant to catch: treating
    execution as proof.

    A pass must therefore carry, in machine-readable form, at least one
    dimension beyond `line`, and at least one falsification -- a record that
    breaking the implementation made a *named* test fail. That is the only
    operational proof that a covered line's behaviour is asserted rather than
    merely executed.
    """
    problems: list[str] = []
    allowed = set(TEST_STRENGTH_DIMENSIONS) | {"line"}
    parsed: list[Mapping[str, object]] = []

    for entry in entries:
        if not isinstance(entry, Mapping):
            problems.append(
                f"test_strength entry {entry!r} is free text. Each entry must "
                f"be an object with `dimension` (one of: "
                + ", ".join(sorted(allowed))
                + ") and `evidence`, optionally `falsified_by`. Prose cannot "
                  "be checked -- 'no branch coverage' contains 'branch'."
            )
            continue
        dimension = str(entry.get("dimension", "")).strip().casefold()
        if dimension not in allowed:
            problems.append(
                f"test_strength dimension {dimension or '(missing)'!r} is not "
                f"recognised; use one of: " + ", ".join(sorted(allowed))
            )
            continue
        if not str(entry.get("evidence", "")).strip():
            problems.append(
                f"test_strength entry for {dimension!r} records no evidence"
            )
        parsed.append(entry)

    if not any(
        str(e.get("dimension", "")).strip().casefold() != "line" for e in parsed
    ):
        problems.append(
            "pass treats line execution as sufficient test evidence. A covered "
            "line is a line that ran, not a line whose behaviour was asserted. "
            "Record at least one of: " + ", ".join(TEST_STRENGTH_DIMENSIONS)
        )

    falsifications = [
        str(e.get("falsified_by", "")).strip()
        for e in parsed
        if str(e.get("falsified_by", "")).strip()
    ]
    if not falsifications:
        problems.append(
            "pass records no `falsified_by`. Name one change that breaks the "
            "implementation and the named test that caught it -- for example "
            "'reverted the guard at parser.py:41 -> test_rejects_empty "
            "failed'. Without it, nothing distinguishes a test that asserts "
            "behaviour from one that merely executes the line."
        )
    elif not any(len(note.split()) >= _MIN_FALSIFICATION_WORDS for note in falsifications):
        problems.append(
            "every `falsified_by` is too short to check. It must name what was "
            "broken and which test failed, not merely assert that something was."
        )
    return problems


def evaluate_acceptance(
    verdict: Verdict, pr_facts: Mapping[str, object], config
) -> Acceptance:
    """The deterministic route for one reviewed delivery.

    Stage 2 of two, reached only after ``validate_verdict`` returned no
    problems -- so the evidence is already known to be current and complete,
    and this return type stays honestly closed over the three acceptance
    values rather than smuggling a refusal through as a fourth.

    ``config`` is duck-typed on purpose. ``policy`` sits below ``config`` in
    the dependency order and must not import it; it reads two attributes and
    performs no I/O of its own.
    """
    head = str(pr_facts.get("head_sha", ""))

    def result(acceptance: str, *reasons: str) -> Acceptance:
        return Acceptance(
            acceptance=acceptance,
            head_sha=head,
            policy_version=ACCEPTANCE_POLICY_VERSION,
            reasons=tuple(reasons),
        )

    if verdict.verdict == "fail":
        return result(
            "defect",
            "Quality Assurance recorded a fail verdict: "
            + ("; ".join(verdict.findings) or "no finding recorded"),
        )
    if verdict.verdict == "blocked":
        return result(
            "protected_change",
            "Quality Assurance could not resolve its uncertainty: "
            + ("; ".join(verdict.blind_spots) or "no reason recorded"),
        )

    protected = protected_matches(
        pr_facts.get("changed_files", ()) or (), config.protected_paths
    )
    if protected:
        return result(
            "protected_change",
            "change touches protected categories: "
            + "; ".join(
                f"{category} ({', '.join(paths)})"
                for category, paths in protected.items()
            ),
        )

    if not config.required_checks:
        return result(
            "protected_change",
            "no required checks configured, so automated acceptance cannot "
            "establish a green baseline. Configure required_checks and branch "
            "protection, or accept this change through the human lane.",
        )

    checks = dict(pr_facts.get("checks", {}) or {})
    unmet = [
        name for name in config.required_checks
        if str(checks.get(name, "")).upper() != "SUCCESS"
    ]
    if unmet:
        return result(
            "defect",
            "required checks are not green: "
            + ", ".join(f"{name}={checks.get(name, 'missing')}" for name in unmet),
        )

    if pr_facts.get("draft"):
        return result("defect", "Pull Request is still a draft")
    if not pr_facts.get("mergeable", False):
        return result(
            "defect", "Pull Request is not mergeable; rebase onto the base branch"
        )

    return result(
        "eligible",
        f"verdict pass bound to head {head[:12]}",
        "all required review dimensions present, no unresolved blind spots",
        "every changed file enumerated and reviewed",
        "required checks green: " + ", ".join(config.required_checks),
    )


# -------------------------------------------------------- work in progress


def is_active(status: Status | None) -> bool:
    return status in ACTIVE_STATUSES


def wip_count(cards: Iterable[Card]) -> int:
    """Cards consuming active attention: In Progress plus In Review."""
    return sum(1 for card in cards if is_active(card.status))


def over_wip(cards: Iterable[Card], limit: int) -> bool:
    return limit > 0 and wip_count(cards) > limit
