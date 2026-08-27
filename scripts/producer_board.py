#!/usr/bin/env python3
"""Public command line entry point for agent-teams Producer workflows.

This file stays the stable surface every SKILL invokes. The behaviour lives in
``scripts/agent_teams/``: model and policy are pure, github and board talk to
the GitHub CLI, and workflows composes them into transactions that report
their own partial failures.

Every command prints one JSON object (or a JSON array, for listings) on stdout
and exits 0, or prints ``{"ok": false, "error": ...}`` on stderr and exits 1.
A skill must never claim a mutation succeeded without that envelope.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent_teams import policy  # noqa: E402
from agent_teams.board import Board, BoardError, PartialHandoff  # noqa: E402
from agent_teams.config import DEFAULT_CONFIG, Config, ConfigError  # noqa: E402
from agent_teams.errors import AgentTeamsError  # noqa: E402
from agent_teams.github import Gh, GitHubError  # noqa: E402
from agent_teams.model import (  # noqa: E402
    ROLES, STATUSES, Card, Role, Status, Verdict,
)
from agent_teams.workflows import Consumer, Producer, WorkflowError  # noqa: E402

#: Retained so existing callers and tests can keep catching one name.
ProducerError = AgentTeamsError

__all__ = [
    "Board", "BoardError", "Card", "Config", "ConfigError", "Consumer", "Gh",
    "GitHubError", "PartialHandoff", "Producer", "ProducerError", "ROLES",
    "STATUSES", "Role", "Status", "Verdict", "WorkflowError", "main", "policy",
]


def _acting_role_option(
    parser: argparse.ArgumentParser,
    fallback: str | None,
    choices: list[str] | None = None,
) -> None:
    """Register ``--acting-role`` without baking the seat into argparse.

    The seat a command acts as is resolved at run time by
    :func:`policy.resolve_acting_role`: a process binding
    (``AGENT_TEAMS_ACTING_ROLE``) wins over the flag, the flag over
    ``fallback``, and ``human`` is refused inside an agent session. Keeping
    the default out of argparse is what lets the resolver tell "the caller
    said human" from "the caller said nothing".
    """
    parser.add_argument(
        "--acting-role", default=None, choices=choices or ROLES,
        help=f"seat this command acts as (default: {fallback or 'required'})",
    )
    parser.set_defaults(acting_role_fallback=fallback)


def _acting_role(args: argparse.Namespace, env: Mapping[str, str]) -> Role:
    return policy.resolve_acting_role(
        Role.parse_optional(args.acting_role), env,
        Role.parse_optional(getattr(args, "acting_role_fallback", None)),
    )


def _print(payload: Any) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


def _read_body(args: argparse.Namespace) -> str:
    if getattr(args, "body_file", None):
        try:
            return Path(args.body_file).read_text(encoding="utf-8")
        except OSError as exc:
            raise WorkflowError(f"cannot read body file {args.body_file}: {exc}") from exc
    return getattr(args, "body", "") or ""


def _read_verdict(path: str) -> Verdict:
    """Load a structured verdict from its JSON document.

    A file rather than flags: a verdict carries enumerated changed files,
    per-dimension evidence, and challenge outcomes, none of which survive
    shell quoting.
    """
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"cannot read evidence file {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise WorkflowError(f"{path} must contain a JSON object")
    return Verdict.from_dict(raw)


def _read_children(path: str) -> list[dict[str, str]]:
    """Load decomposition children from a JSON file.

    Shape: ``[{"title": "...", "body": "..."}, ...]``. A file rather than
    repeated flags, because a Card body is multi-line prose and shell quoting
    mangles it.
    """
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"cannot read children file {path}: {exc}") from exc
    if not isinstance(raw, list) or not all(isinstance(item, dict) for item in raw):
        raise WorkflowError(
            f"{path} must contain a JSON array of objects with 'title' and 'body'"
        )
    return [
        {"title": str(item.get("title", "")), "body": str(item.get("body", ""))}
        for item in raw
    ]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="GitHub Project adapter for agent-teams Producer workflows"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="configuration path (default: .agent-teams/config.json)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="write consuming-repo configuration")
    init.add_argument("--repo", required=True, help="GitHub repository OWNER/REPO")
    init.add_argument("--project-owner", required=True)
    init.add_argument("--project-number", required=True, type=int)
    init.add_argument("--wip-limit", type=int, default=5)
    init.add_argument("--handoff-cap", type=int, default=6)
    init.add_argument(
        "--required-check",
        action="append",
        default=[],
        help="required GitHub check name; repeat for each automated-merge check",
    )
    sub.add_parser("doctor", help="validate gh access, Project fields, and options")

    boot = sub.add_parser(
        "bootstrap", help="read-only session startup context for one seat"
    )
    boot.add_argument("--role", required=True, choices=ROLES)

    listing = sub.add_parser("list", help="list configured Project Cards")
    listing.add_argument("--role", choices=ROLES)
    listing.add_argument("--status")

    brief = sub.add_parser("brief", help="Tech Lead whole-team briefing")
    brief.add_argument(
        "--with-handoffs",
        action="store_true",
        help="also count handoffs per Card (one extra API call per Card)",
    )
    brief.add_argument("--format", choices=("text", "json"), default="text")

    sub.add_parser("triage", help="Blocked Cards grouped by responsible seat")
    sub.add_parser("queue", help="Quality Assurance verification queue inspection")

    dispatch = sub.add_parser("dispatch", help="render Ready work by Role")
    dispatch.add_argument("--role", choices=ROLES)
    dispatch.add_argument("--format", choices=("text", "json"), default="text")

    next_actions = sub.add_parser(
        "next-actions", help="plan runnable stages and allowed human boundaries"
    )
    next_actions.add_argument("issue", type=int, nargs="?")

    gates = sub.add_parser(
        "gates",
        help="list only the boundaries a person must open, read-only; each "
        "entry carries argv when a plugin command opens it",
    )
    gates.add_argument("issue", type=int, nargs="?")

    intake = sub.add_parser("intake", help="create and hand off a requirement")
    intake.add_argument("--title", required=True)
    body = intake.add_mutually_exclusive_group(required=True)
    body.add_argument("--body")
    body.add_argument("--body-file")

    clarify = sub.add_parser(
        "clarify", help="record clarification on an existing returned Card"
    )
    clarify.add_argument("issue", type=int)
    clarification = clarify.add_mutually_exclusive_group(required=True)
    clarification.add_argument("--note")
    clarification.add_argument("--note-file")
    _acting_role_option(clarify, "analyst", ["analyst"])

    create = sub.add_parser("create-card", help="create one Card in an explicit state")
    create.add_argument("--title", required=True)
    create_body = create.add_mutually_exclusive_group(required=True)
    create_body.add_argument("--body")
    create_body.add_argument("--body-file")
    create.add_argument("--status", default="Backlog", choices=STATUSES)
    create.add_argument("--role", default="human", choices=ROLES)
    _acting_role_option(create, "architect")

    promote = sub.add_parser(
        "promote",
        help="human readiness gate: approve a shaped Card into Ready and hand "
        "it to development",
    )
    promote.add_argument("issue", type=int)
    promote.add_argument(
        "--spec",
        help="optional override; defaults to the direct spec recorded on the Card",
    )
    _acting_role_option(promote, "human")
    promote.add_argument("--note", default="")

    decompose = sub.add_parser(
        "decompose", help="create flat implementation Cards from a specification"
    )
    decompose.add_argument("parent", type=int)
    decompose.add_argument(
        "--spec", help="optional override; defaults to the spec recorded on the Card"
    )
    decompose.add_argument(
        "--children",
        required=True,
        help='JSON file: [{"title": "...", "body": "..."}, ...]',
    )
    _acting_role_option(decompose, "architect")

    publish_spec = sub.add_parser(
        "publish-spec",
        help="publish one docs specification through the configured merge mode",
    )
    publish_spec.add_argument("issue", type=int)
    publish_spec.add_argument("--path", required=True)
    _acting_role_option(publish_spec, "architect")

    finalize_spec = sub.add_parser(
        "finalize-spec-merge",
        help="sync and record a user-merged specification Pull Request",
    )
    finalize_spec.add_argument("issue", type=int)

    finalize = sub.add_parser(
        "finalize-readiness", help="hand a human-readied specified Card to dev"
    )
    finalize.add_argument("issue", type=int)

    release = sub.add_parser(
        "release-claim",
        help="deprecated emergency cleanup: delete an abandoned claim branch; "
        "normal interrupted work resumes the existing branch automatically",
    )
    release.add_argument("issue", type=int)
    release.add_argument(
        "--branch", required=True,
        help="the remote claim branch to delete (as named in the Card's handoffs)",
    )
    _acting_role_option(release, "human")
    release.add_argument("--note", default="")

    transition = sub.add_parser("transition", help="move a Card's Status")
    transition.add_argument("issue", type=int)
    transition.add_argument("--to", required=True, choices=STATUSES, dest="to_status")
    _acting_role_option(transition, None)

    handoff = sub.add_parser("handoff", help="change durable Card ownership")
    handoff.add_argument("issue", type=int)
    handoff.add_argument("--from-role", required=True, choices=ROLES)
    handoff.add_argument("--to-role", required=True, choices=ROLES)
    handoff.add_argument("--note", required=True)
    handoff.add_argument("--needs", default="")
    handoff.add_argument("--artifacts", default="")

    # ---------------------------------------------------------- Consumer

    claim = sub.add_parser(
        "claim", help="reserve one Ready Card and open its isolated worktree"
    )
    claim.add_argument("issue", type=int)
    _acting_role_option(claim, None, ["dev", "architect"])

    resume = sub.add_parser(
        "resume", help="materialise an In Progress Card's durable claim worktree"
    )
    resume.add_argument("issue", type=int)
    _acting_role_option(resume, None, ["dev", "architect"])

    submit = sub.add_parser(
        "submit-pr", help="open or update one Pull Request and hand off to qa"
    )
    submit.add_argument("issue", type=int)
    submit.add_argument("--title", required=True)
    submit.add_argument("--body-file", required=True)
    _acting_role_option(submit, "dev", ["dev", "architect"])

    verdict = sub.add_parser(
        "verdict",
        help="publish Quality Assurance review evidence for the current head",
    )
    verdict.add_argument("issue", type=int)
    verdict.add_argument(
        "--evidence-file", required=True, help="JSON verdict document"
    )

    # Deliberately takes no other argument. Every input to the acceptance
    # decision is read from live GitHub state, so there is nothing for a
    # caller to steer -- which is what makes "no agent seat chooses the merge
    # route" a property of the interface rather than a promise in prose.
    accept = sub.add_parser(
        "accept",
        help="evaluate the published verdict and execute the deterministic route",
    )
    accept.add_argument("issue", type=int)

    refresh = sub.add_parser(
        "refresh-verification",
        help="return a stale protected-change exception to QA",
    )
    refresh.add_argument("issue", type=int)

    reconcile = sub.add_parser(
        "reconcile-done", help="record a confirmed merge and clean the claim"
    )
    reconcile.add_argument("issue", type=int)
    _acting_role_option(reconcile, "lead")

    exception = sub.add_parser(
        "approve-exception",
        help="human final gate: merge the exact protected head and reconcile Done",
    )
    exception.add_argument("issue", type=int)
    _acting_role_option(exception, "human")

    worktrees = sub.add_parser(
        "worktree-status", help="claims, worktrees, and presence (read-only)"
    )
    worktrees.add_argument("issue", type=int, nargs="?")
    return parser


def _dispatch_text(queue: list[dict[str, Any]]) -> None:
    if not queue:
        print("No dispatchable Ready Cards.")
        return
    for entry in queue:
        print(
            f"{entry['role']}: #{entry['number']} {entry['title']}\n"
            f"  {entry['url']}\n"
            f"  {entry['prompt']}"
        )


def _brief_text(report: dict[str, Any]) -> None:
    board = report["board"]
    print(f"Board: {board['total']} cards - WIP {board['wip']}/{board['wip_limit']}")
    print("")
    print("By lane")
    for lane, detail in report["lanes"].items():
        label = f"  {lane:<12}{detail['count']}"
        if not detail["cards"]:
            print(label)
            continue
        for index, card in enumerate(detail["cards"]):
            prefix = label if index == 0 else " " * len(label)
            print(
                f"{prefix}  #{card['number']} {card['title']} "
                f"{card.get('routing_state', '')}".rstrip()
            )
    warnings = []
    warnings += [
        f"#{card['number']} blocked - {card['title']}" for card in report["blocked"]
    ]
    warnings += [
        f"#{card['number']} has {card['handoff_count']} handoffs, cap is {card['cap']}"
        for card in report["near_handoff_cap"]
    ]
    warnings += [
        f"#{card['number']} {card['problem']}" for card in report["data_quality"]
    ]
    if warnings:
        print("")
        for line in warnings:
            print(f"  !  {line}")
    print("")
    print(f"Recommended next: {report['recommendation']}")


def main(
    argv: list[str] | None = None,
    gh: Gh | None = None,
    git: Any = None,
    env: Mapping[str, str] | None = None,
) -> int:
    """Run one command. ``gh``, ``git`` and ``env`` are injection points for tests."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    env = os.environ if env is None else env
    try:
        if args.command == "init":
            config = Config.from_dict(
                {
                    "repo": args.repo,
                    "project_owner": args.project_owner,
                    "project_number": args.project_number,
                    "wip_limit": args.wip_limit,
                    "handoff_cap": args.handoff_cap,
                    "required_checks": args.required_check,
                }
            )
            config.write(args.config)
            _print({"ok": True, "config": str(args.config), **config.to_dict()})
            return 0

        config = Config.load(args.config)
        # The process binding, not the flag: the seat is resolved per command
        # below, but the transport is constructed once and must already know
        # whose retry budget it is spending.
        board = Board(config, gh=gh, seat=env.get(policy.ACTING_ROLE_ENV))
        producer = Producer(config, board, git=git)
        consumer = Consumer(config, board, git=git)

        if args.command == "doctor":
            _print(board.doctor())

        elif args.command == "bootstrap":
            _print(producer.bootstrap(Role.parse(args.role)))

        elif args.command == "list":
            cards = board.cards()
            if args.role:
                wanted_role = Role.parse(args.role)
                cards = [card for card in cards if card.role is wanted_role]
            if args.status:
                wanted_status = Status.parse(args.status)
                cards = [card for card in cards if card.status is wanted_status]
            _print([card.to_dict() for card in cards])

        elif args.command == "brief":
            report = producer.brief(with_handoffs=args.with_handoffs)
            if args.format == "json":
                _print(report)
            else:
                _brief_text(report)

        elif args.command == "triage":
            _print(producer.triage())

        elif args.command == "queue":
            _print(producer.verification_queue())

        elif args.command == "dispatch":
            queue = producer.dispatch(Role.parse(args.role) if args.role else None)
            if args.format == "json":
                _print(queue)
            else:
                _dispatch_text(queue)

        elif args.command == "next-actions":
            _print(producer.next_actions(args.issue))

        elif args.command == "gates":
            _print(producer.human_gates(args.issue))

        elif args.command == "intake":
            result = producer.intake(args.title, _read_body(args))
            _print(result)
            return 0 if result.get("ok") else 1

        elif args.command == "clarify":
            note = (
                Path(args.note_file).read_text(encoding="utf-8")
                if args.note_file else args.note
            )
            result = producer.clarify(
                args.issue, note, _acting_role(args, env)
            )
            _print(result)
            return 0 if result.get("ok") else 1

        elif args.command == "create-card":
            result = producer.create_card(
                args.title,
                _read_body(args),
                Status.parse(args.status),
                Role.parse(args.role),
                _acting_role(args, env),
            )
            _print(result)
            return 0 if result.get("ok") else 1

        elif args.command == "promote":
            result = producer.promote(
                args.issue,
                args.spec or "",
                _acting_role(args, env),
                reason=args.note,
                origin=policy.human_origin(env),
            )
            _print(result)
            return 0 if result.get("ok") else 1

        elif args.command == "decompose":
            result = producer.decompose(
                args.parent,
                _read_children(args.children),
                args.spec or "",
                _acting_role(args, env),
            )
            _print(result)
            return 0 if result.get("ok") else 1

        elif args.command == "publish-spec":
            result = producer.publish_specification(
                args.issue, args.path, _acting_role(args, env)
            )
            _print(result)
            return 0 if result.get("ok") else 1

        elif args.command == "finalize-spec-merge":
            result = producer.finalize_specification_merge(args.issue)
            _print(result)
            return 0 if result.get("ok") else 1

        elif args.command == "finalize-readiness":
            result = producer.finalize_readiness(args.issue)
            _print(result)
            return 0 if result.get("ok") else 1

        elif args.command == "release-claim":
            result = producer.release_claim(
                args.issue,
                args.branch,
                _acting_role(args, env),
                reason=args.note,
            )
            _print(result)
            return 0 if result.get("ok") else 1

        elif args.command == "transition":
            _print(
                producer.transition(
                    args.issue,
                    Status.parse(args.to_status),
                    _acting_role(args, env),
                )
            )

        elif args.command == "handoff":
            result = producer.handoff(
                args.issue,
                policy.resolve_acting_role(Role.parse(args.from_role), env),
                Role.parse(args.to_role),
                args.note,
                needs=args.needs,
                artifacts=args.artifacts,
            )
            _print(result)
            return 0 if result.get("ok") else 1

        elif args.command == "claim":
            result = consumer.claim(args.issue, _acting_role(args, env))
            _print(result)
            return 0 if result.get("ok") else 1

        elif args.command == "resume":
            result = consumer.resume(args.issue, _acting_role(args, env))
            _print(result)
            return 0 if result.get("ok") else 1

        elif args.command == "submit-pr":
            result = consumer.submit(
                args.issue,
                _acting_role(args, env),
                args.title,
                _read_body(args),
            )
            _print(result)
            return 0 if result.get("ok") else 1

        elif args.command == "verdict":
            result = consumer.verdict(args.issue, _read_verdict(args.evidence_file))
            _print(result)
            return 0 if result.get("ok") else 1

        elif args.command == "accept":
            result = consumer.accept(args.issue)
            _print(result)
            return 0 if result.get("ok") else 1

        elif args.command == "refresh-verification":
            result = consumer.refresh_verification(args.issue)
            _print(result)
            return 0 if result.get("ok") else 1

        elif args.command == "reconcile-done":
            result = consumer.reconcile(args.issue, _acting_role(args, env))
            _print(result)
            return 0 if result.get("ok") else 1

        elif args.command == "approve-exception":
            result = consumer.approve_exception(
                args.issue, _acting_role(args, env),
                origin=policy.human_origin(env),
            )
            _print(result)
            return 0 if result.get("ok") else 1

        elif args.command == "worktree-status":
            _print(consumer.worktree_status(args.issue))

        else:  # pragma: no cover - argparse makes this unreachable
            parser.error(f"unknown command: {args.command}")
        return 0

    except AgentTeamsError as exc:
        payload: dict[str, Any] = {"ok": False, "error": str(exc)}
        if isinstance(exc, policy.PolicyError):
            payload["refusal"] = type(exc).__name__
        print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
