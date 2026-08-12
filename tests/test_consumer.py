"""Consumer transactions against the injected fake GitHub CLI.

Everything here is hermetic. What it cannot prove is that the assumed `gh`
JSON shapes match a real GitHub CLI -- that remains the largest assurance
gap, and it is recorded as such rather than papered over.
"""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).parent))

from agent_teams.board import Board  # noqa: E402
from agent_teams.config import Config  # noqa: E402
from agent_teams.model import (  # noqa: E402
    ACCEPTANCE_MARKER, Acceptance, REQUIRED_DIMENSIONS, Role, VERDICT_MARKER,
    Verdict,
)
from fake_gh import REPO, FakeGh, FakeGit, board_with  # noqa: E402


def a_config(**overrides):
    raw = {
        "repo": REPO, "project_owner": "acme", "project_number": 1,
        "required_checks": ["build", "test"],
    }
    raw.update(overrides)
    return Config.from_dict(raw)


def a_verdict(**overrides):
    base = dict(
        verdict="pass", card=21, head_sha="a" * 40,
        pull_request=f"https://github.com/{REPO}/pull/57",
        review_dimensions=tuple(REQUIRED_DIMENSIONS),
        changed_files=("src/parser.py", "tests/test_parser.py"),
        test_strength=(
            {"dimension": "branch", "evidence": "14/14 in parser.py",
             "falsified_by": "reverted the guard at parser.py:41 -> "
                             "test_rejects_empty failed"},
        ),
        checks=("python -m unittest discover: 235 passed",),
        next_role=Role.QA,
    )
    base.update(overrides)
    return Verdict(**base)


def verdict_comment(**overrides):
    payload = a_verdict(**overrides).to_dict()
    return VERDICT_MARKER + "\n\n```json\n" + json.dumps(payload) + "\n```"


def acceptance_comment(acceptance="protected_change", head_sha="a" * 40):
    payload = {
        "acceptance": acceptance, "head_sha": head_sha,
        "policy_version": "test", "reasons": ["protected file"],
    }
    return ACCEPTANCE_MARKER + "\n\n```json\n" + json.dumps(payload) + "\n```"


def status_written(gh):
    """The option id of the last Status write, for asserting transitions."""
    edits = gh.calls_matching("project", "item-edit")
    return edits[-1][edits[-1].index("--single-select-option-id") + 1]


class ClaimTests(unittest.TestCase):
    def _consumer(self, items, git=None, config=None, **gh_kwargs):
        from agent_teams.workflows import Consumer
        config = config or a_config()
        gh = FakeGh(items=items, **gh_kwargs)
        return Consumer(config, Board(config, gh=gh), git=git or FakeGit()), gh

    def test_claiming_a_ready_dev_card_succeeds(self):
        consumer, _ = self._consumer(board_with((12, "Implement parser", "Ready", "dev")))
        result = consumer.claim(12, Role.DEV)
        self.assertTrue(result["ok"])
        self.assertEqual(result["branch"], "claim/12-x")
        self.assertIn("worktree", result)

    def test_claim_transitions_to_in_progress_and_leaves_role_alone(self):
        # Status and Role are orthogonal: a claim is a transition, nothing more.
        consumer, gh = self._consumer(board_with((12, "Implement parser", "Ready", "dev")))
        result = consumer.claim(12, Role.DEV)
        self.assertEqual(status_written(gh), "STATUS_IN_PROGRESS")
        self.assertEqual(len(gh.calls_matching("project", "item-edit")), 1)
        self.assertEqual(result["role"], "dev")

    def test_an_architect_may_claim_a_documentation_card(self):
        consumer, _ = self._consumer(board_with((8, "Specify parser", "Ready", "architect")))
        self.assertTrue(consumer.claim(8, Role.ARCHITECT)["ok"])

    def test_an_interrupted_in_progress_card_resumes_its_durable_claim(self):
        git = FakeGit(remote_sha="f" * 40)
        consumer, gh = self._consumer(
            board_with((12, "Implement parser", "In Progress", "dev")),
            git=git,
        )
        result = consumer.resume(12, Role.DEV)
        self.assertTrue(result["ok"])
        self.assertEqual(result["claim_sha"], "f" * 40)
        self.assertIn(("remote_branch_sha", "claim/12-implement-parser"), git.calls)
        self.assertEqual(gh.calls_matching("project", "item-edit"), [])

    def test_a_card_in_the_wrong_status_is_refused_before_any_git_call(self):
        git = FakeGit()
        consumer, gh = self._consumer(board_with((12, "x", "Backlog", "dev")), git=git)
        with self.assertRaises(Exception):
            consumer.claim(12, Role.DEV)
        self.assertEqual(git.calls, [])
        self.assertEqual(gh.calls_matching("project", "item-edit"), [])

    def test_a_card_owned_by_another_seat_is_refused_before_any_git_call(self):
        git = FakeGit()
        consumer, _ = self._consumer(board_with((12, "x", "Ready", "qa")), git=git)
        with self.assertRaises(Exception):
            consumer.claim(12, Role.DEV)
        self.assertEqual(git.calls, [])

    def test_a_seat_that_may_not_claim_is_refused_before_any_git_call(self):
        git = FakeGit()
        consumer, _ = self._consumer(board_with((12, "x", "Ready", "lead")), git=git)
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
        self.assertEqual(gh.calls_matching("project", "item-edit"), [])

    def test_a_lost_race_is_not_a_partial_failure(self):
        # Nothing was written, so there is nothing to recover. Reporting it as
        # partial would send the next session looking for state that is absent.
        consumer, _ = self._consumer(
            board_with((12, "x", "Ready", "dev")), git=FakeGit(race_lost=True)
        )
        result = consumer.claim(12, Role.DEV)
        self.assertNotIn("partial", result)
        self.assertNotIn("completed", result)

    def test_a_lost_race_says_not_to_retry(self):
        consumer, _ = self._consumer(
            board_with((12, "x", "Ready", "dev")), git=FakeGit(race_lost=True)
        )
        self.assertTrue(
            any("not retry" in line.casefold()
                for line in consumer.claim(12, Role.DEV)["next"])
        )

    def test_a_failed_worktree_reports_the_claim_as_completed(self):
        from agent_teams.git import GitError
        consumer, _ = self._consumer(
            board_with((12, "x", "Ready", "dev")),
            git=FakeGit(worktree_error=GitError("disk full")),
        )
        result = consumer.claim(12, Role.DEV)
        self.assertTrue(result["partial"])
        self.assertIn("claim", result["completed"])
        self.assertTrue(result["recovery"])

    def test_a_failed_transition_reports_the_claim_and_worktree_as_completed(self):
        consumer, _ = self._consumer(
            board_with((12, "x", "Ready", "dev")),
            fail_on={"project item-edit": "boom"},
        )
        result = consumer.claim(12, Role.DEV)
        self.assertFalse(result["ok"])
        self.assertTrue(result["partial"])
        self.assertIn("claim", result["completed"])
        self.assertIn("worktree", result["completed"])
        self.assertTrue(any("transition" in step for step in result["recovery"]))


GOOD_PR_BODY = """## Summary
Adds the CSV parser.

## Test Plan
Unit tests for the header cases, including an empty header.

## Automated Verification
`python -m unittest discover -s tests`: 253 passed, 0 failures.

## Human Verification TODO
- Confirm the exported CSV opens correctly in Excel, which we cannot automate.

## Retro Notes
Empty headers were the case the spec did not name.

Closes #23.

<!-- agent-teams:pr -->
"""


class PullRequestContractTests(unittest.TestCase):
    def _problems(self, body):
        from agent_teams.workflows import validate_pr_body
        return validate_pr_body(body)

    def test_a_complete_body_has_no_problems(self):
        self.assertEqual(self._problems(GOOD_PR_BODY), [])

    def test_a_missing_section_is_named(self):
        body = GOOD_PR_BODY.replace("## Automated Verification", "## Notes")
        self.assertTrue(
            any("Automated Verification" in p for p in self._problems(body))
        )

    def test_an_empty_automated_verification_section_is_refused(self):
        body = GOOD_PR_BODY.replace(
            "`python -m unittest discover -s tests`: 253 passed, 0 failures.", ""
        )
        self.assertTrue(any("empty" in p for p in self._problems(body)))

    def test_a_missing_closing_trailer_is_refused(self):
        body = GOOD_PR_BODY.replace("Closes #23.", "")
        self.assertTrue(any("Closes" in p for p in self._problems(body)))

    def test_every_github_auto_close_keyword_is_accepted(self):
        # GitHub closes the Issue on Closes/Fixes/Resolves, case-insensitively.
        # Accepting only "Closes" would refuse a body GitHub handles correctly.
        for keyword in ("Closes", "Fixes", "Resolves", "closes", "FIXES"):
            body = GOOD_PR_BODY.replace("Closes #23.", f"{keyword} #23.")
            self.assertEqual(self._problems(body), [], keyword)

    def test_a_keyword_without_an_issue_number_is_not_a_trailer(self):
        body = GOOD_PR_BODY.replace("Closes #23.", "Closes the parser gap.")
        self.assertTrue(any("Closes" in p for p in self._problems(body)))

    def test_a_missing_marker_is_refused(self):
        body = GOOD_PR_BODY.replace("<!-- agent-teams:pr -->", "")
        self.assertTrue(any("marker" in p for p in self._problems(body)))

    def test_filler_human_verification_is_refused(self):
        body = GOOD_PR_BODY.replace(
            "- Confirm the exported CSV opens correctly in Excel, which we "
            "cannot automate.",
            "- Check that it works",
        )
        self.assertTrue(any("filler" in p for p in self._problems(body)))

    def test_every_problem_is_reported_together(self):
        self.assertGreaterEqual(len(self._problems("## Summary\nonly this")), 4)


class AcceptanceCriteriaTests(unittest.TestCase):
    def _problems(self, body):
        from agent_teams.workflows import acceptance_criteria_problems
        return acceptance_criteria_problems(body)

    def test_all_ticked_criteria_pass(self):
        self.assertEqual(self._problems("- [x] parses headers\n- [x] rejects empty\n"), [])

    def test_a_bare_open_criterion_is_refused(self):
        problems = self._problems("- [x] parses headers\n- [ ] handles empty\n")
        self.assertTrue(any("handles empty" in p for p in problems))

    def test_a_waived_criterion_with_a_reason_passes(self):
        self.assertEqual(self._problems("- [x] a\n- [!] b -- deferred, see #99\n"), [])

    def test_a_bare_waiver_without_a_reason_is_refused(self):
        self.assertTrue(self._problems("- [!] b\n"))

    def test_prose_that_merely_mentions_brackets_is_not_a_criterion(self):
        self.assertEqual(self._problems("The array is written as [ ] in the spec.\n"), [])

    def test_an_empty_body_has_no_criteria_and_no_problems(self):
        self.assertEqual(self._problems(""), [])


class SubmitTests(unittest.TestCase):
    def _consumer(self, items, config=None, git=None, **gh_kwargs):
        from agent_teams.workflows import Consumer
        config = config or a_config()
        gh = FakeGh(items=items, **gh_kwargs)
        return Consumer(config, Board(config, gh=gh), git=git or FakeGit()), gh

    def test_submit_opens_one_pull_request_then_transitions_and_hands_off(self):
        consumer, gh = self._consumer(
            board_with((23, "Active build", "In Progress", "dev"))
        )
        result = consumer.submit(23, Role.DEV, "feat: parser", GOOD_PR_BODY)
        self.assertTrue(result["ok"])
        self.assertEqual(len(gh.calls_matching("pr", "create")), 1)
        self.assertEqual(result["status"], "In Review")
        self.assertEqual(result["role"], "qa")

    def test_resubmitting_updates_the_existing_pull_request(self):
        # One Card, one Consumer, one delivery. A resumed session must not
        # open a second Pull Request for the same claim branch.
        consumer, gh = self._consumer(
            board_with((23, "Active build", "In Progress", "dev")),
            open_prs=[{"number": 57, "url": f"https://github.com/{REPO}/pull/57"}],
        )
        result = consumer.submit(23, Role.DEV, "feat: parser", GOOD_PR_BODY)
        self.assertTrue(result["ok"])
        self.assertEqual(gh.calls_matching("pr", "create"), [])
        self.assertEqual(len(gh.calls_matching("pr", "edit")), 1)

    def test_an_invalid_body_is_refused_before_any_github_mutation(self):
        consumer, gh = self._consumer(board_with((23, "x", "In Progress", "dev")))
        with self.assertRaises(Exception):
            consumer.submit(23, Role.DEV, "feat: parser", "## Summary\nonly this")
        self.assertEqual(gh.calls_matching("pr", "create"), [])
        self.assertEqual(gh.calls_matching("project", "item-edit"), [])

    def test_a_card_not_in_progress_is_refused(self):
        consumer, gh = self._consumer(board_with((23, "x", "Ready", "dev")))
        with self.assertRaises(Exception):
            consumer.submit(23, Role.DEV, "feat: parser", GOOD_PR_BODY)
        self.assertEqual(gh.calls_matching("pr", "create"), [])

    def test_a_failed_handoff_reports_the_pull_request_as_completed(self):
        consumer, _ = self._consumer(
            board_with((23, "x", "In Progress", "dev")),
            fail_on={"issue comment": "boom"},
        )
        result = consumer.submit(23, Role.DEV, "feat: parser", GOOD_PR_BODY)
        self.assertFalse(result["ok"])
        self.assertTrue(result["partial"])

    def test_submit_publishes_the_worktree_to_the_claim_branch(self):
        # The Pull Request is built from the remote branch; a delivery that
        # was committed locally but never pushed reads as an empty diff to
        # every reviewer (observed live on card #14 / PR #17).
        git = FakeGit()
        consumer, gh = self._consumer(
            board_with((23, "Active build", "In Progress", "dev")), git=git
        )
        result = consumer.submit(23, Role.DEV, "feat: parser", GOOD_PR_BODY)
        self.assertTrue(result["ok"])
        self.assertIn(("publish", str(consumer._worktree_for(
            consumer.board.card(23))), "claim/23-active-build"), git.calls)

    def test_a_dirty_worktree_is_refused_before_any_github_mutation(self):
        from agent_teams.git import GitError
        git = FakeGit(publish_error=GitError("uncommitted changes"))
        consumer, gh = self._consumer(
            board_with((23, "Active build", "In Progress", "dev")), git=git
        )
        with self.assertRaises(GitError):
            consumer.submit(23, Role.DEV, "feat: parser", GOOD_PR_BODY)
        self.assertEqual(gh.calls_matching("pr", "create"), [])
        self.assertEqual(gh.calls_matching("project", "item-edit"), [])

    def test_an_empty_delivery_is_refused_before_any_transition(self):
        # Base and head identical on the remote: the Pull Request exists but
        # delivers nothing. QA reviews deliveries, not empty diffs.
        consumer, gh = self._consumer(
            board_with((23, "Active build", "In Progress", "dev")),
        )
        gh.pr_view = {**gh.pr_view, "files": []}
        result = consumer.submit(23, Role.DEV, "feat: parser", GOOD_PR_BODY)
        self.assertFalse(result["ok"])
        self.assertEqual(result["failed"], "delivery")
        self.assertEqual(gh.calls_matching("project", "item-edit"), [])
        self.assertEqual(gh.calls_matching("issue", "comment"), [])

    def test_recovery_never_replays_the_pull_request_creation(self):
        # Creation is not idempotent; replaying the routine would open a
        # second Pull Request for one Card.
        consumer, _ = self._consumer(
            board_with((23, "x", "In Progress", "dev")),
            fail_on={"project item-edit": "boom"},
        )
        result = consumer.submit(23, Role.DEV, "feat: parser", GOOD_PR_BODY)
        self.assertTrue(result["partial"])
        self.assertFalse(any("pr create" in step for step in result["recovery"]))
        self.assertTrue(any("transition" in step for step in result["recovery"]))


class PullRequestReadTests(unittest.TestCase):
    def setUp(self):
        self.gh = FakeGh(items=board_with((21, "Delivery", "In Review", "qa")))
        self.board = Board(a_config(), gh=self.gh)

    def test_pull_request_normalises_head_files_and_checks(self):
        pr = self.board.pull_request(21, "Delivery awaiting verdict")
        self.assertEqual(pr["head_sha"], "a" * 40)
        self.assertEqual(pr["changed_files"], ("src/parser.py", "tests/test_parser.py"))
        self.assertEqual(pr["checks"], {"build": "SUCCESS", "test": "SUCCESS"})
        self.assertTrue(pr["mergeable"])
        self.assertFalse(pr["draft"])

    def test_the_pull_request_is_resolved_by_claim_branch_not_by_number(self):
        # Issues and Pull Requests share one numbering sequence, so the PR
        # number drifts from the Card number whenever anything else was
        # created in between (live: card #14's delivery was PR #17). The
        # claim branch is the only stable link.
        self.board.pull_request(21, "Delivery awaiting verdict")
        view = self.gh.calls_matching("pr", "view")[0]
        self.assertEqual(view[2], "claim/21-delivery-awaiting-verdict")

    def test_raw_github_shapes_never_escape_the_board(self):
        pr = self.board.pull_request(21, "Delivery awaiting verdict")
        for leaked in ("headRefOid", "statusCheckRollup", "isDraft", "files"):
            self.assertNotIn(leaked, pr)

    def test_a_conflicting_pull_request_reads_as_not_mergeable(self):
        self.gh.pr_view = {**self.gh.pr_view, "mergeable": "CONFLICTING"}
        self.assertFalse(self.board.pull_request(21, "Delivery awaiting verdict")["mergeable"])

    def test_an_unnamed_check_is_dropped_rather_than_keyed_on_empty(self):
        self.gh.pr_view = {
            **self.gh.pr_view,
            "statusCheckRollup": [{"conclusion": "SUCCESS"}, {"name": "build",
                                                              "conclusion": "SUCCESS"}],
        }
        self.assertEqual(self.board.pull_request(21, "Delivery awaiting verdict")["checks"], {"build": "SUCCESS"})


class VerdictRecordingTests(unittest.TestCase):
    def _board(self, **gh_kwargs):
        gh = FakeGh(items=board_with((21, "Delivery", "In Review", "qa")), **gh_kwargs)
        return Board(a_config(), gh=gh), gh

    def test_recording_posts_the_marker_and_a_parseable_block(self):
        board, gh = self._board()
        board.record_verdict(21, a_verdict())
        body = gh.calls_matching("issue", "comment")[0][-1]
        self.assertIn("agent-teams:verdict", body)
        self.assertIn('"head_sha"', body)

    def test_a_recorded_verdict_reads_back_identically(self):
        board, gh = self._board()
        original = a_verdict()
        board.record_verdict(21, original)
        body = gh.calls_matching("issue", "comment")[0][-1]
        restored = Board(a_config(), gh=FakeGh(
            items=board_with((21, "Delivery", "In Review", "qa")), comments=[body]
        )).latest_verdict(21)
        self.assertEqual(restored, original)

    def test_the_latest_verdict_wins_when_several_were_posted(self):
        board, _ = self._board(
            comments=[verdict_comment(verdict="fail", findings=("boom",)),
                      verdict_comment()]
        )
        self.assertEqual(board.latest_verdict(21).verdict, "pass")

    def test_no_verdict_comment_reads_as_none_not_a_crash(self):
        board, _ = self._board(comments=["just a chat comment"])
        self.assertIsNone(board.latest_verdict(21))

    def test_a_malformed_verdict_block_reads_as_none(self):
        board, _ = self._board(comments=[f"{VERDICT_MARKER}\n```json\n{{not json\n```"])
        self.assertIsNone(board.latest_verdict(21))

    def test_a_marker_with_no_block_reads_as_none(self):
        board, _ = self._board(comments=[f"{VERDICT_MARKER}\nlooks good to me"])
        self.assertIsNone(board.latest_verdict(21))

    def test_a_schema_invalid_block_is_skipped_for_an_earlier_valid_one(self):
        # Fails open like handoff_count: a broken comment must not hide a
        # readable one, and must not crash a session that could still report.
        board, _ = self._board(comments=[
            verdict_comment(),
            f"{VERDICT_MARKER}\n```json\n{{\"verdict\": \"lgtm\"}}\n```",
        ])
        self.assertEqual(board.latest_verdict(21).verdict, "pass")

    def test_recording_an_acceptance_posts_its_own_marker(self):
        board, gh = self._board()
        board.record_acceptance(21, Acceptance(
            acceptance="eligible", head_sha="a" * 40, policy_version="1",
            reasons=("checks green",),
        ))
        body = gh.calls_matching("issue", "comment")[0][-1]
        self.assertIn("agent-teams:acceptance", body)
        self.assertNotIn("agent-teams:verdict", body)


class AutoMergeTests(unittest.TestCase):
    def test_arming_auto_merge_uses_the_configured_method(self):
        gh = FakeGh(items=board_with((21, "Delivery", "In Review", "qa")))
        Board(a_config(merge_method="rebase"), gh=gh).arm_auto_merge(57, "rebase")
        call = gh.calls_matching("pr", "merge")[0]
        self.assertIn("--auto", call)
        self.assertIn("--rebase", call)
        self.assertIn("--delete-branch", call)

    def test_merge_state_reports_the_merge_commit(self):
        gh = FakeGh(
            items=board_with((21, "Delivery", "In Review", "qa")),
            pr_state={"state": "MERGED", "mergedAt": "2026-08-06T00:00:00Z",
                      "mergeCommit": {"oid": "d" * 40}},
        )
        state = Board(a_config(), gh=gh).merge_state(57)
        self.assertEqual(state["state"], "MERGED")
        self.assertEqual(state["merge_commit"], "d" * 40)

    def test_merge_state_of_an_open_pull_request_is_not_merged(self):
        gh = FakeGh(
            items=board_with((21, "Delivery", "In Review", "qa")),
            pr_state={"state": "OPEN", "mergedAt": None},
        )
        self.assertEqual(Board(a_config(), gh=gh).merge_state(57)["state"], "OPEN")


class VerdictPublicationTests(unittest.TestCase):
    def _consumer(self, config=None, **gh_kwargs):
        from agent_teams.workflows import Consumer
        config = config or a_config()
        gh = FakeGh(items=board_with((21, "Delivery", "In Review", "qa")), **gh_kwargs)
        return Consumer(config, Board(config, gh=gh), git=FakeGit()), gh

    def test_recording_a_current_verdict_succeeds(self):
        consumer, gh = self._consumer()
        result = consumer.verdict(21, a_verdict())
        self.assertTrue(result["ok"])
        self.assertEqual(len(gh.calls_matching("issue", "comment")), 1)

    def test_a_verdict_changes_neither_status_nor_role(self):
        # Evidence is not a route. The route comes from accept, and that
        # separation is what stops a reviewer selecting its own outcome.
        consumer, gh = self._consumer()
        consumer.verdict(21, a_verdict())
        self.assertEqual(gh.calls_matching("project", "item-edit"), [])

    def test_a_stale_verdict_is_refused_and_writes_nothing(self):
        consumer, gh = self._consumer()
        with self.assertRaises(Exception) as caught:
            consumer.verdict(21, a_verdict(head_sha="z" * 40))
        self.assertIn("head", str(caught.exception))
        self.assertEqual(gh.calls_matching("issue", "comment"), [])

    def test_an_incomplete_pass_is_refused_with_every_reason_at_once(self):
        consumer, _ = self._consumer()
        with self.assertRaises(Exception) as caught:
            consumer.verdict(21, a_verdict(
                review_dimensions=("correctness",),
                blind_spots=("did not review the migration",),
                test_strength=("line: 98%",),
            ))
        message = str(caught.exception)
        self.assertIn("dimensions", message)
        self.assertIn("blind spot", message)
        self.assertIn("line execution", message)

    def test_a_fail_verdict_is_recorded_without_completeness_demands(self):
        consumer, _ = self._consumer()
        result = consumer.verdict(21, Verdict(
            verdict="fail", card=21, head_sha="a" * 40, pull_request="p",
            checks=("unittest: 3 failed",),
            findings=("parse crashes on an empty header",), next_role=Role.DEV,
        ))
        self.assertTrue(result["ok"])

    def test_a_card_not_in_review_is_refused(self):
        from agent_teams.workflows import Consumer
        config = a_config()
        gh = FakeGh(items=board_with((21, "Delivery", "In Progress", "qa")))
        consumer = Consumer(config, Board(config, gh=gh), git=FakeGit())
        with self.assertRaises(Exception):
            consumer.verdict(21, a_verdict())


class AcceptTests(unittest.TestCase):
    def _consumer(self, comments, config=None, role="qa", **gh_kwargs):
        from agent_teams.workflows import Consumer
        config = config or a_config()
        gh = FakeGh(
            items=board_with((21, "Delivery", "In Review", role)),
            comments=comments, **gh_kwargs
        )
        return Consumer(config, Board(config, gh=gh), git=FakeGit()), gh

    # Superseded 2026-08-06: this used to assert that an eligible result left
    # the Card at (In Review, qa) and wrote nothing to the board. The slide is
    # the contract, and its route 1 is `In Review -> merged -> Done` with no
    # human in the loop -- so accept now completes the route when the merge has
    # landed. Eligibility already requires every required check to be SUCCESS,
    # so `--auto` normally merges at once and this is the common path. The
    # armed-but-not-yet-merged case is asserted separately below.

    OPEN = {"state": "OPEN", "mergedAt": None}
    MERGED = {"state": "MERGED", "mergedAt": "2026-08-06T00:00:00Z",
              "mergeCommit": {"oid": "d" * 40}}

    def test_an_eligible_pass_arms_auto_merge(self):
        consumer, gh = self._consumer([verdict_comment()], pr_state=self.OPEN)
        result = consumer.accept(21)
        self.assertTrue(result["ok"])
        self.assertEqual(result["acceptance"], "eligible")
        self.assertEqual(len(gh.calls_matching("pr", "merge")), 1)

    def test_an_eligible_pass_completes_to_done_when_the_merge_has_landed(self):
        consumer, gh = self._consumer([verdict_comment()], pr_state=self.MERGED)
        result = consumer.accept(21)
        self.assertEqual(result["acceptance"], "eligible")
        self.assertEqual(result["merge"], "merged")
        self.assertEqual(result["status"], "Done")
        self.assertEqual(result["role"], "lead")
        self.assertEqual(result["merge_commit"], "d" * 40)

    def test_an_eligible_pass_waits_when_the_merge_has_not_landed_yet(self):
        # Checks may be green at accept time and the platform still merges
        # asynchronously. Nothing is forced, and the Card does not move.
        consumer, gh = self._consumer([verdict_comment()], pr_state=self.OPEN)
        result = consumer.accept(21)
        self.assertEqual(result["merge"], "armed")
        self.assertEqual(result["status"], "In Review")
        self.assertEqual(result["role"], "qa")
        self.assertEqual(gh.calls_matching("project", "item-edit"), [])
        self.assertTrue(any("coordinator" in step for step in result["next"]))

    def test_done_is_never_reached_without_a_confirmed_merge(self):
        # The whole point of re-reading state after arming: armed is not merged.
        for state in (self.OPEN, {"state": "CLOSED", "mergedAt": None}):
            consumer, gh = self._consumer([verdict_comment()], pr_state=state)
            result = consumer.accept(21)
            self.assertNotEqual(result.get("status"), "Done", str(state))
            self.assertEqual(gh.calls_matching("project", "item-edit"), [])

    def test_completing_to_done_cleans_the_claim_worktree(self):
        from fake_gh import FakeGit
        git = FakeGit()
        from agent_teams.workflows import Consumer
        config = a_config()
        gh = FakeGh(items=board_with((21, "Delivery", "In Review", "qa")),
                    comments=[verdict_comment()], pr_state=self.MERGED)
        Consumer(config, Board(config, gh=gh), git=git).accept(21)
        self.assertTrue(any(call[0] == "remove" for call in git.calls))

    def test_a_defect_is_unaffected_by_the_merge_state(self):
        consumer, gh = self._consumer(
            [verdict_comment(verdict="fail", findings=("boom",))],
            pr_state=self.MERGED,
        )
        result = consumer.accept(21)
        self.assertEqual(result["acceptance"], "defect")
        self.assertEqual(result["status"], "In Progress")
        self.assertEqual(gh.calls_matching("pr", "merge"), [])

    def test_a_defect_returns_the_card_to_development(self):
        consumer, gh = self._consumer(
            [verdict_comment(verdict="fail", findings=("crashes on empty",))]
        )
        result = consumer.accept(21)
        self.assertEqual(result["acceptance"], "defect")
        self.assertEqual(result["status"], "In Progress")
        self.assertEqual(result["role"], "dev")
        self.assertEqual(gh.calls_matching("pr", "merge"), [])

    def test_a_protected_change_hands_to_human_without_moving_status(self):
        changed = ["scripts/agent_teams/policy.py"]
        consumer, gh = self._consumer([verdict_comment(changed_files=tuple(changed))])
        gh.pr_view = {**gh.pr_view, "files": [{"path": changed[0]}]}
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
        self.assertEqual(gh.calls_matching("issue", "comment"), [])

    def test_a_missing_verdict_is_refused(self):
        consumer, gh = self._consumer(["just a chat comment"])
        with self.assertRaises(Exception):
            consumer.accept(21)
        self.assertEqual(gh.calls_matching("pr", "merge"), [])

    def test_the_acceptance_comment_is_posted_on_every_route(self):
        for comment in (
            verdict_comment(),
            verdict_comment(verdict="fail", findings=("boom",)),
        ):
            consumer, gh = self._consumer([comment])
            consumer.accept(21)
            bodies = [call[-1] for call in gh.calls_matching("issue", "comment")]
            self.assertTrue(any("agent-teams:acceptance" in b for b in bodies))

    def test_no_required_checks_never_yields_eligible(self):
        consumer, gh = self._consumer(
            [verdict_comment()], config=a_config(required_checks=[])
        )
        result = consumer.accept(21)
        self.assertEqual(result["acceptance"], "protected_change")
        self.assertEqual(gh.calls_matching("pr", "merge"), [])

    def test_the_result_records_the_deciding_policy_version(self):
        consumer, _ = self._consumer([verdict_comment()])
        from agent_teams import policy
        self.assertEqual(
            consumer.accept(21)["policy_version"], policy.ACCEPTANCE_POLICY_VERSION
        )

    def test_a_red_required_check_routes_to_defect_not_merge(self):
        consumer, gh = self._consumer([verdict_comment()])
        gh.pr_view = {
            **gh.pr_view,
            "statusCheckRollup": [
                {"name": "build", "conclusion": "SUCCESS"},
                {"name": "test", "conclusion": "FAILURE"},
            ],
        }
        result = consumer.accept(21)
        self.assertEqual(result["acceptance"], "defect")
        self.assertEqual(gh.calls_matching("pr", "merge"), [])

    def test_a_pending_required_check_is_monitored_not_routed_to_dev(self):
        consumer, gh = self._consumer([verdict_comment()])
        gh.pr_view = {
            **gh.pr_view,
            "statusCheckRollup": [
                {"name": "build", "conclusion": "SUCCESS"},
                {"name": "test", "conclusion": None},
            ],
        }
        result = consumer.accept(21)
        self.assertEqual(result["acceptance"], "waiting")
        self.assertEqual(result["status"], "In Review")
        self.assertEqual(result["role"], "qa")
        self.assertEqual(gh.calls_matching("pr", "merge"), [])
        self.assertEqual(gh.calls_matching("project", "item-edit"), [])
        self.assertEqual(gh.calls_matching("issue", "comment"), [])


class ReconcileTests(unittest.TestCase):
    def _consumer(self, pr_state, role="qa", git=None, config=None):
        from agent_teams.workflows import Consumer
        config = config or a_config()
        gh = FakeGh(
            items=board_with((21, "Delivery", "In Review", role)),
            comments=[acceptance_comment("eligible")], pr_state=pr_state,
        )
        return Consumer(config, Board(config, gh=gh), git=git or FakeGit()), gh

    MERGED = {"state": "MERGED", "mergedAt": "2026-08-06T00:00:00Z",
              "mergeCommit": {"oid": "d" * 40}}

    def test_a_merged_pull_request_reconciles_to_done_owned_by_lead(self):
        consumer, _ = self._consumer(self.MERGED)
        result = consumer.reconcile(21, Role.LEAD)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "Done")
        self.assertEqual(result["role"], "lead")

    def test_an_open_pull_request_is_refused_and_mutates_nothing(self):
        consumer, gh = self._consumer({"state": "OPEN", "mergedAt": None})
        with self.assertRaises(Exception) as caught:
            consumer.reconcile(21, Role.LEAD)
        self.assertIn("not merged", str(caught.exception).casefold())
        self.assertEqual(gh.calls_matching("project", "item-edit"), [])

    def test_a_closed_but_unmerged_pull_request_is_refused(self):
        # Closed is not merged. Reconciliation records a merge that happened.
        consumer, gh = self._consumer({"state": "CLOSED", "mergedAt": None})
        with self.assertRaises(Exception):
            consumer.reconcile(21, Role.LEAD)
        self.assertEqual(gh.calls_matching("project", "item-edit"), [])

    def test_reconciliation_records_the_merge_commit(self):
        consumer, _ = self._consumer(self.MERGED)
        self.assertEqual(consumer.reconcile(21, Role.LEAD)["merge_commit"], "d" * 40)

    def test_the_worktree_is_cleaned_only_after_a_confirmed_merge(self):
        git = FakeGit()
        consumer, _ = self._consumer(self.MERGED, git=git)
        consumer.reconcile(21, Role.LEAD)
        self.assertTrue(any(call[0] == "remove" for call in git.calls))

    def test_worktree_cleanup_failure_does_not_fail_the_reconciliation(self):
        # The Card reaching Done is the durable outcome; a worktree that
        # refuses removal is reported, never silently forced.
        class StubbornGit(FakeGit):
            def remove_worktree(self, path, force=False):
                from agent_teams.git import WorktreeNotClean
                raise WorktreeNotClean("uncommitted changes")

        consumer, _ = self._consumer(self.MERGED, git=StubbornGit())
        result = consumer.reconcile(21, Role.LEAD)
        self.assertTrue(result["ok"])
        self.assertFalse(result["cleanup"]["ok"])
        self.assertTrue(result["cleanup"]["recovery"])

    def test_a_seat_that_may_not_reconcile_is_refused(self):
        consumer, gh = self._consumer(self.MERGED)
        with self.assertRaises(Exception):
            consumer.reconcile(21, Role.DEV)
        self.assertEqual(gh.calls_matching("project", "item-edit"), [])

    def test_merge_without_eligible_acceptance_cannot_reach_done(self):
        consumer, gh = self._consumer(self.MERGED)
        gh.comments.clear()
        with self.assertRaisesRegex(Exception, "no eligible acceptance"):
            consumer.reconcile(21, Role.LEAD)
        self.assertEqual(gh.calls_matching("project", "item-edit"), [])

    def test_changed_head_cannot_be_reconciled_even_if_merged(self):
        consumer, gh = self._consumer(self.MERGED)
        gh.comments[:] = [acceptance_comment("eligible", head_sha="z" * 40)]
        with self.assertRaisesRegex(Exception, "differs"):
            consumer.reconcile(21, Role.LEAD)
        self.assertEqual(gh.calls_matching("project", "item-edit"), [])


class ApproveExceptionTests(unittest.TestCase):
    MERGED = {"state": "MERGED", "mergedAt": "2026-08-06T00:00:00Z",
              "mergeCommit": {"oid": "d" * 40}}

    def _consumer(self, *, comments=None, role="human", pr_view=None):
        from agent_teams.workflows import Consumer
        config = a_config()
        gh = FakeGh(
            items=board_with((21, "Delivery", "In Review", role)),
            comments=comments or [acceptance_comment()], pr_state=self.MERGED,
            pr_view=pr_view,
        )
        return Consumer(config, Board(config, gh=gh), git=FakeGit()), gh

    def test_human_command_merges_exact_head_and_reconciles_done(self):
        consumer, gh = self._consumer()
        result = consumer.approve_exception(21, Role.HUMAN)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "Done")
        self.assertEqual(result["role"], "lead")
        self.assertEqual(len(gh.calls_matching("pr", "merge")), 1)
        merge = gh.calls_matching("pr", "merge")[0]
        self.assertEqual(
            merge[merge.index("--match-head-commit") + 1], "a" * 40
        )

    def test_agent_seat_is_refused_before_github(self):
        consumer, gh = self._consumer()
        with self.assertRaises(Exception):
            consumer.approve_exception(21, Role.LEAD)
        self.assertEqual(gh.calls, [])

    def test_changed_head_is_refused_before_merge(self):
        consumer, gh = self._consumer(comments=[acceptance_comment(head_sha="z" * 40)])
        with self.assertRaisesRegex(Exception, "head changed"):
            consumer.approve_exception(21, Role.HUMAN)
        self.assertEqual(gh.calls_matching("pr", "merge"), [])

    def test_controller_returns_changed_exception_head_to_qa(self):
        consumer, gh = self._consumer(
            comments=[acceptance_comment(head_sha="z" * 40)]
        )
        result = consumer.refresh_verification(21)
        self.assertTrue(result["ok"])
        self.assertEqual(result["role"], "qa")
        self.assertEqual(len(gh.calls_matching("project", "item-edit")), 1)
        self.assertEqual(gh.calls_matching("pr", "merge"), [])

    def test_controller_does_not_remove_a_current_exception(self):
        consumer, gh = self._consumer()
        with self.assertRaisesRegex(Exception, "still matches"):
            consumer.refresh_verification(21)
        self.assertEqual(gh.calls_matching("project", "item-edit"), [])


class DoctorAcceptanceTests(unittest.TestCase):
    """doctor validates and explains the acceptance preconditions; it never
    creates them."""

    def test_doctor_reports_empty_required_checks_as_a_problem(self):
        gh = FakeGh(items=board_with((21, "x", "In Review", "qa")))
        report = Board(a_config(required_checks=[]), gh=gh).doctor()
        self.assertTrue(
            any("required_checks" in problem for problem in report["acceptance_problems"])
        )

    def test_doctor_reports_auto_merge_disabled_as_a_problem(self):
        gh = FakeGh(
            items=board_with((21, "x", "In Review", "qa")), auto_merge_allowed=False
        )
        report = Board(a_config(), gh=gh).doctor()
        self.assertTrue(
            any("auto-merge" in problem for problem in report["acceptance_problems"])
        )

    def test_a_fully_configured_board_reports_neither_problem(self):
        gh = FakeGh(items=board_with((21, "x", "In Review", "qa")))
        report = Board(a_config(), gh=gh).doctor()
        for phrase in ("required_checks", "auto-merge"):
            self.assertFalse(
                any(phrase in problem for problem in report["acceptance_problems"]), phrase
            )
