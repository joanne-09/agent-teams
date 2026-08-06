"""Producer transactions composed from policy and the board adapter.

GitHub gives no transaction spanning Issue creation, Project field writes, and
comments. Every workflow here therefore validates all known preconditions
first, executes a documented mutation order, records each step as it lands,
and on failure returns the exact completed prefix plus a fix-forward recipe.

Nothing in this module claims a rollback. If a compensating operation did not
actually run, saying so would be a lie the next session acts on.
"""

from __future__ import annotations

from .errors import AgentTeamsError

import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from . import policy
from .board import Board, BoardError, PartialHandoff
from .config import Config
from .git import ClaimRaceLost, Git, claim_branch, worktree_path
from .github import GitHubError
from .model import (
    Acceptance, Card, Handoff, MutationLog, PR_MARKER, Role, Status, Verdict,
)

#: Files a fresh session reloads to rebuild standing repository context.
#: Presence is reported, contents are opened on demand by the routine -- the
#: bootstrap stays compact rather than pasting whole documents into a prompt.
STANDING_CONTEXT = (
    "AGENTS.md",
    "CLAUDE.md",
    "README.md",
    "docs/ARCHITECTURE.md",
    "docs/IMPLEMENTATION_PLAN.md",
)

STALE_DAYS = 7


class WorkflowError(AgentTeamsError):
    """A Producer transaction refused before mutating anything."""


def _pr_number(reference: Any) -> int | None:
    text = str(reference or "").strip()
    if not text:
        return None
    match = re.search(r"/pull/(\d+)", text) or re.fullmatch(r"#?(\d+)", text)
    return int(match.group(1)) if match else None


class Producer:
    """Every board-shaping transaction a Producer session can run."""

    def __init__(self, config: Config, board: Board):
        self.config = config
        self.board = board

    # ------------------------------------------------------------ read-only

    def bootstrap(self, seat: Role, repo_root: Path | None = None) -> dict[str, Any]:
        """The mandatory read-only startup sequence for a Producer session.

        Loads standing repository pointers, queries the live board, and builds
        the seat-specific orientation the selected routine consumes. Mutates
        nothing: a session that cannot establish where it is has no business
        changing anything (ARCHITECTURE.md 3.5).
        """
        root = repo_root or Path.cwd()
        standing = [
            {"path": name, "present": (root / name).is_file()}
            for name in STANDING_CONTEXT
        ]
        cards = self.board.cards()
        view = self._seat_view(seat, cards)
        return {
            "ok": True,
            "seat": seat.value,
            "seat_name": seat.full_name,
            "execution_shape": "producer",
            "repo": self.config.repo,
            "project": f"{self.config.project_owner}/{self.config.project_number}",
            "standing_context": standing,
            "context_pointers_missing": [
                entry["path"] for entry in standing if not entry["present"]
            ],
            "board": self._projection(cards),
            "seat_view": view,
            "routines": _ROUTINES.get(seat, []),
            "mutations_performed": [],
        }

    def _projection(self, cards: Sequence[Card]) -> dict[str, Any]:
        by_status: dict[str, int] = {}
        by_role: dict[str, int] = {}
        for card in cards:
            key = card.status.value if card.status else "(no Status)"
            by_status[key] = by_status.get(key, 0) + 1
            role_key = card.role.value if card.role else "(no Role)"
            by_role[role_key] = by_role.get(role_key, 0) + 1
        wip = policy.wip_count(cards)
        return {
            "total": len(cards),
            "by_status": by_status,
            "by_role": by_role,
            "wip": wip,
            "wip_limit": self.config.wip_limit,
            "over_wip": policy.over_wip(cards, self.config.wip_limit),
        }

    def _seat_view(self, seat: Role, cards: Sequence[Card]) -> dict[str, Any]:
        def pick(**criteria: Any) -> list[dict[str, Any]]:
            selected = []
            for card in cards:
                if "status" in criteria and card.status is not criteria["status"]:
                    continue
                if "role" in criteria and card.role is not criteria["role"]:
                    continue
                selected.append(card.to_dict())
            return selected

        if seat is Role.ANALYST:
            return {
                "focus": "requirement intake and clarification",
                "needs_clarification": pick(status=Status.BACKLOG, role=Role.ANALYST),
                "backlog": pick(status=Status.BACKLOG),
            }
        if seat is Role.ARCHITECT:
            return {
                "focus": "technical shaping, decomposition, and readiness",
                "awaiting_shaping": pick(status=Status.BACKLOG, role=Role.ARCHITECT),
                "blocked_on_architecture": pick(
                    status=Status.BLOCKED, role=Role.ARCHITECT
                ),
                "ready_specification_cards": pick(
                    status=Status.READY, role=Role.ARCHITECT
                ),
            }
        if seat is Role.QA:
            return {
                "focus": "independent verification queue",
                "verification_queue": pick(status=Status.IN_REVIEW, role=Role.QA),
            }
        if seat is Role.LEAD:
            return {
                "focus": "whole-team flow, priority, and recovery",
                "lanes": self.lanes(cards),
                "human_merge_queue": pick(status=Status.IN_REVIEW, role=Role.HUMAN),
                "blocked": pick(status=Status.BLOCKED),
            }
        return {
            # The human now owns two gates, so the orientation names both
            # queues separately -- "awaiting you" alone hid which decision
            # each Card actually needs.
            "focus": "the two human gates: readiness, then merge",
            "awaiting_readiness": pick(status=Status.BACKLOG, role=Role.HUMAN),
            "awaiting_merge": pick(status=Status.IN_REVIEW, role=Role.HUMAN),
            "awaiting_you": [
                card.to_dict() for card in cards if card.role is Role.HUMAN
            ],
        }

    def lanes(self, cards: Sequence[Card] | None = None) -> dict[str, Any]:
        """Cards grouped by Role lane, then Status -- the LEAD's primary view."""
        cards = self.board.cards() if cards is None else cards
        lanes: dict[str, Any] = {}
        for role in Role:
            owned = [card for card in cards if card.role is role]
            if not owned:
                continue
            lanes[role.value] = {
                "count": len(owned),
                "cards": [
                    {**card.to_dict(), "routing_state": card.routing_state}
                    for card in owned
                ],
            }
        orphans = [card for card in cards if card.role is None]
        if orphans:
            lanes["(no Role)"] = {
                "count": len(orphans),
                "cards": [card.to_dict() for card in orphans],
                "note": "these Cards cannot be dispatched; assign a Role",
            }
        return lanes

    def brief(self, with_handoffs: bool = False) -> dict[str, Any]:
        """The Tech Lead's whole-team briefing.

        Handoff counts cost one API call per Card, so they are opt-in. The
        default briefing is a single board read; ``with_handoffs`` trades
        latency for ping-pong visibility.
        """
        cards = self.board.cards()
        projection = self._projection(cards)
        data_quality = [
            {**card.to_dict(), "problem": problem}
            for card, problem in (
                (card, _data_quality_problem(card)) for card in cards
            )
            if problem
        ]

        near_cap: list[dict[str, Any]] = []
        if with_handoffs and self.config.handoff_cap > 0:
            threshold = max(1, self.config.handoff_cap - 1)
            for card in cards:
                if card.status in (Status.DONE,):
                    continue
                count = self.board.handoff_count(card.number)
                if count >= threshold:
                    near_cap.append(
                        {**card.to_dict(), "handoff_count": count,
                         "cap": self.config.handoff_cap}
                    )

        return {
            "ok": True,
            "repo": self.config.repo,
            "board": projection,
            "lanes": self.lanes(cards),
            "blocked": [
                card.to_dict() for card in cards if card.status is Status.BLOCKED
            ],
            "human_merge_queue": [
                card.to_dict() for card in cards
                if card.status is Status.IN_REVIEW and card.role is Role.HUMAN
            ],
            "verification_queue": [
                card.to_dict() for card in cards
                if card.status is Status.IN_REVIEW and card.role is Role.QA
            ],
            "data_quality": data_quality,
            "near_handoff_cap": near_cap,
            "handoff_counts_included": with_handoffs,
            "recommendation": self._recommend(cards, projection, data_quality),
        }

    def _recommend(
        self,
        cards: Sequence[Card],
        projection: dict[str, Any],
        data_quality: Sequence[dict[str, Any]],
    ) -> str:
        human = [
            card for card in cards
            if card.status is Status.IN_REVIEW and card.role is Role.HUMAN
        ]
        if human:
            oldest = min(human, key=lambda card: card.number)
            return (
                f"Merge gate first: #{oldest.number} is verified and waiting on "
                f"you. Nothing downstream moves until it does."
            )
        if projection["over_wip"]:
            return (
                f"Work in progress is {projection['wip']} against a limit of "
                f"{projection['wip_limit']}. Finish or unblock before starting "
                f"more."
            )
        qa = [
            card for card in cards
            if card.status is Status.IN_REVIEW and card.role is Role.QA
        ]
        if qa:
            return (
                f"Dispatch verification on #{min(c.number for c in qa)}; it is "
                f"the oldest delivery between development and the merge gate."
            )
        ready = [card for card in cards if card.status is Status.READY]
        if ready:
            return f"Dispatch #{min(c.number for c in ready)}; it is Ready to claim."
        blocked = [card for card in cards if card.status is Status.BLOCKED]
        if blocked:
            return (
                f"Nothing is Ready. {len(blocked)} Card(s) are Blocked -- run "
                f"triage before intake."
            )
        if data_quality:
            return (
                f"{len(data_quality)} Card(s) have missing Role or Status and "
                f"cannot be routed. Fix those before dispatching."
            )
        return "The board is clear. Intake new work or refine the Backlog."

    def triage(self) -> dict[str, Any]:
        """Blocked Cards grouped by the seat that owes a resolution."""
        cards = self.board.cards()
        blocked = [card for card in cards if card.status is Status.BLOCKED]
        by_owner: dict[str, list[dict[str, Any]]] = {}
        for card in blocked:
            key = card.role.value if card.role else "(no Role)"
            by_owner.setdefault(key, []).append(card.to_dict())

        unowned = [card.to_dict() for card in blocked if card.role is None]
        return {
            "ok": True,
            "blocked_total": len(blocked),
            "by_responsible_seat": by_owner,
            "unowned_blocked": unowned,
            "data_quality": [
                {**card.to_dict(), "problem": problem}
                for card, problem in (
                    (card, _data_quality_problem(card)) for card in cards
                )
                if problem
            ],
            "recommendation": (
                "Every Blocked Card needs a named seat that owes a decision. "
                "Unowned Blocked Cards are the first thing to fix."
                if unowned
                else "Route each Blocked Card to the seat that can unblock it."
            ),
        }

    def verification_queue(self) -> dict[str, Any]:
        """Quality Assurance queue inspection -- a Producer-shaped routine.

        Inspection is emphatically not verification. This lists and orders
        deliveries awaiting a verdict and emits one kickoff prompt per Card;
        each verdict belongs to a separately bound Consumer session.
        """
        cards = self.board.cards()
        queued = [
            card for card in cards
            if card.status is Status.IN_REVIEW and card.role is Role.QA
        ]
        queued.sort(key=lambda card: card.number)
        return {
            "ok": True,
            "queue_depth": len(queued),
            "queue": [
                {
                    **card.to_dict(),
                    "kickoff_prompt": _kickoff(Role.QA, card),
                }
                for card in queued
            ],
            "awaiting_human": [
                card.to_dict() for card in cards
                if card.status is Status.IN_REVIEW and card.role is Role.HUMAN
            ],
            "note": (
                "This routine inspects and orders the queue. It does not issue "
                "verdicts; each verdict needs its own bound Consumer session."
            ),
        }

    def dispatch(self, seat: Role | None = None) -> list[dict[str, Any]]:
        """Ready Cards, deterministically ordered, with kickoff prompts."""
        configured = self.config.dispatch_role_values
        if seat is not None and seat not in configured:
            raise WorkflowError(
                f"role `{seat}` is not dispatchable; configured roles: "
                + ", ".join(role.value for role in configured)
            )
        rank = {role: index for index, role in enumerate(configured)}
        selected = [
            card for card in self.board.cards()
            if card.status is Status.READY
            and card.role in rank
            and (seat is None or card.role is seat)
        ]
        selected.sort(key=lambda card: (rank[card.role], card.number))
        return [
            {**card.to_dict(), "prompt": _kickoff(card.role, card)}
            for card in selected
        ]

    # ------------------------------------------------------------- mutating

    def intake(self, title: str, body: str) -> dict[str, Any]:
        """Create one durable requirement Card and hand it to the architect.

        Mutation order: Issue -> Project item -> Status -> Role -> comment.
        Every step is recorded so a failure names exactly what already exists.
        """
        title = title.strip()
        body = body.strip()
        if not title:
            raise WorkflowError("intake title must not be empty")
        if not body:
            raise WorkflowError("intake body must not be empty")

        log = MutationLog()

        try:
            issue_url = self.board.gh.run(
                ["issue", "create", "--repo", self.config.repo,
                 "--title", title, "--body", body]
            ).splitlines()[-1]
        except GitHubError as exc:
            return log.partial_result(
                "issue_created", str(exc),
                ["Nothing was created. Re-run intake once the error is resolved."],
            )

        match = re.search(r"/issues/(\d+)(?:\D|$)", issue_url)
        if not match:
            return log.partial_result(
                "issue_number_parsed",
                f"cannot parse Issue number from gh output: {issue_url}",
                [
                    "An Issue may exist. Check the repository before re-running "
                    "intake, or the requirement will be filed twice.",
                ],
            )
        number = int(match.group(1))
        log.record("issue_created", issue=number, url=issue_url)

        try:
            payload = self.board.gh.json(
                ["project", "item-add", str(self.config.project_number),
                 "--owner", self.config.project_owner, "--url", issue_url,
                 "--format", "json"]
            )
            item_id = payload.get("id") if isinstance(payload, dict) else None
            if not item_id:
                raise GitHubError("gh project item-add did not return an item id")
        except GitHubError as exc:
            return log.partial_result(
                "project_item_added", str(exc),
                [
                    f"Issue #{number} exists at {issue_url} but is not on the "
                    f"Project.",
                    f"  gh project item-add {self.config.project_number} "
                    f"--owner {self.config.project_owner} --url {issue_url}",
                    "Then set Status and Role, or re-run this step only.",
                ],
            )
        log.record("project_item_added", item_id=str(item_id))

        try:
            self.board.set_status(str(item_id), Status.BACKLOG)
        except (GitHubError, BoardError) as exc:
            return log.partial_result(
                "status_set", str(exc),
                [
                    f"Issue #{number} is on the Project with no Status.",
                    f"Set Status to {self.config.status_name(Status.BACKLOG)!r} "
                    f"in the Project UI, then set Role to `architect`.",
                ],
            )
        log.record("status_set", status=Status.BACKLOG.value)

        # One Role write, straight to the destination seat. Setting `analyst`
        # first and immediately overwriting it doubled the failure surface for
        # a state no session could ever observe.
        try:
            self.board.set_role(str(item_id), Role.ARCHITECT)
        except (GitHubError, BoardError) as exc:
            return log.partial_result(
                "role_set", str(exc),
                [
                    f"Issue #{number} is in Backlog with no Role.",
                    "Set Role to `architect` in the Project UI, then post the "
                    "intake handoff comment.",
                ],
            )
        log.record("role_set", role=Role.ARCHITECT.value)

        comment = Handoff(
            from_role=Role.ANALYST,
            to_role=Role.ARCHITECT,
            reason="Requirement intake is complete and the Card is shaped.",
            needs=(
                "Shape the durable specification and decide whether this is one "
                "implementation Card or needs decomposition."
            ),
            artifacts=issue_url,
        ).render()

        try:
            self.board.comment_on_card(number, comment)
        except GitHubError as exc:
            return log.partial_result(
                "handoff_comment", str(exc),
                [
                    "Status and Role are already correct; do not change them.",
                    f"  gh issue comment {number} --repo {self.config.repo} "
                    f"--body-file <file>",
                    "The comment body is in the 'comment' field of this result.",
                ],
            ) | {"comment": comment}
        log.record("handoff_comment")

        return {
            "ok": True,
            "issue": number,
            "url": issue_url,
            "status": self.config.status_name(Status.BACKLOG),
            "role": Role.ARCHITECT.value,
            "completed": log.completed,
            "comment": comment,
        }

    def create_card(
        self,
        title: str,
        body: str,
        status: Status,
        role: Role,
        acting_role: Role,
    ) -> dict[str, Any]:
        """Create one Card in an explicit routing state.

        Distinct from intake: this is the architect's decomposition primitive,
        so it takes the destination (Status, Role) rather than assuming one.

        Because the caller names the destination, all three authority questions
        are asked here -- may this seat create work, may it put work *into* that
        Status, and may it place work in that seat's lane. Checking only the
        first would reopen the hole ARCHITECTURE.md Appendix A.2 decision 4 closed for
        ``transition_card``: an analyst refused ``promote_to_ready`` could still
        reach Ready by creating a Card there, and refused the `analyst -> dev`
        edge could still deposit one straight into the development lane.
        """
        policy.check_action("create_requirement_card", acting_role)
        policy.check_action(policy.action_for_transition(status), acting_role)
        # Creating a Card another seat owns *is* a handoff, decided before the
        # Card exists. Keeping it is not, so it must not trip the matrix.
        if role is not acting_role:
            policy.check_handoff(acting_role, role)
        title = title.strip()
        if not title:
            raise WorkflowError("card title must not be empty")
        if not body.strip():
            raise WorkflowError("card body must not be empty")

        log = MutationLog()
        try:
            issue_url = self.board.gh.run(
                ["issue", "create", "--repo", self.config.repo,
                 "--title", title, "--body", body.strip()]
            ).splitlines()[-1]
        except GitHubError as exc:
            return log.partial_result(
                "issue_created", str(exc), ["Nothing was created."]
            )
        match = re.search(r"/issues/(\d+)(?:\D|$)", issue_url)
        if not match:
            return log.partial_result(
                "issue_number_parsed",
                f"cannot parse Issue number from: {issue_url}",
                ["An Issue may exist; check before re-running."],
            )
        number = int(match.group(1))
        log.record("issue_created", issue=number, url=issue_url)

        try:
            payload = self.board.gh.json(
                ["project", "item-add", str(self.config.project_number),
                 "--owner", self.config.project_owner, "--url", issue_url,
                 "--format", "json"]
            )
            item_id = payload.get("id") if isinstance(payload, dict) else None
            if not item_id:
                raise GitHubError("gh project item-add did not return an item id")
        except GitHubError as exc:
            return log.partial_result(
                "project_item_added", str(exc),
                [f"Issue #{number} exists but is not on the Project.",
                 f"  gh project item-add {self.config.project_number} "
                 f"--owner {self.config.project_owner} --url {issue_url}"],
            )
        log.record("project_item_added", item_id=str(item_id))

        try:
            self.board.set_status(str(item_id), status)
        except (GitHubError, BoardError) as exc:
            return log.partial_result(
                "status_set", str(exc),
                [f"Set Status to {self.config.status_name(status)!r} manually."],
            )
        log.record("status_set", status=status.value)

        try:
            self.board.set_role(str(item_id), role)
        except (GitHubError, BoardError) as exc:
            return log.partial_result(
                "role_set", str(exc), [f"Set Role to `{role}` manually."]
            )
        log.record("role_set", role=role.value)

        return {
            "ok": True,
            "issue": number,
            "url": issue_url,
            "status": self.config.status_name(status),
            "role": role.value,
            "completed": log.completed,
        }

    def promote(
        self,
        number: int,
        spec_reference: str,
        acting_role: Role = Role.HUMAN,
        reason: str = "",
    ) -> dict[str, Any]:
        """Open the readiness gate on one shaped Card and send it to development.

        This is the human's routine. An agent seat shapes the Card and hands it
        to `human`; approving it into Ready is the first of the two human gates
        (ARCHITECTURE.md Appendix A.2 decision 6), so `promote_to_ready` refuses every
        artificial intelligence seat before anything here runs.

        Two independent semantic operations run in order: the Status
        transition, then the Role handoff. If the handoff fails, the Card is
        Ready but unowned, and the result says exactly that.
        """
        policy.check_action("promote_to_ready", acting_role)
        card = self.board.card(number)
        if card.role is not None and card.role is not acting_role:
            raise WorkflowError(
                f"Issue #{number} is owned by `{card.role}`, not `{acting_role}`"
            )
        policy.check_transition(card.status, Status.READY)

        gate = self.check_spec_gate(spec_reference)
        if not gate["satisfied"]:
            raise WorkflowError(gate["explanation"])

        log = MutationLog()
        try:
            self.board.transition_card(number, Status.READY, acting_role)
        except (GitHubError, BoardError) as exc:
            return log.partial_result(
                "status_set", str(exc),
                ["Nothing changed. Resolve the error and re-run promote."],
            )
        log.record("status_set", status=Status.READY.value, issue=number)

        try:
            handoff = self.board.handoff_card(
                number,
                acting_role,
                Role.DEV,
                reason=reason or "Specification is durable; implementation is Ready.",
                needs="Implement against the documented acceptance criteria.",
                artifacts=gate["reference"],
            )
        except PartialHandoff as exc:
            return exc.to_result(self.config.repo) | {
                "completed": log.completed + ["role_set"],
            }
        except (GitHubError, BoardError, policy.PolicyError) as exc:
            return log.partial_result(
                "role_set", str(exc),
                [
                    f"Issue #{number} is Ready but still owned by "
                    f"`{acting_role}`. Nothing will pick it up.",
                    f"  producer_board.py handoff {number} --from-role "
                    f"{acting_role} --to-role dev --note '<why>'",
                ],
            )
        log.record("role_set", role=Role.DEV.value)

        return {
            "ok": True,
            "issue": number,
            "url": card.url,
            "status": self.config.status_name(Status.READY),
            "role": Role.DEV.value,
            "spec": gate["reference"],
            "spec_state": gate["state"],
            "completed": log.completed,
            "comment": handoff["comment"],
        }

    def check_spec_gate(self, spec_reference: str) -> dict[str, Any]:
        """Decide whether a specification is durable enough to build against.

        Under the ``merged`` policy the specification must be on the target
        branch first, so development never implements against a document that
        review may still change. Under ``opened`` a linked Pull Request is
        enough and the path never blocks on a human.
        """
        reference = str(spec_reference or "").strip()
        if not reference:
            return {
                "satisfied": False,
                "state": None,
                "reference": "",
                "explanation": (
                    "promote requires a specification reference "
                    "(--spec <pr-url|#number|path>); a Card cannot become Ready "
                    "without a durable specification to build against"
                ),
            }

        number = _pr_number(reference)
        if number is None:
            # A path or plain pointer: it is durable by construction, since it
            # is already on the branch the caller is reading.
            return {
                "satisfied": True,
                "state": "pointer",
                "reference": reference,
                "explanation": "",
            }

        try:
            payload = self.board.gh.json(
                ["pr", "view", str(number), "--repo", self.config.repo,
                 "--json", "number,state,url,mergedAt"]
            )
        except GitHubError as exc:
            return {
                "satisfied": False,
                "state": None,
                "reference": reference,
                "explanation": f"cannot read specification Pull Request #{number}: {exc}",
            }

        state = str(payload.get("state") or "").upper()
        url = str(payload.get("url") or reference)
        merged = bool(payload.get("mergedAt")) or state == "MERGED"

        if not self.config.requires_merged_spec:
            if state == "CLOSED" and not merged:
                return {
                    "satisfied": False, "state": state, "reference": url,
                    "explanation": (
                        f"specification Pull Request #{number} was closed without "
                        f"merging; there is no durable specification to build against"
                    ),
                }
            return {"satisfied": True, "state": state, "reference": url, "explanation": ""}

        if merged:
            return {"satisfied": True, "state": "MERGED", "reference": url, "explanation": ""}
        return {
            "satisfied": False,
            "state": state,
            "reference": url,
            "explanation": (
                f"specification Pull Request #{number} is {state or 'not merged'}. "
                f"This board runs spec_completion=merged, so implementation "
                f"becomes Ready only after the specification is durable on the "
                f"target branch. Ask the human merge authority to review it, or "
                f"set spec_completion=opened if this repository accepts an open "
                f"specification."
            ),
        }

    def decompose(
        self,
        parent: int,
        children: Sequence[dict[str, str]],
        spec_reference: str,
        acting_role: Role = Role.ARCHITECT,
    ) -> dict[str, Any]:
        """Create flat implementation Cards from a durable specification.

        Deliberately flat: no parent/child protocol semantics are invented. The
        parent Card gets a summary comment linking what was created, which is
        the only relationship the board models.

        Children are created at ``(Backlog, human)``, not ``(Ready, dev)``. The
        architect decides what the slices *are*; the human decides whether each
        one is ready to build. Creating them past that gate would let
        decomposition do what `promote` is refused.
        """
        policy.check_action("split_implementation_work", acting_role)
        if not children:
            raise WorkflowError("decompose requires at least one child Card")

        gate = self.check_spec_gate(spec_reference)
        if not gate["satisfied"]:
            raise WorkflowError(gate["explanation"])

        self.board.card(parent)  # refuse early if the parent is not on the board

        created: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        for child in children:
            title = str(child.get("title", "")).strip()
            body = str(child.get("body", "")).strip()
            if not title or not body:
                failures.append({"title": title, "error": "title and body are required"})
                continue
            body = (
                f"{body}\n\n---\nSpecification: {gate['reference']}\n"
                f"Decomposed from #{parent}."
            )
            result = self.create_card(
                title, body, Status.BACKLOG, Role.HUMAN, acting_role
            )
            (created if result.get("ok") else failures).append(result)

        summary_lines = [
            f"Decomposed into {len(created)} implementation Card(s) against "
            f"{gate['reference']}. Each waits at (Backlog, human) for the "
            f"readiness decision:",
            "",
        ]
        summary_lines += [
            f"- #{entry['issue']} {entry.get('url', '')}" for entry in created
        ]
        if failures:
            summary_lines += ["", f"{len(failures)} Card(s) failed to create."]

        comment_posted = False
        if created:
            try:
                self.board.comment_on_card(parent, "\n".join(summary_lines))
                comment_posted = True
            except GitHubError:
                comment_posted = False

        return {
            "ok": not failures,
            "partial": bool(failures and created),
            "parent": parent,
            "spec": gate["reference"],
            "created": created,
            "failed": failures,
            "summary_comment_posted": comment_posted,
            "recovery": (
                [
                    f"{len(failures)} child Card(s) failed. The successful ones "
                    f"already exist -- re-run decompose with only the failed "
                    f"titles, or the board will carry duplicates.",
                ]
                if failures
                else []
            ),
        }

    def release_claim(
        self,
        number: int,
        branch: str,
        acting_role: Role = Role.HUMAN,
        reason: str = "",
    ) -> dict[str, Any]:
        """Release an abandoned claim: delete its branch, return the Card to Ready.

        Triage detects a stale claim and proposes this; running it is the
        human's, because the branch delete discards the claimant's lock and
        putting the Card back through Ready is the readiness decision again.
        The Card must actually be In Progress -- release-claim recovers
        abandoned work; it is not a side door past `promote`.

        Mutation order: branch delete -> Status -> comment. The branch goes
        first because the failure modes are asymmetric: a Ready Card whose dead
        branch survives collides with the next claimant, while an In Progress
        Card with no branch just waits for this command to be re-run.
        """
        policy.check_action("release_claim", acting_role)
        branch = str(branch or "").strip()
        if not branch:
            raise WorkflowError("release-claim requires --branch <claim-branch>")
        if branch in ("main", "master") or branch.startswith("refs/"):
            raise WorkflowError(
                f"refusing to delete {branch!r}; name the Card's claim branch, "
                f"never a mainline"
            )
        card = self.board.card(number)
        if card.status is not Status.IN_PROGRESS:
            raise WorkflowError(
                f"Issue #{number} is "
                f"{card.status.value if card.status else 'without a Status'}, not "
                f"In Progress. release-claim recovers abandoned claims only; for "
                f"the readiness gate use promote, which checks the specification."
            )

        log = MutationLog()
        try:
            self.board.gh.run(
                ["api", "-X", "DELETE",
                 f"repos/{self.config.repo}/git/refs/heads/{branch}"]
            )
        except GitHubError as exc:
            return log.partial_result(
                "branch_deleted", str(exc),
                [
                    "Nothing changed. If the branch is already gone, verify the "
                    "name against the Card's handoff comments; otherwise resolve "
                    "the error and re-run release-claim.",
                ],
            )
        log.record("branch_deleted", branch=branch, issue=number)

        try:
            self.board.transition_card(number, Status.READY, acting_role)
        except (GitHubError, BoardError, policy.PolicyError) as exc:
            return log.partial_result(
                "status_set", str(exc),
                [
                    f"Branch {branch!r} is deleted but Issue #{number} is still "
                    f"In Progress -- it looks claimed and no longer is.",
                    f"  producer_board.py transition {number} --to Ready "
                    f"--acting-role {acting_role}",
                    "Then post the release comment from the 'comment' field.",
                ],
            )
        log.record("status_set", status=Status.READY.value)

        comment = (
            f"Claim released by `{acting_role}`: branch `{branch}` deleted and "
            f"the Card returned to Ready for re-claim. "
            + (reason or "The claim was stale with no recorded progress.")
        )
        try:
            self.board.comment_on_card(number, comment)
        except GitHubError as exc:
            return log.partial_result(
                "release_comment", str(exc),
                [
                    "Branch and Status are already correct; do not change them.",
                    f"  gh issue comment {number} --repo {self.config.repo} "
                    f"--body-file <file>",
                    "The comment body is in the 'comment' field of this result.",
                ],
            ) | {"comment": comment}
        log.record("release_comment")

        result = {
            "ok": True,
            "issue": number,
            "url": card.url,
            "branch_deleted": branch,
            "status": self.config.status_name(Status.READY),
            "role": card.role.value if card.role else None,
            "completed": log.completed,
            "comment": comment,
        }
        if card.role not in self.config.dispatch_role_values:
            result["note"] = (
                f"Card Role is `{card.role.value if card.role else '(none)'}`, "
                f"which is not a dispatchable seat -- hand it to one or nothing "
                f"will pick it up."
            )
        return result

    def handoff(
        self,
        number: int,
        from_role: Role,
        to_role: Role,
        reason: str,
        needs: str = "",
        artifacts: str = "",
    ) -> dict[str, Any]:
        try:
            return self.board.handoff_card(
                number, from_role, to_role, reason, needs, artifacts
            )
        except PartialHandoff as exc:
            return exc.to_result(self.config.repo)

    def transition(
        self, number: int, target: Status, acting_role: Role
    ) -> dict[str, Any]:
        return self.board.transition_card(number, target, acting_role)


#: Which routines each seat may run in a Producer session.
_ROUTINES: dict[Role, list[str]] = {
    Role.ANALYST: ["intake"],
    Role.ARCHITECT: ["decompose", "create-card", "handoff"],
    Role.LEAD: ["brief", "triage", "dispatch", "handoff"],
    Role.QA: ["queue"],
    Role.HUMAN: ["brief", "list", "promote", "handoff"],
    Role.DEV: [],
}


#: ARCHITECTURE.md 9.5. The fixed body shape every governed delivery uses.
PR_SECTIONS = (
    "## Summary", "## Test Plan", "## Automated Verification",
    "## Human Verification TODO", "## Retro Notes",
)

#: Phrases that make a Human Verification item decoration. An item any
#: reviewer could write without reading the change has not identified work a
#: human must actually do, and a list of those trains the reader to skip the
#: section entirely.
_FILLER = (
    "check that it works", "verify it works", "make sure it works",
    "check it works", "test the feature", "looks good", "n/a", "none", "tbd",
)


def validate_pr_body(body: str) -> list[str]:
    """Every way this Pull Request body breaks the section 9.5 contract.

    All at once, not first-defect-wins: a Consumer correcting its delivery
    should learn everything the contract wants in one refusal.
    """
    problems: list[str] = []
    text = body or ""

    for section in PR_SECTIONS:
        if section not in text:
            problems.append(f"missing required section {section}")

    if "## Automated Verification" in text:
        segment = text.split("## Automated Verification", 1)[1]
        segment = segment.split("\n## ", 1)[0].strip()
        if not segment:
            problems.append(
                "## Automated Verification is empty; name the concrete "
                "commands, outputs, and specialist reviews that actually ran"
            )

    # GitHub honours Closes/Fixes/Resolves, case-insensitively. Accepting only
    # the canonical spelling would refuse a body GitHub handles correctly.
    if not re.search(r"\b(?:closes|fixes|resolves)\s+#\d+", text, re.I):
        problems.append(
            "missing the `Closes #<issue>` trailer (or `Fixes`/`Resolves`); "
            "without it GitHub will not close the Issue on merge"
        )

    if PR_MARKER not in text:
        problems.append(
            f"missing the {PR_MARKER} marker that identifies a governed delivery"
        )

    if "## Human Verification TODO" in text:
        segment = text.split("## Human Verification TODO", 1)[1].split("\n## ", 1)[0]
        for line in segment.splitlines():
            item = line.strip().lstrip("-*").strip().casefold().rstrip(".")
            if item and any(item == f or item.startswith(f) for f in _FILLER):
                problems.append(
                    f"filler Human Verification item: {line.strip()!r}. Every "
                    f"item must require genuine human judgment"
                )
    return problems


def acceptance_criteria_problems(card_body: str) -> list[str]:
    """Acceptance criteria that are not in a terminal state.

    A bare ``[ ]`` at submit time means the Card still claims work the
    delivery did not do. ``[!]`` waives an item, but a waiver with no reason
    is just a box nobody ticked.
    """
    problems: list[str] = []
    for line in (card_body or "").splitlines():
        stripped = line.strip()
        if re.match(r"^[-*]\s*\[\s\]", stripped):
            problems.append(f"acceptance criterion is still open: {stripped}")
        elif re.match(r"^[-*]\s*\[!\]", stripped):
            remainder = re.sub(r"^[-*]\s*\[!\]", "", stripped).strip()
            if len(remainder.split()) < 3:
                problems.append(
                    f"waived acceptance criterion has no reason: {stripped}"
                )
    return problems


class Consumer:
    """One Card, one stage. The Consumer half of ARCHITECTURE.md section 7.

    Every routine runs the same spine -- bind, preflight, optional claim,
    bounded work, one durable outcome, legal transition and handoff, stop.
    They differ in exactly two ways: whether the routine claims, and which
    durable outcome it produces. There is one lifecycle here, not three.
    """

    def __init__(self, config: Config, board: Board, git: Any = None):
        self.config = config
        self.board = board
        self.git = git if git is not None else Git(Path.cwd())

    # ---------------------------------------------------------- preflight

    def _bound_card(self, number: int, seat: Role, status: Status) -> Card:
        """Refuse anything but the exact expected pair, before any mutation.

        Live board state always overrides a stale dispatch snapshot
        (ARCHITECTURE.md 3.5), which is why this reads the Card rather than
        trusting the kickoff's stamped pair.
        """
        card = self.board.card(number)
        if card.status is not status:
            raise WorkflowError(
                f"#{number} is {card.routing_state}; this routine requires "
                f"({status}, {seat}). If a kickoff prompt said otherwise it is "
                f"stale -- live board state wins."
            )
        if card.role is not seat:
            raise WorkflowError(
                f"#{number} is owned by `{card.role or '-'}`, not `{seat}`; "
                f"re-read the board before acting"
            )
        return card

    def _worktree_for(self, card: Card) -> Path:
        return worktree_path(Path(self.config.workspace), card.number, card.title)

    # -------------------------------------------------------------- claim

    def claim(self, number: int, seat: Role) -> dict[str, Any]:
        """Reserve one Ready Card and open its isolated worktree.

        Claim first, Status second. The failure modes are asymmetric: a won
        claim with the Card still Ready simply waits for a re-run, but a Card
        moved to In Progress by a session that then lost the race has been
        mutated by a session that never owned it.
        """
        policy.check_action("claim_card", seat)
        card = self._bound_card(number, seat, Status.READY)

        log = MutationLog()
        try:
            claim = self.git.claim(number, card.title, seat.value)
        except ClaimRaceLost as exc:
            # Not a partial failure: nothing was written, so there is nothing
            # to recover and nothing to replay.
            return {
                "ok": False,
                "race_lost": True,
                "issue": number,
                "branch": exc.branch,
                "error": str(exc),
                "next": [
                    "Do not retry. Another session owns this Card.",
                    "Run `dispatch` to pick up different Ready work.",
                    "If the holder looks abandoned, triage can propose a "
                    "release-claim for the human to run.",
                ],
            }
        log.record("claim", branch=claim["branch"], claim_sha=claim["claim_sha"])

        target = self._worktree_for(card)
        try:
            tree = self.git.add_worktree(target, claim["branch"], claim["claim_sha"])
        except AgentTeamsError as exc:
            return log.partial_result(
                "worktree",
                str(exc),
                [
                    f"git worktree add {target} {claim['branch']}",
                    f'producer_board.py transition {number} --to "In Progress" '
                    f"--acting-role {seat}",
                ],
            )
        log.record("worktree", worktree=tree["worktree"], resumed=tree["resumed"])

        try:
            self.board.transition_card(number, Status.IN_PROGRESS, seat)
        except AgentTeamsError as exc:
            return log.partial_result(
                "transition",
                str(exc),
                [
                    f'producer_board.py transition {number} --to "In Progress" '
                    f"--acting-role {seat}"
                ],
            )
        log.record("transition")

        return {
            "ok": True,
            "issue": number,
            "url": card.url,
            "title": card.title,
            "status": Status.IN_PROGRESS.value,
            "role": seat.value,
            **log.artifacts,
        }

    # ------------------------------------------------------------- submit

    def submit(
        self, number: int, seat: Role, title: str, body: str
    ) -> dict[str, Any]:
        """Open or update exactly one Pull Request, then transition and hand off."""
        card = self._bound_card(number, seat, Status.IN_PROGRESS)

        problems = validate_pr_body(body)
        if problems:
            raise WorkflowError(
                "Pull Request body does not meet the delivery contract:\n  - "
                + "\n  - ".join(problems)
            )

        log = MutationLog()
        url = self.board.create_or_update_pull_request(
            number, card.title, title, body
        )
        log.record("pull_request", pull_request=url)

        note = f"Delivery ready for independent verification: {url}"
        recovery_handoff = (
            f"producer_board.py handoff {number} --from-role {seat} "
            f'--to-role qa --note "{note}"'
        )

        try:
            self.board.transition_card(number, Status.IN_REVIEW, seat)
        except AgentTeamsError as exc:
            # Never replays the Pull Request creation: that step has no
            # natural key to collide on, so a second call opens a second
            # Pull Request for one Card.
            return log.partial_result(
                "transition",
                str(exc),
                [
                    f'producer_board.py transition {number} --to "In Review" '
                    f"--acting-role {seat}",
                    recovery_handoff,
                ],
            )
        log.record("transition")

        try:
            self.board.handoff_card(
                number, seat, Role.QA, note,
                needs="verify against the acceptance criteria, then publish a "
                      "verdict bound to the current head",
                artifacts=url,
            )
        except PartialHandoff as exc:
            return exc.to_result(self.config.repo)
        except AgentTeamsError as exc:
            return log.partial_result("handoff", str(exc), [recovery_handoff])
        log.record("handoff")

        return {
            "ok": True,
            "issue": number,
            "url": card.url,
            "status": Status.IN_REVIEW.value,
            "role": Role.QA.value,
            **log.artifacts,
        }

    # ------------------------------------------------------------ verdict

    def verdict(self, number: int, verdict: Verdict) -> dict[str, Any]:
        """Publish review evidence for the exact current head.

        Deliberately performs no transition and no handoff. A verdict is
        evidence; the route is chosen by ``accept`` from deterministic
        policy. That separation is what stops a reviewer selecting its own
        outcome, and it is why this method cannot move the Card at all.
        """
        self._bound_card(number, Role.QA, Status.IN_REVIEW)
        policy.check_action("write_verdict", Role.QA)

        pr = self.board.pull_request(number)
        problems = policy.validate_verdict(
            verdict, pr["head_sha"], pr["changed_files"]
        )
        if problems:
            raise WorkflowError(
                "verdict cannot be published:\n  - " + "\n  - ".join(problems)
            )

        self.board.record_verdict(number, verdict)
        return {
            "ok": True,
            "issue": number,
            "verdict": verdict.verdict,
            "head_sha": verdict.head_sha,
            "pull_request": pr["url"],
            "next": [f"producer_board.py accept {number}"],
        }

    # ------------------------------------------------------------- accept

    def accept(self, number: int) -> dict[str, Any]:
        """Evaluate one reviewed delivery and execute the deterministic route.

        The caller supplies an Issue number and nothing else. Every other
        input is read from live GitHub state and the route comes from
        ``policy.evaluate_acceptance``, so no session can steer its own
        outcome -- there is no argument through which it could.
        """
        card = self._bound_card(number, Role.QA, Status.IN_REVIEW)

        verdict = self.board.latest_verdict(number)
        if verdict is None:
            raise WorkflowError(
                f"#{number} has no parseable verdict. Publish one with "
                f"`producer_board.py verdict {number} --evidence-file ...` "
                f"before accepting."
            )

        pr = self.board.pull_request(number)
        problems = policy.validate_verdict(
            verdict, pr["head_sha"], pr["changed_files"]
        )
        if problems:
            raise WorkflowError(
                "cannot accept on this evidence:\n  - " + "\n  - ".join(problems)
            )

        result = policy.evaluate_acceptance(verdict, pr, self.config)
        self.board.record_acceptance(number, result)

        base = {
            "ok": True,
            "issue": number,
            "url": card.url,
            "acceptance": result.acceptance,
            "head_sha": result.head_sha,
            "policy_version": result.policy_version,
            "reasons": list(result.reasons),
            "pull_request": pr["url"],
        }

        if result.acceptance == "eligible":
            self.board.arm_auto_merge(pr["number"], self.config.merge_method)

            # Eligibility already required every configured check to be
            # SUCCESS, so `--auto` normally merges at once. Re-read rather
            # than assume: armed is not merged, and Done must never be
            # reached on an assumption.
            state = self.board.merge_state(pr["number"])
            if str(state.get("state", "")).upper() == "MERGED":
                return {
                    **base,
                    "merge": "merged",
                    **self._reconcile_to_done(number, card, pr, state, Role.LEAD),
                }

            return {
                **base,
                "status": Status.IN_REVIEW.value,
                "role": Role.QA.value,
                "merge": "armed",
                "next": [
                    "GitHub merges this head once the required checks pass on "
                    "the current base, and disarms if a new commit lands.",
                    f"When the merge confirms: producer_board.py "
                    f"reconcile-done {number}",
                ],
            }

        if result.acceptance == "defect":
            log = MutationLog()
            note = "Verification found a defect: " + "; ".join(result.reasons)
            recovery = [
                f'producer_board.py transition {number} --to "In Progress" '
                f"--acting-role qa",
                f"producer_board.py handoff {number} --from-role qa "
                f'--to-role dev --note "{note}"',
            ]
            try:
                self.board.transition_card(number, Status.IN_PROGRESS, Role.QA)
                log.record("transition")
                self.board.handoff_card(
                    number, Role.QA, Role.DEV, note,
                    needs="correct the finding on the same branch and Pull Request",
                    artifacts=pr["url"],
                )
            except PartialHandoff as exc:
                return exc.to_result(self.config.repo)
            except AgentTeamsError as exc:
                return log.partial_result("route", str(exc), recovery)
            return {
                **base,
                "status": Status.IN_PROGRESS.value,
                "role": Role.DEV.value,
            }

        note = "Protected change requires human review: " + "; ".join(result.reasons)
        try:
            self.board.handoff_card(
                number, Role.QA, Role.HUMAN, note,
                needs="review the protected change and decide",
                artifacts=pr["url"],
            )
        except PartialHandoff as exc:
            return exc.to_result(self.config.repo)
        return {
            **base,
            "status": Status.IN_REVIEW.value,
            "role": Role.HUMAN.value,
        }

    # ---------------------------------------------------------- reconcile

    def _reconcile_to_done(
        self, number: int, card: Card, pr: dict[str, Any],
        state: Mapping[str, Any], acting_role: Role,
    ) -> dict[str, Any]:
        """Move a merged delivery to `(Done, lead)` and clean its claim.

        Shared by ``accept`` -- which completes the eligible route in one go
        when the merge has already landed -- and ``reconcile`` for the case
        where the platform merged later. Callers must have confirmed MERGED
        first; this method records a merge, it never causes one.

        The reconciliation is recorded as `lead` because the Tech Lead owns
        returning completed work to the board. That is not a seat electing to
        act: this path opens only behind a deterministic `eligible` result
        plus a confirmed merge, and `Done` is unreachable without both.
        """
        log = MutationLog()
        try:
            self.board.transition_card(number, Status.DONE, acting_role)
            log.record("transition")
            if card.role is not Role.LEAD:
                self.board.handoff_card(
                    number, card.role or Role.QA, Role.LEAD,
                    f"merged as {state.get('merge_commit') or 'a confirmed merge'}",
                    artifacts=pr["url"],
                )
                log.record("handoff")
        except PartialHandoff as exc:
            return exc.to_result(self.config.repo)
        except AgentTeamsError as exc:
            return log.partial_result(
                "reconcile",
                str(exc),
                [
                    f"producer_board.py transition {number} --to Done "
                    f"--acting-role {acting_role}"
                ],
            )

        # Cleanup last, and never fatal. The Card reaching Done is the durable
        # outcome; a worktree holding unsaved work is reported for a human to
        # resolve rather than forced.
        target = self._worktree_for(card)
        try:
            cleanup = self.git.remove_worktree(target)
        except AgentTeamsError as exc:
            cleanup = {
                "ok": False,
                "worktree": str(target),
                "error": str(exc),
                "recovery": [
                    f"Inspect {target}, save anything you need, then run: "
                    f"git worktree remove {target} --force"
                ],
            }

        return {
            "status": Status.DONE.value,
            "role": Role.LEAD.value,
            "merge_commit": state.get("merge_commit"),
            "cleanup": cleanup,
        }

    def reconcile(self, number: int, acting_role: Role) -> dict[str, Any]:
        """Close out a merge that landed after `accept` armed it.

        `accept` completes the eligible route itself when the merge is already
        visible. This exists for the case where the platform merged later --
        a slow required check, or a queue.
        """
        policy.check_action("reconcile_done", acting_role)
        card = self.board.card(number)
        if card.status is not Status.IN_REVIEW:
            raise WorkflowError(
                f"#{number} is {card.routing_state}; reconciliation applies to "
                f"a Card in In Review whose Pull Request has merged"
            )

        pr = self.board.pull_request(number)
        state = self.board.merge_state(pr["number"])
        if str(state.get("state", "")).upper() != "MERGED":
            raise WorkflowError(
                f"the Pull Request for #{number} is not merged (state "
                f"{state.get('state') or 'unknown'}). Reconciliation records a "
                f"merge that happened; it never causes one."
            )

        outcome = self._reconcile_to_done(number, card, pr, state, acting_role)
        if not outcome.get("status"):  # partial-failure envelope
            return outcome
        return {"ok": True, "issue": number, "url": card.url, **outcome}

    # -------------------------------------------------------- observation

    def worktree_status(self, number: int | None = None) -> dict[str, Any]:
        """Read-only claim and worktree inventory. Mutates nothing.

        This is the input stale-claim detection has been waiting on: it could
        not exist until claims did (ARCHITECTURE.md 11.7).
        """
        if number is not None:
            cards = [self.board.card(number)]
        else:
            cards = [
                card for card in self.board.cards()
                if card.status is Status.IN_PROGRESS
            ]
        known = {
            Path(entry["worktree"]).resolve()
            for entry in self.git.worktrees()
            if entry.get("worktree")
        }
        claims = []
        for card in cards:
            target = self._worktree_for(card)
            claims.append(
                {
                    "issue": card.number,
                    "title": card.title,
                    "routing_state": card.routing_state,
                    "branch": claim_branch(card.number, card.title),
                    "worktree": str(target),
                    "worktree_present": target.resolve() in known,
                }
            )
        return {
            "ok": True,
            "claim_ttl_hours": self.config.claim_ttl_hours,
            "claims": claims,
        }


def _data_quality_problem(card: Card) -> str | None:
    if card.status is None and card.role is None:
        return "no Status and no Role; this Card is invisible to every routine"
    if card.status is None:
        return "no Status; it cannot be counted in work in progress"
    if card.role is None and card.status is not Status.DONE:
        return "no Role; nothing will pick it up"
    return None


def _kickoff(seat: Role | None, card: Card) -> str:
    """A carrier-neutral prompt. Rendering one is not starting a session.

    The expected ``(Status, Role)`` pair is stamped into the prompt so the
    receiving session has something to compare against the live board -- a
    kickoff whose pair no longer matches is stale, and the session should say
    so and stop rather than work from it.
    """
    role = seat.value if seat else "?"
    status = card.status.value if card.status else "?"
    return (
        f"[role:{role}] [board-card:#{card.number}] "
        f"[expected:({status}, {role})] "
        f'Work on "{card.title}". Read the Card and its comments first, verify '
        f"the Card still matches the expected pair, and do not change another "
        f"Card."
    )
