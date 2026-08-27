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

import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from . import policy
from .board import Board, BoardError, PartialHandoff
from .config import Config
from .git import ClaimRaceLost, Git, claim_branch, worktree_path
from .github import GitHubError
from .model import (
    Acceptance, Card, CLARIFICATION_MARKER, DECOMPOSED_CHILD_MARKER,
    DECOMPOSITION_MARKER, Handoff, MutationLog, PR_MARKER, Role,
    SPECIFICATION_MARKER, Status, Verdict,
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

    def __init__(self, config: Config, board: Board, git: Any = None):
        self.config = config
        self.board = board
        self.git = git if git is not None else Git(Path.cwd())

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
            "config_revision": self.config.revision,
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
            "focus": "readiness and exceptional protected or ambiguous QA",
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
            "awaiting_readiness": [
                card.to_dict() for card in cards
                if card.status is Status.BACKLOG and card.role is Role.HUMAN
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
        readiness = [
            card for card in cards
            if card.status is Status.BACKLOG and card.role is Role.HUMAN
        ]
        if readiness:
            oldest = min(readiness, key=lambda card: card.number)
            return (
                f"Readiness gate: #{oldest.number} is specified and waiting for "
                f"your Ready decision."
            )
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

    def next_actions(self, number: int | None = None) -> dict[str, Any]:
        """Plan every runnable stage for a current-session subagent carrier.

        This is read-only. It separates runnable work from the allowed gates so
        a coordinator can keep independent Cards moving while never acting
        as ``human``. Each spawn action binds exactly one Card and stage.
        """
        all_cards = self.board.cards()
        cards = all_cards
        if number is not None:
            cards = [card for card in cards if card.number == number]
            if not cards:
                raise WorkflowError(f"Issue #{number} is not on the configured Project")

        actions: list[dict[str, Any]] = []
        human_gates: list[dict[str, Any]] = []
        waiting: list[dict[str, Any]] = []

        configured = self.config.dispatch_role_values
        role_rank = {role: index for index, role in enumerate(configured)}
        cards_by_number = {card.number: card for card in all_cards}
        dependency_waits: dict[int, tuple[int, ...]] = {}
        ready_candidates = [
            card for card in cards
            if card.status is Status.READY
            and card.role in (Role.DEV, Role.ARCHITECT)
            and card.role in role_rank
        ]
        for candidate in ready_candidates:
            unmet = tuple(
                dependency for dependency in self.board.hard_dependencies(
                    candidate.number
                )
                if dependency not in cards_by_number
                or cards_by_number[dependency].status is not Status.DONE
            )
            if unmet:
                dependency_waits[candidate.number] = unmet
        ready = sorted(
            (card for card in ready_candidates if card.number not in dependency_waits),
            key=lambda card: (role_rank[card.role], card.number),
        )
        if self.config.wip_limit == 0:
            ready_selected = {card.number for card in ready}
        else:
            slots = max(0, self.config.wip_limit - policy.wip_count(all_cards))
            ready_selected = {card.number for card in ready[:slots]}
        architect_authoring_started = False

        for card in sorted(cards, key=lambda item: item.number):
            base = card.to_dict() | {"routing_state": card.routing_state}
            if card.status is Status.BACKLOG and card.role is Role.HUMAN:
                spec = self.board.latest_specification(card.number)
                if spec:
                    human_gates.append({
                        **base, "gate": "readiness", "specification": spec,
                        "instruction": "Move the Card Status to Ready.",
                        "field": self.config.status_field,
                        "value": self.config.status_name(Status.READY),
                        "cli_convenience": f"promote {card.number}",
                    })
                else:
                    waiting.append({
                        **base, "reason": "Card is in the human lane without a "
                        "structured durable specification record; it is not "
                        "ready for approval",
                    })
                continue
            if card.status is Status.READY and card.role is Role.HUMAN:
                spec = self.board.latest_specification(card.number)
                gate = self.check_spec_gate(spec["path"]) if spec else None
                if (spec and gate and gate["satisfied"]
                        and gate.get("commit") == spec.get("commit")):
                    actions.append({
                        **base, "kind": "controller", "role": Role.LEAD.value,
                        "routine": "finalize-readiness",
                        "argv": ["finalize-readiness", str(card.number)],
                        "reason": "the human opened the readiness gate by moving "
                                  "the specified Card to Ready; ownership handoff "
                                  "to dev is deterministic",
                    })
                else:
                    waiting.append({
                        **base, "reason": "Card was moved to Ready without a "
                        "current durable specification record",
                    })
                continue
            if card.status is Status.IN_REVIEW and card.role is Role.HUMAN:
                acceptance = self.board.latest_acceptance(card.number)
                if acceptance and acceptance.acceptance == "protected_change":
                    pr = self.board.pull_request(card.number, card.title)
                    if acceptance.head_sha == pr["head_sha"]:
                        human_gates.append({
                            **base, "gate": "qa_exception",
                            "acceptance": acceptance.to_dict(),
                            "pull_request": pr["url"],
                            "command": f"approve-exception {card.number}",
                        })
                    else:
                        actions.append({
                            **base, "kind": "controller", "role": Role.QA.value,
                            "routine": "refresh-verification",
                            "argv": ["refresh-verification", str(card.number)],
                            "reason": "protected-change evidence is stale because "
                            "the Pull Request head changed",
                        })
                else:
                    waiting.append({
                        **base, "reason": "Card is in the human QA lane without a "
                        "protected-change acceptance record",
                    })
                continue
            if card.status is Status.BACKLOG and card.role is Role.ARCHITECT:
                specification = self.board.latest_specification(card.number)
                if (
                    specification
                    and specification.get("mode") == "manual"
                    and specification.get("state") != "MERGED"
                ):
                    try:
                        spec_pr = self.board.specification_pull_request(
                            str(specification.get("pull_request") or "")
                        )
                    except AgentTeamsError as exc:
                        waiting.append({
                            **base,
                            "reason": "cannot inspect the recorded specification "
                            f"Pull Request: {exc}",
                        })
                        continue
                    if spec_pr["head_sha"] != specification.get("commit"):
                        waiting.append({
                            **base,
                            "reason": "specification Pull Request head no longer "
                            "matches the exact commit recorded on the Card; the "
                            "architect must publish a fresh record",
                        })
                    elif spec_pr["merged"]:
                        actions.append({
                            **base,
                            "kind": "controller",
                            "role": Role.LEAD.value,
                            "routine": "finalize-spec-merge",
                            "argv": ["finalize-spec-merge", str(card.number)],
                            "reason": "the user merged the exact recorded "
                            "specification head; sync the base and record its "
                            "durable base-branch commit",
                        })
                    elif spec_pr["state"] == "OPEN":
                        human_gates.append({
                            **base,
                            "gate": "spec_merge",
                            "specification": specification,
                            "pull_request": spec_pr["url"],
                            "instruction": "Merge the specification Pull Request.",
                        })
                    else:
                        waiting.append({
                            **base,
                            "reason": "specification Pull Request is closed "
                            "without a confirmed merge",
                        })
                    continue
                if (specification and
                        self.board.decomposition_complete(card.number)):
                    waiting.append({
                        **base,
                        "reason": "specification is published and decomposition "
                                  "is complete; implementation children carry "
                                  "their own readiness gates",
                    })
                    continue
                if architect_authoring_started:
                    waiting.append({
                        **base, "reason": "specification authoring is serialized "
                        "because all spec workers share the current "
                        "checkout",
                    })
                else:
                    if self.config.effective_spec_pr_merge_mode() == "manual":
                        prompt = (
                            "Write the specification under docs/ and publish it "
                            "with publish-spec. The configured manual mode creates "
                            "a specification Pull Request; stop after publishing "
                            "and wait for the user to merge it."
                        )
                    else:
                        prompt = (
                            "Write the specification directly under docs/, publish "
                            "it with publish-spec, then decompose or hand the Card "
                            "to the human readiness gate. Create no spec branch or "
                            "Pull Request."
                        )
                    actions.append(_spawn_action(
                        card, Role.ARCHITECT, "authoring-spec",
                        prompt,
                    ))
                    architect_authoring_started = True
                continue
            if card.status is Status.BACKLOG and card.role is Role.ANALYST:
                actions.append(_spawn_action(
                    card, Role.ANALYST, "clarifying-card",
                    "This Card already exists. Resolve its remaining requirement "
                    "question through research, record the answer with clarify, "
                    "then hand the same Card to architect. Never run intake or "
                    "create a replacement Issue.",
                ))
                continue
            if card.status is Status.BLOCKED:
                actions.append(_spawn_action(
                    card, Role.LEAD, "triaging-board",
                    "Resolve this one blocker through repository evidence and "
                    "bounded research. Route the same Card back to its legal "
                    "working state when resolved. Do not ask the human to carry "
                    "a prompt or run mechanical recovery; if an external fact is "
                    "genuinely unavailable, record the durable blocker and stop.",
                ))
                continue
            if card.status is Status.READY and card.role in (Role.DEV, Role.ARCHITECT):
                if card.role not in role_rank:
                    waiting.append({
                        **base, "reason": f"role `{card.role}` is not in configured "
                        "dispatch_roles",
                    })
                elif card.number in dependency_waits:
                    waiting.append({
                        **base, "reason": "hard dependencies are not Done: "
                        + ", ".join(
                            f"#{number}" for number in dependency_waits[card.number]
                        ),
                        "dependencies": list(dependency_waits[card.number]),
                    })
                elif card.number not in ready_selected:
                    waiting.append({
                        **base, "reason": "starting this Card would exceed the "
                        f"work-in-progress limit of {self.config.wip_limit}",
                    })
                else:
                    actions.append(_spawn_action(
                        card, card.role, "consuming-card",
                        "Claim and deliver this Card through exactly one Pull Request.",
                    ))
                continue
            if card.status is Status.IN_PROGRESS and card.role in (Role.DEV, Role.ARCHITECT):
                actions.append(_spawn_action(
                    card, card.role, "consuming-card",
                    "Resume the existing claim, worktree, branch, and Pull Request; "
                    "do not claim again or create a second delivery.",
                ))
                continue
            if card.status is Status.IN_REVIEW and card.role is Role.QA:
                accepted = self.board.latest_acceptance(card.number)
                if accepted:
                    pr = self.board.pull_request(card.number, card.title)
                    if accepted.head_sha != pr["head_sha"]:
                        actions.append(_spawn_action(
                            card, Role.QA, "verifying-delivery",
                            "The Pull Request head changed after acceptance. Review "
                            "the current head and publish fresh evidence before any "
                            "merge or reconciliation.",
                        ))
                    elif accepted.acceptance != "eligible":
                        actions.append({
                            **base, "kind": "controller", "role": Role.QA.value,
                            "routine": "accept", "argv": ["accept", str(card.number)],
                            "reason": "acceptance was recorded but its deterministic "
                            "route did not complete",
                        })
                    else:
                        state = self.board.merge_state(pr["number"])
                        if str(state.get("state", "")).upper() == "MERGED":
                            actions.append({
                                **base, "kind": "reconcile", "role": Role.LEAD.value,
                                "routine": "reconcile-done",
                                "argv": ["reconcile-done", str(card.number)],
                            })
                        elif self.config.effective_code_pr_merge_mode() == "manual":
                            human_gates.append({
                                **base,
                                "gate": "manual_merge",
                                "acceptance": accepted.to_dict(),
                                "pull_request": pr["url"],
                                "instruction": "Merge the eligible Pull Request.",
                                "reason": "merge_mode is manual; the controller "
                                "will not issue a merge command",
                            })
                        elif pr["auto_merge_enabled"]:
                            actions.append({
                                **base, "kind": "monitor", "role": Role.LEAD.value,
                                "routine": "observe-auto-merge",
                                "poll_after_seconds":
                                    self.config.monitor_poll_seconds,
                                "reason": "exact reviewed head is queued for "
                                "GitHub auto-merge",
                            })
                        else:
                            actions.append({
                                **base, "kind": "controller", "role": Role.QA.value,
                                "routine": "accept", "argv": ["accept", str(card.number)],
                                "reason": "eligible acceptance exists but auto-merge "
                                "is not armed; retry the deterministic route",
                            })
                else:
                    verdict = self.board.latest_verdict(card.number)
                    if verdict:
                        pr = self.board.pull_request(card.number, card.title)
                        problems = policy.validate_verdict(
                            verdict, pr["head_sha"], pr["changed_files"],
                            config=self.config,
                        )
                    else:
                        pr, problems = None, ["no verdict"]
                    if verdict and not problems:
                        transient = policy.acceptance_wait_reasons(
                            verdict, pr, self.config
                        )
                        if transient:
                            actions.append({
                                **base, "kind": "monitor",
                                "role": Role.LEAD.value,
                                "routine": "observe-pr-readiness",
                                "poll_after_seconds":
                                    self.config.monitor_poll_seconds,
                                "reason": "; ".join(transient),
                            })
                        else:
                            actions.append({
                                **base, "kind": "controller",
                                "role": Role.QA.value, "routine": "accept",
                                "argv": ["accept", str(card.number)],
                                "reason": "current-head verdict is complete; run "
                                          "the deterministic route",
                            })
                    else:
                        actions.append(_spawn_action(
                            card, Role.QA, "verifying-delivery",
                            "Independently review the current Pull Request head, "
                            "publish the structured verdict, and run deterministic "
                            "acceptance.",
                        ))
                continue
            if card.status not in (Status.DONE,):
                waiting.append({**base, "reason": "no automatic stage is legal"})

        actions.sort(key=lambda entry: (
            role_rank.get(Role.parse(entry["role"]), len(role_rank)),
            entry["number"], entry["routine"],
        ))

        # Stamp each action with the schedule of the seat that will run it.
        # Done here rather than at each construction site so no action shape
        # can be added later that quietly inherits the global budget instead.
        for entry in actions:
            try:
                schedule = self.config.recovery_for(entry["role"])
            except ValueError:  # a seat with no tunable configuration
                continue
            entry["recovery"] = schedule.runtime_dict()
        return {
            "ok": True,
            "config_revision": self.config.revision,
            # Default plus every seat. A coordinator holding one global budget
            # could not honour "the architect gets two attempts, QA gets
            # three"; each spawn action additionally carries its own resolved
            # schedule so the retry rule travels with the work.
            "recovery_policy": self.config.recovery_policy_dict(),
            "actions": actions,
            "human_gates": human_gates,
            "waiting": waiting,
        }

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
        if status is Status.DONE:
            raise WorkflowError(
                "a Card cannot be created Done; completion requires an "
                "exact-head acceptance and confirmed merge"
            )
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

    def clarify(
        self, number: int, note: str, acting_role: Role = Role.ANALYST
    ) -> dict[str, Any]:
        """Resolve a returned requirement on its existing Card."""
        policy.check_handoff(acting_role, Role.ARCHITECT)
        card = self.board.card(number)
        if card.status is not Status.BACKLOG or card.role is not acting_role:
            raise WorkflowError(
                f"#{number} is {card.routing_state}; clarification requires "
                f"(Backlog, {acting_role})"
            )
        note = note.strip()
        if not note:
            raise WorkflowError("clarification note must not be empty")

        log = MutationLog()
        comment = CLARIFICATION_MARKER + "\n\n" + note
        try:
            self.board.comment_on_card(number, comment)
        except AgentTeamsError as exc:
            return log.partial_result(
                "clarification_comment", str(exc), ["Nothing changed; retry clarify."]
            )
        log.record("clarification_comment", issue=number, comment=comment)
        try:
            handoff = self.board.handoff_card(
                number, acting_role, Role.ARCHITECT,
                "Requirement clarification recorded on the existing Card.",
                needs="resume specification authoring from the new clarification",
                artifacts=card.url,
            )
        except PartialHandoff as exc:
            result = exc.to_result(self.config.repo)
            result["completed"] = log.completed + result["completed"]
            result["clarification_comment"] = comment
            return result
        except AgentTeamsError as exc:
            return log.partial_result(
                "handoff", str(exc),
                [f"Clarification is recorded; hand #{number} from analyst to architect."],
            )
        return {
            "ok": True, "issue": number, "status": Status.BACKLOG.value,
            "role": Role.ARCHITECT.value,
            "completed": log.completed + ["handoff"],
            "comment": comment, "handoff": handoff["comment"],
        }

    def promote(
        self,
        number: int,
        spec_reference: str = "",
        acting_role: Role = Role.HUMAN,
        reason: str = "",
    ) -> dict[str, Any]:
        """Open the readiness gate on one shaped Card and send it to development.

        This is the human's routine. An agent seat shapes the Card and hands it
        to `human`; approving it into Ready is the mandatory lifecycle gate
        (ARCHITECTURE.md Appendix A.2 decision 6), so `promote_to_ready` refuses
        every artificial intelligence seat before anything here runs.

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

        recorded = self.board.latest_specification(number)
        if recorded is None:
            raise WorkflowError(
                f"Issue #{number} has no published durable specification. "
                f"The architect must run publish-spec before the Ready decision."
            )
        reference = str(spec_reference or recorded["path"]).strip()
        if reference != recorded["path"]:
            raise WorkflowError(
                f"the Card records specification `{recorded['path']}`, not `{reference}`"
            )
        gate = self.check_spec_gate(reference)
        if not gate["satisfied"]:
            raise WorkflowError(gate["explanation"])
        if gate.get("commit") != recorded.get("commit"):
            raise WorkflowError(
                f"specification `{reference}` changed after it was recorded on the "
                f"Card; the architect must run publish-spec again"
            )

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

    def finalize_readiness(self, number: int) -> dict[str, Any]:
        """Complete the deterministic half of a human Status-to-Ready decision."""
        card = self.board.card(number)
        if card.status is not Status.READY or card.role is not Role.HUMAN:
            raise WorkflowError(
                f"#{number} is {card.routing_state}; readiness finalization "
                "requires the human to have moved a specified Card to Ready"
            )
        recorded = self.board.latest_specification(number)
        if recorded is None:
            raise WorkflowError(
                f"#{number} has no durable specification record"
            )
        gate = self.check_spec_gate(recorded["path"])
        if not gate["satisfied"] or gate.get("commit") != recorded.get("commit"):
            raise WorkflowError(
                "the recorded specification is not the current committed "
                "specification; return the Card to Backlog for architect repair"
            )
        try:
            handoff = self.board.handoff_card(
                number, Role.HUMAN, Role.DEV,
                "The human moved the specified Card to Ready.",
                needs="implement against the recorded acceptance criteria",
                artifacts=gate["reference"],
            )
        except PartialHandoff as exc:
            return exc.to_result(self.config.repo)
        return {
            "ok": True, "issue": number, "status": Status.READY.value,
            "role": Role.DEV.value, "spec": gate["reference"],
            "comment": handoff["comment"],
        }

    def check_spec_gate(self, spec_reference: str) -> dict[str, Any]:
        """Decide whether a specification is durable enough to build against.

        Both publication modes must first place the document on the recorded
        base branch, so development never implements against a review head that
        may still change.
        """
        reference = str(spec_reference or "").strip()
        if not reference:
            return {
                "satisfied": False,
                "state": None,
                "reference": "",
                "explanation": (
                    "promote requires a specification reference "
                    "(--spec docs/...md); a Card cannot become Ready "
                    "without a durable specification to build against"
                ),
            }

        if _pr_number(reference) is not None:
            return {
                "satisfied": False, "state": "PULL_REQUEST",
                "reference": reference,
                "explanation": "a specification Pull Request is not a readiness "
                               "artifact; wait for its configured publication "
                               "route to place the docs/*.md path on the base "
                               "branch and record that durable commit",
            }
        try:
            artifact = self.git.specification(reference)
        except AgentTeamsError as exc:
            return {
                "satisfied": False, "state": None, "reference": reference,
                "explanation": str(exc),
            }
        return {
            "satisfied": True, "state": artifact["state"],
            "reference": artifact["path"], "commit": artifact["commit"],
            "explanation": "",
        }

    def publish_specification(
        self, number: int, reference: str,
        acting_role: Role = Role.ARCHITECT,
    ) -> dict[str, Any]:
        """Publish one specification through the configured durable route."""
        policy.check_action("publish_specification", acting_role)
        card = self.board.card(number)
        if card.status is not Status.BACKLOG or card.role is not acting_role:
            raise WorkflowError(
                f"#{number} is {card.routing_state}; specification "
                f"publication requires (Backlog, {acting_role})"
            )

        if self.config.effective_spec_pr_merge_mode() == "manual":
            artifact = self.git.publish_specification_for_review(
                number, card.title, reference
            )
            pr_title = f"spec: #{number} {card.title}"
            pr_body = (
                f"Specification for #{number}.\n\n"
                f"- Path: `{artifact['path']}`\n"
                f"- Exact review head: `{artifact['commit']}`\n"
                f"- Base: `{artifact['base_branch']}`\n\n"
                "Merge this Pull Request to make the specification durable; "
                "the coordinator will verify and record the base-branch commit."
            )
            try:
                pull_request = self.board.create_or_update_specification_pull_request(
                    artifact["branch"], artifact["base_branch"], pr_title, pr_body
                )
            except AgentTeamsError as exc:
                return {
                    "ok": False,
                    "partial": True,
                    "issue": number,
                    "completed": ["specification_branch_pushed"],
                    "failed": "specification_pull_request",
                    "error": str(exc),
                    "specification": artifact,
                    "recovery": [
                        f"Create one Pull Request from `{artifact['branch']}` "
                        f"to `{artifact['base_branch']}`, then record its URL "
                        f"and this exact commit on Card #{number}.",
                        "Do not rerun publish-spec blindly; the review branch "
                        "already owns the specification content.",
                    ],
                }
            record = {
                "card": number,
                "path": artifact["path"],
                "commit": artifact["commit"],
                "branch": artifact["branch"],
                "base_branch": artifact["base_branch"],
                "mode": "manual",
                "state": "OPEN",
                "pull_request": pull_request,
            }
            completed = [
                "specification_branch_pushed", "specification_pull_request"
            ]
        else:
            artifact = self.git.publish_specification(number, card.title, reference)
            record = {
                "card": number, "path": artifact["path"],
                "commit": artifact["commit"], "branch": artifact["branch"],
                "mode": "direct", "state": "TRACKED",
            }
            completed = ["specification_committed", "specification_pushed"]

        try:
            self.board.record_specification(number, record)
        except AgentTeamsError as exc:
            return {
                "ok": False, "partial": True, "issue": number,
                "completed": completed,
                "failed": "card_record", "error": str(exc),
                "specification": record,
                "recovery": [
                    f"Record the exact `specification` object from this result "
                    f"on Card #{number}.",
                    "Do not replay completed branch, Pull Request, or push mutations.",
                ],
            }
        return {
            "ok": True,
            "issue": number,
            "specification": record,
            "next": (
                ["Wait for the user to merge the specification Pull Request."]
                if record["mode"] == "manual"
                else ["Decompose the work or hand the Card to readiness."]
            ),
        }

    def finalize_specification_merge(self, number: int) -> dict[str, Any]:
        """Sync and record a user-merged specification exact head."""
        card = self.board.card(number)
        if card.status is not Status.BACKLOG or card.role is not Role.ARCHITECT:
            raise WorkflowError(
                f"#{number} is {card.routing_state}; specification merge "
                "finalization requires (Backlog, architect)"
            )
        recorded = self.board.latest_specification(number)
        if not recorded or recorded.get("mode") != "manual":
            raise WorkflowError(
                f"#{number} has no manual specification Pull Request record"
            )
        pull_request = str(recorded.get("pull_request") or "").strip()
        base_branch = str(recorded.get("base_branch") or "").strip()
        if not pull_request or not base_branch:
            raise WorkflowError(
                f"#{number} manual specification record lacks Pull Request or base"
            )

        pr = self.board.specification_pull_request(pull_request)
        if pr["head_sha"] != recorded.get("commit"):
            raise WorkflowError(
                "the specification Pull Request head differs from the exact "
                "commit recorded on the Card"
            )
        if pr["base_branch"] and pr["base_branch"] != base_branch:
            raise WorkflowError(
                f"specification Pull Request targets `{pr['base_branch']}`, "
                f"not recorded base `{base_branch}`"
            )
        if not pr["merged"]:
            raise WorkflowError(
                f"specification Pull Request is {pr['state'] or 'not merged'}; "
                "the user must merge it before finalization"
            )

        artifact = self.git.sync_merged_specification(
            str(recorded["path"]), base_branch
        )
        finalized = {
            **recorded,
            "source_commit": recorded["commit"],
            "commit": artifact["commit"],
            "branch": base_branch,
            "state": "MERGED",
            "merged_at": pr.get("merged_at"),
            "merge_commit": pr.get("merge_commit"),
        }
        try:
            self.board.record_specification(number, finalized)
        except AgentTeamsError as exc:
            return {
                "ok": False,
                "partial": True,
                "issue": number,
                "completed": ["base_branch_synced"],
                "failed": "card_record",
                "error": str(exc),
                "specification": finalized,
                "recovery": [
                    f"producer_board.py finalize-spec-merge {number}",
                ],
            }
        return {
            "ok": True,
            "issue": number,
            "specification": finalized,
            "next": [
                "Resume architect shaping: decompose or hand the Card to readiness."
            ],
        }

    def decompose(
        self,
        parent: int,
        children: Sequence[dict[str, str]],
        spec_reference: str = "",
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

        recorded = self.board.latest_specification(parent)
        if recorded is None:
            raise WorkflowError(
                f"Issue #{parent} has no published durable specification"
            )
        reference = str(spec_reference or recorded["path"]).strip()
        if reference != recorded["path"]:
            raise WorkflowError(
                f"the Card records specification `{recorded['path']}`, not `{reference}`"
            )
        gate = self.check_spec_gate(reference)
        if not gate["satisfied"]:
            raise WorkflowError(gate["explanation"])
        if gate.get("commit") != recorded.get("commit"):
            raise WorkflowError(
                f"specification `{reference}` changed after Card publication; "
                f"run publish-spec again"
            )

        board_cards = self.board.cards()
        if not any(card.number == parent for card in board_cards):
            raise WorkflowError(f"Issue #{parent} is not on the configured Project")

        titles = [str(child.get("title", "")).strip() for child in children]
        duplicates = sorted({
            title for title in titles if title and titles.count(title) > 1
        })
        if duplicates:
            raise WorkflowError(
                "decomposition child titles must be unique: " + ", ".join(duplicates)
            )
        existing_by_title: dict[str, list[Card]] = {}
        for existing in board_cards:
            existing_by_title.setdefault(existing.title, []).append(existing)

        created: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        for child in children:
            title = str(child.get("title", "")).strip()
            body = str(child.get("body", "")).strip()
            if not title or not body:
                failures.append({"title": title, "error": "title and body are required"})
                continue

            reused = None
            for candidate in existing_by_title.get(title, []):
                inheritance = self.board.decomposed_child(candidate.number)
                if (inheritance and inheritance.get("parent") == parent and
                        inheritance.get("path") == recorded["path"] and
                        inheritance.get("commit") == recorded["commit"]):
                    reused = candidate
                    break
            if reused is not None:
                created.append({
                    "ok": True, "issue": reused.number, "url": reused.url,
                    "status": reused.status.value if reused.status else None,
                    "role": reused.role.value if reused.role else None,
                    "reused": True,
                })
                continue

            specification_record = {
                "path": recorded["path"], "commit": recorded["commit"],
                "branch": recorded.get("branch", ""), "inherited_from": parent,
            }
            child_record = {
                "parent": parent, "path": recorded["path"],
                "commit": recorded["commit"], "title": title,
            }
            body = (
                f"{body}\n\n---\nSpecification: {gate['reference']}\n"
                f"Decomposed from #{parent}.\n\n"
                f"{SPECIFICATION_MARKER}\n\n```json\n"
                f"{json.dumps(specification_record, indent=2)}\n```\n\n"
                f"{DECOMPOSED_CHILD_MARKER}\n\n```json\n"
                f"{json.dumps(child_record, indent=2)}\n```"
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
        summary_error = ""
        if created:
            try:
                summary = "\n".join(summary_lines)
                if not failures:
                    summary = DECOMPOSITION_MARKER + "\n" + summary
                self.board.comment_on_card(parent, summary)
                comment_posted = True
            except GitHubError as exc:
                comment_posted = False
                summary_error = str(exc)

        if created and not failures and not comment_posted:
            failures.append({
                "stage": "summary_comment", "error": summary_error or "not posted"
            })

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
                    f"{len(failures)} decomposition step(s) failed. Re-run the "
                    f"same decompose command: children carry structured parent "
                    f"identity, so successful Cards are reused rather than duplicated.",
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
        """Emergency cleanup: delete an abandoned claim and return it to Ready.

        Routine interrupted work uses ``resume`` to continue the existing
        remote claim branch automatically. This human-only destructive fallback
        exists for evidence-backed cases where preserving that branch is unsafe.
        The Card must actually be In Progress, so this is not a side door past
        the readiness gate.

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


#: GitHub honours these case-insensitively, with or without "d"/"s" endings.
CLOSING_KEYWORD = re.compile(
    r"\b(?:clos(?:e|es|ed)|fix(?:es|ed)?|resolv(?:e|es|ed))\s*:?\s+#\d+", re.I
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

    # The delivery names its Card with a plain reference, never a closing
    # keyword. `Closes #N` makes GitHub close the Issue the moment the Pull
    # Request merges, and on a Project with the default "item closed -> Done"
    # workflow that flips Status before `reconcile` runs: two completion
    # authorities racing, observed live in session 8. Completion has exactly
    # one owner -- `reconcile`, which sets Done, hands to lead, and then
    # closes the Issue itself.
    if not re.search(r"(?im)^\s*card:\s*#\d+\s*\.?\s*$", text):
        problems.append(
            "missing the `Card: #<issue>` reference line; it is how the "
            "delivery names the Card without closing it"
        )
    if CLOSING_KEYWORD.search(text):
        problems.append(
            "contains a GitHub closing keyword (Closes/Fixes/Resolves #N); "
            "GitHub would close the Card on merge and race `reconcile`. "
            "Reference the Card as `Card: #<issue>` instead"
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
        branch = claim_branch(card.number, card.title)
        finder = getattr(self.git, "worktree_for_branch", None)
        if callable(finder):
            existing = finder(branch)
            if existing is not None:
                return Path(existing)
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
                    "The coordinator resumes it from durable state later.",
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

    def resume(self, number: int, seat: Role) -> dict[str, Any]:
        """Materialise an interrupted Card's durable claim in this session."""
        policy.check_action("claim_card", seat)
        card = self._bound_card(number, seat, Status.IN_PROGRESS)
        branch = claim_branch(number, card.title)
        sha = self.git.remote_branch_sha(branch)
        target = self._worktree_for(card)
        tree = self.git.add_worktree(target, branch, sha)
        return {
            "ok": True, "issue": number, "url": card.url,
            "status": Status.IN_PROGRESS.value, "role": seat.value,
            "branch": branch, "claim_sha": sha, **tree,
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

        # The Pull Request is built from the remote branch; publishing the
        # delivery therefore includes pushing it. A dirty worktree or a
        # failed push refuses here, before any board mutation.
        published = self.git.publish_delivery(
            self._worktree_for(card), claim_branch(number, card.title)
        )
        if published.get("pushed"):
            log.record("push", head_sha=published.get("head_sha"))

        url = self.board.create_or_update_pull_request(
            number, card.title, title, body
        )
        log.record("pull_request", pull_request=url)

        pr = self.board.pull_request(number, card.title)
        if not pr["changed_files"]:
            # The Pull Request exists but delivers nothing: base and head
            # are identical on the remote. Refuse the handoff -- QA reviews
            # deliveries, not empty diffs.
            return log.partial_result(
                "delivery",
                "the Pull Request diff is empty: origin has no file changes "
                "on the claim branch. Commit the implementation in the "
                "worktree, then run submit-pr again -- it updates this same "
                "Pull Request.",
                [
                    f"producer_board.py submit-pr {number} --title ... "
                    f"--body-file ...",
                ],
            )

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
        card = self._bound_card(number, Role.QA, Status.IN_REVIEW)
        policy.check_action("write_verdict", Role.QA)

        pr = self.board.pull_request(number, card.title)
        problems = policy.validate_verdict(
            verdict, pr["head_sha"], pr["changed_files"], config=self.config
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

        pr = self.board.pull_request(number, card.title)
        problems = policy.validate_verdict(
            verdict, pr["head_sha"], pr["changed_files"], config=self.config
        )
        if problems:
            raise WorkflowError(
                "cannot accept on this evidence:\n  - " + "\n  - ".join(problems)
            )

        transient = policy.acceptance_wait_reasons(verdict, pr, self.config)
        if transient:
            return {
                "ok": True,
                "issue": number,
                "url": card.url,
                "acceptance": "waiting",
                "head_sha": pr["head_sha"],
                "reasons": list(transient),
                "pull_request": pr["url"],
                "status": Status.IN_REVIEW.value,
                "role": Role.QA.value,
                "next": ["The coordinator will monitor GitHub and retry acceptance."],
            }

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
            # A post-merge re-verify reaches here with the Pull Request already
            # merged (``gh pr merge --auto`` on a merged PR is an error, and
            # its mergeability stays UNKNOWN forever). Nothing to arm.
            automatic = self.config.effective_code_pr_merge_mode() == "automatic"
            if automatic and not pr.get("merged"):
                self.board.arm_auto_merge(
                    pr["number"], self.config.effective_code_pr_merge_method()
                )

            # Re-read rather than assume. In automatic mode, armed is not
            # merged. In manual mode, an already-merged Pull Request may be
            # reconciled, but this controller never issues its merge command.
            state = self.board.merge_state(pr["number"])
            if str(state.get("state", "")).upper() == "MERGED":
                return {
                    **base,
                    "merge": "merged",
                    **self._reconcile_to_done(number, card, pr, state, Role.LEAD),
                }

            if self.config.effective_code_pr_merge_mode() == "manual":
                return {
                    **base,
                    "status": Status.IN_REVIEW.value,
                    "role": Role.QA.value,
                    "merge": "awaiting_human",
                    "next": [
                        "Merge the eligible Pull Request in GitHub.",
                        "The current-session coordinator will detect MERGED and "
                        "reconcile the Card to Done automatically.",
                    ],
                }

            return {
                **base,
                "status": Status.IN_REVIEW.value,
                "role": Role.QA.value,
                "merge": "armed",
                "next": [
                    "GitHub merges this head once the required checks pass on "
                    "the current base, and disarms if a new commit lands.",
                    "The current-session coordinator observes this state through "
                    "next-actions and reconciles it automatically after MERGED.",
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
            self.board.reconcile_done_status(number, acting_role)
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
                    f"producer_board.py reconcile-done {number}"
                ],
            )

        # Completion has one owner. The delivery body must not carry a
        # closing keyword (validate_pr_body), so the Issue is still open here;
        # close it now that the board says Done. Non-fatal: Done on the board
        # is the durable outcome, an open Issue is a visible inconsistency.
        try:
            self.board.close_issue(
                number,
                f"Delivered: {pr['url']} merged as "
                f"{state.get('merge_commit') or 'a confirmed merge'}; "
                f"Card reconciled to Done.",
            )
            issue_closed: dict[str, Any] = {"ok": True}
        except AgentTeamsError as exc:
            issue_closed = {
                "ok": False, "error": str(exc),
                "recovery": [f"gh issue close {number} --repo {self.config.repo}"],
            }

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
            "issue_closed": issue_closed,
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

        acceptance = self.board.latest_acceptance(number)
        if acceptance is None or acceptance.acceptance != "eligible":
            raise WorkflowError(
                f"#{number} has no eligible acceptance record to reconcile"
            )
        pr = self.board.pull_request(number, card.title)
        if acceptance.head_sha != pr["head_sha"]:
            raise WorkflowError(
                "the Pull Request head differs from the eligible acceptance; "
                "publish a current-head QA verdict before reconciliation"
            )
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

    def approve_exception(
        self, number: int, acting_role: Role = Role.HUMAN
    ) -> dict[str, Any]:
        """Human final gate: merge the exact reviewed head and reconcile Done."""
        policy.check_action("merge_pull_request", acting_role)
        card = self._bound_card(number, Role.HUMAN, Status.IN_REVIEW)
        acceptance = self.board.latest_acceptance(number)
        if acceptance is None or acceptance.acceptance != "protected_change":
            raise WorkflowError(
                f"#{number} has no protected-change acceptance record to approve"
            )
        pr = self.board.pull_request(number, card.title)
        if acceptance.head_sha != pr["head_sha"]:
            raise WorkflowError(
                "the Pull Request head changed after the exception was recorded; "
                "hand it back to QA for a current-head verdict"
            )
        self.board.merge_pull_request(
            pr["number"],
            self.config.effective_code_pr_merge_method(),
            acceptance.head_sha,
        )
        state = self.board.merge_state(pr["number"])
        if str(state.get("state", "")).upper() != "MERGED":
            raise WorkflowError(
                "GitHub accepted the merge command but has not confirmed MERGED; "
                "the Card remains In Review and may be retried safely"
            )
        return {
            "ok": True, "issue": number, "acceptance": "human_exception",
            "pull_request": pr["url"],
            **self._reconcile_to_done(number, card, pr, state, acting_role),
        }

    def refresh_verification(self, number: int) -> dict[str, Any]:
        """Return a stale human exception to QA without a human command."""
        card = self._bound_card(number, Role.HUMAN, Status.IN_REVIEW)
        acceptance = self.board.latest_acceptance(number)
        if acceptance is None or acceptance.acceptance != "protected_change":
            raise WorkflowError(
                f"#{number} has no protected-change acceptance to invalidate"
            )
        pr = self.board.pull_request(number, card.title)
        if acceptance.head_sha == pr["head_sha"]:
            raise WorkflowError(
                "the protected-change evidence still matches the current head; "
                "the Card remains a human QA exception"
            )
        try:
            return self.board.return_stale_exception_to_qa(
                number, acceptance.head_sha, pr["head_sha"], pr["url"]
            )
        except PartialHandoff as exc:
            return exc.to_result(self.config.repo)

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


def _spawn_action(
    card: Card, seat: Role, routine: str, objective: str
) -> dict[str, Any]:
    """One bounded child-agent request; GitHub state remains authoritative."""
    prompt = (
        f"[role:{seat.value}] [board-card:#{card.number}] "
        f"[expected:({card.status.value if card.status else '?'}, "
        f"{card.role.value if card.role else '?'})] "
        f"[routine:{routine}] [skill:agent-teams:{routine}] "
        f"Invoke `agent-teams:{routine}` through the Skill tool, then work "
        f"only on Card #{card.number}: {objective} "
        f"Bootstrap first, reread live board state, mutate only this Card and "
        f"its governed artifacts, persist the result to GitHub, and stop at the "
        f"stage boundary. Never act as human and never select another Card. "
        f"Run every producer_board.py command with "
        f"{policy.ACTING_ROLE_ENV}={seat.value} in its environment so the "
        f"seat is bound to the process rather than claimed per call."
    )
    return {
        **card.to_dict(),
        "routing_state": card.routing_state,
        "kind": "spawn",
        "role": seat.value,
        "routine": routine,
        "skill": f"agent-teams:{routine}",
        # One plugin agent per seat (agents/<seat>-worker.md). The bodies are
        # identical; the distinct names let the Claude Code agent list and any
        # external monitor show which role each spawned worker holds.
        "agent": f"agent-teams:{seat.value}-worker",
        # Process binding for the worker's shell: policy refuses any
        # ``--acting-role`` that disagrees with it, and refuses ``human``
        # outright inside an agent session.
        "env": {policy.ACTING_ROLE_ENV: seat.value},
        "prompt": prompt,
    }
