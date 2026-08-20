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
    slugify, specification_branch, worktree_path,
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

    def test_specification_branch_is_derived_from_card_identity(self):
        self.assertEqual(
            specification_branch(42, "Implement parser"),
            "spec/42-implement-parser",
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

    def test_a_durable_claim_can_be_resolved_for_session_resume(self):
        repository = self._clone("a")
        result = repository.claim(42, "Implement parser", "dev", "session-a")
        self.assertEqual(repository.remote_branch_sha(result["branch"]),
                         result["claim_sha"])

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

    def test_workspace_change_resumes_the_worktree_for_the_claim_branch(self):
        git, target = self._claimed()
        new_target = self.tmp / "new-workspace" / "claim-42"
        again = git.add_worktree(
            new_target, "claim/42-implement-parser", "unused"
        )
        self.assertTrue(again["resumed"])
        self.assertEqual(Path(again["worktree"]).resolve(), target.resolve())
        self.assertEqual(
            git.worktree_for_branch("claim/42-implement-parser"), target.resolve()
        )
        self.assertFalse(new_target.exists())

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


class PublishDeliveryTests(_OriginFixture, unittest.TestCase):
    """The delivery the reviewer sees is the remote branch, nothing else.

    Proven against real git because the failure that motivates this method
    was invisible to every fake: a session that commits in its worktree and
    opens a Pull Request without pushing believes, honestly, that it shipped
    (live: card #14 / PR #17, a 450-line implementation reviewed as an
    empty diff).
    """

    BRANCH = "claim/42-implement-parser"

    def _claimed(self, name="a"):
        git = self._clone(name)
        claim = git.claim(42, "Implement parser", "dev", f"session-{name}")
        target = self.tmp / "wt" / "claim-42"
        git.add_worktree(target, claim["branch"], claim["claim_sha"])
        return git, target

    def _remote_head(self):
        return _git(self.tmp, "--git-dir", str(self.origin),
                    "rev-parse", f"refs/heads/{self.BRANCH}")

    def test_publish_pushes_the_worktree_commits(self):
        git, target = self._claimed()
        (target / "impl.py").write_text("work\n", encoding="utf-8")
        _git(target, "add", ".")
        _git(target, "commit", "-qm", "implement")
        result = git.publish_delivery(target, self.BRANCH)
        self.assertTrue(result["pushed"])
        self.assertEqual(self._remote_head(), result["head_sha"])

    def test_a_dirty_worktree_is_refused_and_the_remote_is_untouched(self):
        # Auto-committing would decide what belongs in the delivery on the
        # Consumer's behalf; pushing around it would silently leave it out.
        git, target = self._claimed()
        before = self._remote_head()
        (target / "impl.py").write_text("uncommitted\n", encoding="utf-8")
        with self.assertRaises(GitError):
            git.publish_delivery(target, self.BRANCH)
        self.assertEqual(self._remote_head(), before)

    def test_publishing_with_nothing_new_succeeds_as_a_noop(self):
        # Only the claim commit exists: the push is up-to-date and fine at
        # the git layer. Catching the empty *diff* is submit's job, from
        # GitHub's own view of the Pull Request.
        git, target = self._claimed()
        result = git.publish_delivery(target, self.BRANCH)
        self.assertTrue(result["pushed"])
        self.assertEqual(self._remote_head(), result["head_sha"])

    def test_a_path_that_is_not_a_worktree_reports_not_pushed(self):
        # The branch may have been pushed from another machine; the absence
        # of a local worktree is not an error, and the empty-diff guard in
        # submit still stands between that and a hollow delivery.
        git, _ = self._claimed()
        result = git.publish_delivery(self.tmp / "elsewhere", self.BRANCH)
        self.assertTrue(result["ok"])
        self.assertFalse(result["pushed"])


class PublishSpecificationTests(_OriginFixture, unittest.TestCase):
    """Specifications land on the existing branch with no spec PR/branch."""

    def test_publishes_only_the_spec_on_the_current_branch(self):
        git = self._clone("spec")
        path = git.root / "docs" / "specs" / "card-42.md"
        path.parent.mkdir(parents=True)
        path.write_text("# Card 42\n", encoding="utf-8")
        before_refs = _git(
            self.tmp, "--git-dir", str(self.origin), "for-each-ref",
            "--format=%(refname)", "refs/heads",
        ).splitlines()

        result = git.publish_specification(
            42, "Implement parser", "docs/specs/card-42.md"
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["branch"], "main")
        after_refs = _git(
            self.tmp, "--git-dir", str(self.origin), "for-each-ref",
            "--format=%(refname)", "refs/heads",
        ).splitlines()
        self.assertEqual(after_refs, before_refs)
        published = _git(
            self.tmp, "--git-dir", str(self.origin), "show",
            "main:docs/specs/card-42.md",
        )
        self.assertEqual(published, "# Card 42")

    def test_manual_review_branch_leaves_base_untouched_and_checkout_clean(self):
        git = self._clone("manual-spec")
        path = git.root / "docs" / "specs" / "card-42.md"
        path.parent.mkdir(parents=True)
        path.write_text("# Card 42\n", encoding="utf-8")
        base_before = git.head_sha()

        result = git.publish_specification_for_review(
            42, "Implement parser", "docs/specs/card-42.md"
        )

        self.assertEqual(git.head_sha(), base_before)
        self.assertEqual(_git(git.root, "branch", "--show-current"), "main")
        self.assertEqual(_git(git.root, "status", "--porcelain"), "")
        self.assertFalse(path.exists())
        self.assertEqual(
            _git(
                self.tmp, "--git-dir", str(self.origin), "show",
                f"{result['branch']}:docs/specs/card-42.md",
            ),
            "# Card 42",
        )
        base_paths = _git(
            self.tmp, "--git-dir", str(self.origin),
            "ls-tree", "-r", "--name-only", "main",
        ).splitlines()
        self.assertNotIn("docs/specs/card-42.md", base_paths)

    def test_confirmed_manual_merge_syncs_the_spec_to_local_base(self):
        git = self._clone("manual-sync")
        path = git.root / "docs" / "specs" / "card-42.md"
        path.parent.mkdir(parents=True)
        path.write_text("# Card 42\n", encoding="utf-8")
        review = git.publish_specification_for_review(
            42, "Implement parser", "docs/specs/card-42.md"
        )
        _git(
            self.tmp, "--git-dir", str(self.origin), "update-ref",
            "refs/heads/main", review["commit"],
        )

        result = git.sync_merged_specification(
            "docs/specs/card-42.md", "main"
        )

        self.assertTrue(result["synced"])
        self.assertEqual(result["commit"], review["commit"])
        self.assertEqual(path.read_text(encoding="utf-8"), "# Card 42\n")

    def test_unrelated_dirty_file_refuses_before_commit(self):
        git = self._clone("dirty-spec")
        spec = git.root / "docs" / "specs" / "card-42.md"
        spec.parent.mkdir(parents=True)
        spec.write_text("# Card 42\n", encoding="utf-8")
        (git.root / "f.txt").write_text("unrelated\n", encoding="utf-8")
        before = git.head_sha()
        with self.assertRaisesRegex(GitError, "unrelated checkout changes"):
            git.publish_specification(42, "Parser", "docs/specs/card-42.md")
        self.assertEqual(git.head_sha(), before)

    def test_path_outside_docs_is_refused(self):
        git = self._clone("bad-spec")
        with self.assertRaisesRegex(GitError, "below docs"):
            git.publish_specification(42, "Parser", "src/spec.md")

    def test_unchanged_republish_records_the_files_last_commit_not_head(self):
        git = self._clone("republish-spec")
        spec = git.root / "docs" / "specs" / "card-42.md"
        spec.parent.mkdir(parents=True)
        spec.write_text("# Card 42\n", encoding="utf-8")
        first = git.publish_specification(42, "Parser", "docs/specs/card-42.md")

        tracked = git.root / "f.txt"
        tracked.write_text("later change\n", encoding="utf-8")
        _git(git.root, "add", "f.txt")
        _git(git.root, "commit", "-m", "later unrelated commit")

        second = git.publish_specification(42, "Parser", "docs/specs/card-42.md")
        self.assertFalse(second["committed"])
        self.assertEqual(second["commit"], first["commit"])
        self.assertNotEqual(second["commit"], git.head_sha())

    def test_rename_into_spec_path_is_refused_as_unrelated_scope(self):
        git = self._clone("renamed-spec")
        target = git.root / "docs" / "specs" / "card-42.md"
        target.parent.mkdir(parents=True)
        _git(git.root, "mv", "f.txt", "docs/specs/card-42.md")
        with self.assertRaisesRegex(GitError, "unrelated checkout changes"):
            git.publish_specification(42, "Parser", "docs/specs/card-42.md")
