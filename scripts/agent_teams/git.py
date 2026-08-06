"""Local Git and remote ref arbitration.

The remote claim branch is the mutual-exclusion primitive (ARCHITECTURE.md
5.3). A local worktree is not a claim: another machine cannot observe it.

One rule here is load-bearing and was established by test, not by reading
documentation. A claim pushes a *unique* empty commit, never the bare base
SHA. Two Consumers claiming one Card normally branch from the same base, and
pushing an identical SHA to an existing ref is `Everything up-to-date`, exit
0 -- git never evaluates the lease, and both sessions believe they won. The
session nonce in the commit message is what keeps two claims made on one
machine within one clock second from collapsing into that same case.

Raw git output never escapes this module, mirroring the rule that raw GitHub
response shapes never escape ``github.py``.
"""

from __future__ import annotations

import re
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .errors import AgentTeamsError

CLAIM_MARKER = "<!-- agent-teams:claim -->"


class GitError(AgentTeamsError):
    """A git invocation failed for a reason that is not a lost race."""


class ClaimRaceLost(AgentTeamsError):
    """Another session already holds this Card's claim.

    A normal structured outcome, not a defect (ARCHITECTURE.md 11.3). Nothing
    was written, so there is nothing to recover and nothing to retry.
    """

    def __init__(self, number: int, branch: str):
        super().__init__(
            f"claim race lost for #{number}: `{branch}` already exists on the "
            f"remote. Another session owns this Card. Do not retry -- pick up "
            f"different work, or ask the human to run release-claim if the "
            f"holder is abandoned."
        )
        self.number = number
        self.branch = branch


class WorktreeNotClean(AgentTeamsError):
    """The worktree holds work that removing it would destroy."""


def slugify(title: str, limit: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(title or "").casefold()).strip("-")
    if len(slug) > limit:
        slug = slug[:limit].rstrip("-")
    return slug or "card"


def claim_branch(number: int, title: str) -> str:
    return f"claim/{number}-{slugify(title)}"


def worktree_path(workspace: Path, number: int, title: str) -> Path:
    return Path(workspace) / f"claim-{number}-{slugify(title)}"


#: Push rejections that mean "someone else got there first" rather than
#: "the remote is broken". Distinguishing them matters: reporting a broken
#: remote as a lost race would send a Consumer away from work nobody holds.
_RACE_SIGNALS = ("stale info", "rejected", "cannot lock ref", "already exists")


class Git:
    """Runs git in one repository root. Raw git output never escapes here."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def _run(
        self, args: Iterable[str], check: bool = True
    ) -> subprocess.CompletedProcess:
        args = [str(arg) for arg in args]
        result = subprocess.run(
            ["git", *args], cwd=str(self.root), capture_output=True, text=True
        )
        if check and result.returncode != 0:
            raise GitError(
                f"git {' '.join(args)} failed ({result.returncode}): "
                f"{result.stderr.strip()}"
            )
        return result

    def head_sha(self) -> str:
        return self._run(["rev-parse", "HEAD"]).stdout.strip()

    def _claim_message(
        self, number: int, title: str, seat: str, session_id: str, base: str
    ) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return (
            f"claim: #{number} {title}\n\n"
            f"{CLAIM_MARKER}\n"
            f"card: {number}\n"
            f"seat: {seat}\n"
            f"base: {base}\n"
            f"session: {session_id}\n"
            f"claimed-at: {stamp}\n"
        )

    def claim(
        self, number: int, title: str, seat: str, session_id: str | None = None
    ) -> dict[str, Any]:
        """Reserve one Card by compare-and-swap on its remote claim branch.

        Two details are load-bearing.

        The claim commit is built with ``commit-tree`` plumbing, so the
        caller's working tree and current branch are never touched -- a
        resumed session must not find a mystery commit on its own branch.

        The commit is unique per claimant. Pushing the bare base SHA would be
        a no-op success for a second claimant standing on the same base, and
        ``--force-with-lease`` would never be evaluated. The empty expected
        value (the trailing colon) means "this ref must not already exist";
        combined with a unique commit it is a true compare-and-swap.
        """
        session_id = session_id or str(uuid.uuid4())
        branch = claim_branch(number, title)
        ref = f"refs/heads/{branch}"
        base = self.head_sha()
        tree = self._run(["rev-parse", f"{base}^{{tree}}"]).stdout.strip()

        message = self._claim_message(number, title, seat, session_id, base)
        claim_sha = self._run(
            ["commit-tree", tree, "-p", base, "-m", message]
        ).stdout.strip()

        pushed = self._run(
            ["push", "origin", f"{claim_sha}:{ref}", f"--force-with-lease={ref}:"],
            check=False,
        )
        if pushed.returncode != 0:
            stderr = pushed.stderr.casefold()
            if any(signal in stderr for signal in _RACE_SIGNALS):
                raise ClaimRaceLost(number, branch)
            raise GitError(f"claim push failed: {pushed.stderr.strip()}")

        return {
            "ok": True,
            "branch": branch,
            "ref": ref,
            "base_sha": base,
            "claim_sha": claim_sha,
            "session": session_id,
        }

    # -------------------------------------------------------------- worktrees

    def worktrees(self) -> list[dict[str, str]]:
        """Every worktree this repository knows about, as porcelain records."""
        out = self._run(["worktree", "list", "--porcelain"]).stdout
        entries: list[dict[str, str]] = []
        current: dict[str, str] = {}
        for line in out.splitlines():
            if not line.strip():
                if current:
                    entries.append(current)
                    current = {}
                continue
            key, _, value = line.partition(" ")
            current[key] = value
        if current:
            entries.append(current)
        return entries

    def _known_worktrees(self) -> set[Path]:
        return {
            Path(entry["worktree"]).resolve()
            for entry in self.worktrees()
            if entry.get("worktree")
        }

    def add_worktree(self, path: Path, branch: str, sha: str) -> dict[str, Any]:
        """Create the isolated checkout, or resume the existing one.

        Resume rather than fail: an interrupted Consumer picks up the same
        logical assignment (ARCHITECTURE.md 11.5), and recreating would
        discard whatever it had already written.
        """
        path = Path(path)
        if path.resolve() in self._known_worktrees():
            return {
                "ok": True, "resumed": True,
                "worktree": str(path), "branch": branch,
            }
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = self._run(
            ["rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"], check=False
        )
        args = ["worktree", "add", str(path)]
        args += [branch] if existing.returncode == 0 else ["-b", branch, sha]
        self._run(args)
        return {
            "ok": True, "resumed": False,
            "worktree": str(path), "branch": branch,
        }

    def remove_worktree(self, path: Path, force: bool = False) -> dict[str, Any]:
        """Remove a worktree only when doing so destroys nothing.

        Two guards, and ``force`` waives only the second. A path this
        repository does not know as a worktree is refused outright even with
        ``force``, so a wrong argument can never recursively delete an
        unrelated directory (ARCHITECTURE.md 9.7 rule 6).
        """
        path = Path(path)
        if path.resolve() not in self._known_worktrees():
            raise GitError(
                f"{path} is not a worktree of this repository; refusing to "
                f"remove it. Nothing was deleted."
            )
        if not force:
            status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(path), capture_output=True, text=True,
            )
            if status.returncode != 0:
                raise GitError(f"cannot read worktree status: {status.stderr.strip()}")
            if status.stdout.strip():
                raise WorktreeNotClean(
                    f"{path} has uncommitted or untracked changes:\n"
                    f"{status.stdout.strip()}\n"
                    f"Commit, push, or discard them deliberately before removal."
                )
        self._run(["worktree", "remove", str(path), *(["--force"] if force else [])])
        return {"ok": True, "removed": str(path)}
