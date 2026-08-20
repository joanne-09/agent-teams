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

import os
import re
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

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
            f"remote. Another session owns this Card. Do not retry or delete "
            f"the branch; the coordinator will resume the Card's durable claim "
            f"after it reaches In Progress."
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

def specification_branch(number: int, title: str) -> str:
    return f"spec/{number}-{slugify(title)}"



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
        self, args: Iterable[str], check: bool = True,
        env: Mapping[str, str] | None = None,
    ) -> subprocess.CompletedProcess:
        args = [str(arg) for arg in args]
        result = subprocess.run(
            ["git", *args], cwd=str(self.root), capture_output=True, text=True,
            env=dict(env) if env is not None else None,
        )
        if check and result.returncode != 0:
            raise GitError(
                f"git {' '.join(args)} failed ({result.returncode}): "
                f"{result.stderr.strip()}"
            )
        return result

    def head_sha(self) -> str:
        return self._run(["rev-parse", "HEAD"]).stdout.strip()

    def _specification_path(self, reference: str) -> tuple[Path, str]:
        """Resolve one repository-relative Markdown specification safely."""
        raw = str(reference or "").strip().replace(chr(92), "/")
        if not raw or raw.startswith("/") or re.match(r"^[A-Za-z]:", raw):
            raise GitError("specification path must be repository-relative")
        target = (self.root / raw).resolve()
        root = self.root.resolve()
        try:
            relative = target.relative_to(root).as_posix()
        except ValueError as exc:
            raise GitError("specification path escapes the repository") from exc
        if not relative.startswith("docs/") or not relative.endswith(".md"):
            raise GitError("specification path must be a Markdown file below docs/")
        return target, relative

    def specification(self, reference: str) -> dict[str, Any]:
        """Verify that a direct specification is tracked in current HEAD."""
        _target, relative = self._specification_path(reference)
        tracked = self._run(
            ["ls-files", "--error-unmatch", "--", relative], check=False
        )
        if tracked.returncode != 0:
            raise GitError(
                f"specification `{relative}` is not tracked in the current branch"
            )
        commit = self._run(["log", "-1", "--format=%H", "--", relative]).stdout.strip()
        if not commit:
            raise GitError(f"specification `{relative}` has no committed Git version")
        return {
            "ok": True,
            "path": relative,
            "commit": commit,
            "head_sha": self.head_sha(),
            "state": "TRACKED",
        }

    def publish_specification(
        self, number: int, title: str, reference: str
    ) -> dict[str, Any]:
        """Commit and push one spec on the checkout's current branch.

        No branch or Pull Request is created. The checkout may be dirty only
        at the requested specification path, and only that path is staged.
        """
        target, relative = self._specification_path(reference)
        if not target.is_file() or not target.read_text(encoding="utf-8").strip():
            raise GitError(f"specification `{relative}` is missing or empty")

        branch = self._run(
            ["symbolic-ref", "--quiet", "--short", "HEAD"], check=False
        ).stdout.strip()
        if not branch:
            raise GitError(
                "cannot publish a specification from a detached HEAD; check out "
                "the branch that should receive it"
            )

        dirty_lines = [
            line for line in self._run(
                ["status", "--porcelain", "--untracked-files=all"]
            ).stdout.splitlines()
            if line.strip()
        ]
        unrelated = []
        for line in dirty_lines:
            if " -> " in line:
                unrelated.append(line)
                continue
            changed = line[3:].strip().replace(chr(92), "/")
            if changed != relative:
                unrelated.append(line)
        if unrelated:
            raise GitError(
                "cannot publish a specification while unrelated checkout changes "
                "exist; preserve or finish them first:\n" + "\n".join(unrelated)
            )

        self._run(["add", "--", relative])
        changed = self._run(["diff", "--cached", "--quiet"], check=False)
        committed = changed.returncode != 0
        if committed:
            self._run(
                ["commit", "-m", f"spec: document #{number} {str(title).strip()}",
                 "--", relative]
            )

        commit = self.specification(relative)["commit"]
        pushed = self._run(
            ["push", "origin", f"HEAD:refs/heads/{branch}"], check=False
        )
        if pushed.returncode != 0:
            raise GitError(
                f"specification is committed locally as {commit}, but pushing "
                f"current branch `{branch}` failed: {pushed.stderr.strip()}"
            )
        return {
            "ok": True,
            "path": relative,
            "commit": commit,
            "branch": branch,
            "committed": committed,
            "pushed": True,
            "state": "TRACKED",
        }

    def publish_specification_for_review(
        self, number: int, title: str, reference: str
    ) -> dict[str, Any]:
        """Publish only one specification on a deterministic review branch.

        A temporary index builds the commit without moving the current branch
        or mixing in the caller's real index. After the remote branch owns the
        exact content, the local path is restored to current HEAD so the shared
        checkout stays clean while the user reviews the Pull Request.
        """
        target, relative = self._specification_path(reference)
        if not target.is_file() or not target.read_text(encoding="utf-8").strip():
            raise GitError(f"specification `{relative}` is missing or empty")

        base_branch = self._run(
            ["symbolic-ref", "--quiet", "--short", "HEAD"], check=False
        ).stdout.strip()
        if not base_branch:
            raise GitError(
                "cannot publish a specification from a detached HEAD; check out "
                "the branch the specification Pull Request should target"
            )

        dirty_lines = [
            line for line in self._run(
                ["status", "--porcelain", "--untracked-files=all"]
            ).stdout.splitlines()
            if line.strip()
        ]
        unrelated = []
        for line in dirty_lines:
            if " -> " in line:
                unrelated.append(line)
                continue
            changed = line[3:].strip().replace(chr(92), "/")
            if changed != relative:
                unrelated.append(line)
        if unrelated:
            raise GitError(
                "cannot publish a specification while unrelated checkout changes "
                "exist; preserve or finish them first:\n" + "\n".join(unrelated)
            )

        base_sha = self.head_sha()
        base_tree = self._run(["rev-parse", f"{base_sha}^{{tree}}"]).stdout.strip()
        with tempfile.TemporaryDirectory(prefix="agent-teams-spec-index-") as temp:
            environment = os.environ.copy()
            environment["GIT_INDEX_FILE"] = str(Path(temp) / "index")
            self._run(["read-tree", base_sha], env=environment)
            self._run(["add", "--", relative], env=environment)
            tree = self._run(["write-tree"], env=environment).stdout.strip()
            if tree == base_tree:
                raise GitError(
                    f"specification `{relative}` does not differ from "
                    f"`{base_branch}`; there is no review change to publish"
                )
            commit = self._run(
                [
                    "commit-tree", tree, "-p", base_sha, "-m",
                    f"spec: document #{number} {str(title).strip()}",
                ],
                env=environment,
            ).stdout.strip()

        branch = specification_branch(number, title)
        ref = f"refs/heads/{branch}"
        remote = self._run(["ls-remote", "--heads", "origin", ref], check=False)
        if remote.returncode != 0:
            raise GitError(
                f"cannot inspect specification branch `{branch}`: "
                f"{remote.stderr.strip()}"
            )
        remote_line = next(
            (line for line in remote.stdout.splitlines() if line.strip()), ""
        )
        remote_sha = remote_line.split()[0] if remote_line else ""
        pushed = self._run(
            [
                "push", "origin", f"{commit}:{ref}",
                f"--force-with-lease={ref}:{remote_sha}",
            ],
            check=False,
        )
        if pushed.returncode != 0:
            raise GitError(
                f"specification review branch `{branch}` was not updated: "
                f"{pushed.stderr.strip()}"
            )

        tracked = self._run(
            ["ls-files", "--error-unmatch", "--", relative], check=False
        ).returncode == 0
        if tracked:
            self._run(
                ["restore", "--staged", "--worktree", "--source=HEAD", "--", relative]
            )
        else:
            self._run(["reset", "--", relative], check=False)
            target.unlink()

        return {
            "ok": True, "path": relative, "commit": commit, "branch": branch,
            "base_branch": base_branch, "base_sha": base_sha, "pushed": True,
            "state": "PULL_REQUEST_PENDING",
        }

    def sync_merged_specification(
        self, reference: str, base_branch: str
    ) -> dict[str, Any]:
        """Fast-forward the clean shared checkout after a spec PR is merged."""
        _target, relative = self._specification_path(reference)
        current = self._run(
            ["symbolic-ref", "--quiet", "--short", "HEAD"], check=False
        ).stdout.strip()
        if current != base_branch:
            raise GitError(
                f"cannot sync merged specification on `{current or 'detached HEAD'}`; "
                f"check out recorded base branch `{base_branch}`"
            )
        dirty = self._run(
            ["status", "--porcelain", "--untracked-files=all"]
        ).stdout.strip()
        if dirty:
            raise GitError(
                "cannot sync a merged specification while checkout changes exist:\n"
                + dirty
            )
        remote_ref = f"refs/remotes/origin/{base_branch}"
        fetched = self._run(
            ["fetch", "origin", f"refs/heads/{base_branch}:{remote_ref}"],
            check=False,
        )
        if fetched.returncode != 0:
            raise GitError(
                f"cannot fetch merged specification base `{base_branch}`: "
                f"{fetched.stderr.strip()}"
            )
        ancestor = self._run(
            ["merge-base", "--is-ancestor", "HEAD", remote_ref], check=False
        )
        if ancestor.returncode != 0:
            raise GitError(
                f"local `{base_branch}` diverged from `origin/{base_branch}`; "
                "resolve it before finalizing the specification merge"
            )
        self._run(["merge", "--ff-only", remote_ref])
        artifact = self.specification(relative)
        return {**artifact, "branch": base_branch, "synced": True}

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

    def remote_branch_sha(self, branch: str) -> str:
        """Resolve a durable remote claim without changing local state."""
        ref = f"refs/heads/{branch}"
        result = self._run(["ls-remote", "--heads", "origin", ref], check=False)
        if result.returncode != 0:
            raise GitError(
                f"cannot inspect remote claim {branch}: {result.stderr.strip()}"
            )
        line = next((line for line in result.stdout.splitlines() if line.strip()), "")
        sha = line.split()[0] if line else ""
        if not re.fullmatch(r"[0-9a-fA-F]{40,64}", sha):
            raise GitError(
                f"remote claim {branch} does not exist; re-read the Card before "
                "trying to resume it"
            )
        return sha

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

    def worktree_for_branch(self, branch: str) -> Path | None:
        """Find an existing claim checkout even if workspace config changed."""
        wanted = f"refs/heads/{branch}"
        matches = [
            Path(entry["worktree"]).resolve()
            for entry in self.worktrees()
            if entry.get("branch") == wanted and entry.get("worktree")
        ]
        if len(matches) > 1:
            raise GitError(
                f"branch `{branch}` is checked out in multiple worktrees: "
                + ", ".join(str(path) for path in matches)
            )
        return matches[0] if matches else None

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
        existing_path = self.worktree_for_branch(branch)
        if existing_path is not None:
            return {
                "ok": True, "resumed": True,
                "worktree": str(existing_path), "branch": branch,
            }
        if path.resolve() in self._known_worktrees():
            raise GitError(
                f"{path} is already a worktree for another branch; refusing "
                f"to replace it while materializing `{branch}`"
            )
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

    def publish_delivery(self, path: Path, branch: str) -> dict[str, Any]:
        """Push the worktree's commits so the Pull Request holds the real work.

        The Pull Request is built from the remote claim branch, never from
        this machine's worktree -- a delivery that was committed but not
        pushed reads as an empty diff to every reviewer, while the submitting
        session honestly believes it shipped (observed live on card #14).

        A dirty worktree is refused outright rather than auto-committed:
        deciding what belongs in the delivery is the Consumer's job, and
        pushing around uncommitted work would silently leave it out.

        A path this repository does not know as a worktree is not an error:
        the branch may have been pushed from another machine, and the empty-
        diff guard in ``submit`` still stands between that and a hollow
        delivery.
        """
        path = Path(path)
        if path.resolve() not in self._known_worktrees():
            return {
                "ok": True, "pushed": False,
                "note": f"no worktree at {path} on this machine; relying on "
                        f"the remote branch as already pushed",
            }
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(path), capture_output=True, text=True,
        )
        if status.returncode != 0:
            raise GitError(f"cannot read worktree status: {status.stderr.strip()}")
        if status.stdout.strip():
            raise GitError(
                f"{path} has uncommitted or untracked changes:\n"
                f"{status.stdout.strip()}\n"
                f"Commit what belongs in the delivery (or discard the rest "
                f"deliberately), then submit again."
            )
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(path), capture_output=True, text=True,
        )
        if head.returncode != 0:
            raise GitError(f"cannot read worktree HEAD: {head.stderr.strip()}")
        pushed = subprocess.run(
            ["git", "push", "origin", f"HEAD:refs/heads/{branch}"],
            cwd=str(path), capture_output=True, text=True,
        )
        if pushed.returncode != 0:
            raise GitError(f"delivery push failed: {pushed.stderr.strip()}")
        return {"ok": True, "pushed": True, "head_sha": head.stdout.strip()}

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
