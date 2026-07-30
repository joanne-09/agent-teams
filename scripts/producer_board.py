#!/usr/bin/env python3
"""Minimal GitHub Project adapter for the board-superpowers Producer MVP."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


ROLES = ("analyst", "architect", "rd", "qa", "em", "human")
HANDOFF_AUTHORITY = {
    "analyst": {"architect", "em", "human"},
    "architect": {"rd", "qa", "em", "human"},
    "rd": {"architect", "qa", "em"},
    "qa": {"architect", "rd", "em", "human"},
    "em": {"analyst", "architect", "rd", "qa", "human"},
    "human": {"analyst", "architect", "rd", "qa", "em"},
}
DEFAULT_CONFIG = Path(".board-superpowers/producer.json")


class ProducerError(RuntimeError):
    """Expected configuration, validation, or GitHub failure."""


@dataclass(frozen=True)
class Config:
    repo: str
    project_owner: str
    project_number: int
    role_field: str = "Role"
    status_field: str = "Status"
    backlog_status: str = "Backlog"
    ready_status: str = "Ready"
    dispatch_roles: tuple[str, ...] = ("architect", "rd", "qa")

    @classmethod
    def load(cls, path: Path) -> "Config":
        if not path.is_file():
            raise ProducerError(
                f"configuration missing: {path}; run producer_board.py init"
            )
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProducerError(f"cannot read configuration {path}: {exc}") from exc

        required = ("repo", "project_owner", "project_number")
        missing = [key for key in required if raw.get(key) in (None, "")]
        if missing:
            raise ProducerError(
                "configuration missing required keys: " + ", ".join(missing)
            )

        roles = tuple(raw.get("dispatch_roles", ("architect", "rd", "qa")))
        unknown = sorted(set(roles) - set(ROLES))
        if unknown:
            raise ProducerError(
                "configuration contains unknown dispatch roles: " + ", ".join(unknown)
            )

        try:
            project_number = int(raw["project_number"])
        except (TypeError, ValueError) as exc:
            raise ProducerError("project_number must be a positive integer") from exc
        if project_number < 1:
            raise ProducerError("project_number must be a positive integer")

        return cls(
            repo=str(raw["repo"]),
            project_owner=str(raw["project_owner"]),
            project_number=project_number,
            role_field=str(raw.get("role_field", "Role")),
            status_field=str(raw.get("status_field", "Status")),
            backlog_status=str(raw.get("backlog_status", "Backlog")),
            ready_status=str(raw.get("ready_status", "Ready")),
            dispatch_roles=roles,
        )

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(self)
        payload["dispatch_roles"] = list(self.dispatch_roles)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


class Gh:
    """Small injectable wrapper around the GitHub CLI."""

    def run(self, args: Iterable[str]) -> str:
        command = ["gh", *list(args)]
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise ProducerError(f"{' '.join(command)} failed: {detail}")
        return completed.stdout.strip()

    def json(self, args: Iterable[str]) -> Any:
        output = self.run(args)
        try:
            return json.loads(output)
        except json.JSONDecodeError as exc:
            raise ProducerError(f"gh returned invalid JSON: {output[:200]}") from exc


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
        self._project_id_cache: str | None = None
        self._fields_cache: list[dict[str, Any]] | None = None

    def project_id(self) -> str:
        if self._project_id_cache is None:
            payload = self.gh.json(
                [
                    "project",
                    "view",
                    str(self.config.project_number),
                    "--owner",
                    self.config.project_owner,
                    "--format",
                    "json",
                ]
            )
            project_id = payload.get("id") if isinstance(payload, dict) else None
            if not project_id:
                raise ProducerError("gh project view did not return a project id")
            self._project_id_cache = str(project_id)
        return self._project_id_cache

    def fields(self) -> list[dict[str, Any]]:
        if self._fields_cache is None:
            payload = self.gh.json(
                [
                    "project",
                    "field-list",
                    str(self.config.project_number),
                    "--owner",
                    self.config.project_owner,
                    "--format",
                    "json",
                ]
            )
            fields = payload.get("fields", []) if isinstance(payload, dict) else []
            if not isinstance(fields, list):
                raise ProducerError("gh project field-list returned an invalid shape")
            self._fields_cache = fields
        return self._fields_cache

    def field(self, name: str) -> dict[str, Any]:
        for field in self.fields():
            if _casefold_equal(field.get("name"), name):
                if not field.get("id"):
                    raise ProducerError(f"Project field {name!r} has no id")
                return field
        raise ProducerError(f"Project is missing required field {name!r}")

    def option(self, field: dict[str, Any], value: str) -> dict[str, Any]:
        options = field.get("options", [])
        for option in options if isinstance(options, list) else []:
            if _casefold_equal(option.get("name"), value):
                if not option.get("id"):
                    raise ProducerError(
                        f"Project field option {value!r} has no id"
                    )
                return option
        raise ProducerError(
            f"Project field {field.get('name')!r} is missing option {value!r}"
        )

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

    def _normalise_item(self, item: dict[str, Any]) -> dict[str, Any] | None:
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

        return {
            "item_id": item.get("id"),
            "number": int(number),
            "repo": repository or self.config.repo,
            "title": str(content.get("title") or item.get("title") or ""),
            "url": str(content.get("url") or ""),
            "status": self._item_field_value(item, self.config.status_field),
            "role": self._item_field_value(item, self.config.role_field),
        }

    def cards(self) -> list[dict[str, Any]]:
        payload = self.gh.json(
            [
                "project",
                "item-list",
                str(self.config.project_number),
                "--owner",
                self.config.project_owner,
                "--format",
                "json",
                "--limit",
                "100",
            ]
        )
        items = payload.get("items", []) if isinstance(payload, dict) else []
        if not isinstance(items, list):
            raise ProducerError("gh project item-list returned an invalid shape")
        cards = [self._normalise_item(item) for item in items if isinstance(item, dict)]
        return [card for card in cards if card is not None]

    def card(self, number: int) -> dict[str, Any]:
        for card in self.cards():
            if card["number"] == number:
                return card
        raise ProducerError(
            f"Issue #{number} from {self.config.repo} is not on the configured Project"
        )

    def _set_single_select(self, item_id: str, field_name: str, value: str) -> None:
        field = self.field(field_name)
        option = self.option(field, value)
        self.gh.run(
            [
                "project",
                "item-edit",
                "--id",
                item_id,
                "--project-id",
                self.project_id(),
                "--field-id",
                str(field["id"]),
                "--single-select-option-id",
                str(option["id"]),
            ]
        )

    def doctor(self) -> dict[str, Any]:
        if shutil.which("gh") is None and isinstance(self.gh, Gh):
            raise ProducerError("gh is not installed or is not on PATH")
        self.gh.run(["auth", "status"])
        project_id = self.project_id()
        role_field = self.field(self.config.role_field)
        status_field = self.field(self.config.status_field)
        for role in ROLES:
            self.option(role_field, role)
        self.option(status_field, self.config.backlog_status)
        self.option(status_field, self.config.ready_status)
        return {
            "ok": True,
            "repo": self.config.repo,
            "project_owner": self.config.project_owner,
            "project_number": self.config.project_number,
            "project_id": project_id,
            "role_field": self.config.role_field,
            "status_field": self.config.status_field,
        }

    def dispatch(self, role: str | None = None) -> list[dict[str, Any]]:
        if role is not None and role not in self.config.dispatch_roles:
            raise ProducerError(
                f"role {role!r} is not dispatchable; configured roles: "
                + ", ".join(self.config.dispatch_roles)
            )
        rank = {name: index for index, name in enumerate(self.config.dispatch_roles)}
        selected = []
        for card in self.cards():
            card_role = str(card.get("role") or "").casefold()
            if not _casefold_equal(card.get("status"), self.config.ready_status):
                continue
            if card_role not in rank:
                continue
            if role is not None and card_role != role:
                continue
            selected.append(card)
        selected.sort(key=lambda card: (rank[str(card["role"]).casefold()], card["number"]))
        return [
            {
                **card,
                "prompt": (
                    f"[role:{str(card['role']).casefold()}] "
                    f"[board-card:#{card['number']}] "
                    f'Work on "{card["title"]}". Read the Card first and do not '
                    "change another Card."
                ),
            }
            for card in selected
        ]

    def handoff(
        self,
        number: int,
        from_role: str,
        to_role: str,
        note: str,
    ) -> dict[str, Any]:
        _validate_role(from_role)
        _validate_role(to_role)
        if to_role not in HANDOFF_AUTHORITY[from_role]:
            raise ProducerError(f"handoff {from_role} -> {to_role} is not allowed")
        card = self.card(number)
        if not _casefold_equal(card.get("role"), from_role):
            raise ProducerError(
                f"Issue #{number} is owned by {card.get('role')!r}, not {from_role!r}"
            )
        item_id = card.get("item_id")
        if not item_id:
            raise ProducerError(f"Issue #{number} Project item has no id")

        self._set_single_select(str(item_id), self.config.role_field, to_role)
        comment = (
            f"Board handoff: `{from_role}` → `{to_role}`\n\n"
            f"{note.strip() or 'No additional handoff note.'}"
        )
        self.gh.run(
            [
                "issue",
                "comment",
                str(number),
                "--repo",
                self.config.repo,
                "--body",
                comment,
            ]
        )
        return {
            "ok": True,
            "issue": number,
            "url": card.get("url"),
            "from_role": from_role,
            "role": to_role,
            "comment": comment,
        }

    def intake(self, title: str, body: str) -> dict[str, Any]:
        title = title.strip()
        body = body.strip()
        if not title:
            raise ProducerError("intake title must not be empty")
        if not body:
            raise ProducerError("intake body must not be empty")

        issue_url = self.gh.run(
            [
                "issue",
                "create",
                "--repo",
                self.config.repo,
                "--title",
                title,
                "--body",
                body,
            ]
        ).splitlines()[-1]
        match = re.search(r"/issues/(\d+)(?:\D|$)", issue_url)
        if not match:
            raise ProducerError(f"cannot parse Issue number from gh output: {issue_url}")
        number = int(match.group(1))

        payload = self.gh.json(
            [
                "project",
                "item-add",
                str(self.config.project_number),
                "--owner",
                self.config.project_owner,
                "--url",
                issue_url,
                "--format",
                "json",
            ]
        )
        item_id = payload.get("id") if isinstance(payload, dict) else None
        if not item_id:
            raise ProducerError("gh project item-add did not return an item id")

        self._set_single_select(
            str(item_id), self.config.status_field, self.config.backlog_status
        )
        self._set_single_select(str(item_id), self.config.role_field, "analyst")
        self._set_single_select(str(item_id), self.config.role_field, "architect")

        comment = (
            "Board handoff: `analyst` → `architect`\n\n"
            "Requirement intake is complete. Shape the durable specification; "
            "the Card remains in Backlog."
        )
        self.gh.run(
            [
                "issue",
                "comment",
                str(number),
                "--repo",
                self.config.repo,
                "--body",
                comment,
            ]
        )
        return {
            "ok": True,
            "issue": number,
            "url": issue_url,
            "status": self.config.backlog_status,
            "role": "architect",
            "comment": comment,
        }


def _validate_role(role: str) -> None:
    if role not in ROLES:
        raise ProducerError(
            f"unknown role {role!r}; expected one of: {', '.join(ROLES)}"
        )


def _read_body(args: argparse.Namespace) -> str:
    if args.body_file:
        try:
            return Path(args.body_file).read_text(encoding="utf-8")
        except OSError as exc:
            raise ProducerError(f"cannot read body file {args.body_file}: {exc}") from exc
    return args.body or ""


def _print(payload: Any) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Minimal GitHub Project adapter for Producer workflows"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="configuration path (default: .board-superpowers/producer.json)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="write consuming-repo configuration")
    init.add_argument("--repo", required=True, help="GitHub repository OWNER/REPO")
    init.add_argument("--project-owner", required=True)
    init.add_argument("--project-number", required=True, type=int)

    subparsers.add_parser("doctor", help="validate gh access and Project fields")

    listing = subparsers.add_parser("list", help="list configured Project Cards")
    listing.add_argument("--role", choices=ROLES)
    listing.add_argument("--status")

    dispatch = subparsers.add_parser("dispatch", help="render Ready work by Role")
    dispatch.add_argument("--role", choices=ROLES)
    dispatch.add_argument("--format", choices=("text", "json"), default="text")

    intake = subparsers.add_parser("intake", help="create and hand off a requirement")
    intake.add_argument("--title", required=True)
    body = intake.add_mutually_exclusive_group(required=True)
    body.add_argument("--body")
    body.add_argument("--body-file")

    handoff = subparsers.add_parser("handoff", help="change durable Card ownership")
    handoff.add_argument("issue", type=int)
    handoff.add_argument("--from-role", required=True, choices=ROLES)
    handoff.add_argument("--to-role", required=True, choices=ROLES)
    handoff.add_argument("--note", required=True)
    return parser


def main(argv: list[str] | None = None, gh: Gh | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            if args.project_number < 1:
                raise ProducerError("project-number must be a positive integer")
            config = Config(
                repo=args.repo,
                project_owner=args.project_owner,
                project_number=args.project_number,
            )
            config.write(args.config)
            _print({"ok": True, "config": str(args.config), **asdict(config)})
            return 0

        config = Config.load(args.config)
        board = Board(config, gh=gh)

        if args.command == "doctor":
            _print(board.doctor())
        elif args.command == "list":
            cards = board.cards()
            if args.role:
                cards = [
                    card for card in cards if _casefold_equal(card.get("role"), args.role)
                ]
            if args.status:
                cards = [
                    card
                    for card in cards
                    if _casefold_equal(card.get("status"), args.status)
                ]
            _print(cards)
        elif args.command == "dispatch":
            queue = board.dispatch(args.role)
            if args.format == "json":
                _print(queue)
            else:
                if not queue:
                    print("No dispatchable Ready Cards.")
                for entry in queue:
                    print(
                        f"{entry['role']}: #{entry['number']} {entry['title']}\n"
                        f"  {entry['url']}\n"
                        f"  {entry['prompt']}"
                    )
        elif args.command == "intake":
            _print(board.intake(args.title, _read_body(args)))
        elif args.command == "handoff":
            _print(
                board.handoff(
                    args.issue, args.from_role, args.to_role, args.note
                )
            )
        else:  # pragma: no cover - argparse makes this unreachable
            parser.error(f"unknown command: {args.command}")
        return 0
    except ProducerError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
