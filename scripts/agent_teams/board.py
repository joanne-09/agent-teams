"""Semantic board operations over one GitHub Project.

The surface here is deliberately semantic rather than a generic field setter.
``transition_card`` and ``handoff_card`` exist; ``set_card_field`` does not.
That is what keeps lifecycle rules enforceable in one place instead of spread
across skill prose (ARCHITECTURE.md 4.8).

Every mutating method checks policy *before* it calls GitHub, so a refusal
costs nothing and leaves no partial state.
"""

from __future__ import annotations

from .errors import AgentTeamsError

from dataclasses import replace
from typing import Any

from . import policy
from .config import Config
from .github import Gh, GitHubError, fetch_all_items
from .model import Card, Handoff, Role, Status, HANDOFF_MARKER


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
        self.gh = gh or Gh()
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
        items = fetch_all_items(self._raw_items, what="Project items")
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

        return {
            "ok": True,
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
            "spec_completion": self.config.spec_completion,
        }


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
