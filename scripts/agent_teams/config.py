"""Consuming-repo configuration and its validation.

One config file describes which repository and Project this checkout governs,
what the board's fields are called, and the two tuning knobs the runbook
exposes (work-in-progress limit and handoff cap).

Validation reports *every* defect it finds rather than the first, because a
Producer session that has to re-run ``doctor`` six times to learn six missing
options has been failed by its tooling.
"""

from __future__ import annotations

from .errors import AgentTeamsError

import json
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping

from .model import Role, Status

DEFAULT_CONFIG = Path(".agent-teams/config.json")

#: How an architect signals that implementation work may become Ready.
#: ``merged``  -- the specification must be durable on the target branch first
#: ``opened``  -- a linked specification Pull Request is enough
SPEC_COMPLETION_VALUES = ("merged", "opened")

_REPO_PATTERN = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")


class ConfigError(AgentTeamsError):
    """The configuration is absent, unreadable, or self-inconsistent."""


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
    wip_limit: int = 5
    handoff_cap: int = 6
    spec_completion: str = "merged"
    #: Canonical Status value -> the option name this Project actually uses.
    #: Absent entries fall back to the canonical name.
    status_overrides: Mapping[str, str] = field(default_factory=dict)

    # ------------------------------------------------------------ accessors

    def status_name(self, status: Status) -> str:
        """The board option name for a canonical Status."""
        if status is Status.BACKLOG and self.backlog_status:
            return self.backlog_status
        if status is Status.READY and self.ready_status:
            return self.ready_status
        return self.status_overrides.get(status.value, status.value)

    def all_status_names(self) -> dict[Status, str]:
        return {status: self.status_name(status) for status in Status}

    @property
    def dispatch_role_values(self) -> tuple[Role, ...]:
        return tuple(Role.parse(name) for name in self.dispatch_roles)

    @property
    def requires_merged_spec(self) -> bool:
        return self.spec_completion == "merged"

    # -------------------------------------------------------- serialisation

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "repo": self.repo,
            "project_owner": self.project_owner,
            "project_number": self.project_number,
            "role_field": self.role_field,
            "status_field": self.status_field,
            "backlog_status": self.backlog_status,
            "ready_status": self.ready_status,
            "dispatch_roles": list(self.dispatch_roles),
            "wip_limit": self.wip_limit,
            "handoff_cap": self.handoff_cap,
            "spec_completion": self.spec_completion,
        }
        if self.status_overrides:
            payload["status_overrides"] = dict(self.status_overrides)
        return payload

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8"
        )

    @classmethod
    def load(cls, path: Path) -> "Config":
        if not path.is_file():
            raise ConfigError(
                f"configuration missing: {path}; run producer_board.py init"
            )
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigError(f"cannot read configuration {path}: {exc}") from exc
        if not isinstance(raw, dict):
            raise ConfigError(f"configuration {path} must contain a JSON object")
        return cls.from_dict(raw)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "Config":
        problems: list[str] = []

        repo = str(raw.get("repo") or "").strip()
        if not repo:
            problems.append("repo is required")
        elif not _REPO_PATTERN.match(repo):
            problems.append(f"repo must look like OWNER/REPO; got {repo!r}")

        owner = str(raw.get("project_owner") or "").strip()
        if not owner:
            problems.append("project_owner is required")

        number = _positive_int(raw.get("project_number"), "project_number", problems)

        role_field = _non_empty(raw, "role_field", "Role", problems)
        status_field = _non_empty(raw, "status_field", "Status", problems)
        backlog = _non_empty(raw, "backlog_status", "Backlog", problems)
        ready = _non_empty(raw, "ready_status", "Ready", problems)

        roles_raw = raw.get("dispatch_roles", ("architect", "rd", "qa"))
        if isinstance(roles_raw, str) or not isinstance(roles_raw, (list, tuple)):
            problems.append("dispatch_roles must be a list of seat tokens")
            roles: tuple[str, ...] = ()
        else:
            roles = tuple(str(value) for value in roles_raw)
            unknown = [name for name in roles if name not in {r.value for r in Role}]
            if unknown:
                problems.append(
                    "configuration contains unknown dispatch roles: "
                    + ", ".join(sorted(unknown))
                )
            duplicates = sorted({name for name in roles if roles.count(name) > 1})
            if duplicates:
                problems.append(
                    "dispatch_roles contains duplicates: " + ", ".join(duplicates)
                )
            if not roles:
                problems.append("dispatch_roles must not be empty")

        wip_limit = _non_negative_int(raw.get("wip_limit", 5), "wip_limit", problems)
        handoff_cap = _non_negative_int(
            raw.get("handoff_cap", 6), "handoff_cap", problems
        )

        spec_completion = str(raw.get("spec_completion", "merged")).strip().casefold()
        if spec_completion not in SPEC_COMPLETION_VALUES:
            problems.append(
                "spec_completion must be one of "
                + ", ".join(SPEC_COMPLETION_VALUES)
                + f"; got {spec_completion!r}"
            )

        overrides_raw = raw.get("status_overrides", {}) or {}
        overrides: dict[str, str] = {}
        if not isinstance(overrides_raw, dict):
            problems.append("status_overrides must be a JSON object")
        else:
            canonical = {status.value for status in Status}
            for key, value in overrides_raw.items():
                if key not in canonical:
                    problems.append(
                        f"status_overrides key {key!r} is not a canonical Status; "
                        "expected one of: " + ", ".join(sorted(canonical))
                    )
                elif not str(value or "").strip():
                    problems.append(f"status_overrides[{key!r}] must not be empty")
                else:
                    overrides[key] = str(value).strip()

        if problems:
            raise ConfigError(
                "configuration is invalid:\n  - " + "\n  - ".join(problems)
            )

        return cls(
            repo=repo,
            project_owner=owner,
            project_number=number,
            role_field=role_field,
            status_field=status_field,
            backlog_status=backlog,
            ready_status=ready,
            dispatch_roles=roles,
            wip_limit=wip_limit,
            handoff_cap=handoff_cap,
            spec_completion=spec_completion,
            status_overrides=overrides,
        )

    def evolve(self, **changes: Any) -> "Config":
        return replace(self, **changes)


def _non_empty(
    raw: Mapping[str, Any], key: str, default: str, problems: list[str]
) -> str:
    value = raw.get(key, default)
    text = str(value if value is not None else "").strip()
    if not text:
        problems.append(f"{key} must not be empty")
        return default
    return text


def _positive_int(value: Any, key: str, problems: list[str]) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        problems.append(f"{key} must be a positive integer")
        return 1
    if number < 1:
        problems.append(f"{key} must be a positive integer")
        return 1
    return number


def _non_negative_int(value: Any, key: str, problems: list[str]) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        problems.append(f"{key} must be a non-negative integer")
        return 0
    if number < 0:
        problems.append(f"{key} must be a non-negative integer")
        return 0
    return number
