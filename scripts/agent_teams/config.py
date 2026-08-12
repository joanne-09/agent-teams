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

_REPO_PATTERN = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")

#: How the deterministic merge controller closes an eligible Pull Request.
MERGE_METHODS = ("squash", "merge", "rebase")

#: The protected set of ARCHITECTURE.md 4.5, as repository-relative globs.
#: Repository policy may ADD patterns or whole categories. It may not remove
#: one: emptying a default category is a validation error, so dropping
#: protection is a visible, deliberate edit rather than a silent omission.
DEFAULT_PROTECTED_PATHS: Mapping[str, tuple[str, ...]] = {
    "authority-and-policy": (
        "scripts/agent_teams/policy.py",
        "scripts/agent_teams/model.py",
    ),
    "acceptance-and-merge": (
        "scripts/agent_teams/git.py",
        "scripts/agent_teams/workflows.py",
    ),
    "github-workflows-and-credentials": (".github/workflows/**", "**/*credential*"),
    "dependencies-and-manifests": (
        ".claude-plugin/**", "**/package.json", "**/pyproject.toml",
        "**/requirements*.txt",
    ),
    "agent-instructions": ("skills/**", "CLAUDE.md", "AGENTS.md"),
    "security-boundaries": ("**/auth/**", "**/*secret*"),
    "architecture-and-design": ("docs/ARCHITECTURE.md", "docs/specs/**"),
}


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
    dispatch_roles: tuple[str, ...] = ("architect", "dev", "qa")
    wip_limit: int = 5
    handoff_cap: int = 6
    #: Canonical Status value -> the option name this Project actually uses.
    #: Absent entries fall back to the canonical name.
    status_overrides: Mapping[str, str] = field(default_factory=dict)
    #: Where claim worktrees live. Must resolve outside the repository tree.
    workspace: str = "../.worktrees"
    #: Protected category -> globs. Defaults merged in; may only grow.
    protected_paths: Mapping[str, tuple[str, ...]] = field(
        default_factory=lambda: dict(DEFAULT_PROTECTED_PATHS)
    )
    #: Checks that must conclude SUCCESS before a delivery is eligible.
    #: Empty fails closed: nothing is ever eligible (ARCHITECTURE.md 4.5).
    required_checks: tuple[str, ...] = ()
    merge_method: str = "squash"
    #: Age past which triage flags a claim as stale.
    claim_ttl_hours: int = 72

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
        }
        if self.status_overrides:
            payload["status_overrides"] = dict(self.status_overrides)
        payload["workspace"] = self.workspace
        payload["protected_paths"] = {
            key: list(value) for key, value in self.protected_paths.items()
        }
        payload["required_checks"] = list(self.required_checks)
        payload["merge_method"] = self.merge_method
        payload["claim_ttl_hours"] = self.claim_ttl_hours
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

        roles_raw = raw.get("dispatch_roles", ("architect", "dev", "qa"))
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

        workspace = _non_empty(raw, "workspace", "../.worktrees", problems)
        if not workspace.startswith(".."):
            problems.append(
                "workspace must resolve outside the repository tree (start it "
                f"with '..'); got {workspace!r}. A repo-internal worktree gets "
                "scanned by editors and confuses which checkout is canonical."
            )

        merge_method = str(raw.get("merge_method", "squash")).strip().casefold()
        if merge_method not in MERGE_METHODS:
            problems.append(
                "merge_method must be one of " + ", ".join(MERGE_METHODS)
                + f"; got {merge_method!r}"
            )

        checks_raw = raw.get("required_checks", ()) or ()
        required_checks: tuple[str, ...] = ()
        if isinstance(checks_raw, str) or not isinstance(checks_raw, (list, tuple)):
            problems.append("required_checks must be a list of check names")
        else:
            required_checks = tuple(
                str(name).strip() for name in checks_raw if str(name).strip()
            )

        claim_ttl_hours = _non_negative_int(
            raw.get("claim_ttl_hours", 72), "claim_ttl_hours", problems
        )

        protected_raw = raw.get("protected_paths", {}) or {}
        protected: dict[str, tuple[str, ...]] = {
            key: tuple(value) for key, value in DEFAULT_PROTECTED_PATHS.items()
        }
        if not isinstance(protected_raw, dict):
            problems.append("protected_paths must be a JSON object")
        else:
            for key, value in protected_raw.items():
                if isinstance(value, str) or not isinstance(value, (list, tuple)):
                    problems.append(
                        f"protected_paths[{key!r}] must be a list of glob patterns"
                    )
                    continue
                patterns = tuple(str(p).strip() for p in value if str(p).strip())
                if key in DEFAULT_PROTECTED_PATHS and not patterns:
                    problems.append(
                        f"protected_paths[{key!r}] is a default protected "
                        "category and must not be emptied; repository policy "
                        "may add categories but must not silently remove one"
                    )
                    continue
                # dict.fromkeys preserves order while dropping duplicates, so a
                # repository re-stating a default pattern does not double it.
                protected[key] = tuple(dict.fromkeys(protected.get(key, ()) + patterns))

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
            status_overrides=overrides,
            workspace=workspace,
            protected_paths=protected,
            required_checks=required_checks,
            merge_method=merge_method,
            claim_ttl_hours=claim_ttl_hours,
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
