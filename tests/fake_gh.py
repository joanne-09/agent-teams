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
        _item("ITEM_12", 12, "Implement parser", "Ready", "dev"),
        _item("ITEM_8", 8, "Specify parser", "Ready", "architect"),
        _item("ITEM_9", 9, "Blocked work", "Blocked", "dev"),
        _item("ITEM_10", 10, "Missing Role", "Ready"),
        _item("ITEM_OTHER", 99, "Wrong repository", "Ready", "dev", repo="acme/other"),
        _item("ITEM_20", 20, "Shaped requirement", "Backlog", "architect"),
        _item("ITEM_21", 21, "Delivery awaiting verdict", "In Review", "qa"),
        _item("ITEM_22", 22, "Verified, awaiting merge", "In Review", "human"),
        _item("ITEM_23", 23, "Active build", "In Progress", "dev"),
    ]
}


def board_with(*specs):
    """An item list of exactly the Cards a test needs.

    Pass ``(number, title, status, role)`` tuples. Use this instead of adding
    to ``ITEMS`` when a test needs one particular routing state -- the shared
    fixture is asserted on by the briefing and lane tests, so growing it to
    suit one test breaks several others.
    """
    return {
        "items": [
            _item(f"ITEM_{number}", number, title, status, role)
            for number, title, status, role in specs
        ]
    }


class FakeGh:
    """Injectable stand-in for :class:`agent_teams.github.Gh`."""

    def __init__(
        self, *, fail_on=None, comments=None, pr_state=None, items=None,
        pr_view=None, open_prs=None, auto_merge_allowed=True, issue_bodies=None,
    ):
        #: subcommand pair (e.g. "issue comment") -> message, or
        #: (message, nth) to fail only the nth occurrence. The nth form is how
        #: a failure between two identical calls -- the Status write and the
        #: Role write are both ``project item-edit`` -- gets exercised.
        self.fail_on = dict(fail_on or {})
        self.comments = list(comments or [])
        self.issue_bodies = dict(issue_bodies or {})
        self.pr_state = pr_state or {"state": "MERGED", "mergedAt": "2026-07-30T00:00:00Z"}
        self.items = items if items is not None else ITEMS
        #: The review facts `Board.pull_request` normalises.
        self.pr_view = pr_view if pr_view is not None else {
            "number": 57,
            "url": f"https://github.com/{REPO}/pull/57",
            "headRefOid": "a" * 40,
            "state": "OPEN",
            "mergeable": "MERGEABLE",
            "isDraft": False,
            "files": [{"path": "src/parser.py"}, {"path": "tests/test_parser.py"}],
            "statusCheckRollup": [
                {"name": "build", "conclusion": "SUCCESS"},
                {"name": "test", "conclusion": "SUCCESS"},
            ],
        }
        #: Pull Requests already open on a head branch, so create-or-update
        #: can be exercised both ways. Empty means "no Pull Request yet".
        self.open_prs = list(open_prs or [])
        self.auto_merge_allowed = auto_merge_allowed
        self.calls: list[list[str]] = []
        self._seen: dict[str, int] = {}
        #: Mirrors ``Gh.mutations``: Board keys its read cache on it.
        self.mutations = 0
        self.closed_issues: list[int] = []

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

    def _items_page(self, args):
        """Answer Board.ITEMS_QUERY over ``self.items`` with real cursors."""
        fields = dict(
            args[i + 1].split("=", 1) for i, a in enumerate(args) if a in ("-f", "-F")
        )
        first = int(fields.get("first", 100))
        start = int(fields.get("after", 0) or 0)
        raw = self.items
        items = list(raw.get("items", [])) if isinstance(raw, dict) else list(raw)
        page = items[start:start + first]
        nodes = []
        for item in page:
            node = {"id": item.get("id"), "content": item.get("content")}
            status = item.get(fields.get("status", "Status"), item.get("status"))
            role = item.get(fields.get("role", "Role"), item.get("role"))
            node["status"] = {"name": status} if isinstance(status, str) else status
            node["role"] = {"name": role} if isinstance(role, str) else role
            nodes.append(node)
        end = start + len(page)
        return {"data": {"repositoryOwner": {"projectV2": {"items": {
            "pageInfo": {"hasNextPage": end < len(items), "endCursor": str(end)},
            "nodes": nodes,
        }}}}}

    def calls_matching(self, *prefix):
        want = list(prefix)
        return [call for call in self.calls if call[: len(want)] == want]

    # ------------------------------------------------------------- responses

    def run(self, args):
        args = self._record(args)
        head = args[:2]
        if head == ["auth", "status"]:
            return "authenticated"
        if head != ["api", f"repos/{REPO}"]:
            self.mutations += 1
        if head == ["issue", "create"]:
            if "--body" in args:
                self.issue_bodies[42] = str(args[args.index("--body") + 1])
            return f"https://github.com/{REPO}/issues/42"
        if head == ["issue", "close"]:
            self.closed_issues.append(int(args[2]))
            return ""
        if head == ["issue", "comment"]:
            if "--body" in args:
                self.comments.append(str(args[args.index("--body") + 1]))
            return ""
        if head == ["project", "item-edit"]:
            return ""
        if head == ["api", "-X"]:  # gh api -X DELETE repos/.../git/refs/heads/...
            return ""
        if head == ["api", f"repos/{REPO}"]:  # REST repo object: allow_auto_merge
            return str(self.auto_merge_allowed).casefold()
        if head == ["pr", "create"]:
            return f"https://github.com/{REPO}/pull/57"
        if head == ["pr", "merge"]:
            if "--auto" in args:
                self.pr_view["autoMergeRequest"] = {"enabledAt": "now"}
            return ""
        if head == ["pr", "edit"]:
            return ""
        raise AssertionError(f"unexpected gh run call: {args}")

    def json(self, args):
        args = self._record(args)
        head = args[:2]
        if head == ["project", "view"]:
            return {"id": "PROJECT_ID"}
        if head == ["project", "field-list"]:
            return FIELDS
        if head == ["api", "graphql"]:
            return self._items_page(args)
        if head == ["project", "item-add"]:
            return {"id": "ITEM_42"}
        if head == ["issue", "view"]:
            number = int(args[2])
            return {
                "body": self.issue_bodies.get(number, ""),
                "comments": [{"body": body} for body in self.comments],
            }
        if head == ["pr", "view"]:
            # Two callers with different --json field sets: pull_request()
            # asks for the review facts, merge_state() for the merge outcome.
            wanted = args[args.index("--json") + 1] if "--json" in args else ""
            if "mergedAt" in wanted and "headRefOid" in wanted:
                return {**self.pr_view, **self.pr_state}
            if "mergedAt" in wanted:
                return {"number": self.pr_view["number"], **self.pr_state}
            return dict(self.pr_view)
        if head == ["pr", "list"]:
            return list(self.open_prs)
        raise AssertionError(f"unexpected gh json call: {args}")


class FakeGit:
    """Injectable stand-in for :class:`agent_teams.git.Git`.

    Records claim and worktree calls so a test can assert that a refusal
    happened *before* any git work, and can arm a lost race or a worktree
    failure on demand.
    """

    def __init__(self, *, race_lost=False, worktree_error=None, publish_error=None,
                 specification=None, remote_sha=None):
        self.race_lost = race_lost
        self.worktree_error = worktree_error
        self.publish_error = publish_error
        self.remote_sha = remote_sha or "c" * 40
        self.specification_artifact = specification or {
            "ok": True, "path": "docs/specs/card-20.md",
            "commit": "e" * 40, "head_sha": "e" * 40,
            "branch": "main", "state": "TRACKED", "committed": True,
            "pushed": True,
        }
        self.calls: list[tuple] = []

    def claim(self, number, title, seat, session_id=None):
        self.calls.append(("claim", number, seat))
        if self.race_lost:
            from agent_teams.git import ClaimRaceLost
            raise ClaimRaceLost(number, f"claim/{number}-x")
        return {
            "ok": True, "branch": f"claim/{number}-x",
            "ref": f"refs/heads/claim/{number}-x",
            "base_sha": "b" * 40, "claim_sha": "c" * 40, "session": "s1",
        }

    def remote_branch_sha(self, branch):
        self.calls.append(("remote_branch_sha", branch))
        return self.remote_sha

    def add_worktree(self, path, branch, sha):
        self.calls.append(("worktree", str(path)))
        if self.worktree_error:
            raise self.worktree_error
        return {
            "ok": True, "resumed": False, "worktree": str(path), "branch": branch,
        }

    def publish_delivery(self, path, branch):
        self.calls.append(("publish", str(path), branch))
        if self.publish_error:
            raise self.publish_error
        return {"ok": True, "pushed": True, "head_sha": "d" * 40}

    def specification(self, reference):
        self.calls.append(("specification", reference))
        result = dict(self.specification_artifact)
        result["path"] = reference
        return result

    def publish_specification(self, number, title, reference):
        self.calls.append(("publish_specification", number, reference))
        result = dict(self.specification_artifact)
        result["path"] = reference
        return result

    def publish_specification_for_review(self, number, title, reference):
        self.calls.append(("publish_specification_for_review", number, reference))
        return {
            "ok": True,
            "path": reference,
            "commit": "f" * 40,
            "branch": f"spec/{number}-shaped-requirement",
            "base_branch": "main",
            "base_sha": "e" * 40,
            "pushed": True,
            "state": "PULL_REQUEST_PENDING",
        }

    def sync_merged_specification(self, reference, base_branch):
        self.calls.append(("sync_merged_specification", reference, base_branch))
        result = dict(self.specification_artifact)
        result.update({"path": reference, "branch": base_branch, "synced": True})
        return result

    def remove_worktree(self, path, force=False):
        self.calls.append(("remove", str(path)))
        return {"ok": True, "removed": str(path)}

    def worktrees(self):
        return []


class SaturatingGh(FakeGh):
    """A Project of ``total`` items served through real cursor pages.

    Records every page size asked for, so tests can assert the read followed
    cursors at the configured page size rather than re-reading from the top.
    """

    def __init__(self, total: int, **kwargs):
        super().__init__(**kwargs)
        self.total = total
        self.limits_requested: list[int] = []
        self.items = {"items": [
            _item(f"ITEM_{n}", n, f"Card {n}", "Ready", "dev")
            for n in range(1, total + 1)
        ]}

    def json(self, args):
        args = list(args)
        if args[:2] == ["api", "graphql"]:
            fields = dict(
                args[i + 1].split("=", 1) for i, a in enumerate(args) if a in ("-f", "-F")
            )
            self.limits_requested.append(int(fields["first"]))
        return super().json(args)
