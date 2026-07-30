"""Partial-failure and fix-forward behaviour (plan M1.6).

GitHub offers no transaction across Issue creation, Project field writes, and
comments. Every one of those boundaries is exercised here, and every assertion
is about the same two things: does the result name exactly what already landed,
and does the recovery advice match reality?

The recurring anti-requirement: nothing may claim a rollback that did not run.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).parent))

from agent_teams.board import Board  # noqa: E402
from agent_teams.config import Config  # noqa: E402
from agent_teams.model import Role, Status  # noqa: E402
from agent_teams.workflows import Producer  # noqa: E402
from fake_gh import REPO, FakeGh  # noqa: E402


def producer(gh):
    config = Config.from_dict(
        {"repo": REPO, "project_owner": "acme", "project_number": 1}
    )
    return Producer(config, Board(config, gh)), config


class IntakeFailureTests(unittest.TestCase):
    """Mutation order: issue -> project item -> Status -> Role -> comment."""

    def test_failure_creating_the_issue_leaves_nothing_behind(self):
        gh = FakeGh(fail_on={"issue create": "network down"})
        result, _ = producer(gh)
        outcome = result.intake("Add parser", "Acceptance: parses JSON.")
        self.assertFalse(outcome["ok"])
        self.assertFalse(outcome["partial"])
        self.assertEqual(outcome["completed"], [])
        self.assertEqual(outcome["failed"], "issue_created")

    def test_failure_adding_to_the_project_reports_the_orphan_issue(self):
        gh = FakeGh(fail_on={"project item-add": "project unreachable"})
        result, _ = producer(gh)
        outcome = result.intake("Add parser", "Acceptance: parses JSON.")
        self.assertTrue(outcome["partial"])
        self.assertEqual(outcome["completed"], ["issue_created"])
        self.assertEqual(outcome["failed"], "project_item_added")
        # The Issue number must survive, or the operator cannot find it.
        self.assertEqual(outcome["issue"], 42)
        self.assertIn("42", outcome["url"])
        recovery = " ".join(outcome["recovery"])
        self.assertIn("gh project item-add", recovery)

    def test_failure_setting_status_reports_the_card_with_no_status(self):
        gh = FakeGh(fail_on={"project item-edit": ("field write refused", 1)})
        result, _ = producer(gh)
        outcome = result.intake("Add parser", "Acceptance: parses JSON.")
        self.assertEqual(outcome["completed"], ["issue_created", "project_item_added"])
        self.assertEqual(outcome["failed"], "status_set")
        self.assertEqual(outcome["item_id"], "ITEM_42")
        self.assertIn("Backlog", " ".join(outcome["recovery"]))

    def test_failure_setting_role_reports_a_backlog_card_with_no_owner(self):
        gh = FakeGh(fail_on={"project item-edit": ("field write refused", 2)})
        result, _ = producer(gh)
        outcome = result.intake("Add parser", "Acceptance: parses JSON.")
        self.assertEqual(
            outcome["completed"],
            ["issue_created", "project_item_added", "status_set"],
        )
        self.assertEqual(outcome["failed"], "role_set")
        self.assertIn("architect", " ".join(outcome["recovery"]))

    def test_failure_posting_the_comment_keeps_the_body_for_replay(self):
        gh = FakeGh(fail_on={"issue comment": "comment rejected"})
        result, _ = producer(gh)
        outcome = result.intake("Add parser", "Acceptance: parses JSON.")
        self.assertEqual(outcome["failed"], "handoff_comment")
        self.assertIn("role_set", outcome["completed"])
        # Recovery must forbid re-flipping fields and hand over the exact body.
        recovery = " ".join(outcome["recovery"])
        self.assertIn("do not change them", recovery)
        self.assertIn("gh issue comment", recovery)
        self.assertIn("**Handoff**: `analyst` -> `architect`", outcome["comment"])

    def test_success_writes_one_role_not_two(self):
        # The pre-package implementation set Role to analyst then immediately
        # overwrote it with architect, doubling the failure surface for a state
        # no session could ever observe.
        gh = FakeGh()
        result, _ = producer(gh)
        outcome = result.intake("Add parser", "Acceptance: parses JSON.")
        self.assertTrue(outcome["ok"])
        edits = gh.calls_matching("project", "item-edit")
        self.assertEqual(len(edits), 2)
        self.assertIn("STATUS_BACKLOG", edits[0])
        self.assertIn("ROLE_ARCHITECT", edits[1])
        self.assertNotIn("ROLE_ANALYST", [token for call in edits for token in call])


class HandoffFailureTests(unittest.TestCase):
    def test_comment_failure_after_role_change_is_reported_as_partial(self):
        gh = FakeGh(fail_on={"issue comment": "comment rejected"})
        result, config = producer(gh)
        outcome = result.handoff(8, Role.ARCHITECT, Role.RD, "Spec merged.")
        self.assertFalse(outcome["ok"])
        self.assertTrue(outcome["partial"])
        self.assertEqual(outcome["completed"], ["role_set"])
        self.assertEqual(outcome["failed"], "handoff_comment")
        self.assertEqual(outcome["role"], "rd")
        recovery = " ".join(outcome["recovery"])
        self.assertIn("do not change it back", recovery)
        self.assertIn(config.repo, recovery)
        self.assertIn("**Handoff**", outcome["comment"])

    def test_no_rollback_is_ever_claimed(self):
        gh = FakeGh(fail_on={"issue comment": "comment rejected"})
        result, _ = producer(gh)
        outcome = result.handoff(8, Role.ARCHITECT, Role.RD, "Spec merged.")
        serialised = repr(outcome).casefold()
        for forbidden in ("rolled back", "rollback", "reverted", "undone"):
            self.assertNotIn(forbidden, serialised)


class PromoteFailureTests(unittest.TestCase):
    def test_handoff_failure_leaves_a_ready_card_and_says_so(self):
        # Status write succeeds; the Role write inside the handoff fails.
        gh = FakeGh(fail_on={"project item-edit": ("field write refused", 2)})
        result, _ = producer(gh)
        outcome = result.promote(20, "https://github.com/acme/widgets/pull/57")
        self.assertFalse(outcome["ok"])
        self.assertEqual(outcome["completed"], ["status_set"])
        self.assertEqual(outcome["failed"], "role_set")
        recovery = " ".join(outcome["recovery"])
        self.assertIn("Ready but still owned", recovery)
        self.assertIn("Nothing will pick it up", recovery)
        self.assertIn("producer_board.py handoff 20", recovery)

    def test_status_failure_changes_nothing(self):
        gh = FakeGh(fail_on={"project item-edit": ("field write refused", 1)})
        result, _ = producer(gh)
        outcome = result.promote(20, "https://github.com/acme/widgets/pull/57")
        self.assertEqual(outcome["completed"], [])
        self.assertIn("Nothing changed", " ".join(outcome["recovery"]))


class DecomposeFailureTests(unittest.TestCase):
    def test_partial_creation_warns_about_duplicates_on_retry(self):
        # Second child's Issue creation fails.
        gh = FakeGh(fail_on={"issue create": ("rate limited", 2)})
        result, _ = producer(gh)
        outcome = result.decompose(
            20,
            [
                {"title": "Parser core", "body": "Acceptance: parses JSON."},
                {"title": "Parser errors", "body": "Acceptance: reports position."},
            ],
            "https://github.com/acme/widgets/pull/57",
        )
        self.assertFalse(outcome["ok"])
        self.assertTrue(outcome["partial"])
        self.assertEqual(len(outcome["created"]), 1)
        self.assertEqual(len(outcome["failed"]), 1)
        self.assertIn("duplicates", " ".join(outcome["recovery"]))

    def test_a_child_missing_a_body_is_rejected_without_calling_github(self):
        gh = FakeGh()
        result, _ = producer(gh)
        outcome = result.decompose(
            20,
            [{"title": "No body"}],
            "https://github.com/acme/widgets/pull/57",
        )
        self.assertFalse(outcome["ok"])
        self.assertEqual(gh.calls_matching("issue", "create"), [])


if __name__ == "__main__":
    unittest.main()
