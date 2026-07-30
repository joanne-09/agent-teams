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
from typing import Any, Iterable, Sequence

from . import policy
from .board import Board, BoardError, PartialHandoff
from .config import Config
from .github import GitHubError
from .model import Card, Handoff, MutationLog, Role, Status

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
        if seat is Role.EM:
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
        """Cards grouped by Role lane, then Status -- the EM's primary view."""
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
        """The Engineering Manager's whole-team briefing.

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
        reach Ready by creating a Card there, and refused the `analyst -> rd`
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
                Role.RD,
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
                    f"{acting_role} --to-role rd --note '<why>'",
                ],
            )
        log.record("role_set", role=Role.RD.value)

        return {
            "ok": True,
            "issue": number,
            "url": card.url,
            "status": self.config.status_name(Status.READY),
            "role": Role.RD.value,
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

        Children are created at ``(Backlog, human)``, not ``(Ready, rd)``. The
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
    Role.EM: ["brief", "triage", "dispatch", "handoff"],
    Role.QA: ["queue"],
    Role.HUMAN: ["brief", "list", "promote", "handoff"],
    Role.RD: [],
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
    """A carrier-neutral prompt. Rendering one is not starting a session."""
    role = seat.value if seat else "?"
    return (
        f"[role:{role}] [board-card:#{card.number}] "
        f'Work on "{card.title}". Read the Card and its comments first, and do '
        f"not change another Card."
    )
