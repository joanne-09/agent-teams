"""A fake GitHub CLI shared by the board and workflow test suites.

Records every call so tests can assert on mutation order, and lets any single
subcommand be armed to fail -- which is how partial-failure recovery gets
exercised without a live Project.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from agent_teams.github import GitHubError  # noqa: E402
from agent_teams.model import ROLES  # noqa: E402

REPO = "acme/widgets"

FIELDS = {
    "fields": [
        {
            "id": "ROLE_FIELD",
            "name": "Role",
            "options": [{"id": f"ROLE_{n.upper()}", "name": n} for n in ROLES],
        },
        {
            "id": "STATUS_FIELD",
            "name": "Status",
            "options": [
                {"id": "STATUS_BACKLOG", "name": "Backlog"},
                {"id": "STATUS_READY", "name": "Ready"},
                {"id": "STATUS_IN_PROGRESS", "name": "In Progress"},
                {"id": "STATUS_BLOCKED", "name": "Blocked"},
                {"id": "STATUS_IN_REVIEW", "name": "In Review"},
                {"id": "STATUS_DONE", "name": "Done"},
            ],
        },
    ]
}


def _item(item_id, number, title, status=None, role=None, repo=REPO):
    entry = {
        "id": item_id,
        "content": {
            "number": number,
            "repository": repo,
            "title": title,
            "url": f"https://github.com/{repo}/issues/{number}",
        },
    }
    if status is not None:
        entry["status"] = status
    if role is not None:
        entry["role"] = role
    return entry


ITEMS = {
    "items": [
        _item("ITEM_12", 12, "Implement parser", "Ready", "rd"),
        _item("ITEM_8", 8, "Specify parser", "Ready", "architect"),
        _item("ITEM_9", 9, "Blocked work", "Blocked", "rd"),
        _item("ITEM_10", 10, "Missing Role", "Ready"),
        _item("ITEM_OTHER", 99, "Wrong repository", "Ready", "rd", repo="acme/other"),
        _item("ITEM_20", 20, "Shaped requirement", "Backlog", "architect"),
        _item("ITEM_21", 21, "Delivery awaiting verdict", "In Review", "qa"),
        _item("ITEM_22", 22, "Verified, awaiting merge", "In Review", "human"),
        _item("ITEM_23", 23, "Active build", "In Progress", "rd"),
    ]
}


class FakeGh:
    """Injectable stand-in for :class:`agent_teams.github.Gh`."""

    def __init__(self, *, fail_on=None, comments=None, pr_state=None, items=None):
        #: subcommand pair (e.g. "issue comment") -> message, or
        #: (message, nth) to fail only the nth occurrence. The nth form is how
        #: a failure between two identical calls -- the Status write and the
        #: Role write are both ``project item-edit`` -- gets exercised.
        self.fail_on = dict(fail_on or {})
        self.comments = list(comments or [])
        self.pr_state = pr_state or {"state": "MERGED", "mergedAt": "2026-07-30T00:00:00Z"}
        self.items = items if items is not None else ITEMS
        self.calls: list[list[str]] = []
        self._seen: dict[str, int] = {}

    # ------------------------------------------------------------- plumbing

    def available(self) -> bool:
        return True

    def _maybe_fail(self, args):
        key = " ".join(args[:2])
        self._seen[key] = self._seen.get(key, 0) + 1
        if key not in self.fail_on:
            return
        rule = self.fail_on[key]
        if isinstance(rule, tuple):
            message, nth = rule
            if self._seen[key] != nth:
                return
        else:
            message = rule
        raise GitHubError(message, kind="test")

    def _record(self, args):
        args = list(args)
        self.calls.append(args)
        self._maybe_fail(args)
        return args

    def calls_matching(self, *prefix):
        want = list(prefix)
        return [call for call in self.calls if call[: len(want)] == want]

    # ------------------------------------------------------------- responses

    def run(self, args):
        args = self._record(args)
        head = args[:2]
        if head == ["auth", "status"]:
            return "authenticated"
        if head == ["issue", "create"]:
            return f"https://github.com/{REPO}/issues/42"
        if head in (["project", "item-edit"], ["issue", "comment"]):
            return ""
        raise AssertionError(f"unexpected gh run call: {args}")

    def json(self, args):
        args = self._record(args)
        head = args[:2]
        if head == ["project", "view"]:
            return {"id": "PROJECT_ID"}
        if head == ["project", "field-list"]:
            return FIELDS
        if head == ["project", "item-list"]:
            return self.items
        if head == ["project", "item-add"]:
            return {"id": "ITEM_42"}
        if head == ["issue", "view"]:
            return {"comments": [{"body": body} for body in self.comments]}
        if head == ["pr", "view"]:
            return {
                "number": 57,
                "url": f"https://github.com/{REPO}/pull/57",
                **self.pr_state,
            }
        raise AssertionError(f"unexpected gh json call: {args}")


class SaturatingGh(FakeGh):
    """Returns exactly as many items as the caller asked for, up to ``total``.

    Models the only truncation signal ``gh project item-list`` gives: a
    response that comes back exactly at the requested limit.
    """

    def __init__(self, total: int, **kwargs):
        super().__init__(**kwargs)
        self.total = total
        self.limits_requested: list[int] = []

    def json(self, args):
        args = list(args)
        if args[:2] == ["project", "item-list"]:
            self.calls.append(args)
            limit = int(args[args.index("--limit") + 1])
            self.limits_requested.append(limit)
            count = min(limit, self.total)
            return {
                "items": [
                    _item(f"ITEM_{n}", n, f"Card {n}", "Ready", "rd")
                    for n in range(1, count + 1)
                ]
            }
        return super().json(args)
