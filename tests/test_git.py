"""Tests for the Git adapter, including the claim compare-and-swap.

The race tests use a real local bare repository as origin. Nothing here
touches the network, but the exclusivity claim must be proven against real
git ref semantics -- a fake would have agreed with the wrong implementation,
and the wrong implementation is the obvious one (see ClaimRaceTests).
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
    CLAIM_MARKER, ClaimRaceLost, Git, GitError, WorktreeNotClean, claim_branch,
    slugify, worktree_path,
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

    def test_a_title_with_no_usable_characters_still_yields_a_slug(self):
        self.assertEqual(slugify("!!!"), "card")

    def test_claim_branch_is_derived_from_card_identity(self):
        self.assertEqual(
            claim_branch(42, "Implement parser"), "claim/42-implement-parser"
        )


class _OriginFixture:
    """A local bare repository as origin, plus clones on a common base.

    A mixin rather than a base TestCase: subclassing a populated TestCase
    would re-run every inherited race test in each subclass, and these are
    the slowest tests in the suite because they drive real git.
    """

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

    def _remote_message(self, branch="claim/42-implement-parser"):
        return _git(
            self.tmp, "--git-dir", str(self.origin), "log", "-1",
            "--format=%B", f"refs/heads/{branch}",
        )


class ClaimRaceTests(_OriginFixture, unittest.TestCase):
    """Exclusivity proven against real git ref semantics."""

    def test_first_claimant_wins(self):
        result = self._clone("a").claim(42, "Implement parser", "dev", "session-a")
        self.assertTrue(result["ok"])
        self.assertEqual(result["branch"], "claim/42-implement-parser")

    def test_second_claimant_from_the_same_base_loses(self):
        # The regression that motivates the unique claim commit. Both clones
        # sit on the identical base SHA; pushing that bare SHA would report
        # "Everything up-to-date" and exit 0 for BOTH claimants.
        self._clone("a").claim(42, "Implement parser", "dev", "session-a")
        with self.assertRaises(ClaimRaceLost):
            self._clone("b").claim(42, "Implement parser", "dev", "session-b")

    def test_race_loss_leaves_the_remote_ref_owned_by_the_winner(self):
        self._clone("a").claim(42, "Implement parser", "dev", "session-a")
        with self.assertRaises(ClaimRaceLost):
            self._clone("b").claim(42, "Implement parser", "dev", "session-b")
        body = self._remote_message()
        self.assertIn("session-a", body)
        self.assertNotIn("session-b", body)

    def test_the_claim_commit_is_never_the_base_commit(self):
        # If these were equal the push would be a no-op success and the lease
        # would never be evaluated.
        result = self._clone("a").claim(42, "Implement parser", "dev", "session-a")
        self.assertNotEqual(result["claim_sha"], result["base_sha"])

    def test_two_claims_in_the_same_second_produce_distinct_commits(self):
        # Without the session nonce these would be identical commit objects.
        a = self._clone("a").claim(42, "Implement parser", "dev", "session-a")
        _git(self.tmp, "--git-dir", str(self.origin), "update-ref", "-d",
             "refs/heads/claim/42-implement-parser")
        b = self._clone("b").claim(42, "Implement parser", "dev", "session-b")
        self.assertNotEqual(a["claim_sha"], b["claim_sha"])

    def test_claim_records_the_marker_and_seat(self):
        self._clone("a").claim(42, "Implement parser", "dev", "session-a")
        body = self._remote_message()
        self.assertIn(CLAIM_MARKER, body)
        self.assertIn("seat: dev", body)
        self.assertIn("card: 42", body)

    def test_claiming_does_not_move_the_callers_branch(self):
        # commit-tree plumbing: the caller's checkout must be untouched, so a
        # resumed session never finds a mystery commit on its working branch.
        git = self._clone("a")
        before = git.head_sha()
        git.claim(42, "Implement parser", "dev", "session-a")
        self.assertEqual(git.head_sha(), before)

    def test_a_generic_git_failure_is_not_reported_as_a_lost_race(self):
        # Misreading a broken remote as "someone else owns this" would send a
        # Consumer away from work nobody holds.
        git = self._clone("a")
        _git(git.root, "remote", "set-url", "origin", str(self.tmp / "nonexistent.git"))
        with self.assertRaises(GitError):
            git.claim(42, "Implement parser", "dev", "session-a")


class WorktreeTests(_OriginFixture, unittest.TestCase):
    """One Consumer, one worktree -- and never a destructive removal."""

    def _claimed(self, name="a"):
        git = self._clone(name)
        claim = git.claim(42, "Implement parser", "dev", f"session-{name}")
        target = self.tmp / "wt" / "claim-42"
        git.add_worktree(target, claim["branch"], claim["claim_sha"])
        return git, target

    def test_worktree_path_is_derived_from_card_identity(self):
        path = worktree_path(Path("/w"), 42, "Implement parser")
        self.assertEqual(path.name, "claim-42-implement-parser")

    def test_add_worktree_checks_out_the_claim_commit(self):
        _, target = self._claimed()
        self.assertTrue((target / "f.txt").is_file())

    def test_adding_an_existing_worktree_resumes_instead_of_failing(self):
        # An interrupted Consumer must resume the same assignment, not have
        # its work discarded and recreated.
        git, target = self._claimed()
        again = git.add_worktree(target, "claim/42-implement-parser", "unused")
        self.assertTrue(again["ok"])
        self.assertTrue(again["resumed"])

    def test_remove_refuses_a_worktree_with_uncommitted_changes(self):
        git, target = self._claimed()
        (target / "f.txt").write_text("edited\n", encoding="utf-8")
        with self.assertRaises(WorktreeNotClean):
            git.remove_worktree(target)
        self.assertTrue(target.is_dir())

    def test_remove_refuses_a_worktree_with_untracked_files(self):
        git, target = self._claimed()
        (target / "scratch.txt").write_text("notes\n", encoding="utf-8")
        with self.assertRaises(WorktreeNotClean):
            git.remove_worktree(target)
        self.assertTrue(target.is_dir())

    def test_remove_succeeds_on_a_clean_worktree(self):
        git, target = self._claimed()
        self.assertTrue(git.remove_worktree(target)["ok"])
        self.assertFalse(target.is_dir())

    def test_force_removes_a_dirty_worktree_when_explicitly_asked(self):
        git, target = self._claimed()
        (target / "scratch.txt").write_text("notes\n", encoding="utf-8")
        self.assertTrue(git.remove_worktree(target, force=True)["ok"])

    def test_remove_refuses_a_path_that_is_not_a_worktree(self):
        # ARCHITECTURE.md 9.7 rule 6: never delete an unresolved path. A wrong
        # argument must not recursively delete an unrelated directory.
        git = self._clone("a")
        stray = self.tmp / "not-a-worktree"
        stray.mkdir()
        (stray / "important.txt").write_text("do not delete\n", encoding="utf-8")
        with self.assertRaises(GitError):
            git.remove_worktree(stray)
        self.assertTrue((stray / "important.txt").is_file())

    def test_force_does_not_bypass_the_unknown_path_guard(self):
        # force waives the clean check, never the "is this even ours" check.
        git = self._clone("a")
        stray = self.tmp / "not-a-worktree-2"
        stray.mkdir()
        (stray / "important.txt").write_text("do not delete\n", encoding="utf-8")
        with self.assertRaises(GitError):
            git.remove_worktree(stray, force=True)
        self.assertTrue((stray / "important.txt").is_file())

    def test_worktrees_lists_the_created_checkout(self):
        git, target = self._claimed()
        paths = {Path(e["worktree"]).resolve() for e in git.worktrees() if "worktree" in e}
        self.assertIn(target.resolve(), paths)
