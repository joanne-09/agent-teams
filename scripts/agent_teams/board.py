"""Semantic board operations over one GitHub Project.

The surface here is deliberately semantic rather than a generic field setter.
``transition_card`` and ``handoff_card`` exist; ``set_card_field`` does not.
That is what keeps lifecycle rules enforceable in one place instead of spread
across skill prose (ARCHITECTURE.md 9.8).

Every mutating method checks policy *before* it calls GitHub, so a refusal
costs nothing and leaves no partial state.
"""

from __future__ import annotations

from .errors import AgentTeamsError

import json
import re
from dataclasses import replace
from typing import Any

from . import policy
from .config import Config
from .git import claim_branch
from .github import Gh, GitHubError, fetch_all_items
from .model import (
    ACCEPTANCE_MARKER, Acceptance, Card, DECOMPOSED_CHILD_MARKER,
    DECOMPOSITION_MARKER, DomainError, HANDOFF_MARKER, Handoff, Role,
    SPECIFICATION_MARKER, Status, VERDICT_MARKER, Verdict,
)


class BoardError(AgentTeamsError):
    """A board-level precondition failed."""


def _casefold_equal(left: Any, right: Any) -> bool:
    return str(left or "").casefold() == str(right or "").casefold()


def _value_name(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("name", "value", "text", "title"):
            if value.get(key) is not None:
                return str(value[key])
    return str(value)


class Board:
    def __init__(self, config: Config, gh: Gh | None = None):
        self.config = config
        self.gh = gh or Gh(recovery=config.recovery)
        self._project_id: str | None = None
        self._fields: list[dict[str, Any]] | None = None

    # ------------------------------------------------------------- metadata

    def project_id(self) -> str:
        if self._project_id is None:
            payload = self.gh.json(
                [
                    "project", "view", str(self.config.project_number),
                    "--owner", self.config.project_owner, "--format", "json",
                ]
            )
            value = payload.get("id") if isinstance(payload, dict) else None
            if not value:
                raise BoardError("gh project view did not return a project id")
            self._project_id = str(value)
        return self._project_id

    def fields(self) -> list[dict[str, Any]]:
        if self._fields is None:
            payload = self.gh.json(
                [
                    "project", "field-list", str(self.config.project_number),
                    "--owner", self.config.project_owner, "--format", "json",
                ]
            )
            fields = payload.get("fields", []) if isinstance(payload, dict) else []
            if not isinstance(fields, list):
                raise BoardError("gh project field-list returned an invalid shape")
            self._fields = fields
        return self._fields

    def find_field(self, name: str) -> dict[str, Any] | None:
        for candidate in self.fields():
            if _casefold_equal(candidate.get("name"), name):
                return candidate
        return None

    def field(self, name: str) -> dict[str, Any]:
        found = self.find_field(name)
        if found is None:
            raise BoardError(f"Project is missing required field {name!r}")
        if not found.get("id"):
            raise BoardError(f"Project field {name!r} has no id")
        return found

    @staticmethod
    def find_option(field: dict[str, Any], value: str) -> dict[str, Any] | None:
        options = field.get("options", [])
        for option in options if isinstance(options, list) else []:
            if _casefold_equal(option.get("name"), value):
                return option
        return None

    def option(self, field: dict[str, Any], value: str) -> dict[str, Any]:
        found = self.find_option(field, value)
        if found is None:
            raise BoardError(
                f"Project field {field.get('name')!r} is missing option {value!r}"
            )
        if not found.get("id"):
            raise BoardError(f"Project field option {value!r} has no id")
        return found

    # ---------------------------------------------------------------- reads

    def _item_field_value(self, item: dict[str, Any], field_name: str) -> str | None:
        for key, value in item.items():
            if key.casefold() == field_name.casefold():
                return _value_name(value)

        field_values = item.get("fieldValues")
        if isinstance(field_values, dict):
            nodes = field_values.get("nodes", [])
        elif isinstance(field_values, list):
            nodes = field_values
        else:
            nodes = []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            field = node.get("field") or {}
            if _casefold_equal(field.get("name"), field_name):
                return _value_name(node)
        return None

    def _status_from_name(self, raw: Any) -> Status | None:
        """Map a board option name back to a canonical Status."""
        if raw in (None, ""):
            return None
        for status, configured in self.config.all_status_names().items():
            if _casefold_equal(configured, raw):
                return status
        return Status.parse_optional(raw)

    def _normalise_item(self, item: dict[str, Any]) -> Card | None:
        content = item.get("content")
        if not isinstance(content, dict):
            return None
        number = content.get("number")
        if number is None:
            return None

        repository = content.get("repository")
        if isinstance(repository, dict):
            repository = (
                repository.get("nameWithOwner")
                or repository.get("name")
                or repository.get("url")
            )
        repository = str(repository or "")
        if repository and not _casefold_equal(repository, self.config.repo):
            return None

        return Card(
            item_id=item.get("id"),
            number=int(number),
            repo=repository or self.config.repo,
            title=str(content.get("title") or item.get("title") or ""),
            url=str(content.get("url") or ""),
            status=self._status_from_name(
                self._item_field_value(item, self.config.status_field)
            ),
            role=Role.parse_optional(
                self._item_field_value(item, self.config.role_field)
            ),
        )

    def _raw_items(self, limit: int) -> list[dict[str, Any]]:
        payload = self.gh.json(
            [
                "project", "item-list", str(self.config.project_number),
                "--owner", self.config.project_owner, "--format", "json",
                "--limit", str(limit),
            ]
        )
        items = payload.get("items", []) if isinstance(payload, dict) else []
        if not isinstance(items, list):
            raise BoardError("gh project item-list returned an invalid shape")
        return items

    def cards(self) -> list[Card]:
        """Every Card on the Project belonging to the configured repository."""
        items = fetch_all_items(
            self._raw_items,
            page_limit=self.config.board_page_limit,
            max_items=self.config.board_max_items,
            what="Project items",
        )
        normalised = (
            self._normalise_item(item) for item in items if isinstance(item, dict)
        )
        return [card for card in normalised if card is not None]

    def card(self, number: int) -> Card:
        for card in self.cards():
            if card.number == number:
                return card
        raise BoardError(
            f"Issue #{number} from {self.config.repo} is not on the configured Project"
        )

    def comments(self, number: int) -> list[str]:
        payload = self.gh.json(
            ["issue", "view", str(number), "--repo", self.config.repo,
             "--json", "comments"]
        )
        raw = payload.get("comments", []) if isinstance(payload, dict) else []
        bodies = []
        for entry in raw if isinstance(raw, list) else []:
            if isinstance(entry, dict) and entry.get("body"):
                bodies.append(str(entry["body"]))
            elif isinstance(entry, str):
                bodies.append(entry)
        return bodies

    def issue_body(self, number: int) -> str:
        payload = self.gh.json(
            ["issue", "view", str(number), "--repo", self.config.repo,
             "--json", "body"]
        )
        return str(payload.get("body", "")) if isinstance(payload, dict) else ""

    def handoff_count(self, number: int) -> int:
        """How many structured handoffs this Card has already absorbed."""
        try:
            return sum(1 for body in self.comments(number) if HANDOFF_MARKER in body)
        except GitHubError:
            # A Card whose comments cannot be read must not block a handoff --
            # report zero and let the cap fail open rather than stall the team.
            return 0

    def card_with_handoffs(self, number: int) -> Card:
        card = self.card(number)
        return replace(card, handoff_count=self.handoff_count(number))

    # ------------------------------------------------------------- mutation

    def _set_single_select(self, item_id: str, field_name: str, value: str) -> None:
        field = self.field(field_name)
        option = self.option(field, value)
        self.gh.run(
            [
                "project", "item-edit",
                "--id", item_id,
                "--project-id", self.project_id(),
                "--field-id", str(field["id"]),
                "--single-select-option-id", str(option["id"]),
            ]
        )

    def set_status(self, item_id: str, status: Status) -> None:
        self._set_single_select(
            item_id, self.config.status_field, self.config.status_name(status)
        )

    def set_role(self, item_id: str, role: Role) -> None:
        self._set_single_select(item_id, self.config.role_field, role.value)

    def comment_on_card(self, number: int, body: str) -> None:
        self.gh.run(
            ["issue", "comment", str(number), "--repo", self.config.repo,
             "--body", body]
        )

    def transition_card(
        self, number: int, target: Status, acting_role: Role
    ) -> dict[str, Any]:
        """Move a Card's Status. Never touches Role.

        The authority check keys off the *destination*, because reaching Ready
        or Done are governed decisions in their own right rather than plain
        lifecycle moves.
        """
        if target is Status.DONE:
            raise BoardError(
                "Done is reachable only through reconcile-done after an exact-head "
                "acceptance and a confirmed merge"
            )
        policy.check_action(policy.action_for_transition(target), acting_role)
        card = self.card(number)
        policy.check_transition(card.status, target)
        if not card.item_id:
            raise BoardError(f"Issue #{number} Project item has no id")
        self.set_status(str(card.item_id), target)
        return {
            "ok": True,
            "issue": number,
            "url": card.url,
            "status_before": card.status.value if card.status else None,
            "status": target.value,
            "role": card.role.value if card.role else None,
        }

    def reconcile_done_status(
        self, number: int, acting_role: Role
    ) -> dict[str, Any]:
        """Set Done for a caller that already proved acceptance and merge.

        This primitive is intentionally separate from ``transition_card`` so
        the generic CLI cannot manufacture completion without merge evidence.
        """
        policy.check_action("reconcile_done", acting_role)
        card = self.card(number)
        policy.check_transition(card.status, Status.DONE)
        if not card.item_id:
            raise BoardError(f"Issue #{number} Project item has no id")
        self.set_status(str(card.item_id), Status.DONE)
        return {
            "ok": True, "issue": number, "url": card.url,
            "status_before": card.status.value if card.status else None,
            "status": Status.DONE.value,
            "role": card.role.value if card.role else None,
        }

    def handoff_card(
        self,
        number: int,
        from_role: Role,
        to_role: Role,
        reason: str,
        needs: str = "",
        artifacts: str = "",
    ) -> dict[str, Any]:
        """Change durable ownership and leave the receiver enough context.

        Role only. If the lifecycle also moves, that is a separate
        ``transition_card`` call -- keeping them independent is what makes both
        idempotent and separately recoverable.
        """
        policy.check_action("handoff_card", from_role)
        card = self.card(number)
        if card.role is not None and card.role != from_role:
            raise BoardError(
                f"Issue #{number} is owned by `{card.role}`, not `{from_role}`; "
                f"re-read the board before handing off"
            )
        count = self.handoff_count(number)
        policy.check_handoff(from_role, to_role, count, self.config.handoff_cap)
        if not card.item_id:
            raise BoardError(f"Issue #{number} Project item has no id")

        handoff = Handoff(from_role, to_role, reason, needs, artifacts)
        comment = handoff.render()

        # Role first, then the comment. If the comment fails, recovery writes
        # the missing context rather than flipping ownership back and forth.
        self.set_role(str(card.item_id), to_role)
        try:
            self.comment_on_card(number, comment)
        except GitHubError as exc:
            raise PartialHandoff(
                number=number,
                to_role=to_role,
                comment=comment,
                cause=str(exc),
            ) from exc

        return {
            "ok": True,
            "issue": number,
            "url": card.url,
            "from_role": from_role.value,
            "role": to_role.value,
            "handoff_count": count + 1,
            "comment": comment,
        }

    def return_stale_exception_to_qa(
        self, number: int, accepted_head: str, current_head: str, pr_url: str
    ) -> dict[str, Any]:
        """Controller route when a human exception's reviewed head is stale.

        This is not the controller acting as the human. The exception decision
        no longer exists for the new head, so the deterministic safety route
        removes the Card from the human gate and requests fresh QA evidence.
        """
        if not accepted_head or not current_head or accepted_head == current_head:
            raise BoardError("stale-exception return requires two different heads")
        card = self.card(number)
        if card.status is not Status.IN_REVIEW or card.role is not Role.HUMAN:
            raise BoardError(
                f"Issue #{number} is {card.routing_state}; stale-exception "
                "return requires (In Review, human)"
            )
        count = self.handoff_count(number)
        policy.check_handoff(Role.HUMAN, Role.QA, count, self.config.handoff_cap)
        if not card.item_id:
            raise BoardError(f"Issue #{number} Project item has no id")
        handoff = Handoff(
            Role.HUMAN, Role.QA,
            "Controller invalidated the exception because the Pull Request "
            "head changed after QA evidence.",
            needs="review the current head and publish fresh evidence",
            artifacts=pr_url,
        )
        comment = handoff.render()
        self.set_role(str(card.item_id), Role.QA)
        try:
            self.comment_on_card(number, comment)
        except GitHubError as exc:
            raise PartialHandoff(number, Role.QA, comment, str(exc)) from exc
        return {
            "ok": True, "issue": number, "role": Role.QA.value,
            "accepted_head": accepted_head, "current_head": current_head,
            "comment": comment,
        }

    # --------------------------------------------------------- pull requests

    #: Everything the acceptance evaluator needs, in one round trip.
    _PR_FIELDS = (
        "number,url,headRefOid,state,mergeable,isDraft,files,statusCheckRollup,"
        "autoMergeRequest"
    )

    def pull_request(self, number: int, card_title: str) -> dict[str, Any]:
        """The Card's Pull Request, normalised. Raw gh shapes stop here.

        Resolved by claim branch, never by number: Issues and Pull Requests
        share one numbering sequence, so the Pull Request number drifts from
        the Card number whenever anything else was created in between. The
        claim branch is the stable link (the same key
        ``create_or_update_pull_request`` writes under).
        """
        raw = self.gh.json(
            ["pr", "view", claim_branch(number, card_title),
             "--repo", self.config.repo, "--json", self._PR_FIELDS]
        )
        checks = {
            str(entry.get("name", "")): str(entry.get("conclusion", ""))
            for entry in (raw.get("statusCheckRollup") or [])
            if entry.get("name")
        }
        return {
            "number": raw.get("number"),
            "url": raw.get("url", ""),
            "head_sha": str(raw.get("headRefOid", "")),
            "state": str(raw.get("state", "")),
            "mergeable": str(raw.get("mergeable", "")).upper() == "MERGEABLE",
            "mergeable_state": str(raw.get("mergeable", "")).upper(),
            "draft": bool(raw.get("isDraft", False)),
            "auto_merge_enabled": bool(raw.get("autoMergeRequest")),
            "changed_files": tuple(
                str(entry.get("path", ""))
                for entry in (raw.get("files") or [])
                if entry.get("path")
            ),
            "checks": checks,
        }

    def create_or_update_pull_request(
        self, number: int, card_title: str, title: str, body: str
    ) -> str:
        """Exactly one Pull Request per claim branch. Idempotent by branch.

        One Card, one Consumer, one delivery (ARCHITECTURE.md Appendix A.1).
        A resumed or corrected session must update the Pull Request it
        already opened rather than opening a second one, so this keys off the
        claim branch rather than on whether this session remembers creating
        one.
        """
        branch = claim_branch(number, card_title)
        existing = self.gh.json(
            ["pr", "list", "--repo", self.config.repo, "--head", branch,
             "--state", "open", "--json", "number,url"]
        )
        if existing:
            self.gh.run(
                ["pr", "edit", str(existing[0]["number"]), "--repo", self.config.repo,
                 "--title", title, "--body", body]
            )
            return str(existing[0].get("url", ""))
        return self.gh.run(
            ["pr", "create", "--repo", self.config.repo, "--head", branch,
             "--title", title, "--body", body]
        ).strip()

    def create_or_update_specification_pull_request(
        self, branch: str, base_branch: str, title: str, body: str
    ) -> str:
        """Create the one user-merged specification PR for a stable branch."""
        existing = self.gh.json(
            [
                "pr", "list", "--repo", self.config.repo, "--head", branch,
                "--state", "open", "--json", "number,url",
            ]
        )
        if existing:
            self.gh.run(
                [
                    "pr", "edit", str(existing[0]["number"]),
                    "--repo", self.config.repo, "--base", base_branch,
                    "--title", title, "--body", body,
                ]
            )
            return str(existing[0].get("url", ""))
        return self.gh.run(
            [
                "pr", "create", "--repo", self.config.repo,
                "--head", branch, "--base", base_branch,
                "--title", title, "--body", body,
            ]
        ).strip()

    def specification_pull_request(self, reference: str) -> dict[str, Any]:
        """Normalize the exact specification PR recorded on a Card."""
        text = str(reference or "").strip()
        match = re.search(r"(?:/pull/|#)?(\d+)(?:\D|$)", text)
        if match is None:
            raise BoardError(
                f"invalid specification Pull Request reference: {reference!r}"
            )
        raw = self.gh.json(
            [
                "pr", "view", match.group(1), "--repo", self.config.repo,
                "--json",
                "number,url,headRefOid,baseRefName,state,mergedAt,mergeCommit",
            ]
        )
        state = str(raw.get("state") or "").upper()
        return {
            "number": raw.get("number"),
            "url": str(raw.get("url") or text),
            "head_sha": str(raw.get("headRefOid") or ""),
            "base_branch": str(raw.get("baseRefName") or ""),
            "state": state,
            "merged": bool(raw.get("mergedAt")) or state == "MERGED",
            "merged_at": raw.get("mergedAt"),
            "merge_commit": (raw.get("mergeCommit") or {}).get("oid"),
        }

    def record_verdict(self, number: int, verdict: Verdict) -> None:
        self.comment_on_card(number, _render_block(VERDICT_MARKER, verdict.to_dict()))

    def record_specification(self, number: int, specification: dict[str, Any]) -> None:
        self.comment_on_card(
            number, _render_block(SPECIFICATION_MARKER, specification)
        )

    def record_acceptance(self, number: int, acceptance: Acceptance) -> None:
        self.comment_on_card(
            number, _render_block(ACCEPTANCE_MARKER, acceptance.to_dict())
        )

    def latest_verdict(self, number: int) -> "Verdict | None":
        """The most recent parseable verdict, or None.

        Fails open like ``handoff_count``: an unreadable or schema-invalid
        comment reads as 'not a verdict' and the search continues to older
        ones, rather than crashing a session that could still explain itself.
        A missing verdict refuses the accept, which is the safe direction.
        """
        for body in reversed(self.comments(number)):
            if VERDICT_MARKER not in body:
                continue
            payload = _parse_block(body)
            if payload is None:
                continue
            try:
                return Verdict.from_dict(payload)
            except (DomainError, TypeError, ValueError):
                continue
        return None

    def latest_specification(self, number: int) -> dict[str, Any] | None:
        """The newest durable spec record from comments or Issue body.

        Decomposed children inherit the record inside their body, avoiding a
        second mutation that could leave a created child permanently unable to
        pass readiness.
        """
        payload = self.gh.json(
            ["issue", "view", str(number), "--repo", self.config.repo,
             "--json", "body,comments"]
        )
        bodies = [str(payload.get("body", ""))]
        bodies += [
            str(entry.get("body", ""))
            for entry in (payload.get("comments", []) or [])
            if isinstance(entry, dict) and entry.get("body")
        ]
        for body in reversed(bodies):
            if SPECIFICATION_MARKER not in body:
                continue
            record = _parse_block(body, SPECIFICATION_MARKER)
            if not isinstance(record, dict):
                continue
            path = str(record.get("path") or "").strip()
            commit = str(record.get("commit") or "").strip()
            if path and commit:
                return {**record, "path": path, "commit": commit}
        return None

    def hard_dependencies(self, number: int) -> tuple[int, ...]:
        """Machine-readable depends-on: #N edges from one Card body."""
        body = self.issue_body(number)
        dependencies = {
            int(match.group(1))
            for match in re.finditer(
                r"(?im)^\s*depends-on\s*:\s*#(\d+)\b", body
            )
        }
        dependencies.discard(number)
        return tuple(sorted(dependencies))

    def decomposed_child(self, number: int) -> dict[str, Any] | None:
        body = self.issue_body(number)
        if DECOMPOSED_CHILD_MARKER not in body:
            return None
        return _parse_block(body, DECOMPOSED_CHILD_MARKER)

    def decomposition_complete(self, number: int) -> bool:
        return any(DECOMPOSITION_MARKER in body for body in self.comments(number))

    def latest_acceptance(self, number: int) -> "Acceptance | None":
        """The newest parseable deterministic acceptance record."""
        for body in reversed(self.comments(number)):
            if ACCEPTANCE_MARKER not in body:
                continue
            payload = _parse_block(body)
            if payload is None:
                continue
            try:
                return Acceptance.from_dict(payload)
            except (DomainError, TypeError, ValueError):
                continue
        return None

    def arm_auto_merge(self, pr_number: int, method: str) -> dict[str, Any]:
        """Hand the merge to GitHub, which owns retesting against the base.

        Not an immediate merge: `--auto` lands the reviewed head only once
        required checks pass on the *current* base, and disarms if a new
        commit arrives. That is the stale-base guarantee, and it belongs to
        the platform that owns the base rather than to this code.
        """
        self.gh.run(
            ["pr", "merge", str(pr_number), "--repo", self.config.repo,
             "--auto", f"--{method}", "--delete-branch"]
        )
        return {"ok": True, "pull_request": pr_number, "method": method, "armed": True}

    def merge_pull_request(
        self, pr_number: int, method: str, expected_head: str
    ) -> dict[str, Any]:
        """Merge an exact Pull Request after the human exception gate."""
        self.gh.run(
            ["pr", "merge", str(pr_number), "--repo", self.config.repo,
             f"--{method}", "--delete-branch", "--match-head-commit",
             expected_head]
        )
        return {
            "ok": True, "pull_request": pr_number, "method": method,
            "expected_head": expected_head,
        }

    def merge_state(self, pr_number: int) -> dict[str, Any]:
        raw = self.gh.json(
            ["pr", "view", str(pr_number), "--repo", self.config.repo,
             "--json", "state,mergedAt,mergeCommit"]
        )
        return {
            "state": str(raw.get("state", "")),
            "merged_at": raw.get("mergedAt"),
            "merge_commit": (raw.get("mergeCommit") or {}).get("oid"),
        }

    def auto_merge_enabled(self) -> bool:
        # ``gh repo view --json autoMergeAllowed`` is not a supported JSON
        # field on real gh (observed on 2.97.0); the REST repository object
        # exposes the same setting as ``allow_auto_merge``.
        raw = self.gh.run(
            ["api", f"repos/{self.config.repo}", "--jq", ".allow_auto_merge"]
        )
        return str(raw).strip().casefold() == "true"

    # ------------------------------------------------------------- diagnosis

    def doctor(self) -> dict[str, Any]:
        """Validate the whole board contract and report every defect at once.

        Returning after the first missing option would make an operator re-run
        this six times to learn six things.
        """
        problems: list[str] = []
        details: dict[str, Any] = {}

        if isinstance(self.gh, Gh) and not self.gh.available():
            raise BoardError("gh is not installed or is not on PATH")

        try:
            self.gh.run(["auth", "status"])
        except GitHubError as exc:
            raise BoardError(str(exc)) from exc

        try:
            details["project_id"] = self.project_id()
        except (GitHubError, BoardError) as exc:
            raise BoardError(str(exc)) from exc

        role_field = self.find_field(self.config.role_field)
        if role_field is None:
            problems.append(
                f"Project has no {self.config.role_field!r} field; add a "
                f"single-select field with options: " + ", ".join(r.value for r in Role)
            )
        else:
            missing = [
                role.value for role in Role
                if self.find_option(role_field, role.value) is None
            ]
            if missing:
                problems.append(
                    f"{self.config.role_field!r} is missing options: "
                    + ", ".join(missing)
                )

        status_field = self.find_field(self.config.status_field)
        expected = self.config.all_status_names()
        if status_field is None:
            problems.append(
                f"Project has no {self.config.status_field!r} field; add a "
                f"single-select field with options: "
                + ", ".join(expected.values())
            )
        else:
            missing = [
                name for name in expected.values()
                if self.find_option(status_field, name) is None
            ]
            if missing:
                problems.append(
                    f"{self.config.status_field!r} is missing options: "
                    + ", ".join(missing)
                )

        if problems:
            raise BoardError(
                "the board is not ready:\n  - " + "\n  - ".join(problems)
            )

        # Acceptance readiness is reported, not raised. A repository doing
        # Producer-only work is perfectly usable without an automated merge
        # path; what is not acceptable is discovering at `accept` time that
        # the path was never going to work.
        acceptance_problems: list[str] = []
        if not self.config.required_checks:
            acceptance_problems.append(
                "required_checks is empty, so no delivery can ever be eligible "
                "for deterministic acceptance; every pass will route to the human "
                "protected-change lane. Name the checks that must be green."
            )
        elif self.config.merge_mode == "automatic":
            try:
                if not self.auto_merge_enabled():
                    acceptance_problems.append(
                        f"auto-merge is not enabled on {self.config.repo}, so "
                        f"`gh pr merge --auto` will fail. Enable it in "
                        f"repository settings, and configure branch protection "
                        f"with the required checks -- without protection "
                        f"--auto merges immediately and the retest guarantee "
                        f"is vacuous."
                    )
            except GitHubError as exc:
                acceptance_problems.append(
                    f"could not read auto-merge settings for {self.config.repo}: "
                    f"{exc}"
                )

        return {
            "ok": True,
            "config_revision": self.config.revision,
            "acceptance_problems": acceptance_problems,
            "repo": self.config.repo,
            "project_owner": self.config.project_owner,
            "project_number": self.config.project_number,
            "project_id": details["project_id"],
            "role_field": self.config.role_field,
            "status_field": self.config.status_field,
            "statuses_validated": [name for name in expected.values()],
            "roles_validated": [role.value for role in Role],
            "wip_limit": self.config.wip_limit,
            "handoff_cap": self.config.handoff_cap,
            "monitor_poll_seconds": self.config.monitor_poll_seconds,
            "board_page_limit": self.config.board_page_limit,
            "board_max_items": self.config.board_max_items,
            "recovery": self.config.recovery.to_dict(),
            "spec_merge_mode": self.config.spec_merge_mode,
            "merge_mode": self.config.merge_mode,
            "merge_method": self.config.merge_method,
            "specification_mode": self.config.spec_merge_mode,
        }


def _render_block(marker: str, payload: dict[str, Any]) -> str:
    """A human-readable marker plus one machine-parseable JSON block.

    Both audiences at once: queue inspection greps the marker, the acceptance
    evaluator parses the block, and a person reading the Issue sees neither
    as noise.
    """
    return marker + "\n\n```json\n" + json.dumps(payload, indent=2) + "\n```"


def _parse_block(
    body: str, marker: str | None = None
) -> "dict[str, Any] | None":
    offset = body.find(marker) + len(marker) if marker and marker in body else 0
    start = body.find("```json", offset)
    end = body.find("```", start + 7)
    if start < 0 or end < 0:
        return None
    try:
        payload = json.loads(body[start + 7 : end])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


class PartialHandoff(AgentTeamsError):
    """Role was changed but the context comment did not land.

    Carries everything a fix-forward needs, because the ownership change is
    already visible to the next session and re-flipping it would be worse.
    """

    def __init__(self, number: int, to_role: Role, comment: str, cause: str):
        super().__init__(
            f"Issue #{number} Role was set to `{to_role}` but the handoff comment "
            f"failed to post: {cause}"
        )
        self.number = number
        self.to_role = to_role
        self.comment = comment
        self.cause = cause

    def to_result(self, repo: str) -> dict[str, Any]:
        return {
            "ok": False,
            "partial": True,
            "completed": ["role_set"],
            "failed": "handoff_comment",
            "error": self.cause,
            "issue": self.number,
            "role": self.to_role.value,
            "recovery": [
                "Role is already correct; do not change it back.",
                "Post the missing context comment with:",
                f"  gh issue comment {self.number} --repo {repo} --body-file <file>",
                "Comment body to post is in the 'comment' field of this result.",
            ],
            "comment": self.comment,
        }
