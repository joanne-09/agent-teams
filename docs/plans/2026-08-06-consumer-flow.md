# Consumer Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the agent-teams Consumer half — one lifecycle, three routines (Developer implement, Architect document, QA verify) carrying a Card from `Ready` through claim, worktree, Pull Request, evidence-grounded verdict, deterministic acceptance, auto-merge, and reconciliation to `Done`.

**Architecture:** A new `git.py` adapter owns the remote-branch compare-and-swap claim and worktree isolation. `policy.py` gains pure protected-path classification, verdict validation, and the acceptance decision table — no network, so every edge is asserted individually. A `Consumer` class in `workflows.py` composes them into five transactions that report honest partial failure. Six new CLI commands on the existing stable entry point. Two new skills derived from board-superpowers, superpowers, and gstack.

**Tech Stack:** Python 3.9+ standard library only, `unittest`, GitHub CLI (`gh`), Git, Claude Code plugin `SKILL.md` format.

**Design source:** [`../specs/2026-08-06-consumer-flow-design.md`](../specs/2026-08-06-consumer-flow-design.md). Normative parent: [`../ARCHITECTURE.md`](../ARCHITECTURE.md).

## Global Constraints

- **Python standard library only.** No dependency install, no virtualenv, no SQLite.
- **Tests are `unittest`**, discovered by `python -m unittest discover -s tests -p "test_*.py"`. Not pytest.
- **No test may touch the network or a real Project.** Git tests use a local bare repository as origin.
- **`policy.py` touches no network.** It imports nothing that reaches GitHub or the filesystem.
- **Every mutation returns `"ok": true`** on success; expected failures print `{"ok": false, "error": ...}` on stderr and exit 1.
- **Multi-step mutations never claim a rollback that did not run.** They return `{ok:false, partial:true, completed:[...], failed:..., recovery:[...]}`.
- **Semantic operations only.** Never add `set_card_field` or any generic setter.
- **No skill may reference `superpowers:` or `gstack:`.** A grep for those prefixes across `skills/` must return nothing — that absence is the proof these are derivations, not runtime dependencies.
- **Skills contain no raw Project field identifiers** and no ad hoc `gh` commands. Every mutation goes through `scripts/producer_board.py`.
- **Write files as UTF-8 and keep new file content ASCII-only.** `ATTRIBUTION.md` already carries mojibake from a prior encoding slip; do not add more.
- **Platform is Windows + PowerShell.** Use `pathlib`, never hardcode `/` separators in Python.
- **Commit style is conventional commits** (`feat:`, `fix:`, `test:`, `docs:`).

---

## File Structure

| File | Responsibility |
|---|---|
| `scripts/agent_teams/git.py` | **New.** Claim branch/worktree naming, compare-and-swap claim push, worktree create/resume/remove with guards. Knows nothing about GitHub. |
| `scripts/agent_teams/config.py` | Modify. Five new keys; `protected_paths` may only grow. |
| `scripts/agent_teams/model.py` | Modify. `Verdict` expanded to the §9.6 contract; new `Acceptance`. |
| `scripts/agent_teams/policy.py` | Modify. Glob translator, `classify_protected`, `validate_verdict`, `evaluate_acceptance`, `ACCEPTANCE_POLICY_VERSION`. |
| `scripts/agent_teams/board.py` | Modify. Pull Request reads, verdict/acceptance comments, arm auto-merge. |
| `scripts/agent_teams/workflows.py` | Modify. New `Consumer` class: `claim`, `submit`, `verdict`, `accept`, `reconcile`. |
| `scripts/producer_board.py` | Modify. Six new subcommands. |
| `skills/consuming-card/` | **New.** Developer + Architect-documentation routines. |
| `skills/verifying-delivery/` | **New.** QA verification routine. |
| `tests/test_git.py` | **New.** Real-git claim race and worktree guard tests. |
| `tests/test_acceptance.py` | **New.** Protected classification, verdict validation, acceptance decision table. |
| `tests/test_consumer.py` | **New.** `Consumer` transactions against `FakeGh`. |
| `tests/fake_gh.py` | Modify. Pull Request fixtures. |

---

## Task 1: Claim branch naming and the compare-and-swap primitive

The two-winners hazard is the single most important behaviour in this plan. Build it first and prove it first.

**Files:**
- Create: `scripts/agent_teams/git.py`
- Test: `tests/test_git.py`

**Interfaces:**
- Consumes: nothing (leaf adapter).
- Produces: `slugify(title, limit=40) -> str`; `claim_branch(number, title) -> str`; `class GitError(AgentTeamsError)`; `class ClaimRaceLost(AgentTeamsError)`; `class Git` with `__init__(root: Path)`, `head_sha() -> str`, `claim(number, title, seat, session_id) -> dict`.

- [ ] **Step 1: Write the failing test for naming**

Create `tests/test_git.py`:

```python
"""Tests for the Git adapter, including the claim compare-and-swap.

The race tests use a real local bare repository as origin. Nothing here
touches the network, but the exclusivity claim must be proven against real
git ref semantics -- a fake would have agreed with the wrong implementation.
"""

import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from agent_teams.git import (  # noqa: E402
    ClaimRaceLost, Git, GitError, claim_branch, slugify,
)


def _force_remove(func, path, _exc):
    """Windows leaves git object files read-only; chmod then retry."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def _git(cwd, *args):
    result = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True
    )
    if result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {result.stderr}")
    return result.stdout.strip()


class NamingTests(unittest.TestCase):
    def test_slug_is_lowercase_hyphenated_and_bounded(self):
        self.assertEqual(slugify("Implement CSV Export!"), "implement-csv-export")

    def test_slug_collapses_runs_and_trims_edges(self):
        self.assertEqual(slugify("  --Fix   the__parser--  "), "fix-the-parser")

    def test_slug_is_truncated_without_a_trailing_hyphen(self):
        slug = slugify("a" * 30 + " " + "b" * 30)
        self.assertLessEqual(len(slug), 40)
        self.assertFalse(slug.endswith("-"))

    def test_claim_branch_is_derived_from_card_identity(self):
        self.assertEqual(claim_branch(42, "Implement parser"), "claim/42-implement-parser")
```

- [ ] **Step 2: Run it and watch it fail**

Run: `python -m unittest tests.test_git -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent_teams.git'`

- [ ] **Step 3: Write the naming half of `git.py`**

```python
"""Local Git and remote ref arbitration.

The remote claim branch is the mutual-exclusion primitive (ARCHITECTURE.md
5.3). A local worktree is not a claim: another machine cannot observe it.

One rule here is load-bearing and was established by test, not by reading
documentation. A claim pushes a *unique* empty commit, never the bare base
SHA. Two Consumers claiming one Card normally branch from the same base, and
pushing an identical SHA to an existing ref is `Everything up-to-date`, exit
0 -- git never evaluates the lease, and both sessions believe they won. The
session nonce in the commit message is what keeps two claims on one machine
in one clock second from colliding into that same case.
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


def slugify(title: str, limit: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(title or "").casefold()).strip("-")
    if len(slug) > limit:
        slug = slug[:limit].rstrip("-")
    return slug or "card"


def claim_branch(number: int, title: str) -> str:
    return f"claim/{number}-{slugify(title)}"
```

- [ ] **Step 4: Run the naming tests**

Run: `python -m unittest tests.test_git -v`
Expected: PASS, 4 tests.

- [ ] **Step 5: Write the failing race tests**

Append to `tests/test_git.py`:

```python
class ClaimRaceTests(unittest.TestCase):
    """Exclusivity proven against real git, with a local bare repo as origin."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, onerror=_force_remove)
        self.origin = self.tmp / "origin.git"
        _git(self.tmp, "init", "-q", "--bare", "-b", "main", str(self.origin))

        seed = self.tmp / "seed"
        _git(self.tmp, "clone", "-q", str(self.origin), str(seed))
        _git(seed, "config", "user.email", "t@example.invalid")
        _git(seed, "config", "user.name", "Test")
        (seed / "f.txt").write_text("base\n", encoding="utf-8")
        _git(seed, "add", ".")
        _git(seed, "commit", "-qm", "base")
        _git(seed, "push", "-q", "origin", "main")

    def _clone(self, name):
        path = self.tmp / name
        _git(self.tmp, "clone", "-q", str(self.origin), str(path))
        _git(path, "config", "user.email", "t@example.invalid")
        _git(path, "config", "user.name", "Test")
        return Git(path)

    def test_first_claimant_wins(self):
        result = self._clone("a").claim(42, "Implement parser", "dev", "session-a")
        self.assertTrue(result["ok"])
        self.assertEqual(result["branch"], "claim/42-implement-parser")

    def test_second_claimant_from_the_same_base_loses(self):
        # The regression that motivates the unique claim commit. Both clones
        # sit on the identical base SHA; a bare-SHA push would report
        # "Everything up-to-date" and exit 0 for BOTH.
        self._clone("a").claim(42, "Implement parser", "dev", "session-a")
        with self.assertRaises(ClaimRaceLost):
            self._clone("b").claim(42, "Implement parser", "dev", "session-b")

    def test_race_loss_leaves_the_remote_ref_owned_by_the_winner(self):
        self._clone("a").claim(42, "Implement parser", "dev", "session-a")
        with self.assertRaises(ClaimRaceLost):
            self._clone("b").claim(42, "Implement parser", "dev", "session-b")
        body = _git(
            self.tmp, "--git-dir", str(self.origin), "log", "-1",
            "--format=%B", "refs/heads/claim/42-implement-parser",
        )
        self.assertIn("session-a", body)
        self.assertNotIn("session-b", body)

    def test_two_claims_in_the_same_second_produce_distinct_commits(self):
        # Without the nonce these would be identical commit objects and the
        # second push would collapse into the "Everything up-to-date" case.
        a = self._clone("a").claim(42, "Implement parser", "dev", "session-a")
        with self.assertRaises(ClaimRaceLost):
            self._clone("b").claim(42, "Implement parser", "dev", "session-b")
        self.assertNotEqual(a["claim_sha"], a["base_sha"])

    def test_claim_records_the_marker_and_seat(self):
        self._clone("a").claim(42, "Implement parser", "dev", "session-a")
        body = _git(
            self.tmp, "--git-dir", str(self.origin), "log", "-1",
            "--format=%B", "refs/heads/claim/42-implement-parser",
        )
        self.assertIn(CLAIM_MARKER, body)
        self.assertIn("seat: dev", body)
```

Add `CLAIM_MARKER` to the import line at the top of the test file.

- [ ] **Step 6: Run and watch them fail**

Run: `python -m unittest tests.test_git -v`
Expected: FAIL with `AttributeError` / `TypeError` — `Git` has no `claim`.

- [ ] **Step 7: Implement `Git.claim`**

Append to `scripts/agent_teams/git.py`:

```python
class Git:
    """Runs git in one repository root. Raw git output never escapes here."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def _run(self, args: Iterable[str], check: bool = True) -> subprocess.CompletedProcess:
        result = subprocess.run(
            ["git", *args],
            cwd=str(self.root),
            capture_output=True,
            text=True,
        )
        if check and result.returncode != 0:
            raise GitError(
                f"git {' '.join(args)} failed ({result.returncode}): "
                f"{result.stderr.strip()}"
            )
        return result

    def head_sha(self) -> str:
        return self._run(["rev-parse", "HEAD"]).stdout.strip()

    def _claim_message(self, number, title, seat, session_id, base) -> str:
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

    def claim(self, number: int, title: str, seat: str, session_id: str | None = None) -> dict[str, Any]:
        """Reserve one Card by compare-and-swap on its remote claim branch.

        Uses ``commit-tree`` plumbing so the caller's working tree and current
        branch are never touched: the claim commit is built directly from the
        base commit's tree.
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
            [
                "push", "origin", f"{claim_sha}:{ref}",
                f"--force-with-lease={ref}:",
            ],
            check=False,
        )
        if pushed.returncode != 0:
            stderr = pushed.stderr.casefold()
            if "stale info" in stderr or "rejected" in stderr or "cannot lock" in stderr:
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
```

- [ ] **Step 8: Run the full file**

Run: `python -m unittest tests.test_git -v`
Expected: PASS, 9 tests.

- [ ] **Step 9: Commit**

```bash
git add scripts/agent_teams/git.py tests/test_git.py
git commit -m "feat: add Git claim compare-and-swap with unique claim commit

A bare-SHA push to an existing ref is 'Everything up-to-date', exit 0, and
never evaluates the lease -- so two Consumers branching from the same base
would both win. The claim commit carries a session nonce so no two claims
can produce the same commit object."
```

---

## Task 2: Worktree create, resume, and guarded removal

**Files:**
- Modify: `scripts/agent_teams/git.py`
- Test: `tests/test_git.py`

**Interfaces:**
- Consumes: `Git`, `claim_branch`, `GitError` from Task 1.
- Produces: `worktree_path(workspace, number, title) -> Path`; `Git.add_worktree(path, branch, sha) -> dict`; `Git.worktrees() -> list[dict]`; `Git.remove_worktree(path, force=False) -> dict`; `class WorktreeNotClean(AgentTeamsError)`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_git.py`:

```python
class WorktreeTests(ClaimRaceTests):
    """Reuses the bare-origin fixture; adds worktree lifecycle assertions."""

    def test_worktree_path_is_derived_from_card_identity(self):
        path = worktree_path(Path("/w"), 42, "Implement parser")
        self.assertEqual(path.name, "claim-42-implement-parser")

    def test_add_worktree_checks_out_the_claim_commit(self):
        git = self._clone("a")
        claim = git.claim(42, "Implement parser", "dev", "session-a")
        target = self.tmp / "wt" / "claim-42"
        result = git.add_worktree(target, claim["branch"], claim["claim_sha"])
        self.assertTrue(result["ok"])
        self.assertTrue((target / "f.txt").is_file())

    def test_adding_an_existing_worktree_resumes_instead_of_failing(self):
        git = self._clone("a")
        claim = git.claim(42, "Implement parser", "dev", "session-a")
        target = self.tmp / "wt" / "claim-42"
        git.add_worktree(target, claim["branch"], claim["claim_sha"])
        again = git.add_worktree(target, claim["branch"], claim["claim_sha"])
        self.assertTrue(again["ok"])
        self.assertTrue(again["resumed"])

    def test_remove_refuses_a_worktree_with_uncommitted_changes(self):
        git = self._clone("a")
        claim = git.claim(42, "Implement parser", "dev", "session-a")
        target = self.tmp / "wt" / "claim-42"
        git.add_worktree(target, claim["branch"], claim["claim_sha"])
        (target / "f.txt").write_text("edited\n", encoding="utf-8")
        with self.assertRaises(WorktreeNotClean):
            git.remove_worktree(target)
        self.assertTrue(target.is_dir())

    def test_remove_refuses_a_worktree_with_untracked_files(self):
        git = self._clone("a")
        claim = git.claim(42, "Implement parser", "dev", "session-a")
        target = self.tmp / "wt" / "claim-42"
        git.add_worktree(target, claim["branch"], claim["claim_sha"])
        (target / "scratch.txt").write_text("notes\n", encoding="utf-8")
        with self.assertRaises(WorktreeNotClean):
            git.remove_worktree(target)

    def test_remove_succeeds_on_a_clean_worktree(self):
        git = self._clone("a")
        claim = git.claim(42, "Implement parser", "dev", "session-a")
        target = self.tmp / "wt" / "claim-42"
        git.add_worktree(target, claim["branch"], claim["claim_sha"])
        self.assertTrue(git.remove_worktree(target)["ok"])
        self.assertFalse(target.is_dir())

    def test_remove_refuses_a_path_that_is_not_a_worktree(self):
        git = self._clone("a")
        stray = self.tmp / "not-a-worktree"
        stray.mkdir()
        (stray / "important.txt").write_text("do not delete\n", encoding="utf-8")
        with self.assertRaises(GitError):
            git.remove_worktree(stray)
        self.assertTrue((stray / "important.txt").is_file())
```

Extend the import at the top of the test file to include `WorktreeNotClean` and `worktree_path`.

- [ ] **Step 2: Run and watch them fail**

Run: `python -m unittest tests.test_git -v`
Expected: FAIL — `ImportError: cannot import name 'worktree_path'`

- [ ] **Step 3: Implement worktrees**

Add to `scripts/agent_teams/git.py`:

```python
class WorktreeNotClean(AgentTeamsError):
    """The worktree holds work that removing it would destroy."""


def worktree_path(workspace: Path, number: int, title: str) -> Path:
    return Path(workspace) / f"claim-{number}-{slugify(title)}"
```

And these methods on `Git`:

```python
    def worktrees(self) -> list[dict[str, str]]:
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

    def add_worktree(self, path: Path, branch: str, sha: str) -> dict[str, Any]:
        """Create the isolated checkout, or resume the existing one.

        Resume rather than fail: an interrupted Consumer must be able to pick
        up the same assignment (ARCHITECTURE.md 11.5), and recreating would
        discard whatever it had already written.
        """
        path = Path(path)
        known = {Path(entry["worktree"]).resolve() for entry in self.worktrees() if "worktree" in entry}
        if path.resolve() in known:
            return {"ok": True, "resumed": True, "worktree": str(path), "branch": branch}
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = self._run(
            ["rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"], check=False
        )
        args = ["worktree", "add", str(path)]
        args += [branch] if existing.returncode == 0 else ["-b", branch, sha]
        self._run(args)
        return {"ok": True, "resumed": False, "worktree": str(path), "branch": branch}

    def remove_worktree(self, path: Path, force: bool = False) -> dict[str, Any]:
        """Remove a worktree only when doing so destroys nothing.

        ARCHITECTURE.md 9.7 rule 6: never delete an unresolved path. A path
        this repository does not know as a worktree is refused outright, so a
        wrong argument cannot recursively delete an unrelated directory.
        """
        path = Path(path)
        known = {Path(entry["worktree"]).resolve() for entry in self.worktrees() if "worktree" in entry}
        if path.resolve() not in known:
            raise GitError(
                f"{path} is not a worktree of this repository; refusing to remove it"
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
```

- [ ] **Step 4: Run**

Run: `python -m unittest tests.test_git -v`
Expected: PASS, 16 tests.

- [ ] **Step 5: Commit**

```bash
git add scripts/agent_teams/git.py tests/test_git.py
git commit -m "feat: add guarded worktree create, resume, and removal"
```

---

## Task 3: Configuration additions

**Files:**
- Modify: `scripts/agent_teams/config.py`
- Test: `tests/test_producer_board.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `Config.workspace: str`, `Config.protected_paths: Mapping[str, tuple[str, ...]]`, `Config.required_checks: tuple[str, ...]`, `Config.merge_method: str`, `Config.claim_ttl_hours: int`, and module constant `DEFAULT_PROTECTED_PATHS`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_producer_board.py`:

```python
class ConsumerConfigTests(unittest.TestCase):
    BASE = {"repo": "acme/widgets", "project_owner": "acme", "project_number": 1}

    def test_defaults_cover_every_protected_category(self):
        config = Config.from_dict(dict(self.BASE))
        self.assertEqual(config.workspace, "../.worktrees")
        self.assertEqual(config.merge_method, "squash")
        self.assertEqual(config.required_checks, ())
        self.assertIn("authority-and-policy", config.protected_paths)
        self.assertIn("agent-instructions", config.protected_paths)

    def test_repository_policy_may_add_patterns_to_a_category(self):
        config = Config.from_dict(
            {**self.BASE, "protected_paths": {"security-boundaries": ["infra/**"]}}
        )
        patterns = config.protected_paths["security-boundaries"]
        self.assertIn("infra/**", patterns)
        self.assertIn("**/auth/**", patterns)  # default survives

    def test_repository_policy_may_add_a_new_category(self):
        config = Config.from_dict(
            {**self.BASE, "protected_paths": {"billing": ["src/billing/**"]}}
        )
        self.assertIn("billing", config.protected_paths)

    def test_emptying_a_default_category_is_a_validation_error(self):
        # Section 4.5: policy may add categories, never silently remove one.
        with self.assertRaises(ConfigError) as caught:
            Config.from_dict({**self.BASE, "protected_paths": {"agent-instructions": []}})
        self.assertIn("agent-instructions", str(caught.exception))

    def test_unknown_merge_method_is_rejected(self):
        with self.assertRaises(ConfigError):
            Config.from_dict({**self.BASE, "merge_method": "cherry-pick"})

    def test_workspace_must_resolve_outside_the_repository(self):
        with self.assertRaises(ConfigError):
            Config.from_dict({**self.BASE, "workspace": ".worktrees"})
```

- [ ] **Step 2: Run and watch it fail**

Run: `python -m unittest tests.test_producer_board -v`
Expected: FAIL with `AttributeError: 'Config' object has no attribute 'workspace'`

- [ ] **Step 3: Implement**

In `config.py`, add the module constant above `Config`:

```python
#: The protected set of ARCHITECTURE.md 4.5, as repository-relative globs.
#: Repository policy may ADD patterns or categories. It may not remove one:
#: a configuration that empties a default category is a validation error, so
#: dropping protection is a visible edit rather than a silent omission.
DEFAULT_PROTECTED_PATHS: Mapping[str, tuple[str, ...]] = {
    "authority-and-policy": (
        "scripts/agent_teams/policy.py", "scripts/agent_teams/model.py",
    ),
    "acceptance-and-merge": (
        "scripts/agent_teams/git.py", "scripts/agent_teams/workflows.py",
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

MERGE_METHODS = ("squash", "merge", "rebase")
```

Add the fields to the `Config` dataclass:

```python
    workspace: str = "../.worktrees"
    protected_paths: Mapping[str, tuple[str, ...]] = field(
        default_factory=lambda: dict(DEFAULT_PROTECTED_PATHS)
    )
    required_checks: tuple[str, ...] = ()
    merge_method: str = "squash"
    claim_ttl_hours: int = 72
```

Add to `to_dict`:

```python
        payload["workspace"] = self.workspace
        payload["protected_paths"] = {k: list(v) for k, v in self.protected_paths.items()}
        payload["required_checks"] = list(self.required_checks)
        payload["merge_method"] = self.merge_method
        payload["claim_ttl_hours"] = self.claim_ttl_hours
```

Add to `from_dict`, before the `if problems:` block:

```python
        workspace = _non_empty(raw, "workspace", "../.worktrees", problems)
        if not workspace.startswith(".."):
            problems.append(
                "workspace must resolve outside the repository tree "
                f"(start with '..'); got {workspace!r}. Repo-internal worktrees "
                "get scanned by editors and confuse which checkout is canonical."
            )

        merge_method = str(raw.get("merge_method", "squash")).strip().casefold()
        if merge_method not in MERGE_METHODS:
            problems.append(
                "merge_method must be one of " + ", ".join(MERGE_METHODS)
                + f"; got {merge_method!r}"
            )

        checks_raw = raw.get("required_checks", ()) or ()
        if isinstance(checks_raw, str) or not isinstance(checks_raw, (list, tuple)):
            problems.append("required_checks must be a list of check names")
            required_checks: tuple[str, ...] = ()
        else:
            required_checks = tuple(str(name).strip() for name in checks_raw if str(name).strip())

        claim_ttl = _non_negative_int(
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
                    problems.append(f"protected_paths[{key!r}] must be a list of globs")
                    continue
                patterns = tuple(str(p).strip() for p in value if str(p).strip())
                if key in DEFAULT_PROTECTED_PATHS and not patterns:
                    problems.append(
                        f"protected_paths[{key!r}] is a default protected category "
                        "and must not be emptied; repository policy may add "
                        "categories but must not silently remove one"
                    )
                    continue
                protected[key] = tuple(dict.fromkeys(protected.get(key, ()) + patterns))
```

Pass all five into the returned `cls(...)`.

- [ ] **Step 4: Run**

Run: `python -m unittest tests.test_producer_board -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/agent_teams/config.py tests/test_producer_board.py
git commit -m "feat: add Consumer configuration keys with grow-only protected paths"
```

---

## Task 4: Protected-path classification

**Files:**
- Modify: `scripts/agent_teams/policy.py`
- Test: `tests/test_acceptance.py`

**Interfaces:**
- Consumes: `Config.protected_paths` from Task 3.
- Produces: `glob_to_regex(pattern) -> re.Pattern`; `path_matches(path, pattern) -> bool`; `classify_protected(changed_paths, protected_paths) -> tuple[str, ...]`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_acceptance.py`:

```python
"""Tests for protected classification, verdict validation, and acceptance.

The acceptance decision table is asserted row by row rather than sampled, for
the same reason the transition and authority tables are: this layer touches no
network, so covering the edges is cheap, and a merge route reached by an
unasserted path is exactly the class of hole that sampling misses.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from agent_teams import policy  # noqa: E402
from agent_teams.config import DEFAULT_PROTECTED_PATHS  # noqa: E402


class GlobTests(unittest.TestCase):
    def test_double_star_spans_directory_separators(self):
        self.assertTrue(policy.path_matches("a/b/c/auth/login.py", "**/auth/**"))

    def test_single_star_does_not_span_separators(self):
        self.assertFalse(policy.path_matches("src/deep/file.py", "src/*.py"))
        self.assertTrue(policy.path_matches("src/file.py", "src/*.py"))

    def test_leading_double_star_matches_at_the_root(self):
        self.assertTrue(policy.path_matches("package.json", "**/package.json"))

    def test_exact_path_matches_only_itself(self):
        self.assertTrue(policy.path_matches("CLAUDE.md", "CLAUDE.md"))
        self.assertFalse(policy.path_matches("docs/CLAUDE.md", "CLAUDE.md"))

    def test_dots_are_literal_not_wildcards(self):
        self.assertFalse(policy.path_matches("CLAUDEXmd", "CLAUDE.md"))


class ProtectedClassificationTests(unittest.TestCase):
    def test_unprotected_change_matches_nothing(self):
        self.assertEqual(
            policy.classify_protected(["src/parser.py"], DEFAULT_PROTECTED_PATHS), ()
        )

    def test_every_default_category_is_reachable(self):
        # A category no path can match is decoration, not protection.
        samples = {
            "authority-and-policy": "scripts/agent_teams/policy.py",
            "acceptance-and-merge": "scripts/agent_teams/workflows.py",
            "github-workflows-and-credentials": ".github/workflows/ci.yml",
            "dependencies-and-manifests": ".claude-plugin/plugin.json",
            "agent-instructions": "skills/consuming-card/SKILL.md",
            "security-boundaries": "src/auth/session.py",
            "architecture-and-design": "docs/ARCHITECTURE.md",
        }
        self.assertEqual(set(samples), set(DEFAULT_PROTECTED_PATHS))
        for category, path in samples.items():
            self.assertEqual(
                policy.classify_protected([path], DEFAULT_PROTECTED_PATHS),
                (category,),
                path,
            )

    def test_one_protected_path_among_many_still_flags(self):
        changed = ["README.md", "src/parser.py", "scripts/agent_teams/policy.py"]
        self.assertEqual(
            policy.classify_protected(changed, DEFAULT_PROTECTED_PATHS),
            ("authority-and-policy",),
        )

    def test_categories_are_returned_sorted_and_deduplicated(self):
        changed = ["skills/a/SKILL.md", "skills/b/SKILL.md", "CLAUDE.md", "AGENTS.md"]
        self.assertEqual(
            policy.classify_protected(changed, DEFAULT_PROTECTED_PATHS),
            ("agent-instructions",),
        )

    def test_windows_separators_are_normalised(self):
        self.assertEqual(
            policy.classify_protected(
                ["scripts\\agent_teams\\policy.py"], DEFAULT_PROTECTED_PATHS
            ),
            ("authority-and-policy",),
        )
```

- [ ] **Step 2: Run and watch it fail**

Run: `python -m unittest tests.test_acceptance -v`
Expected: FAIL — `module 'agent_teams.policy' has no attribute 'path_matches'`

- [ ] **Step 3: Implement**

Add to `policy.py` (it already imports nothing that reaches the network; `re` is fine):

```python
# ------------------------------------------------------------ protected paths

#: ``fnmatch`` has no ``**``, and a protected-path rule that silently fails to
#: span directories would be worse than no rule at all. This translator is
#: small enough to test on its own, which is exactly why it is not inlined.
def glob_to_regex(pattern: str) -> "re.Pattern[str]":
    parts: list[str] = []
    index = 0
    text = str(pattern).replace("\\", "/")
    while index < len(text):
        char = text[index]
        if text.startswith("**/", index):
            parts.append("(?:.*/)?")
            index += 3
        elif text.startswith("**", index):
            parts.append(".*")
            index += 2
        elif char == "*":
            parts.append("[^/]*")
            index += 1
        elif char == "?":
            parts.append("[^/]")
            index += 1
        else:
            parts.append(re.escape(char))
            index += 1
    return re.compile("^" + "".join(parts) + "$")


def path_matches(path: str, pattern: str) -> bool:
    return bool(glob_to_regex(pattern).match(str(path).replace("\\", "/")))


def classify_protected(
    changed_paths: Iterable[str], protected_paths: Mapping[str, Iterable[str]]
) -> tuple[str, ...]:
    """Which protected categories this change touches, sorted and unique."""
    paths = [str(p).replace("\\", "/") for p in changed_paths]
    matched = {
        category
        for category, patterns in protected_paths.items()
        for pattern in patterns
        for path in paths
        if path_matches(path, pattern)
    }
    return tuple(sorted(matched))
```

Add `import re` to the imports at the top of `policy.py`.

- [ ] **Step 4: Run**

Run: `python -m unittest tests.test_acceptance -v`
Expected: PASS, 10 tests.

- [ ] **Step 5: Commit**

```bash
git add scripts/agent_teams/policy.py tests/test_acceptance.py
git commit -m "feat: add protected-path classification with a real glob translator"
```

---

## Task 5: The verdict and acceptance contracts

**Files:**
- Modify: `scripts/agent_teams/model.py`
- Test: `tests/test_acceptance.py`

**Interfaces:**
- Consumes: `Role`, `DomainError`.
- Produces: expanded `Verdict` (fields per §6.1 of the spec), `Verdict.to_dict()`, `Verdict.from_dict(raw)`, `REQUIRED_DIMENSIONS`, `TEST_STRENGTH_DIMENSIONS`, and `Acceptance` with `.to_dict()`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_acceptance.py`:

```python
from agent_teams.model import (  # noqa: E402
    Acceptance, DomainError, REQUIRED_DIMENSIONS, Role, Verdict,
)


def a_pass(**overrides):
    """A complete, valid pass verdict. Tests override one field at a time."""
    base = dict(
        verdict="pass",
        card=42,
        pull_request="https://github.com/acme/widgets/pull/57",
        head_sha="a" * 40,
        design_baseline=("docs/specs/parser.md",),
        review_dimensions=tuple(REQUIRED_DIMENSIONS),
        changed_files=("src/parser.py", "tests/test_parser.py"),
        design_conformance=("AC1 -> parser.parse -> test_parses_header",),
        test_strength=("branch: 14/14", "negative: malformed header rejected"),
        checks=("python -m unittest discover: 145 passed",),
        findings=(),
        challenges=(),
        blind_spots=(),
        limitations="",
        next_role=Role.QA,
    )
    base.update(overrides)
    return Verdict(**base)


class VerdictContractTests(unittest.TestCase):
    def test_a_complete_pass_constructs(self):
        self.assertEqual(a_pass().verdict, "pass")

    def test_looks_good_is_not_a_verdict(self):
        with self.assertRaises(DomainError):
            a_pass(checks=())

    def test_an_unknown_verdict_value_is_rejected(self):
        with self.assertRaises(DomainError):
            a_pass(verdict="lgtm")

    def test_a_pass_requires_a_head_sha(self):
        with self.assertRaises(DomainError):
            a_pass(head_sha="")

    def test_a_pass_requires_changed_files(self):
        with self.assertRaises(DomainError):
            a_pass(changed_files=())

    def test_a_blocked_verdict_may_omit_checks(self):
        blocked = Verdict(
            verdict="blocked", card=42, head_sha="b" * 40,
            pull_request="https://example.invalid/pull/1",
            blind_spots=("cannot reach the staging database",),
            next_role=Role.HUMAN,
        )
        self.assertEqual(blocked.verdict, "blocked")

    def test_round_trips_through_dict(self):
        original = a_pass()
        self.assertEqual(Verdict.from_dict(original.to_dict()), original)


class AcceptanceContractTests(unittest.TestCase):
    def test_only_three_acceptance_values_exist(self):
        self.assertEqual(Acceptance.VALUES, ("eligible", "defect", "protected_change"))

    def test_an_unknown_acceptance_value_is_rejected(self):
        with self.assertRaises(DomainError):
            Acceptance(acceptance="merge-it", head_sha="a" * 40, policy_version="1")

    def test_acceptance_requires_reasons(self):
        result = Acceptance(
            acceptance="eligible", head_sha="a" * 40, policy_version="1",
            reasons=("all required checks green",),
        )
        self.assertIn("reasons", result.to_dict())

    def test_a_verdict_cannot_be_constructed_from_an_acceptance(self):
        # The separation is structural, not merely prose: QA writes one type,
        # policy writes the other, and neither converts into the other.
        self.assertFalse(hasattr(Acceptance, "to_verdict"))
        self.assertFalse(hasattr(Verdict, "to_acceptance"))
```

- [ ] **Step 2: Run and watch it fail**

Run: `python -m unittest tests.test_acceptance -v`
Expected: FAIL — `ImportError: cannot import name 'Acceptance'`

- [ ] **Step 3: Implement**

Replace the existing `Verdict` in `model.py` and add `Acceptance`:

```python
ACCEPTANCE_MARKER = "<!-- agent-teams:acceptance -->"

#: ARCHITECTURE.md 9.6. A pass missing any of these has not reviewed the
#: delivery, whatever its prose says.
REQUIRED_DIMENSIONS: tuple[str, ...] = (
    "design", "architecture", "correctness", "edge-cases",
    "security", "compatibility", "cross-file", "test-strength",
)

#: Line coverage is execution evidence, not behavioural proof. A pass must
#: carry at least one of these stronger dimensions.
TEST_STRENGTH_DIMENSIONS: tuple[str, ...] = (
    "branch", "scenario", "mutation", "integration", "property", "negative",
)


@dataclass(frozen=True)
class Verdict:
    """A Quality Assurance result. Evidence only -- never a merge route."""

    verdict: str
    card: int
    pull_request: str = ""
    head_sha: str = ""
    design_baseline: tuple[str, ...] = ()
    review_dimensions: tuple[str, ...] = ()
    changed_files: tuple[str, ...] = ()
    design_conformance: tuple[str, ...] = ()
    test_strength: tuple[str, ...] = ()
    checks: tuple[str, ...] = ()
    findings: tuple[str, ...] = ()
    challenges: tuple[str, ...] = ()
    blind_spots: tuple[str, ...] = ()
    limitations: str = ""
    next_role: Role | None = None

    VALUES = ("pass", "fail", "blocked")

    def __post_init__(self) -> None:
        if self.verdict not in self.VALUES:
            raise DomainError(
                f"verdict must be one of {', '.join(self.VALUES)}; got {self.verdict!r}"
            )
        if not str(self.head_sha).strip():
            raise DomainError(
                "a verdict must name the exact Pull Request head it reviewed; "
                "evidence not bound to a commit cannot be checked for staleness"
            )
        if self.verdict == "blocked":
            return
        if not self.checks:
            raise DomainError(
                "a pass or fail verdict requires at least one recorded check; "
                "'looks good' is not a verdict"
            )
        if self.verdict == "pass" and not self.changed_files:
            raise DomainError(
                "a pass must enumerate every changed file it reviewed; an "
                "unenumerated change is an unreviewed change"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "card": self.card,
            "pull_request": self.pull_request,
            "head_sha": self.head_sha,
            "design_baseline": list(self.design_baseline),
            "review_dimensions": list(self.review_dimensions),
            "changed_files": list(self.changed_files),
            "design_conformance": list(self.design_conformance),
            "test_strength": list(self.test_strength),
            "checks": list(self.checks),
            "findings": list(self.findings),
            "challenges": list(self.challenges),
            "blind_spots": list(self.blind_spots),
            "limitations": self.limitations,
            "next_role": self.next_role.value if self.next_role else None,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "Verdict":
        tuples = (
            "design_baseline", "review_dimensions", "changed_files",
            "design_conformance", "test_strength", "checks", "findings",
            "challenges", "blind_spots",
        )
        return cls(
            verdict=str(raw.get("verdict", "")),
            card=int(raw.get("card", 0)),
            pull_request=str(raw.get("pull_request", "")),
            head_sha=str(raw.get("head_sha", "")),
            limitations=str(raw.get("limitations", "")),
            next_role=Role.parse_optional(raw.get("next_role")),
            **{name: tuple(raw.get(name, ()) or ()) for name in tuples},
        )


@dataclass(frozen=True)
class Acceptance:
    """A deterministic routing decision. Written by policy, never by a seat."""

    acceptance: str
    head_sha: str
    policy_version: str
    reasons: tuple[str, ...] = ()

    VALUES = ("eligible", "defect", "protected_change")

    def __post_init__(self) -> None:
        if self.acceptance not in self.VALUES:
            raise DomainError(
                f"acceptance must be one of {', '.join(self.VALUES)}; "
                f"got {self.acceptance!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "acceptance": self.acceptance,
            "head_sha": self.head_sha,
            "policy_version": self.policy_version,
            "reasons": list(self.reasons),
        }
```

Add `Mapping` to the `typing` import in `model.py`.

- [ ] **Step 4: Fix the existing callers**

`Verdict` gained a required `head_sha`. Run the whole suite and repair every construction site:

Run: `python -m unittest discover -s tests -p "test_*.py"`
Fix each failure by adding a `head_sha` to the fixture. Where an existing test asserted the old two-argument shape, leave a comment saying what changed and why, per the established convention.

- [ ] **Step 5: Run the whole suite**

Run: `python -m unittest discover -s tests -p "test_*.py"`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/agent_teams/model.py tests/
git commit -m "feat: expand Verdict to the evidence contract and add Acceptance

Kept as two types rather than one with a route field: QA writes Verdict,
policy writes Acceptance, and neither converts into the other."
```

---

## Task 6: Verdict validation and the acceptance decision table

**Files:**
- Modify: `scripts/agent_teams/policy.py`
- Test: `tests/test_acceptance.py`

**Interfaces:**
- Consumes: `Verdict`, `Acceptance`, `REQUIRED_DIMENSIONS`, `TEST_STRENGTH_DIMENSIONS`, `classify_protected`.
- Produces: `ACCEPTANCE_POLICY_VERSION: str`; `class StaleEvidence(PolicyError)`; `class InvalidPass(PolicyError)`; `validate_verdict(verdict, live_head_sha, live_changed_files) -> list[str]`; `evaluate_acceptance(verdict, pr_facts, config) -> Acceptance` where `pr_facts` is a mapping with keys `head_sha`, `changed_files`, `checks` (name -> conclusion), `mergeable` (bool), `draft` (bool).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_acceptance.py`:

```python
from agent_teams.config import Config  # noqa: E402


def facts(**overrides):
    base = dict(
        head_sha="a" * 40,
        changed_files=("src/parser.py", "tests/test_parser.py"),
        checks={"build": "SUCCESS", "test": "SUCCESS"},
        mergeable=True,
        draft=False,
    )
    base.update(overrides)
    return base


def a_config(**overrides):
    raw = {
        "repo": "acme/widgets", "project_owner": "acme", "project_number": 1,
        "required_checks": ["build", "test"],
    }
    raw.update(overrides)
    return Config.from_dict(raw)


class VerdictValidationTests(unittest.TestCase):
    def test_a_current_complete_pass_has_no_problems(self):
        self.assertEqual(
            policy.validate_verdict(a_pass(), "a" * 40, facts()["changed_files"]), []
        )

    def test_a_head_mismatch_is_a_problem(self):
        problems = policy.validate_verdict(a_pass(), "b" * 40, facts()["changed_files"])
        self.assertTrue(any("head" in p for p in problems))

    def test_a_missing_review_dimension_is_a_problem(self):
        verdict = a_pass(review_dimensions=REQUIRED_DIMENSIONS[:-1])
        problems = policy.validate_verdict(verdict, "a" * 40, facts()["changed_files"])
        self.assertTrue(any("test-strength" in p for p in problems))

    def test_an_unresolved_blind_spot_is_a_problem(self):
        verdict = a_pass(blind_spots=("did not review the migration",))
        problems = policy.validate_verdict(verdict, "a" * 40, facts()["changed_files"])
        self.assertTrue(any("blind spot" in p for p in problems))

    def test_an_unenumerated_changed_file_is_a_problem(self):
        problems = policy.validate_verdict(
            a_pass(), "a" * 40, ("src/parser.py", "tests/test_parser.py", "src/sneaky.py")
        )
        self.assertTrue(any("sneaky" in p for p in problems))

    def test_line_coverage_alone_is_not_test_strength(self):
        verdict = a_pass(test_strength=("line: 98%",))
        problems = policy.validate_verdict(verdict, "a" * 40, facts()["changed_files"])
        self.assertTrue(any("line execution" in p for p in problems))

    def test_a_fail_verdict_need_not_be_complete(self):
        verdict = Verdict(
            verdict="fail", card=42, head_sha="a" * 40,
            pull_request="https://example.invalid/pull/1",
            checks=("unittest: 3 failed",),
            findings=("parser.parse crashes on an empty header",),
            next_role=Role.DEV,
        )
        self.assertEqual(policy.validate_verdict(verdict, "a" * 40, ("src/parser.py",)), [])

    def test_a_stale_fail_verdict_is_still_a_problem(self):
        verdict = Verdict(
            verdict="fail", card=42, head_sha="a" * 40,
            pull_request="https://example.invalid/pull/1",
            checks=("unittest: 3 failed",), next_role=Role.DEV,
        )
        self.assertTrue(policy.validate_verdict(verdict, "z" * 40, ("src/parser.py",)))


class AcceptanceTableTests(unittest.TestCase):
    def test_row_3_fail_routes_to_defect(self):
        verdict = Verdict(
            verdict="fail", card=42, head_sha="a" * 40,
            pull_request="p", checks=("unittest: 3 failed",), next_role=Role.DEV,
        )
        result = policy.evaluate_acceptance(verdict, facts(), a_config())
        self.assertEqual(result.acceptance, "defect")

    def test_row_4_blocked_routes_to_protected_change(self):
        verdict = Verdict(
            verdict="blocked", card=42, head_sha="a" * 40, pull_request="p",
            blind_spots=("cannot reach staging",), next_role=Role.HUMAN,
        )
        result = policy.evaluate_acceptance(verdict, facts(), a_config())
        self.assertEqual(result.acceptance, "protected_change")

    def test_row_5_a_protected_path_routes_to_protected_change_even_on_a_clean_pass(self):
        verdict = a_pass(changed_files=("scripts/agent_teams/policy.py",))
        result = policy.evaluate_acceptance(
            verdict, facts(changed_files=("scripts/agent_teams/policy.py",)), a_config()
        )
        self.assertEqual(result.acceptance, "protected_change")
        self.assertTrue(any("authority-and-policy" in r for r in result.reasons))

    def test_row_6_empty_required_checks_fails_closed(self):
        result = policy.evaluate_acceptance(
            a_pass(), facts(), a_config(required_checks=[])
        )
        self.assertEqual(result.acceptance, "protected_change")
        self.assertTrue(any("required checks" in r for r in result.reasons))

    def test_row_7_a_red_required_check_routes_to_defect(self):
        result = policy.evaluate_acceptance(
            a_pass(), facts(checks={"build": "SUCCESS", "test": "FAILURE"}), a_config()
        )
        self.assertEqual(result.acceptance, "defect")

    def test_row_7_a_missing_required_check_routes_to_defect(self):
        result = policy.evaluate_acceptance(
            a_pass(), facts(checks={"build": "SUCCESS"}), a_config()
        )
        self.assertEqual(result.acceptance, "defect")

    def test_row_8_an_unmergeable_pull_request_routes_to_defect(self):
        result = policy.evaluate_acceptance(a_pass(), facts(mergeable=False), a_config())
        self.assertEqual(result.acceptance, "defect")

    def test_row_8_a_draft_pull_request_routes_to_defect(self):
        result = policy.evaluate_acceptance(a_pass(), facts(draft=True), a_config())
        self.assertEqual(result.acceptance, "defect")

    def test_row_9_a_clean_current_complete_pass_is_eligible(self):
        result = policy.evaluate_acceptance(a_pass(), facts(), a_config())
        self.assertEqual(result.acceptance, "eligible")
        self.assertEqual(result.head_sha, "a" * 40)
        self.assertEqual(result.policy_version, policy.ACCEPTANCE_POLICY_VERSION)

    def test_the_result_always_carries_reasons(self):
        for verdict, fact, config in (
            (a_pass(), facts(), a_config()),
            (a_pass(), facts(mergeable=False), a_config()),
            (a_pass(), facts(), a_config(required_checks=[])),
        ):
            self.assertTrue(policy.evaluate_acceptance(verdict, fact, config).reasons)


class MergeFloorTests(unittest.TestCase):
    def test_direct_merge_remains_refused_for_every_agent_seat(self):
        for seat in (Role.ANALYST, Role.ARCHITECT, Role.DEV, Role.QA, Role.LEAD):
            with self.assertRaises(policy.ActionForbidden, msg=str(seat)):
                policy.check_action("merge_pull_request", seat)

    def test_direct_merge_is_still_a_hard_floor(self):
        self.assertIn("merge_pull_request", policy.HARD_FLOORS)

    def test_no_seat_may_request_the_merge_controller_directly(self):
        # Arming auto-merge is a consequence of an eligible acceptance, never
        # an action a seat requests. There is no seat row that permits it.
        for seat in Role:
            with self.assertRaises(policy.ActionForbidden, msg=str(seat)):
                policy.check_action("request_automated_merge", seat)
```

- [ ] **Step 2: Run and watch it fail**

Run: `python -m unittest tests.test_acceptance -v`
Expected: FAIL — `module 'agent_teams.policy' has no attribute 'validate_verdict'`

- [ ] **Step 3: Implement**

Add to `policy.py`:

```python
# ----------------------------------------------------------------- acceptance

#: Identifies the code that made an acceptance decision. Not configuration:
#: a repository cannot claim a decision was made by a policy it did not run.
ACCEPTANCE_POLICY_VERSION = "1"


class StaleEvidence(PolicyError):
    """The verdict does not describe the Pull Request's current head."""


class InvalidPass(PolicyError):
    """A pass that does not meet the evidence contract."""


def validate_verdict(
    verdict: Verdict, live_head_sha: str, live_changed_files: Iterable[str]
) -> list[str]:
    """Every reason this verdict cannot be acted on. Empty means usable.

    Reported all at once rather than first-defect-wins, so a Quality
    Assurance session learns everything it must redo in one pass.
    """
    problems: list[str] = []
    if verdict.head_sha != live_head_sha:
        problems.append(
            f"verdict reviewed head {verdict.head_sha[:12]} but the Pull "
            f"Request head is now {str(live_head_sha)[:12]}; a new commit "
            f"invalidates the evidence. Re-review the current head."
        )
    if verdict.verdict != "pass":
        return problems

    missing = [d for d in REQUIRED_DIMENSIONS if d not in verdict.review_dimensions]
    if missing:
        problems.append(
            "pass is missing required review dimensions: " + ", ".join(missing)
        )
    if verdict.blind_spots:
        problems.append(
            "pass leaves an unresolved blind spot: " + "; ".join(verdict.blind_spots)
        )
    unreviewed = sorted(set(str(p) for p in live_changed_files) - set(verdict.changed_files))
    if unreviewed:
        problems.append(
            "pass does not enumerate every changed file; unreviewed: "
            + ", ".join(unreviewed)
        )
    strength = " ".join(verdict.test_strength).casefold()
    if not any(dimension in strength for dimension in TEST_STRENGTH_DIMENSIONS):
        problems.append(
            "pass treats line execution as sufficient test evidence. Record at "
            "least one of: " + ", ".join(TEST_STRENGTH_DIMENSIONS)
        )
    return problems


def evaluate_acceptance(verdict: Verdict, pr_facts: Mapping[str, object], config) -> Acceptance:
    """The deterministic route for one reviewed delivery.

    Called only after ``validate_verdict`` returned no problems, so the
    evidence is already known to be current and complete and the return type
    stays honestly closed over the three acceptance values.
    """
    head = str(pr_facts.get("head_sha", ""))

    def result(acceptance: str, *reasons: str) -> Acceptance:
        return Acceptance(
            acceptance=acceptance,
            head_sha=head,
            policy_version=ACCEPTANCE_POLICY_VERSION,
            reasons=tuple(reasons),
        )

    if verdict.verdict == "fail":
        return result("defect", "Quality Assurance recorded a fail verdict")
    if verdict.verdict == "blocked":
        return result(
            "protected_change",
            "Quality Assurance could not resolve its uncertainty: "
            + ("; ".join(verdict.blind_spots) or "no reason recorded"),
        )

    protected = classify_protected(
        pr_facts.get("changed_files", ()) or (), config.protected_paths
    )
    if protected:
        return result(
            "protected_change",
            "change touches protected categories: " + ", ".join(protected),
        )

    if not config.required_checks:
        return result(
            "protected_change",
            "no required checks configured; automated acceptance cannot "
            "establish a green baseline. Configure required_checks and branch "
            "protection, or accept this change through the human lane.",
        )

    checks = dict(pr_facts.get("checks", {}) or {})
    unmet = [
        name for name in config.required_checks
        if str(checks.get(name, "")).upper() != "SUCCESS"
    ]
    if unmet:
        return result(
            "defect",
            "required checks are not green: "
            + ", ".join(f"{n}={checks.get(n, 'missing')}" for n in unmet),
        )

    if pr_facts.get("draft"):
        return result("defect", "Pull Request is still a draft")
    if not pr_facts.get("mergeable", False):
        return result("defect", "Pull Request is not mergeable; rebase onto the base branch")

    return result(
        "eligible",
        f"verdict pass bound to head {head[:12]}",
        "all required review dimensions present, no blind spots",
        "every changed file enumerated and reviewed",
        "required checks green: " + ", ".join(config.required_checks),
    )
```

Add `Acceptance`, `REQUIRED_DIMENSIONS`, `TEST_STRENGTH_DIMENSIONS`, and `Verdict` to the `from .model import ...` line.

Add a `request_automated_merge` row to `ACTION_POLICY` refusing every seat, with the note that it exists to make the refusal assertable:

```python
    # Not a seat action. Arming auto-merge is a consequence of an eligible
    # acceptance result, never something a session requests. The row exists so
    # that "no seat may request it" is an assertion rather than an absence.
    "request_automated_merge": {role: _N for role in Role},
```

Add its refusal reason:

```python
    "request_automated_merge": (
        "merging is not a seat action. Publish a complete verdict for the "
        "current head and run `accept`; deterministic policy decides the route"
    ),
```

- [ ] **Step 4: Run**

Run: `python -m unittest tests.test_acceptance -v`
Expected: PASS.

- [ ] **Step 5: Run the whole suite**

Run: `python -m unittest discover -s tests -p "test_*.py"`
Expected: PASS. `test_policy.py` asserts the action table exhaustively and will need `request_automated_merge` added to its expected set.

- [ ] **Step 6: Commit**

```bash
git add scripts/agent_teams/policy.py tests/
git commit -m "feat: add verdict validation and the deterministic acceptance table

Two stages: validate_verdict refuses on stale or incomplete evidence before
evaluate_acceptance is reached, so its return type stays closed over the
three acceptance values. merge_pull_request stays a hard floor."
```

---

## Task 7: Pull Request operations on the board

**Files:**
- Modify: `scripts/agent_teams/board.py`, `tests/fake_gh.py`
- Test: `tests/test_consumer.py`

**Interfaces:**
- Consumes: `Gh`, `Config`, `Verdict`, `Acceptance`.
- Produces: `Board.pull_request(number) -> dict` (keys `number`, `url`, `head_sha`, `state`, `mergeable`, `draft`, `changed_files`, `checks`); `Board.record_verdict(number, verdict)`; `Board.record_acceptance(number, acceptance)`; `Board.latest_verdict(number) -> Verdict | None`; `Board.arm_auto_merge(pr_number, method) -> dict`; `Board.merge_state(pr_number) -> dict`; `Board.auto_merge_enabled() -> bool`. (`create_or_update_pull_request` belongs to Task 9, which is where it is defined and tested.)

- [ ] **Step 1: Extend `fake_gh.py`**

Add `pr_view=None, open_prs=None` to the `FakeGh.__init__` signature, and inside it:

```python
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
        #: Pull Requests already open on a head branch, so create-or-update can
        #: be exercised both ways. Empty means "no Pull Request yet".
        self.open_prs = list(open_prs or [])
```

Replace the `["pr", "view"]` branch in `json` with:

```python
        if head == ["pr", "view"]:
            # Two callers with different --json field sets: pull_request() asks
            # for the review facts, merge_state() asks for the merge outcome.
            wanted = args[args.index("--json") + 1] if "--json" in args else ""
            if "mergedAt" in wanted:
                return {"number": self.pr_view["number"], **self.pr_state}
            return dict(self.pr_view)
        if head == ["pr", "list"]:
            return list(self.open_prs)
```

Extend the `run` dispatch:

```python
        if head == ["pr", "create"]:
            return f"https://github.com/{REPO}/pull/57"
        if head in (["pr", "merge"], ["pr", "edit"]):
            return ""
        if head == ["repo", "view"]:
            return "true"
```

Leave `pr_state` as it is: `merge_state` still reads it, so the existing merged-state fixtures keep working unchanged.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_consumer.py`:

```python
"""Consumer transactions against the injected fake GitHub CLI."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).parent))

from agent_teams.board import Board  # noqa: E402
from agent_teams.config import Config  # noqa: E402
from agent_teams.model import Acceptance, Role  # noqa: E402
from fake_gh import REPO, FakeGh, board_with  # noqa: E402


def a_config(**overrides):
    raw = {
        "repo": REPO, "project_owner": "acme", "project_number": 1,
        "required_checks": ["build", "test"],
    }
    raw.update(overrides)
    return Config.from_dict(raw)


class PullRequestReadTests(unittest.TestCase):
    def setUp(self):
        self.gh = FakeGh(items=board_with((21, "Delivery", "In Review", "qa")))
        self.board = Board(a_config(), gh=self.gh)

    def test_pull_request_normalises_head_files_and_checks(self):
        pr = self.board.pull_request(21)
        self.assertEqual(pr["head_sha"], "a" * 40)
        self.assertEqual(pr["changed_files"], ("src/parser.py", "tests/test_parser.py"))
        self.assertEqual(pr["checks"], {"build": "SUCCESS", "test": "SUCCESS"})
        self.assertTrue(pr["mergeable"])
        self.assertFalse(pr["draft"])

    def test_raw_github_shapes_never_escape_the_board(self):
        pr = self.board.pull_request(21)
        for leaked in ("headRefOid", "statusCheckRollup", "isDraft"):
            self.assertNotIn(leaked, pr)


class VerdictRecordingTests(unittest.TestCase):
    def test_recording_a_verdict_posts_the_marker_and_machine_block(self):
        gh = FakeGh(items=board_with((21, "Delivery", "In Review", "qa")))
        board = Board(a_config(), gh=gh)
        from agent_teams.model import REQUIRED_DIMENSIONS, Verdict
        verdict = Verdict(
            verdict="pass", card=21, head_sha="a" * 40, pull_request="p",
            review_dimensions=REQUIRED_DIMENSIONS,
            changed_files=("src/parser.py",),
            test_strength=("branch: 14/14",), checks=("unittest: 145 passed",),
            next_role=Role.QA,
        )
        board.record_verdict(21, verdict)
        body = gh.calls_matching("issue", "comment")[0][-1]
        self.assertIn("agent-teams:verdict", body)
        self.assertIn('"head_sha"', body)

    def test_the_latest_verdict_wins_when_several_were_posted(self):
        from agent_teams.model import VERDICT_MARKER
        comments = [
            f"{VERDICT_MARKER}\n```json\n"
            '{"verdict": "fail", "card": 21, "head_sha": "aaa", "checks": ["x"]}\n```',
            f"{VERDICT_MARKER}\n```json\n"
            '{"verdict": "pass", "card": 21, "head_sha": "bbb", "checks": ["y"],'
            ' "changed_files": ["src/parser.py"]}\n```',
        ]
        gh = FakeGh(items=board_with((21, "Delivery", "In Review", "qa")), comments=comments)
        board = Board(a_config(), gh=gh)
        self.assertEqual(board.latest_verdict(21).verdict, "pass")

    def test_no_verdict_comment_reads_as_none_not_a_crash(self):
        gh = FakeGh(items=board_with((21, "Delivery", "In Review", "qa")), comments=["hello"])
        self.assertIsNone(Board(a_config(), gh=gh).latest_verdict(21))

    def test_a_malformed_verdict_block_reads_as_none(self):
        from agent_teams.model import VERDICT_MARKER
        gh = FakeGh(
            items=board_with((21, "Delivery", "In Review", "qa")),
            comments=[f"{VERDICT_MARKER}\n```json\n{{not json\n```"],
        )
        self.assertIsNone(Board(a_config(), gh=gh).latest_verdict(21))


class AutoMergeTests(unittest.TestCase):
    def test_arming_auto_merge_uses_the_configured_method(self):
        gh = FakeGh(items=board_with((21, "Delivery", "In Review", "qa")))
        Board(a_config(merge_method="rebase"), gh=gh).arm_auto_merge(57, "rebase")
        call = gh.calls_matching("pr", "merge")[0]
        self.assertIn("--auto", call)
        self.assertIn("--rebase", call)
        self.assertIn("--delete-branch", call)
```

- [ ] **Step 3: Run and watch it fail**

Run: `python -m unittest tests.test_consumer -v`
Expected: FAIL — `Board` has no `pull_request`.

- [ ] **Step 4: Implement on `Board`**

```python
    # ------------------------------------------------------- pull requests

    _PR_FIELDS = "number,url,headRefOid,state,mergeable,isDraft,files,statusCheckRollup"

    def pull_request(self, number: int) -> dict[str, Any]:
        """The linked Pull Request, normalised. Raw gh shapes stop here."""
        raw = self.gh.json(
            ["pr", "view", str(number), "--repo", self.config.repo,
             "--json", self._PR_FIELDS]
        )
        checks = {
            str(entry.get("name", "")): str(entry.get("conclusion", ""))
            for entry in (raw.get("statusCheckRollup") or [])
            if entry.get("name")
        }
        return {
            "number": raw.get("number"),
            "url": raw.get("url", ""),
            "head_sha": str(raw.get("headRefOid", "")),
            "state": str(raw.get("state", "")),
            "mergeable": str(raw.get("mergeable", "")).upper() == "MERGEABLE",
            "draft": bool(raw.get("isDraft", False)),
            "changed_files": tuple(
                str(f.get("path", "")) for f in (raw.get("files") or []) if f.get("path")
            ),
            "checks": checks,
        }

    def record_verdict(self, number: int, verdict: Verdict) -> None:
        self.comment_on_card(number, _render_block(VERDICT_MARKER, verdict.to_dict()))

    def record_acceptance(self, number: int, acceptance: Acceptance) -> None:
        self.comment_on_card(
            number, _render_block(ACCEPTANCE_MARKER, acceptance.to_dict())
        )

    def latest_verdict(self, number: int) -> Verdict | None:
        """The most recent parseable verdict, or None.

        Fails open like ``handoff_count``: an unreadable or malformed comment
        reads as 'no verdict', which refuses the accept, rather than crashing
        a session that could still report why.
        """
        for body in reversed(self.comments(number)):
            if VERDICT_MARKER not in body:
                continue
            payload = _parse_block(body)
            if payload is None:
                continue
            try:
                return Verdict.from_dict(payload)
            except (DomainError, TypeError, ValueError):
                continue
        return None

    def arm_auto_merge(self, pr_number: int, method: str) -> dict[str, Any]:
        self.gh.run(
            ["pr", "merge", str(pr_number), "--repo", self.config.repo,
             "--auto", f"--{method}", "--delete-branch"]
        )
        return {"ok": True, "pull_request": pr_number, "method": method, "armed": True}

    def merge_state(self, pr_number: int) -> dict[str, Any]:
        raw = self.gh.json(
            ["pr", "view", str(pr_number), "--repo", self.config.repo,
             "--json", "state,mergedAt,mergeCommit"]
        )
        return {
            "state": str(raw.get("state", "")),
            "merged_at": raw.get("mergedAt"),
            "merge_commit": (raw.get("mergeCommit") or {}).get("oid"),
        }
```

And module-level helpers in `board.py`:

```python
def _render_block(marker: str, payload: dict[str, Any]) -> str:
    """A human-readable marker plus one parseable JSON block."""
    return marker + "\n\n```json\n" + json.dumps(payload, indent=2) + "\n```"


def _parse_block(body: str) -> dict[str, Any] | None:
    start = body.find("```json")
    end = body.find("```", start + 7)
    if start < 0 or end < 0:
        return None
    try:
        payload = json.loads(body[start + 7 : end])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None
```

Add `import json` and the new model imports to `board.py`.

- [ ] **Step 5: Extend `doctor` with the two acceptance preconditions**

Spec assumption 1 and 2: without repository auto-merge enabled and required checks configured, the merge path is either broken or vacuous. `doctor` validates and explains; it never creates.

Write the failing tests first, in `tests/test_consumer.py`:

```python
class DoctorAcceptanceTests(unittest.TestCase):
    def test_doctor_reports_auto_merge_disabled_as_a_problem(self):
        gh = FakeGh(items=board_with((21, "x", "In Review", "qa")))
        gh.auto_merge_allowed = False
        report = Board(a_config(), gh=gh).doctor()
        self.assertTrue(any("auto-merge" in p for p in report["problems"]))

    def test_doctor_reports_empty_required_checks_as_a_problem(self):
        gh = FakeGh(items=board_with((21, "x", "In Review", "qa")))
        report = Board(a_config(required_checks=[]), gh=gh).doctor()
        self.assertTrue(
            any("required_checks" in p and "eligible" in p for p in report["problems"])
        )
```

Add `self.auto_merge_allowed = True` to `FakeGh.__init__`, and make its `run` return `str(self.auto_merge_allowed).casefold()` for `["repo", "view"]`.

Then, inside `Board.doctor`, before it assembles its result:

```python
        if not self.config.required_checks:
            problems.append(
                "required_checks is empty, so no delivery can ever be eligible "
                "for automated acceptance; every pass will route to the human "
                "protected-change lane. Configure the check names that must be "
                "green before a merge."
            )
        else:
            allowed = self.gh.run(
                ["repo", "view", self.config.repo, "--json", "autoMergeAllowed",
                 "--jq", ".autoMergeAllowed"]
            ).strip().casefold()
            if allowed != "true":
                problems.append(
                    "auto-merge is not enabled on "
                    f"{self.config.repo}; `gh pr merge --auto` will fail. Enable "
                    "it in repository settings, and configure branch protection "
                    "with the required checks -- without protection, --auto "
                    "merges immediately and the retest guarantee is vacuous."
                )
```

- [ ] **Step 6: Run**

Run: `python -m unittest tests.test_consumer -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add scripts/agent_teams/board.py tests/fake_gh.py tests/test_consumer.py
git commit -m "feat: add Pull Request reads, verdict/acceptance records, and auto-merge arming

doctor now reports the two acceptance preconditions: repository auto-merge
and a non-empty required_checks. It validates and explains; it never creates."
```

---

## Task 8: `Consumer.claim`

**Files:**
- Modify: `scripts/agent_teams/workflows.py`
- Test: `tests/test_consumer.py`

**Interfaces:**
- Consumes: `Git`, `ClaimRaceLost`, `worktree_path`, `Board`, `policy`.
- Produces: `class Consumer` with `__init__(config, board, git=None)` and `claim(number, seat) -> dict`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_consumer.py`:

```python
class FakeGit:
    """Records claim and worktree calls; arms a race loss on demand."""

    def __init__(self, *, race_lost=False):
        self.race_lost = race_lost
        self.calls = []

    def claim(self, number, title, seat, session_id=None):
        self.calls.append(("claim", number, seat))
        if self.race_lost:
            from agent_teams.git import ClaimRaceLost
            raise ClaimRaceLost(number, f"claim/{number}-x")
        return {
            "ok": True, "branch": f"claim/{number}-x", "ref": f"refs/heads/claim/{number}-x",
            "base_sha": "b" * 40, "claim_sha": "c" * 40, "session": "s1",
        }

    def add_worktree(self, path, branch, sha):
        self.calls.append(("worktree", str(path)))
        return {"ok": True, "resumed": False, "worktree": str(path), "branch": branch}


class ClaimTests(unittest.TestCase):
    def _consumer(self, items, git=None, **gh_kwargs):
        from agent_teams.workflows import Consumer
        gh = FakeGh(items=items, **gh_kwargs)
        board = Board(a_config(), gh=gh)
        return Consumer(a_config(), board, git=git or FakeGit()), gh

    def test_claiming_a_ready_dev_card_succeeds(self):
        consumer, gh = self._consumer(board_with((12, "Implement parser", "Ready", "dev")))
        result = consumer.claim(12, Role.DEV)
        self.assertTrue(result["ok"])
        self.assertEqual(result["branch"], "claim/12-x")
        self.assertIn("worktree", result)

    def test_claim_transitions_to_in_progress_and_leaves_role_alone(self):
        consumer, gh = self._consumer(board_with((12, "Implement parser", "Ready", "dev")))
        consumer.claim(12, Role.DEV)
        self.assertEqual(result_status(gh), "STATUS_IN_PROGRESS")
        self.assertEqual(len(gh.calls_matching("project", "item-edit")), 1)

    def test_a_card_in_the_wrong_status_is_refused_before_any_git_call(self):
        git = FakeGit()
        consumer, gh = self._consumer(board_with((12, "x", "Backlog", "dev")), git=git)
        with self.assertRaises(Exception):
            consumer.claim(12, Role.DEV)
        self.assertEqual(git.calls, [])

    def test_a_card_owned_by_another_seat_is_refused_before_any_git_call(self):
        git = FakeGit()
        consumer, gh = self._consumer(board_with((12, "x", "Ready", "qa")), git=git)
        with self.assertRaises(Exception):
            consumer.claim(12, Role.DEV)
        self.assertEqual(git.calls, [])

    def test_a_seat_that_may_not_claim_is_refused_before_any_git_call(self):
        git = FakeGit()
        consumer, gh = self._consumer(board_with((12, "x", "Ready", "lead")), git=git)
        with self.assertRaises(Exception):
            consumer.claim(12, Role.LEAD)
        self.assertEqual(git.calls, [])

    def test_a_lost_race_writes_nothing_to_the_board(self):
        consumer, gh = self._consumer(
            board_with((12, "x", "Ready", "dev")), git=FakeGit(race_lost=True)
        )
        result = consumer.claim(12, Role.DEV)
        self.assertFalse(result["ok"])
        self.assertTrue(result["race_lost"])
        self.assertNotIn("partial", result)
        self.assertEqual(gh.calls_matching("project", "item-edit"), [])

    def test_a_failed_transition_reports_the_claim_as_completed(self):
        consumer, gh = self._consumer(
            board_with((12, "x", "Ready", "dev")),
            fail_on={"project item-edit": "boom"},
        )
        result = consumer.claim(12, Role.DEV)
        self.assertFalse(result["ok"])
        self.assertTrue(result["partial"])
        self.assertIn("claim", " ".join(result["completed"]))
        self.assertTrue(any("transition" in step for step in result["recovery"]))


def result_status(gh):
    edits = gh.calls_matching("project", "item-edit")
    return edits[-1][edits[-1].index("--single-select-option-id") + 1]
```

- [ ] **Step 2: Run and watch it fail**

Run: `python -m unittest tests.test_consumer -v`
Expected: FAIL — `ImportError: cannot import name 'Consumer'`

- [ ] **Step 3: Implement**

Add to `workflows.py`:

```python
class Consumer:
    """One Card, one stage. The Consumer half of ARCHITECTURE.md section 7.

    Every routine runs the same spine -- bind, preflight, optional claim,
    bounded work, one durable outcome, legal transition and handoff, stop.
    They differ only in whether they claim and what they produce.
    """

    def __init__(self, config: Config, board: Board, git=None):
        self.config = config
        self.board = board
        self.git = git if git is not None else Git(Path.cwd())

    def _bound_card(self, number: int, seat: Role, status: Status) -> Card:
        """Refuse anything but the exact expected pair, before any mutation."""
        card = self.board.card(number)
        if card.status is not status:
            raise WorkflowError(
                f"#{number} is {card.routing_state}; this routine requires "
                f"({status}, {seat}). Live board state overrides a stale kickoff."
            )
        if card.role is not seat:
            raise WorkflowError(
                f"#{number} is owned by `{card.role or '-'}`, not `{seat}`; "
                f"re-read the board before acting"
            )
        return card

    def claim(self, number: int, seat: Role) -> dict[str, Any]:
        """Reserve one Ready Card and open its isolated worktree.

        Claim first, Status second. The failure modes are asymmetric: a won
        claim with the Card still Ready waits for a re-run, but a Card moved
        to In Progress by a session that then lost the race has been mutated
        by a session that never owned it.
        """
        policy.check_action("claim_card", seat)
        card = self._bound_card(number, seat, Status.READY)

        log = MutationLog()
        try:
            claim = self.git.claim(number, card.title, seat.value)
        except ClaimRaceLost as exc:
            return {
                "ok": False,
                "race_lost": True,
                "issue": number,
                "branch": exc.branch,
                "error": str(exc),
                "next": [
                    "Do not retry. Another session owns this Card.",
                    "Run `dispatch` to pick different Ready work.",
                ],
            }
        log.record("claim", branch=claim["branch"], claim_sha=claim["claim_sha"])

        target = worktree_path(Path(self.config.workspace), number, card.title)
        try:
            tree = self.git.add_worktree(target, claim["branch"], claim["claim_sha"])
        except AgentTeamsError as exc:
            return log.partial_result(
                "worktree",
                str(exc),
                [
                    f"git worktree add {target} {claim['branch']}",
                    f"producer_board.py transition {number} --to \"In Progress\" "
                    f"--acting-role {seat}",
                ],
            )
        log.record("worktree", worktree=tree["worktree"], resumed=tree["resumed"])

        try:
            self.board.transition_card(number, Status.IN_PROGRESS, seat)
        except AgentTeamsError as exc:
            return log.partial_result(
                "transition",
                str(exc),
                [
                    f"producer_board.py transition {number} --to \"In Progress\" "
                    f"--acting-role {seat}"
                ],
            )
        log.record("transition")

        return {
            "ok": True,
            "issue": number,
            "url": card.url,
            "status": Status.IN_PROGRESS.value,
            "role": seat.value,
            **log.artifacts,
        }
```

Add the imports: `from pathlib import Path`, and `from .git import ClaimRaceLost, Git, worktree_path`.

- [ ] **Step 4: Run**

Run: `python -m unittest tests.test_consumer -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/agent_teams/workflows.py tests/test_consumer.py
git commit -m "feat: add Consumer.claim with claim-first compensation order"
```

---

## Task 9: `Consumer.submit` and the Pull Request contract

**Files:**
- Modify: `scripts/agent_teams/workflows.py`
- Test: `tests/test_consumer.py`

**Interfaces:**
- Consumes: `Consumer` from Task 8.
- Produces: `validate_pr_body(body) -> list[str]`; `acceptance_criteria_problems(card_body) -> list[str]`; `Consumer.submit(number, seat, title, body) -> dict`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_consumer.py`:

```python
GOOD_PR_BODY = """## Summary
Adds the parser.

## Test Plan
Unit tests for the header cases.

## Automated Verification
`python -m unittest discover -s tests`: 145 passed.

## Human Verification TODO
- Confirm the CSV opens correctly in Excel, which we cannot automate.

## Retro Notes
Empty headers were the case the spec did not name.

Closes #12.

<!-- agent-teams:pr -->
"""


class PullRequestContractTests(unittest.TestCase):
    def test_a_complete_body_has_no_problems(self):
        from agent_teams.workflows import validate_pr_body
        self.assertEqual(validate_pr_body(GOOD_PR_BODY), [])

    def test_a_missing_automated_verification_section_is_refused(self):
        from agent_teams.workflows import validate_pr_body
        body = GOOD_PR_BODY.replace("## Automated Verification", "## Notes")
        self.assertTrue(any("Automated Verification" in p for p in validate_pr_body(body)))

    def test_a_missing_closing_trailer_is_refused(self):
        from agent_teams.workflows import validate_pr_body
        self.assertTrue(
            any("Closes" in p for p in validate_pr_body(GOOD_PR_BODY.replace("Closes #12.", "")))
        )

    def test_a_missing_marker_is_refused(self):
        from agent_teams.workflows import validate_pr_body
        body = GOOD_PR_BODY.replace("<!-- agent-teams:pr -->", "")
        self.assertTrue(any("marker" in p for p in validate_pr_body(body)))

    def test_filler_human_verification_is_refused(self):
        from agent_teams.workflows import validate_pr_body
        body = GOOD_PR_BODY.replace(
            "- Confirm the CSV opens correctly in Excel, which we cannot automate.",
            "- Check that it works",
        )
        self.assertTrue(any("filler" in p for p in validate_pr_body(body)))

    def test_bare_acceptance_criteria_are_refused(self):
        from agent_teams.workflows import acceptance_criteria_problems
        problems = acceptance_criteria_problems("- [x] parses headers\n- [ ] handles empty\n")
        self.assertTrue(any("handles empty" in p for p in problems))

    def test_waived_acceptance_criteria_need_a_reason(self):
        from agent_teams.workflows import acceptance_criteria_problems
        self.assertEqual(
            acceptance_criteria_problems("- [x] a\n- [!] b -- deferred, see #99\n"), []
        )

    def test_a_bare_waiver_without_a_reason_is_refused(self):
        from agent_teams.workflows import acceptance_criteria_problems
        self.assertTrue(acceptance_criteria_problems("- [!] b\n"))


class SubmitTests(unittest.TestCase):
    def _consumer(self, items, **gh_kwargs):
        from agent_teams.workflows import Consumer
        gh = FakeGh(items=items, **gh_kwargs)
        return Consumer(a_config(), Board(a_config(), gh=gh), git=FakeGit()), gh

    def test_submit_opens_one_pull_request_then_transitions_and_hands_off(self):
        consumer, gh = self._consumer(board_with((23, "Active build", "In Progress", "dev")))
        result = consumer.submit(23, Role.DEV, "feat: parser", GOOD_PR_BODY)
        self.assertTrue(result["ok"])
        self.assertEqual(len(gh.calls_matching("pr", "create")), 1)
        self.assertEqual(result["status"], "In Review")
        self.assertEqual(result["role"], "qa")

    def test_an_invalid_body_is_refused_before_any_github_call(self):
        consumer, gh = self._consumer(board_with((23, "x", "In Progress", "dev")))
        with self.assertRaises(Exception):
            consumer.submit(23, Role.DEV, "feat: parser", "## Summary\nonly this")
        self.assertEqual(gh.calls_matching("pr", "create"), [])

    def test_a_failed_handoff_reports_the_pull_request_as_completed(self):
        consumer, gh = self._consumer(
            board_with((23, "x", "In Progress", "dev")),
            fail_on={"issue comment": "boom"},
        )
        result = consumer.submit(23, Role.DEV, "feat: parser", GOOD_PR_BODY)
        self.assertFalse(result["ok"])
        self.assertTrue(result["partial"])
        self.assertTrue(any("handoff" in step for step in result["recovery"]))
        # Never replays the Pull Request creation: that step is not idempotent.
        self.assertFalse(any("pr create" in step for step in result["recovery"]))
```

- [ ] **Step 2: Run and watch it fail**

Run: `python -m unittest tests.test_consumer -v`
Expected: FAIL — `cannot import name 'validate_pr_body'`

- [ ] **Step 3: Implement**

Add to `workflows.py`:

```python
PR_SECTIONS = (
    "## Summary", "## Test Plan", "## Automated Verification",
    "## Human Verification TODO", "## Retro Notes",
)

#: Phrases that make a Human Verification item decoration. An item that any
#: reviewer could write without reading the change has not identified work a
#: human must actually do.
_FILLER = (
    "check that it works", "verify it works", "make sure it works",
    "test the feature", "looks good", "n/a", "none", "tbd",
)


def validate_pr_body(body: str) -> list[str]:
    """Every way this Pull Request body breaks the section 9.5 contract."""
    problems: list[str] = []
    for section in PR_SECTIONS:
        if section not in body:
            problems.append(f"missing required section {section}")
    if "## Automated Verification" in body:
        segment = body.split("## Automated Verification", 1)[1]
        segment = segment.split("\n## ", 1)[0].strip()
        if not segment:
            problems.append(
                "## Automated Verification is empty; name the concrete commands, "
                "outputs, and specialist reviews that actually ran"
            )
    if not re.search(r"Closes #\d+", body):
        problems.append(
            "missing the `Closes #<issue>` trailer; without it GitHub will not "
            "close the Issue on merge"
        )
    if PR_MARKER not in body:
        problems.append(f"missing the {PR_MARKER} marker that identifies a governed delivery")
    if "## Human Verification TODO" in body:
        segment = body.split("## Human Verification TODO", 1)[1].split("\n## ", 1)[0]
        for line in segment.splitlines():
            item = line.strip().lstrip("-*").strip().casefold()
            if item and any(item.startswith(f) or item == f for f in _FILLER):
                problems.append(
                    f"filler Human Verification item: {line.strip()!r}. Every item "
                    f"must require genuine human judgment"
                )
    return problems


def acceptance_criteria_problems(card_body: str) -> list[str]:
    """Acceptance criteria that are not in a terminal state.

    A bare `[ ]` at submit time means the Card claims work the delivery did
    not do. `[!]` waives an item, but a waiver without a reason is just a
    box nobody ticked.
    """
    problems: list[str] = []
    for line in (card_body or "").splitlines():
        stripped = line.strip()
        if re.match(r"^[-*]\s*\[\s\]", stripped):
            problems.append(f"acceptance criterion is still open: {stripped}")
        elif re.match(r"^[-*]\s*\[!\]", stripped):
            remainder = re.sub(r"^[-*]\s*\[!\]", "", stripped).strip()
            if len(remainder.split()) < 3:
                problems.append(f"waived acceptance criterion has no reason: {stripped}")
    return problems
```

And the method on `Consumer`:

```python
    def submit(self, number: int, seat: Role, title: str, body: str) -> dict[str, Any]:
        """Open or update exactly one Pull Request, then transition and hand off."""
        card = self._bound_card(number, seat, Status.IN_PROGRESS)

        problems = validate_pr_body(body)
        if problems:
            raise WorkflowError(
                "Pull Request body does not meet the delivery contract:\n  - "
                + "\n  - ".join(problems)
            )

        log = MutationLog()
        url = self.board.create_or_update_pull_request(number, card.title, title, body)
        log.record("pull_request", pull_request=url)

        try:
            self.board.transition_card(number, Status.IN_REVIEW, seat)
        except AgentTeamsError as exc:
            return log.partial_result(
                "transition", str(exc),
                [
                    f'producer_board.py transition {number} --to "In Review" '
                    f"--acting-role {seat}",
                    f"producer_board.py handoff {number} --from-role {seat} "
                    f'--to-role qa --note "delivery ready" --artifacts "{url}"',
                ],
            )
        log.record("transition")

        note = f"Delivery ready for independent verification: {url}"
        try:
            self.board.handoff_card(
                number, seat, Role.QA, note,
                needs="verify against the acceptance criteria and publish a verdict",
                artifacts=url,
            )
        except PartialHandoff as exc:
            return exc.to_result(self.config.repo)
        except AgentTeamsError as exc:
            return log.partial_result(
                "handoff", str(exc),
                [
                    f"producer_board.py handoff {number} --from-role {seat} "
                    f'--to-role qa --note "{note}" --artifacts "{url}"'
                ],
            )
        log.record("handoff")

        return {
            "ok": True, "issue": number, "url": card.url,
            "status": Status.IN_REVIEW.value, "role": Role.QA.value,
            **log.artifacts,
        }
```

And on `Board`:

```python
    def create_or_update_pull_request(
        self, number: int, card_title: str, title: str, body: str
    ) -> str:
        """Exactly one Pull Request per claim branch. Idempotent by branch.

        One Card, one Consumer, one delivery (ARCHITECTURE.md Appendix A.1). A
        resumed or corrected session must update the Pull Request it already
        opened rather than opening a second one, so this keys off the claim
        branch rather than on whether this session remembers creating it.
        """
        branch = claim_branch(number, card_title)
        existing = self.gh.json(
            ["pr", "list", "--repo", self.config.repo, "--head", branch,
             "--state", "open", "--json", "number,url"]
        )
        if existing:
            self.gh.run(
                ["pr", "edit", str(existing[0]["number"]), "--repo", self.config.repo,
                 "--title", title, "--body", body]
            )
            return str(existing[0]["url"])
        return self.gh.run(
            ["pr", "create", "--repo", self.config.repo, "--head", branch,
             "--title", title, "--body", body]
        ).strip()
```

Add `from .git import claim_branch` to `board.py`, and `import re` plus `PR_MARKER` to the `workflows.py` imports.

Add one more test to `SubmitTests` covering the update path:

```python
    def test_resubmitting_updates_the_existing_pull_request_instead_of_opening_a_second(self):
        consumer, gh = self._consumer(
            board_with((23, "Active build", "In Progress", "dev")),
            open_prs=[{"number": 57, "url": f"https://github.com/{REPO}/pull/57"}],
        )
        result = consumer.submit(23, Role.DEV, "feat: parser", GOOD_PR_BODY)
        self.assertTrue(result["ok"])
        self.assertEqual(gh.calls_matching("pr", "create"), [])
        self.assertEqual(len(gh.calls_matching("pr", "edit")), 1)
```

- [ ] **Step 4: Run**

Run: `python -m unittest tests.test_consumer -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/agent_teams/workflows.py scripts/agent_teams/board.py tests/
git commit -m "feat: add Consumer.submit with the Pull Request delivery contract"
```

---

## Task 10: `Consumer.verdict` — evidence only

**Files:**
- Modify: `scripts/agent_teams/workflows.py`
- Test: `tests/test_consumer.py`

**Interfaces:**
- Consumes: `Consumer`, `Board.pull_request`, `Board.record_verdict`, `policy.validate_verdict`.
- Produces: `Consumer.verdict(number, verdict) -> dict`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_consumer.py`:

```python
class VerdictTests(unittest.TestCase):
    def _consumer(self, **gh_kwargs):
        from agent_teams.workflows import Consumer
        gh = FakeGh(items=board_with((21, "Delivery", "In Review", "qa")), **gh_kwargs)
        return Consumer(a_config(), Board(a_config(), gh=gh), git=FakeGit()), gh

    def _verdict(self, **overrides):
        from agent_teams.model import REQUIRED_DIMENSIONS, Verdict
        base = dict(
            verdict="pass", card=21, head_sha="a" * 40, pull_request="p",
            review_dimensions=REQUIRED_DIMENSIONS,
            changed_files=("src/parser.py", "tests/test_parser.py"),
            test_strength=("branch: 14/14",), checks=("unittest: 145 passed",),
            next_role=Role.QA,
        )
        base.update(overrides)
        return Verdict(**base)

    def test_recording_a_current_verdict_succeeds(self):
        consumer, gh = self._consumer()
        result = consumer.verdict(21, self._verdict())
        self.assertTrue(result["ok"])
        self.assertEqual(len(gh.calls_matching("issue", "comment")), 1)

    def test_a_verdict_changes_neither_status_nor_role(self):
        # Evidence is not a route. The route comes from accept.
        consumer, gh = self._consumer()
        consumer.verdict(21, self._verdict())
        self.assertEqual(gh.calls_matching("project", "item-edit"), [])

    def test_a_stale_verdict_is_refused_and_writes_nothing(self):
        consumer, gh = self._consumer()
        with self.assertRaises(Exception) as caught:
            consumer.verdict(21, self._verdict(head_sha="z" * 40))
        self.assertIn("head", str(caught.exception))
        self.assertEqual(gh.calls_matching("issue", "comment"), [])

    def test_an_incomplete_pass_is_refused_with_every_reason_at_once(self):
        consumer, gh = self._consumer()
        with self.assertRaises(Exception) as caught:
            consumer.verdict(
                21,
                self._verdict(
                    review_dimensions=("correctness",),
                    blind_spots=("did not review the migration",),
                    test_strength=("line: 98%",),
                ),
            )
        message = str(caught.exception)
        self.assertIn("dimensions", message)
        self.assertIn("blind spot", message)
        self.assertIn("line execution", message)

    def test_a_fail_verdict_is_recorded_without_completeness_demands(self):
        consumer, gh = self._consumer()
        from agent_teams.model import Verdict
        result = consumer.verdict(
            21,
            Verdict(
                verdict="fail", card=21, head_sha="a" * 40, pull_request="p",
                checks=("unittest: 3 failed",),
                findings=("parse crashes on an empty header",), next_role=Role.DEV,
            ),
        )
        self.assertTrue(result["ok"])
```

- [ ] **Step 2: Run and watch it fail**

Run: `python -m unittest tests.test_consumer -v`
Expected: FAIL — `Consumer` has no `verdict`.

- [ ] **Step 3: Implement**

```python
    def verdict(self, number: int, verdict: Verdict) -> dict[str, Any]:
        """Publish review evidence for the exact current head.

        Deliberately performs no transition and no handoff. A verdict is
        evidence; the route is chosen by ``accept`` from deterministic policy.
        That separation is what stops a reviewer selecting its own outcome.
        """
        self._bound_card(number, Role.QA, Status.IN_REVIEW)
        policy.check_action("write_verdict", Role.QA)

        pr = self.board.pull_request(number)
        problems = policy.validate_verdict(verdict, pr["head_sha"], pr["changed_files"])
        if problems:
            raise WorkflowError(
                "verdict cannot be published:\n  - " + "\n  - ".join(problems)
            )

        self.board.record_verdict(number, verdict)
        return {
            "ok": True, "issue": number, "verdict": verdict.verdict,
            "head_sha": verdict.head_sha, "pull_request": pr["url"],
            "next": [f"producer_board.py accept {number}"],
        }
```

- [ ] **Step 4: Run**

Run: `python -m unittest tests.test_consumer -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/agent_teams/workflows.py tests/test_consumer.py
git commit -m "feat: add Consumer.verdict as evidence only, with no route selection"
```

---

## Task 11: `Consumer.accept` — the deterministic tail

**Files:**
- Modify: `scripts/agent_teams/workflows.py`
- Test: `tests/test_consumer.py`

**Interfaces:**
- Consumes: `policy.evaluate_acceptance`, `Board.latest_verdict`, `Board.record_acceptance`, `Board.arm_auto_merge`.
- Produces: `Consumer.accept(number) -> dict`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_consumer.py`:

```python
def verdict_comment(**overrides):
    import json
    from agent_teams.model import REQUIRED_DIMENSIONS, VERDICT_MARKER
    payload = {
        "verdict": "pass", "card": 21, "head_sha": "a" * 40, "pull_request": "p",
        "review_dimensions": list(REQUIRED_DIMENSIONS),
        "changed_files": ["src/parser.py", "tests/test_parser.py"],
        "test_strength": ["branch: 14/14"], "checks": ["unittest: 145 passed"],
        "blind_spots": [], "next_role": "qa",
    }
    payload.update(overrides)
    return VERDICT_MARKER + "\n\n```json\n" + json.dumps(payload) + "\n```"


class AcceptTests(unittest.TestCase):
    def _consumer(self, comments, config=None, **gh_kwargs):
        from agent_teams.workflows import Consumer
        config = config or a_config()
        gh = FakeGh(
            items=board_with((21, "Delivery", "In Review", "qa")),
            comments=comments, **gh_kwargs
        )
        return Consumer(config, Board(config, gh=gh), git=FakeGit()), gh

    def test_an_eligible_pass_arms_auto_merge_and_leaves_the_card_in_review(self):
        consumer, gh = self._consumer([verdict_comment()])
        result = consumer.accept(21)
        self.assertTrue(result["ok"])
        self.assertEqual(result["acceptance"], "eligible")
        self.assertEqual(len(gh.calls_matching("pr", "merge")), 1)
        self.assertEqual(gh.calls_matching("project", "item-edit"), [])

    def test_a_defect_returns_the_card_to_development_on_the_same_pull_request(self):
        consumer, gh = self._consumer([verdict_comment(verdict="fail")])
        result = consumer.accept(21)
        self.assertEqual(result["acceptance"], "defect")
        self.assertEqual(result["status"], "In Progress")
        self.assertEqual(result["role"], "dev")
        self.assertEqual(gh.calls_matching("pr", "merge"), [])

    def test_a_protected_change_hands_to_human_without_moving_status(self):
        consumer, gh = self._consumer(
            [verdict_comment(changed_files=["scripts/agent_teams/policy.py"])],
        )
        gh.pr_view = {**gh.pr_view, "files": [{"path": "scripts/agent_teams/policy.py"}]}
        result = consumer.accept(21)
        self.assertEqual(result["acceptance"], "protected_change")
        self.assertEqual(result["role"], "human")
        self.assertEqual(result["status"], "In Review")
        self.assertTrue(any("authority-and-policy" in r for r in result["reasons"]))

    def test_stale_evidence_is_refused_and_mutates_nothing(self):
        consumer, gh = self._consumer([verdict_comment(head_sha="z" * 40)])
        with self.assertRaises(Exception) as caught:
            consumer.accept(21)
        self.assertIn("head", str(caught.exception))
        self.assertEqual(gh.calls_matching("pr", "merge"), [])
        self.assertEqual(gh.calls_matching("project", "item-edit"), [])

    def test_a_missing_verdict_is_refused(self):
        consumer, gh = self._consumer(["just a chat comment"])
        with self.assertRaises(Exception):
            consumer.accept(21)

    def test_the_acceptance_comment_is_posted_on_every_route(self):
        for comment in (verdict_comment(), verdict_comment(verdict="fail")):
            consumer, gh = self._consumer([comment])
            consumer.accept(21)
            bodies = [c[-1] for c in gh.calls_matching("issue", "comment")]
            self.assertTrue(any("agent-teams:acceptance" in b for b in bodies))

    def test_no_required_checks_never_yields_eligible(self):
        consumer, gh = self._consumer([verdict_comment()], config=a_config(required_checks=[]))
        result = consumer.accept(21)
        self.assertEqual(result["acceptance"], "protected_change")
        self.assertEqual(gh.calls_matching("pr", "merge"), [])
```

- [ ] **Step 2: Run and watch it fail**

Run: `python -m unittest tests.test_consumer -v`
Expected: FAIL — `Consumer` has no `accept`.

- [ ] **Step 3: Implement**

```python
    def accept(self, number: int) -> dict[str, Any]:
        """Evaluate one reviewed delivery and execute the deterministic route.

        The seat does not choose here. It supplies an Issue number; every
        other input is read from live GitHub state, and the route comes from
        ``policy.evaluate_acceptance``.
        """
        card = self._bound_card(number, Role.QA, Status.IN_REVIEW)

        verdict = self.board.latest_verdict(number)
        if verdict is None:
            raise WorkflowError(
                f"#{number} has no parseable verdict. Publish one with "
                f"`producer_board.py verdict {number} ...` before accepting."
            )

        pr = self.board.pull_request(number)
        problems = policy.validate_verdict(verdict, pr["head_sha"], pr["changed_files"])
        if problems:
            raise WorkflowError(
                "cannot accept on this evidence:\n  - " + "\n  - ".join(problems)
            )

        result = policy.evaluate_acceptance(verdict, pr, self.config)
        self.board.record_acceptance(number, result)

        base = {
            "ok": True, "issue": number, "url": card.url,
            "acceptance": result.acceptance, "head_sha": result.head_sha,
            "policy_version": result.policy_version, "reasons": list(result.reasons),
            "pull_request": pr["url"],
        }

        if result.acceptance == "eligible":
            self.board.arm_auto_merge(pr["number"], self.config.merge_method)
            return {
                **base,
                "status": Status.IN_REVIEW.value, "role": Role.QA.value,
                "merge": "armed",
                "next": [
                    "GitHub merges when required checks pass on the current base.",
                    f"After merge: producer_board.py reconcile-done {number}",
                ],
            }

        if result.acceptance == "defect":
            log = MutationLog()
            note = "Verification found a defect: " + "; ".join(result.reasons)
            try:
                self.board.transition_card(number, Status.IN_PROGRESS, Role.QA)
                log.record("transition")
                self.board.handoff_card(
                    number, Role.QA, Role.DEV, note,
                    needs="correct the finding on the same branch and Pull Request",
                    artifacts=pr["url"],
                )
            except PartialHandoff as exc:
                return exc.to_result(self.config.repo)
            except AgentTeamsError as exc:
                return log.partial_result(
                    "route", str(exc),
                    [
                        f'producer_board.py transition {number} --to "In Progress" '
                        f"--acting-role qa",
                        f"producer_board.py handoff {number} --from-role qa "
                        f'--to-role dev --note "{note}"',
                    ],
                )
            return {**base, "status": Status.IN_PROGRESS.value, "role": Role.DEV.value}

        note = "Protected change requires human review: " + "; ".join(result.reasons)
        try:
            self.board.handoff_card(
                number, Role.QA, Role.HUMAN, note,
                needs="review the protected change and decide",
                artifacts=pr["url"],
            )
        except PartialHandoff as exc:
            return exc.to_result(self.config.repo)
        return {**base, "status": Status.IN_REVIEW.value, "role": Role.HUMAN.value}
```

- [ ] **Step 4: Run**

Run: `python -m unittest tests.test_consumer -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/agent_teams/workflows.py tests/test_consumer.py
git commit -m "feat: add Consumer.accept with deterministic routing and auto-merge arming"
```

---

## Task 12: `Consumer.reconcile` — confirm, then clean

**Files:**
- Modify: `scripts/agent_teams/workflows.py`
- Test: `tests/test_consumer.py`

**Interfaces:**
- Consumes: `Board.merge_state`, `Git.remove_worktree`, `worktree_path`.
- Produces: `Consumer.reconcile(number, acting_role) -> dict`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_consumer.py`:

```python
class ReconcileTests(unittest.TestCase):
    def _consumer(self, pr_state, role="qa", git=None):
        from agent_teams.workflows import Consumer
        gh = FakeGh(items=board_with((21, "Delivery", "In Review", role)), pr_state=pr_state)
        return Consumer(a_config(), Board(a_config(), gh=gh), git=git or FakeGit()), gh

    def test_a_merged_pull_request_reconciles_to_done_owned_by_lead(self):
        consumer, gh = self._consumer({"state": "MERGED", "mergedAt": "2026-08-06T00:00:00Z"})
        result = consumer.reconcile(21, Role.LEAD)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "Done")
        self.assertEqual(result["role"], "lead")

    def test_an_unmerged_pull_request_is_refused_and_mutates_nothing(self):
        consumer, gh = self._consumer({"state": "OPEN", "mergedAt": None})
        with self.assertRaises(Exception) as caught:
            consumer.reconcile(21, Role.LEAD)
        self.assertIn("not merged", str(caught.exception).casefold())
        self.assertEqual(gh.calls_matching("project", "item-edit"), [])

    def test_a_closed_but_unmerged_pull_request_is_refused(self):
        consumer, gh = self._consumer({"state": "CLOSED", "mergedAt": None})
        with self.assertRaises(Exception):
            consumer.reconcile(21, Role.LEAD)

    def test_worktree_cleanup_failure_does_not_fail_the_reconciliation(self):
        # The Card reaching Done is the durable outcome; a worktree that
        # refuses to be removed is reported, never silently forced.
        class StubbornGit(FakeGit):
            def remove_worktree(self, path, force=False):
                from agent_teams.git import WorktreeNotClean
                raise WorktreeNotClean("uncommitted changes")

        consumer, gh = self._consumer(
            {"state": "MERGED", "mergedAt": "2026-08-06T00:00:00Z"}, git=StubbornGit()
        )
        result = consumer.reconcile(21, Role.LEAD)
        self.assertTrue(result["ok"])
        self.assertIn("cleanup", result)
        self.assertFalse(result["cleanup"]["ok"])
```

- [ ] **Step 2: Run and watch it fail**

Run: `python -m unittest tests.test_consumer -v`
Expected: FAIL — `Consumer` has no `reconcile`.

- [ ] **Step 3: Implement**

```python
    def reconcile(self, number: int, acting_role: Role) -> dict[str, Any]:
        """Close out a confirmed merge. Never assumes the merge happened."""
        policy.check_action("reconcile_done", acting_role)
        card = self.board.card(number)
        if card.status is not Status.IN_REVIEW:
            raise WorkflowError(
                f"#{number} is {card.routing_state}; reconciliation applies to a "
                f"Card in In Review whose Pull Request has merged"
            )

        pr = self.board.pull_request(number)
        state = self.board.merge_state(pr["number"])
        if str(state.get("state", "")).upper() != "MERGED":
            raise WorkflowError(
                f"Pull Request for #{number} is not merged (state "
                f"{state.get('state') or 'unknown'}). Reconciliation records a "
                f"merge that happened; it never causes one."
            )

        log = MutationLog()
        try:
            self.board.transition_card(number, Status.DONE, acting_role)
            log.record("transition")
            if card.role is not Role.LEAD:
                self.board.handoff_card(
                    number, card.role or Role.QA, Role.LEAD,
                    f"merged as {state.get('merge_commit') or 'confirmed merge'}",
                    artifacts=pr["url"],
                )
                log.record("handoff")
        except PartialHandoff as exc:
            return exc.to_result(self.config.repo)
        except AgentTeamsError as exc:
            return log.partial_result(
                "reconcile", str(exc),
                [f'producer_board.py transition {number} --to Done --acting-role {acting_role}'],
            )

        target = worktree_path(Path(self.config.workspace), number, card.title)
        try:
            cleanup = self.git.remove_worktree(target)
        except AgentTeamsError as exc:
            cleanup = {
                "ok": False,
                "worktree": str(target),
                "error": str(exc),
                "recovery": [
                    f"Inspect {target}, save anything you need, then run: "
                    f"git worktree remove {target} --force"
                ],
            }

        return {
            "ok": True, "issue": number, "url": card.url,
            "status": Status.DONE.value, "role": Role.LEAD.value,
            "merge_commit": state.get("merge_commit"), "cleanup": cleanup,
        }
```

- [ ] **Step 4: Run the whole suite**

Run: `python -m unittest discover -s tests -p "test_*.py"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/agent_teams/workflows.py tests/test_consumer.py
git commit -m "feat: add Consumer.reconcile with confirmed-merge precondition"
```

---

## Task 13: Command-line surface

**Files:**
- Modify: `scripts/producer_board.py`
- Test: `tests/test_producer_board.py`

**Interfaces:**
- Consumes: `Consumer` and every method from Tasks 8-12.
- Produces: subcommands `claim`, `submit-pr`, `verdict`, `accept`, `reconcile-done`, `worktree-status`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_producer_board.py`:

```python
class ConsumerCommandTests(CliTests):
    """Round-trips through main(), asserting the CLI envelope contract.

    Subclasses CliTests to reuse its tmpdir config fixture and _run helper.
    """

    def _run_git(self, *argv, gh=None, git=None):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = producer_board.main(
                ["--config", str(self.config_path), *argv],
                gh=gh or FakeGh(), git=git,
            )
        return code, out.getvalue(), err.getvalue()

    def test_claim_prints_an_ok_envelope_and_exits_zero(self):
        from fake_gh import board_with
        code, out, _ = self._run_git(
            "claim", "12", "--acting-role", "dev",
            gh=FakeGh(items=board_with((12, "Implement parser", "Ready", "dev"))),
            git=FakeGit(),
        )
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(out)["ok"])

    def test_a_lost_race_exits_one_and_never_reports_success(self):
        # The failure a skill is most likely to misread. It must not exit 0,
        # and stderr must not carry an "ok": true envelope.
        from fake_gh import board_with
        code, out, err = self._run_git(
            "claim", "12", "--acting-role", "dev",
            gh=FakeGh(items=board_with((12, "x", "Ready", "dev"))),
            git=FakeGit(race_lost=True),
        )
        self.assertEqual(code, 1)
        payload = json.loads(err or out)
        self.assertFalse(payload["ok"])
        self.assertTrue(payload["race_lost"])
        self.assertNotIn("partial", payload)

    def test_accept_takes_only_an_issue_number(self):
        parser = producer_board._build_parser()
        args = parser.parse_args(["accept", "21"])
        self.assertEqual(args.command, "accept")
        self.assertEqual(args.issue, 21)
        # No flag exists through which a caller could steer the route.
        for forbidden in ("merge", "acceptance", "force", "route"):
            self.assertFalse(hasattr(args, forbidden), forbidden)

    def test_there_is_no_command_that_merges_a_chosen_pull_request(self):
        parser = producer_board._build_parser()
        for attempt in (["merge", "57"], ["merge-pr", "57"], ["request-merge", "57"]):
            with self.assertRaises(SystemExit, msg=str(attempt)):
                parser.parse_args(attempt)

    def test_worktree_status_is_read_only(self):
        from fake_gh import board_with
        gh = FakeGh(items=board_with((23, "Active build", "In Progress", "dev")))
        code, out, _ = self._run_git("worktree-status", gh=gh, git=FakeGit())
        self.assertEqual(code, 0)
        self.assertEqual(gh.calls_matching("project", "item-edit"), [])
        self.assertEqual(gh.calls_matching("issue", "comment"), [])
```

Import `FakeGit` from `tests/test_consumer.py` (or lift it into `fake_gh.py` alongside `FakeGh`; lifting is cleaner, since two test modules now need it — do that and import it from `fake_gh` in both).

- [ ] **Step 2: Run and watch it fail**

Run: `python -m unittest tests.test_producer_board -v`
Expected: FAIL — `invalid choice: 'claim'`

- [ ] **Step 3: Add the parsers**

In `_build_parser`, before `return parser`:

```python
    claim = sub.add_parser(
        "claim", help="reserve one Ready Card and open its isolated worktree"
    )
    claim.add_argument("issue", type=int)
    claim.add_argument("--acting-role", required=True, choices=["dev", "architect"])

    submit = sub.add_parser(
        "submit-pr", help="open or update one Pull Request and hand off to qa"
    )
    submit.add_argument("issue", type=int)
    submit.add_argument("--title", required=True)
    submit.add_argument("--body-file", required=True)
    submit.add_argument("--acting-role", default="dev", choices=["dev", "architect"])

    verdict = sub.add_parser(
        "verdict", help="publish Quality Assurance review evidence for the current head"
    )
    verdict.add_argument("issue", type=int)
    verdict.add_argument("--evidence-file", required=True, help="JSON verdict document")

    accept = sub.add_parser(
        "accept",
        help="evaluate the published verdict and execute the deterministic route",
    )
    accept.add_argument("issue", type=int)

    reconcile = sub.add_parser(
        "reconcile-done", help="record a confirmed merge and clean the claim"
    )
    reconcile.add_argument("issue", type=int)
    reconcile.add_argument("--acting-role", default="lead", choices=ROLES)

    worktrees = sub.add_parser(
        "worktree-status", help="claims, worktrees, and ages (read-only)"
    )
    worktrees.add_argument("issue", type=int, nargs="?")
```

`accept` deliberately takes no other argument. Every input to the decision is read from live GitHub state, so there is nothing for a caller to steer.

- [ ] **Step 4: Add the dispatch branches**

First widen the signature so a fake Git can be injected the same way a fake `gh` already is — the CLI is otherwise untestable for the claim path:

```python
def main(argv: list[str] | None = None, gh: Gh | None = None, git: Any = None) -> int:
```

In `main`, after the `Producer` construction:

```python
        consumer = Consumer(config, board, git=git)

        if args.command == "claim":
            _print(consumer.claim(args.issue, Role.parse(args.acting_role)))

        elif args.command == "submit-pr":
            _print(
                consumer.submit(
                    args.issue, Role.parse(args.acting_role),
                    args.title, _read_body(args),
                )
            )

        elif args.command == "verdict":
            raw = json.loads(Path(args.evidence_file).read_text(encoding="utf-8"))
            _print(consumer.verdict(args.issue, Verdict.from_dict(raw)))

        elif args.command == "accept":
            _print(consumer.accept(args.issue))

        elif args.command == "reconcile-done":
            _print(consumer.reconcile(args.issue, Role.parse(args.acting_role)))

        elif args.command == "worktree-status":
            _print(consumer.worktree_status(args.issue))
```

Add `Consumer` and `Verdict` to the imports and to `__all__`.

Make sure a `claim` returning `{"ok": false, "race_lost": true}` exits **1**, not 0 — a skill must never read a lost race as a win. Find the existing return-code logic and route any envelope with a falsy `ok` to exit 1.

- [ ] **Step 5: Implement `Consumer.worktree_status`**

```python
    def worktree_status(self, number: int | None = None) -> dict[str, Any]:
        """Read-only claim and worktree inventory. Mutates nothing.

        This is the input stale-claim detection has been waiting on: it could
        not exist until claims did.
        """
        cards = [self.board.card(number)] if number else [
            card for card in self.board.cards() if card.status is Status.IN_PROGRESS
        ]
        known = {
            Path(entry["worktree"]).resolve()
            for entry in self.git.worktrees()
            if "worktree" in entry
        }
        entries = []
        for card in cards:
            target = worktree_path(Path(self.config.workspace), card.number, card.title)
            entries.append(
                {
                    "issue": card.number,
                    "title": card.title,
                    "routing_state": card.routing_state,
                    "branch": claim_branch(card.number, card.title),
                    "worktree": str(target),
                    "worktree_present": target.resolve() in known,
                }
            )
        return {"ok": True, "claim_ttl_hours": self.config.claim_ttl_hours, "claims": entries}
```

Add `claim_branch` to the `git` import in `workflows.py`.

- [ ] **Step 6: Run the whole suite**

Run: `python -m unittest discover -s tests -p "test_*.py"`
Expected: PASS.

- [ ] **Step 7: Validate the plugin manifest**

Run: `claude plugin validate .`
Expected: warning-free.

- [ ] **Step 8: Commit**

```bash
git add scripts/producer_board.py tests/test_producer_board.py
git commit -m "feat: add six Consumer commands to the public CLI

accept takes only an issue number: every input to the acceptance decision
is read from live GitHub state, so no caller can steer the route."
```

---

## Task 14: `skills/consuming-card/`

**Files:**
- Create: `skills/consuming-card/SKILL.md`, `skills/consuming-card/references/claim-and-worktree.md`, `skills/consuming-card/references/tdd-discipline.md`, `skills/consuming-card/references/pr-contract.md`

**Interfaces:**
- Consumes: the CLI from Task 13.
- Produces: the Developer and Architect-documentation routines.

Sources to read before writing: `../agent-teams-main/skills/consuming-card/SKILL.md` and its `references/stage-{1,2,3,4}-*.md`; `../agent-teams-main/skills/enforcing-pr-contract/` including `references/filler-detection.md`; and the local superpowers cache at `C:\Users\User\.claude\plugins\cache\claude-plugins-official\superpowers\6.2.0\skills\{test-driven-development,verification-before-completion,using-git-worktrees,finishing-a-development-branch}\SKILL.md`.

- [ ] **Step 1: Write `SKILL.md`**

Frontmatter carries `name: consuming-card` and a trigger-rich `description`: `[board-card:#N]`, "claim card 12", "work on card 47", "implement #N", "let me take #N", plus do-NOT-use disambiguation pointing at `briefing-board`, `intaking-requirement`, `triaging-board`, and `verifying-delivery`.

Body sections, in order:

1. **Bind and preflight.** One Card, one seat. Validate the `[expected:(Status, Role)]` stamp the kickoff carries against live board state; a mismatch is a stale kickoff — say so and stop.
2. **Claim.** `producer_board.py claim N --acting-role dev`. Adopt the race-lost rule verbatim in spirit: a lost race is a clean exit, **never retried**. Do not return to the repository root to work.
3. **Plan.** Bound to this Card's acceptance criteria only.
4. **Implement through test-driven development.** Adopt the Iron Law ("no production code without a failing test first"), Red-Green-Refactor with the mandatory verify-red step, the good-test qualities table, and the rationalizations table. Adopt the two refusal reflexes from board-superpowers B3/B4: do not bypass test-driven development because the change feels obvious, and do not edit files outside this Card's scope.
5. **Verify.** Adopt the Iron Law of verification-before-completion: no completion claim without fresh evidence in this message, plus the gate function and the claim/requires/not-sufficient table.
6. **Submit.** `producer_board.py submit-pr N --title ... --body-file ...`. The five-section contract, the closing trailer, and the no-filler rule for Human Verification.
7. **Blocked.** Record the blocker, `transition --to Blocked`, hand to `architect`, preserve the claim and worktree.
8. **Boundaries.** No merge. No second Card. No self-promotion to Ready. Never report "prompt rendered" as "session started".

Add the derivation header comment naming board-superpowers and superpowers.

- [ ] **Step 2: Write the three reference files**

`claim-and-worktree.md`: the race-lost rule and why it is never retried; resume semantics for an interrupted session; the removal guards; the "a local worktree is not a claim" rule.

`tdd-discipline.md`: the full Red-Green-Refactor detail, the good/bad test examples adapted to Python and `unittest`, and the rationalizations table.

`pr-contract.md`: the five sections with templates, the filler-detection list, and the acceptance-criteria terminal-state rule (`[x]` or `[!]<reason>`; bare `[ ]` refuses).

- [ ] **Step 3: Verify the no-sibling-reference invariant**

Run: `grep -rE "superpowers:|gstack:/" skills/`
Expected: **no output**. Any hit is a runtime dependency and must be rewritten as prose.

- [ ] **Step 4: Check body length**

Run: `wc -l skills/consuming-card/SKILL.md`
Expected: under 300 lines; spillover goes to `references/`.

- [ ] **Step 5: Commit**

```bash
git add skills/consuming-card/
git commit -m "feat: add consuming-card skill for the Developer and Architect routines"
```

---

## Task 15: `skills/verifying-delivery/`

**Files:**
- Create: `skills/verifying-delivery/SKILL.md`, `skills/verifying-delivery/references/review-dimensions.md`, `skills/verifying-delivery/references/evidence-and-challenge.md`, `skills/verifying-delivery/references/verdict-schema.md`

**Interfaces:**
- Consumes: the `verdict` and `accept` commands from Task 13; `REQUIRED_DIMENSIONS` from Task 5.
- Produces: the QA verification routine.

Sources: gstack `/review` and `/qa` (fetch `https://raw.githubusercontent.com/garrytan/gstack/main/review/SKILL.md` and `.../qa/SKILL.md`); `../agent-teams-main/skills/reviewing-pr-queue/`; the superpowers cache `requesting-code-review` and `verification-before-completion`.

- [ ] **Step 1: Write `SKILL.md`**

Frontmatter `name: verifying-delivery`, description triggering on `[role:qa] [board-card:#N]`, "verify #N", "review the delivery", "QA card 21", with do-NOT-use pointing at `inspecting-queue` (which surveys the queue and issues no verdicts).

Body sections:

1. **Bind.** Require `(In Review, qa)` and a linked Pull Request. Record the head SHA now; everything below is bound to it.
2. **Enumerate completely.** Every changed, new, and deleted file. Split large changes into bounded review units. An unenumerated file is an unreviewed file, and `accept` will refuse a pass that omits one.
3. **Review the eight dimensions** — design, architecture, correctness, edge cases, security, compatibility, cross-file, test strength. Each must appear in `review_dimensions` or the pass is invalid.
4. **Ground every finding.** Adopt gstack's pre-emit verification gate: a finding must quote the specific code lines motivating it. Unquoted findings are suppressed, not promoted. Adopt confidence calibration 1-10 — below 7 carries caveats, 3-4 goes to an appendix.
5. **Challenge every material finding.** A separate pass tries to falsify it against callers, related files, existing mitigations, intended behaviour, and contrary evidence. Record the challenge outcome, not just the finding.
6. **Detect blind spots and repeat the affected dimension.** Adopt the conditional red-team pass for diffs over ~200 lines or when a critical finding exists. A blind spot that survives means the verdict is not a pass — `blind_spots` must be empty for a pass, and `accept` enforces it.
7. **Judge test strength, not line coverage.** Require at least one of branch, scenario, mutation, integration, property, or negative evidence. Adopt gstack's plan-completion audit vocabulary — `DONE` / `PARTIAL` / `NOT DONE` / `CHANGED` / `UNVERIFIABLE` — for acceptance-criteria conformance.
8. **Browser evidence for user-interface Cards.** Adopt gstack `/qa`'s rules: repro is everything, every issue carries a screenshot, verify before documenting, never include credentials, check the console after every interaction.
9. **Publish.** `producer_board.py verdict N --evidence-file ...`. Then `producer_board.py accept N`.
10. **Boundaries.** **QA never modifies production code** — that collapses independent verification, and it is why gstack's fix-first triage is deliberately not adopted. QA never merges. QA never selects its own route: the verdict is evidence, the route comes from `accept`.

- [ ] **Step 2: Write the three reference files**

`review-dimensions.md`: what each of the eight dimensions asks, with the specialist-dispatch pattern (bounded passes per dimension, deduplicated, confidence-boosted when two passes agree) and the note that reviewer passes are evidence producers, never nested authorities — the bound QA Consumer owns completeness and synthesis.

`evidence-and-challenge.md`: the pre-emit verification gate, confidence calibration, the falsification checklist, and the blind-spot loop.

`verdict-schema.md`: the JSON document `--evidence-file` expects, field by field, with one complete worked example that would pass `validate_verdict` and one that would be refused, annotated with which rule refuses it.

- [ ] **Step 3: Verify the invariant again**

Run: `grep -rE "superpowers:|gstack:/" skills/`
Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add skills/verifying-delivery/
git commit -m "feat: add verifying-delivery skill for evidence-grounded QA review

Adopts gstack's pre-emit verification gate and confidence calibration;
deliberately rejects its fix-first triage, which would have QA editing the
production code it is meant to independently verify."
```

---

## Task 16: Router, attribution, and migration records

**Files:**
- Modify: `skills/using-agent-teams/SKILL.md`, `ATTRIBUTION.md`, `docs/skill_migration.md`, `docs/skill_migration_audit.md`

- [ ] **Step 1: Add the Consumer routes to the router**

Add rows mapping intent to the two new skills: "work on #N" / "implement this card" / `[board-card:#N]` -> `consuming-card`; "verify #N" / "review the delivery" -> `verifying-delivery`. Keep the existing non-signals list and extend it: a quoted kickoff prompt is still not a routing request.

Re-state, unchanged: **the router may never infer `human`.**

- [ ] **Step 2: Update `ATTRIBUTION.md`**

Replace the two `(planned)` cells with the real derivation targets. Add gstack's confirmed MIT license. Keep the closing paragraph's grep claim, which Tasks 14 and 15 verified.

- [ ] **Step 3: Add migration sections 8 and 9 to `docs/skill_migration.md`**

Follow the existing per-migration format exactly: **Adopted**, **Rewired**, **Rejected**, **Kept from ours**. The headline rejection is gstack's fix-first triage, with the reason.

- [ ] **Step 4: Add per-item audit rows to `docs/skill_migration_audit.md`**

Every section of each source gets a disposition: verbatim / adapted / restored / rejected, with where and why. This is the file that proves nothing was dropped silently.

- [ ] **Step 5: Commit**

```bash
git add skills/using-agent-teams/SKILL.md ATTRIBUTION.md docs/skill_migration.md docs/skill_migration_audit.md
git commit -m "docs: route the Consumer skills and record the superpowers/gstack derivations"
```

---

## Task 17: Documentation reconciliation

**Files:**
- Modify: `docs/ARCHITECTURE.md`, `docs/IMPLEMENTATION_PLAN.md`, `docs/USAGE.md`, `README.md`, `CLAUDE_TESTING.md`

- [ ] **Step 1: Update `ARCHITECTURE.md`**

§10.1: move "Consumer workflow skills", "Git claim and worktree service", and "Pull Request contract service" from **designed** to **built**. §9.8: move `claim_card`, `link_pull_request_to_card`, `record_verdict`, `evaluate_acceptance`, `request_automated_merge`, and `reconcile_done` from "designed" to "built". §11.7: strike the note that stale-claim detection cannot exist until claims do — `worktree-status` now supplies it.

Add a sentence to §9.7 recording the unique-claim-commit rule and why: a bare-SHA push to an existing ref is a no-op success and produces two winners.

Appendix A.3: decision 8 is now implemented, with the clarification that `merge_pull_request` remains a hard floor and the controller reaches merge through eligibility rather than through a seat action.

- [ ] **Step 2: Update `IMPLEMENTATION_PLAN.md`**

It is the sole status ledger. Mark the M4 and M5 work items delivered, and keep every live-GitHub item **pending** — nothing in this plan proves live behaviour.

- [ ] **Step 3: Update `USAGE.md` and `README.md`**

`USAGE.md`: extend the daily loop with claim, submit, verify, accept, reconcile, and add a troubleshooting entry for a lost claim race and one for `protected_change`. `README.md`: the six commands and the five configuration keys, including the warning that empty `required_checks` never yields `eligible`.

- [ ] **Step 4: Correct `CLAUDE_TESTING.md`**

It still describes four skills. Update it to nine and add the Consumer test procedure.

- [ ] **Step 5: Full verification**

```bash
python -m unittest discover -s tests -p "test_*.py"
claude plugin validate .
grep -rE "superpowers:|gstack:/" skills/
git diff --check
```

Expected: all tests pass; validation warning-free; the grep returns nothing; no whitespace errors.

Report the actual test count. Do not claim a number you have not seen printed.

- [ ] **Step 6: Commit**

```bash
git add docs/ README.md CLAUDE_TESTING.md
git commit -m "docs: reconcile architecture, ledger, usage, and testing with the Consumer flow"
```

---

## Verification Checklist

- [ ] Two clones racing one Card produce exactly one winner (`tests/test_git.py`)
- [ ] The loser writes nothing to the board and is never retried
- [ ] A claim resumes from durable state rather than recreating
- [ ] No worktree with uncommitted or untracked work can be removed
- [ ] Every default protected category is reachable by some path
- [ ] Emptying a default protected category fails configuration validation
- [ ] Every acceptance decision-table row is asserted individually
- [ ] Empty `required_checks` never yields `eligible`
- [ ] A stale verdict refuses and mutates nothing
- [ ] A pass with a blind spot, a missing dimension, an unenumerated file, or line-coverage-only evidence refuses
- [ ] `merge_pull_request` is still in `HARD_FLOORS` and refuses every agent seat
- [ ] No seat may take `request_automated_merge`
- [ ] `accept` takes only an issue number
- [ ] A verdict changes neither Status nor Role
- [ ] Reconciliation refuses unless the Pull Request is actually merged
- [ ] `grep -rE "superpowers:|gstack:/" skills/` returns nothing
- [ ] `claude plugin validate .` is warning-free
