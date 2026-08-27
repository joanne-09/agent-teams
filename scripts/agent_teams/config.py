"""Consuming-repo configuration and its validation.

One config file describes which repository and Project this checkout governs,
what the board's fields are called, and every supported operational tuning
knob. Runtime timing, retry, pagination, and merge choices belong here rather
than as constants scattered through adapters or skill prose.

Validation reports *every* defect it finds rather than the first, because a
Producer session that has to re-run ``doctor`` six times to learn six missing
options has been failed by its tooling.
"""

from __future__ import annotations

from .errors import AgentTeamsError

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping

from . import policy
from .model import Role, Status

DEFAULT_CONFIG = Path(".agent-teams/config.json")

_REPO_PATTERN = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")

#: How the deterministic merge controller closes an eligible *code* Pull
#: Request.
MERGE_METHODS = ("squash", "merge", "rebase")

#: Who closes an eligible *code* Pull Request after deterministic acceptance.
MERGE_MODES = ("automatic", "manual")

#: How *specification* changes reach the repository's base branch.
SPEC_MERGE_MODES = ("direct", "manual")

#: Renamed 2026-08-21. The old pair could not be told apart by name: neither
#: ``spec_merge_mode`` nor ``merge_mode`` said which Pull Request it governed,
#: and ``merge_method`` read as if it belonged to whichever one you had just
#: looked at. Old keys still parse so no consuming repository breaks; they are
#: dropped when configuration is written.
LEGACY_KEYS: Mapping[str, str] = {
    "spec_merge_mode": "spec_pr_merge_mode",
    "merge_mode": "code_pr_merge_mode",
    "merge_method": "code_pr_merge_method",
}

#: Which operational settings each role may override, and by implication which
#: agent consumes each one. A field under a role that does not consume it is a
#: validation error rather than a silent no-op: the whole reason this block
#: exists is that you could not previously tell which agent read which field,
#: and a key that parses but does nothing is the worst form of that.
ROLE_CONFIG_KEYS: Mapping[str, tuple[str, ...]] = {
    "analyst": ("recovery",),
    "architect": ("recovery", "spec_pr_merge_mode"),
    "dev": ("recovery",),
    "qa": ("recovery",),
    "lead": ("recovery",),
    # Not a board Role. The merge executor is a function inside `accept` and
    # `approve-exception`, and the team lead asked for it to be tunable as its
    # own "person" regardless of which seat's process runs it.
    "merge_master": ("recovery", "code_pr_merge_mode", "code_pr_merge_method"),
}

ROLE_CONFIG_SEATS: tuple[str, ...] = tuple(ROLE_CONFIG_KEYS)

#: Reverse of ROLE_CONFIG_KEYS for the non-``recovery`` fields, so a misplaced
#: key can be refused with the seat that actually owns it.
_ROLE_KEY_OWNER: Mapping[str, str] = {
    "spec_pr_merge_mode": "architect",
    "code_pr_merge_mode": "merge_master",
    "code_pr_merge_method": "merge_master",
}

#: Paths whose change makes a delivery user-facing, and therefore makes
#: browser evidence mandatory for a QA pass. Repository policy may add
#: patterns; the defaults always apply.
DEFAULT_UI_PATHS: tuple[str, ...] = (
    "**/*.html", "**/*.htm", "**/*.css", "**/*.scss", "**/*.sass", "**/*.less",
    "**/*.jsx", "**/*.tsx", "**/*.vue", "**/*.svelte",
    "**/components/**", "**/pages/**", "**/views/**",
)

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
class RecoveryConfig:
    """Bounded retry and exponential-backoff settings.

    ``max_retries`` counts retries after the initial attempt. A value of zero
    disables retries. The same schedule is emitted to the coordinating skill
    and used for transient, read-only GitHub calls.
    """

    max_retries: int = 1
    initial_backoff_seconds: float = 5.0
    backoff_multiplier: float = 2.0
    max_backoff_seconds: float = 60.0

    def retry_delay_seconds(self, retry_number: int) -> float:
        """Delay before one-based ``retry_number``, capped deterministically."""
        if retry_number < 1:
            raise ValueError("retry_number must be at least 1")
        delay = self.initial_backoff_seconds * (
            self.backoff_multiplier ** (retry_number - 1)
        )
        return float(min(delay, self.max_backoff_seconds))

    def retry_delays_seconds(self) -> tuple[float, ...]:
        return tuple(
            self.retry_delay_seconds(number)
            for number in range(1, self.max_retries + 1)
        )

    def merged(self, overrides: Mapping[str, Any]) -> "RecoveryConfig":
        """This schedule with named fields replaced, field by field.

        Deliberately not wholesale replacement. A role that asks for one more
        retry must keep the rest of the schedule it did not mention; replacing
        the whole object would reset its backoff to the dataclass default and
        change the delay invisibly.
        """
        return replace(self, **{
            name: value for name, value in overrides.items()
            if name in _RECOVERY_FIELDS
        })

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_retries": self.max_retries,
            "initial_backoff_seconds": self.initial_backoff_seconds,
            "backoff_multiplier": self.backoff_multiplier,
            "max_backoff_seconds": self.max_backoff_seconds,
        }

    def runtime_dict(self) -> dict[str, Any]:
        return {
            **self.to_dict(),
            "retry_delays_seconds": list(self.retry_delays_seconds()),
        }


_RECOVERY_FIELDS = (
    "max_retries", "initial_backoff_seconds", "backoff_multiplier",
    "max_backoff_seconds",
)


@dataclass(frozen=True)
class RoleSettings:
    """One role's overrides. Absent fields inherit the top-level default.

    Only what the repository actually overrode is stored, never a resolved
    copy. Freezing a resolved schedule here would break inheritance the moment
    the dashboard edited a top-level value: a role that had asked for one
    different field would silently stop tracking the other three.
    """

    #: Only the recovery fields this role restated, already validated.
    recovery: Mapping[str, Any] = field(default_factory=dict)
    spec_pr_merge_mode: str | None = None
    code_pr_merge_mode: str | None = None
    code_pr_merge_method: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.recovery:
            payload["recovery"] = dict(self.recovery)
        for name in _ROLE_KEY_OWNER:
            value = getattr(self, name)
            if value is not None:
                payload[name] = value
        return payload


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
    #: Coordinator wait between read-only merge/readiness observations.
    monitor_poll_seconds: int = 30
    #: Initial and maximum Project item-list limits.
    board_page_limit: int = 100
    board_max_items: int = 2000
    #: Default bounded recovery schedule for every role. GitHub transport
    #: applies it only to safe reads; the coordinating skill applies it to
    #: unchanged actions. Per-role overrides live in ``roles``.
    recovery: RecoveryConfig = field(default_factory=RecoveryConfig)
    #: Seat -> the settings that seat overrides. Absent seats inherit every
    #: top-level default, so this block is optional in full.
    roles: Mapping[str, RoleSettings] = field(default_factory=dict)
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
    #: SPEC Pull Request, consumed by the architect. ``direct`` commits the
    #: specification on the current branch and opens no Pull Request at all;
    #: ``manual`` publishes a spec Pull Request and waits for the user to
    #: merge it. Renamed from ``spec_merge_mode``.
    spec_pr_merge_mode: str = "direct"
    #: CODE Pull Request, consumed by the merge executor. ``automatic`` keeps
    #: the routine path human-free after the Ready gate; ``manual`` asks the
    #: user to merge an eligible Pull Request themselves. Renamed from
    #: ``merge_mode``.
    code_pr_merge_mode: str = "automatic"
    #: How the CODE Pull Request is closed when agent-teams issues the merge
    #: itself. Renamed from ``merge_method``.
    code_pr_merge_method: str = "squash"
    #: Extra globs marking user-facing files. Merged with DEFAULT_UI_PATHS; a
    #: delivery touching any of them needs browser evidence to pass QA.
    ui_paths: tuple[str, ...] = ()
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

    # ------------------------------------------------------ per-role lookup

    def recovery_for(self, seat: str) -> RecoveryConfig:
        """The bounded retry schedule this seat actually runs under."""
        seat = str(seat).strip().casefold()
        if seat not in ROLE_CONFIG_KEYS:
            raise ValueError(
                f"unknown configuration seat {seat!r}; expected one of: "
                + ", ".join(ROLE_CONFIG_SEATS)
            )
        overrides = self.roles.get(seat)
        if overrides is None or not overrides.recovery:
            return self.recovery
        return self.recovery.merged(overrides.recovery)

    def recovery_policy_dict(self) -> dict[str, Any]:
        """The whole retry surface, default plus every seat, for the planner.

        Emitted in full rather than only where a seat differs. The coordinating
        skill must not have to work out whether an absent seat means "inherits"
        or "not applicable", and a monitor reading the plan can show each
        worker the exact schedule it is being held to.
        """
        return {
            "default": self.recovery.runtime_dict(),
            "roles": {
                seat: self.recovery_for(seat).runtime_dict()
                for seat in ROLE_CONFIG_SEATS
            },
        }

    def _role_value(self, seat: str, name: str, default: str) -> str:
        overrides = self.roles.get(seat)
        value = getattr(overrides, name, None) if overrides else None
        return value if value is not None else default

    def effective_spec_pr_merge_mode(self) -> str:
        """How the specification reaches the base branch, architect override
        applied."""
        return self._role_value(
            "architect", "spec_pr_merge_mode", self.spec_pr_merge_mode
        )

    def effective_code_pr_merge_mode(self) -> str:
        """Who merges an eligible code Pull Request, merge-master override
        applied."""
        return self._role_value(
            "merge_master", "code_pr_merge_mode", self.code_pr_merge_mode
        )

    def effective_code_pr_merge_method(self) -> str:
        """How agent-teams closes a code Pull Request, merge-master override
        applied."""
        return self._role_value(
            "merge_master", "code_pr_merge_method", self.code_pr_merge_method
        )

    # --------------------------------------------------------- user surface

    def ui_path_patterns(self) -> tuple[str, ...]:
        """Built-in user-facing globs plus whatever the repository added."""
        return tuple(dict.fromkeys(DEFAULT_UI_PATHS + tuple(self.ui_paths)))

    def is_ui_path(self, path: str) -> bool:
        return any(
            policy.path_matches(path, pattern)
            for pattern in self.ui_path_patterns()
        )

    def ui_paths_touched(self, paths: Any) -> tuple[str, ...]:
        """The changed paths that make this delivery user-facing."""
        return tuple(sorted(
            {str(path) for path in paths if self.is_ui_path(str(path))}
        ))

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
            "monitor_poll_seconds": self.monitor_poll_seconds,
            "board_page_limit": self.board_page_limit,
            "board_max_items": self.board_max_items,
            "recovery": self.recovery.to_dict(),
        }
        roles = {
            seat: settings
            for seat, settings in (
                (seat, self.roles[seat].to_dict())
                for seat in ROLE_CONFIG_SEATS if seat in self.roles
            )
            if settings
        }
        if roles:
            payload["roles"] = roles
        if self.status_overrides:
            payload["status_overrides"] = dict(self.status_overrides)
        payload["workspace"] = self.workspace
        payload["protected_paths"] = {
            key: list(value) for key, value in self.protected_paths.items()
        }
        payload["required_checks"] = list(self.required_checks)
        # The legacy names are deliberately absent: a written file always
        # carries the current vocabulary, so a repository migrates simply by
        # letting agent-teams save once.
        payload["spec_pr_merge_mode"] = self.spec_pr_merge_mode
        payload["code_pr_merge_mode"] = self.code_pr_merge_mode
        payload["code_pr_merge_method"] = self.code_pr_merge_method
        if self.ui_paths:
            payload["ui_paths"] = list(self.ui_paths)
        payload["claim_ttl_hours"] = self.claim_ttl_hours
        return payload

    @property
    def revision(self) -> str:
        """Stable identity for one validated, normalized config snapshot."""
        canonical = json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def write(self, path: Path) -> None:
        """Atomically replace a config so concurrent sessions see all or none."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        document = json.dumps(self.to_dict(), indent=2) + "\n"
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                prefix=f".{path.name}.",
                suffix=".tmp",
                dir=str(path.parent),
                delete=False,
            ) as stream:
                temporary = Path(stream.name)
                stream.write(document)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            temporary = None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

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

        monitor_poll_seconds = _positive_int(
            raw.get("monitor_poll_seconds", 30),
            "monitor_poll_seconds",
            problems,
        )
        board_page_limit = _positive_int(
            raw.get("board_page_limit", 100), "board_page_limit", problems
        )
        board_max_items = _positive_int(
            raw.get("board_max_items", 2000), "board_max_items", problems
        )
        if board_max_items < board_page_limit:
            problems.append(
                "board_max_items must be greater than or equal to "
                "board_page_limit"
            )

        recovery_default = RecoveryConfig()
        recovery_raw = raw.get("recovery", {})
        if not isinstance(recovery_raw, dict):
            problems.append("recovery must be a JSON object")
            recovery = recovery_default
        else:
            recovery = RecoveryConfig(
                max_retries=_non_negative_int(
                    recovery_raw.get("max_retries", recovery_default.max_retries),
                    "recovery.max_retries",
                    problems,
                ),
                initial_backoff_seconds=_non_negative_float(
                    recovery_raw.get(
                        "initial_backoff_seconds",
                        recovery_default.initial_backoff_seconds,
                    ),
                    "recovery.initial_backoff_seconds",
                    problems,
                ),
                backoff_multiplier=_float_at_least(
                    recovery_raw.get(
                        "backoff_multiplier", recovery_default.backoff_multiplier
                    ),
                    "recovery.backoff_multiplier",
                    1.0,
                    problems,
                ),
                max_backoff_seconds=_non_negative_float(
                    recovery_raw.get(
                        "max_backoff_seconds", recovery_default.max_backoff_seconds
                    ),
                    "recovery.max_backoff_seconds",
                    problems,
                ),
            )
            if recovery.max_backoff_seconds < recovery.initial_backoff_seconds:
                problems.append(
                    "recovery.max_backoff_seconds must be greater than or equal "
                    "to recovery.initial_backoff_seconds"
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

        spec_pr_merge_mode = _merge_choice(
            raw, "spec_pr_merge_mode", "direct", SPEC_MERGE_MODES, problems
        )
        code_pr_merge_mode = _merge_choice(
            raw, "code_pr_merge_mode", "automatic", MERGE_MODES, problems
        )
        code_pr_merge_method = _merge_choice(
            raw, "code_pr_merge_method", "squash", MERGE_METHODS, problems
        )

        role_settings = _parse_roles(raw.get("roles", {}) or {}, problems)

        ui_raw = raw.get("ui_paths", ()) or ()
        ui_paths: tuple[str, ...] = ()
        if isinstance(ui_raw, str) or not isinstance(ui_raw, (list, tuple)):
            problems.append("ui_paths must be a list of glob patterns")
        else:
            ui_paths = tuple(dict.fromkeys(
                str(pattern).strip() for pattern in ui_raw
                if str(pattern).strip()
            ))

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
            monitor_poll_seconds=monitor_poll_seconds,
            board_page_limit=board_page_limit,
            board_max_items=board_max_items,
            recovery=recovery,
            status_overrides=overrides,
            workspace=workspace,
            protected_paths=protected,
            required_checks=required_checks,
            spec_pr_merge_mode=spec_pr_merge_mode,
            code_pr_merge_mode=code_pr_merge_mode,
            code_pr_merge_method=code_pr_merge_method,
            ui_paths=ui_paths,
            roles=role_settings,
            claim_ttl_hours=claim_ttl_hours,
        )

    def evolve(self, **changes: Any) -> "Config":
        return replace(self, **changes)


def _merge_choice(
    raw: Mapping[str, Any],
    key: str,
    default: str,
    allowed: tuple[str, ...],
    problems: list[str],
) -> str:
    """One merge setting, accepting its pre-2026-08-21 name.

    The current name wins when both are present, which is what a dashboard
    mid-migration emits: it has already written the new key and has not yet
    stopped writing the old one.
    """
    legacy = next((old for old, new in LEGACY_KEYS.items() if new == key), None)
    if key in raw:
        value = raw[key]
    elif legacy is not None and legacy in raw:
        value = raw[legacy]
    else:
        return default
    text = str(value if value is not None else "").strip().casefold()
    if text not in allowed:
        problems.append(
            f"{key} must be one of " + ", ".join(allowed) + f"; got {text!r}"
        )
        return default
    return text


def _parse_roles(
    raw: Any, problems: list[str]
) -> dict[str, "RoleSettings"]:
    """The optional per-role override block.

    Every defect is collected rather than raised, matching the rest of this
    module: a session should learn about all six misplaced keys at once.
    """
    if not isinstance(raw, dict):
        problems.append("roles must be a JSON object keyed by seat")
        return {}

    parsed: dict[str, RoleSettings] = {}
    for seat_raw, settings in raw.items():
        seat = str(seat_raw).strip().casefold()
        if seat not in ROLE_CONFIG_KEYS:
            problems.append(
                f"roles contains unknown seat {seat!r}; expected one of: "
                + ", ".join(ROLE_CONFIG_SEATS)
            )
            continue
        if not isinstance(settings, dict):
            problems.append(f"roles[{seat!r}] must be a JSON object")
            continue

        allowed = ROLE_CONFIG_KEYS[seat]
        values: dict[str, Any] = {}
        for key, value in settings.items():
            name = LEGACY_KEYS.get(str(key), str(key))
            if name in allowed:
                values[name] = value
                continue
            owner = _ROLE_KEY_OWNER.get(name)
            if owner is not None:
                problems.append(
                    f"roles.{seat} does not consume {name!r}; that field is "
                    f"read by the {owner} role, so set it under "
                    f"roles.{owner} or at the top level"
                )
            else:
                problems.append(
                    f"roles.{seat} has no setting {name!r}; it accepts: "
                    + ", ".join(allowed)
                )

        overrides: dict[str, Any] = {}
        recovery_raw = values.pop("recovery", None)
        if recovery_raw is not None:
            if not isinstance(recovery_raw, dict):
                problems.append(f"roles.{seat}.recovery must be a JSON object")
            else:
                overrides["recovery"] = _recovery_overrides(
                    recovery_raw, f"roles.{seat}.recovery", problems
                )

        for name, value in values.items():
            allowed_values = {
                "spec_pr_merge_mode": SPEC_MERGE_MODES,
                "code_pr_merge_mode": MERGE_MODES,
                "code_pr_merge_method": MERGE_METHODS,
            }[name]
            text = str(value if value is not None else "").strip().casefold()
            if text not in allowed_values:
                problems.append(
                    f"roles.{seat}.{name} must be one of "
                    + ", ".join(allowed_values) + f"; got {text!r}"
                )
                continue
            overrides[name] = text

        if overrides:
            parsed[seat] = RoleSettings(**overrides)
    return parsed


def _recovery_overrides(
    raw: Mapping[str, Any], prefix: str, problems: list[str]
) -> dict[str, Any]:
    """Only the recovery fields this role restated, each validated.

    Stored as the override subset rather than a resolved schedule so that a
    later edit to the top-level default still reaches the fields this role did
    not mention.
    """
    overrides: dict[str, Any] = {}
    for key, value in raw.items():
        name = str(key)
        if name == "max_retries":
            overrides[name] = _non_negative_int(
                value, f"{prefix}.max_retries", problems
            )
        elif name in ("initial_backoff_seconds", "max_backoff_seconds"):
            overrides[name] = _non_negative_float(
                value, f"{prefix}.{name}", problems
            )
        elif name == "backoff_multiplier":
            overrides[name] = _float_at_least(
                value, f"{prefix}.backoff_multiplier", 1.0, problems
            )
        else:
            problems.append(
                f"{prefix} has no setting {name!r}; it accepts: "
                + ", ".join(_RECOVERY_FIELDS)
            )
    initial = overrides.get("initial_backoff_seconds")
    maximum = overrides.get("max_backoff_seconds")
    if initial is not None and maximum is not None and maximum < initial:
        problems.append(
            f"{prefix}.max_backoff_seconds must be greater than or equal to "
            f"{prefix}.initial_backoff_seconds"
        )
    return overrides


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


def _non_negative_float(value: Any, key: str, problems: list[str]) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        problems.append(f"{key} must be a non-negative number")
        return 0.0
    if number < 0 or number == float("inf") or number != number:
        problems.append(f"{key} must be a finite non-negative number")
        return 0.0
    return number


def _float_at_least(
    value: Any,
    key: str,
    minimum: float,
    problems: list[str],
) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        problems.append(f"{key} must be a number of at least {minimum:g}")
        return minimum
    if (
        number < minimum
        or number == float("inf")
        or number != number
    ):
        problems.append(f"{key} must be a finite number of at least {minimum:g}")
        return minimum
    return number
