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
    Acceptance, BLOCKING_SEVERITIES, Card, CODE_SMELLS,
    MINIMUM_FINDING_CONFIDENCE, REQUIRED_DIMENSIONS, Role, SEVERITIES, Status,
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
    # Sending a Card back to the architect because QA found the *specification*
    # wrong. Human-only, and deliberately so: the team lead's instruction when
    # he asked for this loop was that the human approval step stays and only
    # the record becomes trackable. An agent seat that could reopen a spec on
    # its own reading would be able to rewrite the baseline it is judged
    # against, which is the one thing the design-conformance dimension rests
    # on. It is not a HARD_FLOOR -- nothing merges -- but no agent seat holds
    # it.
    "approve_specification_change": {
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
    "approve_specification_change": (
        "reopening a specification is a human decision. Record the conflict as "
        "a `spec_change_requests` entry on the verdict -- the document, the "
        "clause, what you observed, and what you suggest instead -- and "
        "`accept` will route the Card to the human, who approves it back to "
        "the architect"
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


# ------------------------------------------------------------ seat binding

#: Environment variable that binds a process to one seat. Set it when a worker
#: is spawned (``AGENT_TEAMS_ACTING_ROLE=dev``) and every command in that
#: process acts as that seat; a ``--acting-role`` that disagrees is refused.
ACTING_ROLE_ENV = "AGENT_TEAMS_ACTING_ROLE"

#: Environment markers that an agent harness stamps on every subprocess it
#: runs. Their presence means "this command was issued by a model session",
#: and a model session never holds human authority.
AGENT_SESSION_MARKERS: tuple[str, ...] = ("CLAUDECODE", "CLAUDE_CODE_SESSION_ID")


class SeatMismatch(ActionForbidden):
    """The seat a command claims is not the seat its process is bound to."""


def agent_session(env: Mapping[str, str]) -> bool:
    """True when the process runs inside an agent harness."""
    return any(env.get(marker) for marker in AGENT_SESSION_MARKERS)


#: Environment variable through which a non-agent human surface names itself.
#: It is a *provenance label*, never an authority grant: the ``human`` refusal
#: below still keys on :data:`AGENT_SESSION_MARKERS`, so setting this inside an
#: agent session buys the caller nothing. What it earns is a durable trail that
#: says which surface a person opened a gate from.
HUMAN_ORIGIN_ENV = "AGENT_TEAMS_HUMAN_ORIGIN"

#: Closed vocabulary. It is closed because the value reaches a GitHub comment;
#: free text there would be an injection surface, and an unrecognised label is
#: more likely a typo than a new surface.
HUMAN_ORIGINS: tuple[str, ...] = ("terminal", "dashboard")


def human_origin(env: Mapping[str, str]) -> str:
    """Name the surface a human command was issued from, for the durable trail.

    Absent the variable the answer is ``terminal`` -- the historical and still
    the default way a person opens a gate. This never widens who may act as
    ``human``; :func:`resolve_acting_role` alone decides that.
    """
    raw = (env.get(HUMAN_ORIGIN_ENV) or "").strip().lower()
    if not raw:
        return "terminal"
    if raw not in HUMAN_ORIGINS:
        raise ActionForbidden(
            f"unknown human origin {raw!r} ({HUMAN_ORIGIN_ENV}); known surfaces: "
            + ", ".join(HUMAN_ORIGINS)
        )
    return raw


def resolve_acting_role(
    claimed: Role | None, env: Mapping[str, str], fallback: Role | None = None
) -> Role:
    """Decide which seat a command really acts as.

    Precedence: the process binding (``ACTING_ROLE_ENV``) over the command
    line, and the command line over the command's own default (``fallback``).
    Two refusals guard the human gates:

    * a bound process may not claim a different seat -- the flag is a
      convenience, the binding is the authority;
    * a process inside an agent harness may not act as ``human``, explicitly
      or by default. Human authority is exercised from the human's own shell.

    This is a process-level floor, not a cryptographic one: an agent that
    deliberately scrubs its environment can still lie. The gate it closes is
    the one that actually fired live -- a lead running ``promote`` with no
    ``--acting-role`` and inheriting the human default.
    """
    bound_raw = (env.get(ACTING_ROLE_ENV) or "").strip()
    bound = Role.parse(bound_raw) if bound_raw else None
    if bound is not None and claimed is not None and claimed is not bound:
        raise SeatMismatch(
            f"this process is bound to seat `{bound}` ({ACTING_ROLE_ENV}); "
            f"it may not act as `{claimed}`"
        )
    seat = bound or claimed or fallback
    if seat is None:
        raise ActionForbidden(
            f"no acting seat: pass --acting-role or set {ACTING_ROLE_ENV}"
        )
    if seat is Role.HUMAN and agent_session(env):
        origin = "defaulted to" if claimed is None and bound is None else "claims"
        raise ActionForbidden(
            f"this command {origin} `human`, but it is running inside an agent "
            f"session. Human authority is never exercised from a model's shell: "
            f"run it from your own terminal, or pass the seat you actually are "
            f"with --acting-role <seat> and let policy decide."
        )
    return seat


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
    verdict: Verdict,
    live_head_sha: str,
    live_changed_files: Iterable[str],
    config=None,
) -> list[str]:
    """Every reason this verdict cannot be acted on. Empty means usable.

    Stage 1 of two. Reported all at once rather than first-defect-wins, so a
    Quality Assurance session learns everything it must redo in one pass.

    A refusal here is not a route. Stale or incomplete evidence is not a code
    defect and must not push the Card into the Developer lane; the correct
    recovery is re-reviewing the current head.

    ``config`` is optional and duck-typed, matching ``evaluate_acceptance``:
    this module sits below config in the dependency order and must not import
    it. When supplied, it decides which changed paths are user-facing and
    therefore whether browser evidence is required. When absent, every other
    check still runs.
    """
    problems: list[str] = []
    if verdict.head_sha != live_head_sha:
        problems.append(
            f"verdict reviewed head {str(verdict.head_sha)[:12]} but the Pull "
            f"Request head is now {str(live_head_sha)[:12]}; a new commit "
            f"invalidates the evidence. Re-review the current head."
        )
    # Checked before the early return below: a specification conflict is most
    # often reported on a `fail`, which is exactly the verdict value that skips
    # the rest of these rules. Findings are here for the same reason and a
    # stronger one -- a `fail`'s findings are what the Developer is handed.
    problems.extend(_spec_change_problems(verdict))
    problems.extend(_findings_problems(verdict.findings))
    if verdict.verdict != "pass":
        return problems

    problems.extend(_pass_severity_problems(verdict))
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
    problems.extend(_browser_evidence_problems(verdict, config))
    return problems


#: What a finding must name to be checkable at all. ``severity`` says what it
#: costs if it ships, ``dimension`` says which of the nine lenses found it,
#: ``confidence`` says how sure the reviewer is that it is real, and
#: ``evidence`` is the quoted code without which the skill's step 4 does not
#: promote the finding in the first place.
FINDING_FIELDS: tuple[str, ...] = (
    "severity", "dimension", "confidence", "evidence",
)


def _findings_problems(entries: Iterable[object]) -> list[str]:
    """Why these findings cannot be compared, challenged, or acted on.

    Structured for the same reason ``test_strength`` is, and the history is
    the argument. Findings were free text until 2026-09-04, so every rule the
    review skill stated about them -- carry a severity, score the confidence,
    name the smell from the catalogue, do not invent one -- was checkable by a
    reader and by nothing else. An inflated ``[critical]`` tag, a severity
    word that meant whatever the writer wanted, and a smell coined on the spot
    were all indistinguishable from the real thing to every consumer
    downstream.

    Prose is refused outright rather than tolerated alongside objects. The
    lesson is ``RETIRED_KEYS`` from earlier the same day: a permissive reader
    that silently accepts the old shape converts a loud failure into a quiet
    wrong answer, and the reviewer never learns the rule exists.

    Called before ``validate_verdict``'s early return, deliberately. A
    ``fail``'s findings are the payload that routes to the Developer -- the
    one verdict value whose findings are actually acted on -- so checking them
    only on a ``pass`` would leave the important case unchecked.
    """
    problems: list[str] = []
    severities = set(SEVERITIES)
    dimensions = set(REQUIRED_DIMENSIONS)
    smells = set(CODE_SMELLS)

    for index, entry in enumerate(entries):
        label = f"findings[{index}]"
        if not isinstance(entry, Mapping):
            problems.append(
                f"{label} is free text. Each finding must be an object naming "
                + ", ".join(FINDING_FIELDS)
                + ", optionally `smell`. Prose cannot be compared to another "
                  "reviewer's wording or to the same defect on the next Card."
            )
            continue

        severity = str(entry.get("severity", "")).strip().casefold()
        if severity not in severities:
            problems.append(
                f"{label} severity {severity or '(missing)'!r} is not "
                f"recognised; use one of: " + ", ".join(SEVERITIES)
            )

        dimension = str(entry.get("dimension", "")).strip().casefold()
        if dimension not in dimensions:
            problems.append(
                f"{label} dimension {dimension or '(missing)'!r} is not one "
                f"of the nine reviewed dimensions; use one of: "
                + ", ".join(REQUIRED_DIMENSIONS)
            )

        problems.extend(_confidence_problems(label, entry.get("confidence")))

        if not str(entry.get("evidence", "") or "").strip():
            problems.append(
                f"{label} records no evidence. A finding that quotes nothing "
                f"is an impression, and an impression is not promoted."
            )

        # Absent is correct and common: most findings have no smell, and a
        # plain logic bug has none. Only a value outside the catalogue is a
        # problem -- that is `code-smells.md`'s "do not invent entries",
        # which until now no check could enforce.
        smell = str(entry.get("smell", "") or "").strip()
        if smell and smell not in smells:
            problems.append(
                f"{label} names a smell that is not in the catalogue: "
                f"{smell!r}. Use an entry from "
                f"references/code-smells.md or describe the finding plainly; "
                f"a private vocabulary is worse than none, because it looks "
                f"shared."
            )
    return problems


def _render_finding(entry: object) -> str:
    """One finding as the line the Developer reads on the Card.

    The acceptance reason is where a `fail` actually reaches a person, so the
    structure has to collapse back into a sentence rather than arrive as a
    repr. Malformed entries are rendered as written: this runs after
    ``validate_verdict`` has already refused them, and inventing a tidy shape
    for something the validator rejected would hide which one was wrong.
    """
    if not isinstance(entry, Mapping):
        return str(entry)
    severity = str(entry.get("severity", "")).strip() or "unrated"
    dimension = str(entry.get("dimension", "")).strip()
    evidence = " ".join(str(entry.get("evidence", "") or "").split())
    smell = str(entry.get("smell", "") or "").strip()
    head = f"[{severity}]" + (f" {dimension}" if dimension else "")
    tail = f" ({smell})" if smell else ""
    return f"{head}: {evidence}{tail}"


def _confidence_problems(label: str, raw: object) -> list[str]:
    """Why this confidence score cannot be read.

    ``bool`` is rejected explicitly because it is an ``int`` in Python, and
    ``True`` would otherwise read as confidence 1 -- a score below the
    publishing floor arriving as a plausible-looking value.
    """
    if isinstance(raw, bool) or not isinstance(raw, int):
        return [
            f"{label} records no usable confidence; score it 1-10. "
            f"How sure you are is not what the severity says."
        ]
    if not 1 <= raw <= 10:
        return [f"{label} confidence {raw} is outside 1-10"]
    if raw < MINIMUM_FINDING_CONFIDENCE:
        return [
            f"{label} is published at confidence {raw}, which is too low to "
            f"act on; move it to `limitations` with the reason. Do not delete "
            f"it -- a dropped finding reaches nobody and nobody learns it was "
            f"dropped."
        ]
    return []


def _pass_severity_problems(verdict: Verdict) -> list[str]:
    """Why this pass contradicts its own findings.

    The one rule here that changes an outcome rather than a format.
    ``verdict-schema.md`` has always said a ``critical`` or ``high`` finding
    on a ``pass`` is a contradiction, and nothing enforced it, which made
    writing ``pass`` above a serious finding the cheapest way to ship it.

    The refusal names ``fail`` rather than asking for the finding to be
    softened or removed. The finding is the honest part of the verdict; the
    verdict value is the part that disagrees with it.
    """
    problems: list[str] = []
    for index, entry in enumerate(verdict.findings):
        if not isinstance(entry, Mapping):
            continue  # already reported as free text
        severity = str(entry.get("severity", "")).strip().casefold()
        if severity not in BLOCKING_SEVERITIES:
            continue
        problems.append(
            f"pass carries a {severity} finding (findings[{index}], "
            f"{str(entry.get('dimension', '')).strip() or 'unknown dimension'}"
            f"): a finding that would send the Card back to the Developer is "
            f"what `fail` means. A pass may carry medium and low findings; "
            f"that is what they are for."
        )
    return problems


#: What a specification-change request must name to be actionable. Anything
#: less is an opinion about a document, which the architect cannot diff.
SPEC_CHANGE_FIELDS: tuple[str, ...] = (
    "document", "clause", "conflict", "suggested_change",
)


def _spec_change_problems(verdict: Verdict) -> list[str]:
    """Why these specification-change requests cannot be routed.

    Silent when there are none: this is an occasional finding, not a section
    every verdict must fill in, and a required-but-usually-empty field teaches
    reviewers to write something to satisfy the validator.

    The four required keys are the difference between a request the architect
    can act on and a complaint. "The spec is wrong" names no document. "AC3
    contradicts AC5" names no fix. What the architect needs is: which document,
    which part of it, what was observed that conflicts with it, and what to
    write instead.
    """
    requests = verdict.spec_change_requests
    if not requests:
        return []
    if isinstance(requests, (str, bytes)) or not isinstance(
        requests, (list, tuple)
    ):
        return ["spec_change_requests must be a list of objects, not prose"]

    problems: list[str] = []
    for index, request in enumerate(requests):
        label = f"spec_change_requests[{index}]"
        if not isinstance(request, Mapping):
            problems.append(
                f"{label} must be an object naming "
                + ", ".join(SPEC_CHANGE_FIELDS)
            )
            continue
        missing = [
            name for name in SPEC_CHANGE_FIELDS
            if not str(request.get(name, "") or "").strip()
        ]
        if missing:
            problems.append(
                f"{label} is missing {', '.join(missing)}; a specification "
                f"change the architect cannot diff is a complaint, not a "
                f"request"
            )
    return problems


#: Enough of a flow to count as driving the interface. One step is a page load
#: and a screenshot, which is the incidental check this rule replaces.
MINIMUM_FLOW_STEPS = 2


def _browser_evidence_problems(verdict: Verdict, config) -> list[str]:
    """Why this user-facing pass has not actually been exercised as a user.

    Silent when the delivery touches no user-facing file, or when no config was
    supplied to say which files those are. A rule that fired on every pass
    would put an empty browser section on parser changes, and a section written
    to satisfy a validator teaches nothing.
    """
    if config is None:
        return []
    touched = config.ui_paths_touched(verdict.changed_files)
    if not touched:
        return []

    where = ", ".join(touched)
    evidence = verdict.browser_evidence
    if evidence is None:
        return [
            f"this delivery changes user-facing files ({where}) so a pass "
            f"requires browser_evidence: the flows you drove, the invalid "
            f"input you fed each field, and the console state after. Re-running "
            f"the Developer's unit tests is not independent verification"
        ]
    if not isinstance(evidence, Mapping):
        return ["browser_evidence must be a JSON object, not free prose"]

    problems: list[str] = []

    flows = evidence.get("flows")
    if not isinstance(flows, (list, tuple)) or not flows:
        problems.append(
            "browser_evidence.flows must list at least one flow you drove "
            f"through the interface at {where}"
        )
    else:
        for index, flow in enumerate(flows):
            label = f"browser_evidence.flows[{index}]"
            if not isinstance(flow, Mapping):
                problems.append(f"{label} must be an object")
                continue
            if not str(flow.get("name", "")).strip():
                problems.append(f"{label} must carry a name saying what it did")
            steps = flow.get("steps")
            count = len(steps) if isinstance(steps, (list, tuple)) else 0
            if count < MINIMUM_FLOW_STEPS:
                problems.append(
                    f"{label} records {count} step(s); a flow needs at least "
                    f"{MINIMUM_FLOW_STEPS}. Opening the page and screenshotting "
                    f"it is the incidental check this rule replaces"
                )

    cases = evidence.get("input_validation")
    if not isinstance(cases, (list, tuple)) or not cases:
        problems.append(
            "browser_evidence.input_validation must record at least one field "
            "fed invalid or garbage input, with what you expected and what "
            "actually happened"
        )
    else:
        for index, case in enumerate(cases):
            label = f"browser_evidence.input_validation[{index}]"
            if not isinstance(case, Mapping):
                problems.append(f"{label} must be an object")
                continue
            missing = [
                key for key in ("field", "input", "expected", "actual")
                if not str(case.get(key, "")).strip()
            ]
            if missing:
                problems.append(f"{label} is missing: " + ", ".join(missing))

    console = evidence.get("console")
    if not isinstance(console, Mapping) or "errors" not in console:
        # An absent console block and a clean one are different claims. Empty
        # means "I looked and it was quiet"; absent means "I did not look",
        # and the live ES-module blank page was a console error sitting behind
        # a fully green test suite.
        problems.append(
            "browser_evidence.console must record the console state, including "
            "an `errors` list. An empty list is a finding; an absent one is a "
            "gap"
        )
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

    # Mergeability is a question about an open Pull Request. Once merged,
    # GitHub reports ``UNKNOWN`` indefinitely; waiting on it would park the
    # Card in In Review forever (observed live on a post-merge re-verify).
    mergeable_state = str(pr_facts.get("mergeable_state", "")).strip().upper()
    if not _is_merged(pr_facts) and mergeable_state in {"", "UNKNOWN"}:
        reasons.append("GitHub is still calculating mergeability")
    return tuple(reasons)


def _is_merged(pr_facts: Mapping[str, object]) -> bool:
    return bool(pr_facts.get("merged")) or (
        str(pr_facts.get("state", "")).strip().upper() == "MERGED"
    )


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

    # Checked before `fail`, and that order is the whole point. A defect whose
    # cause is the specification used to route to `dev` along with every other
    # fail -- to the one seat that may not change a specification. The Card
    # then bounced, or a person edited the document by hand and approved their
    # own edit, off the record. See the 2026-09-04 decision record.
    #
    # The route is `protected_change` rather than a fourth acceptance value:
    # `docs/specs/**` is already a protected category, so a change to a
    # specification was always a human decision. What was missing was any way
    # for QA to *say so*, not a new lane to say it in.
    if verdict.spec_change_requests:
        named = "; ".join(
            f"{request.get('document')} ({request.get('clause')}): "
            f"{request.get('conflict')}"
            for request in verdict.spec_change_requests
            if isinstance(request, Mapping)
        )
        return result(
            "protected_change",
            "Quality Assurance reports the specification itself is in "
            "conflict, which no Developer seat may correct: " + named,
            "approve it back to the architect, or reject the request and hand "
            "the Card on with the reason recorded",
        )
    if verdict.verdict == "fail":
        return result(
            "defect",
            "Quality Assurance recorded a fail verdict: "
            + ("; ".join(_render_finding(f) for f in verdict.findings)
               or "no finding recorded"),
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
    if not _is_merged(pr_facts) and not pr_facts.get("mergeable", False):
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
