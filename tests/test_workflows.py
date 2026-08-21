"""Producer routine behaviour: the four flows from ARCHITECTURE.md section 6."""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).parent))

from agent_teams import policy  # noqa: E402
from agent_teams.board import Board  # noqa: E402
from agent_teams.config import Config  # noqa: E402
from agent_teams.model import (  # noqa: E402
    ACCEPTANCE_MARKER, DECOMPOSED_CHILD_MARKER, DECOMPOSITION_MARKER, Role,
    SPECIFICATION_MARKER, Status,
)
from agent_teams.workflows import Producer, WorkflowError  # noqa: E402
from fake_gh import REPO, FakeGh, FakeGit, board_with  # noqa: E402

SPEC_PATH = "docs/specs/card-20.md"
SPEC_COMMIT = "e" * 40
SPEC_COMMENT = (
    SPECIFICATION_MARKER + "\n\n```json\n" +
    json.dumps({"card": 20, "path": SPEC_PATH, "commit": SPEC_COMMIT,
                "branch": "main"}) + "\n```"
)

def manual_spec_comment(state="OPEN", commit="f" * 40):
    payload = {
        "card": 20,
        "path": SPEC_PATH,
        "commit": commit,
        "branch": "spec/20-shaped-requirement",
        "base_branch": "main",
        "mode": "manual",
        "state": state,
        "pull_request": f"https://github.com/{REPO}/pull/57",
    }
    return (
        SPECIFICATION_MARKER + "\n\n```json\n"
        + json.dumps(payload) + "\n```"
    )



def producer(gh=None, git=None, **config_overrides):
    gh = gh or FakeGh()
    base = {"repo": REPO, "project_owner": "acme", "project_number": 1}
    base.update(config_overrides)
    config = Config.from_dict(base)
    return Producer(config, Board(config, gh), git=git or FakeGit()), gh


class SpecGateTests(unittest.TestCase):
    """Ready requires a direct, tracked Git specification."""

    def test_tracked_git_specification_satisfies_the_gate(self):
        team, _ = producer()
        gate = team.check_spec_gate(SPEC_PATH)
        self.assertTrue(gate["satisfied"])
        self.assertEqual(gate["state"], "TRACKED")
        self.assertEqual(gate["commit"], SPEC_COMMIT)

    def test_pull_request_reference_is_refused(self):
        team, gh = producer()
        gate = team.check_spec_gate("https://github.com/acme/widgets/pull/57")
        self.assertFalse(gate["satisfied"])
        self.assertIn("not a readiness artifact", gate["explanation"])
        self.assertEqual(gh.calls_matching("pr", "view"), [])

    def test_no_reference_refuses(self):
        team, _ = producer()
        gate = team.check_spec_gate("")
        self.assertFalse(gate["satisfied"])
        self.assertIn("specification reference", gate["explanation"])


#: A Card the architect has already shaped and handed to the human for the
#: readiness decision -- the state `promote` now expects to act on.
AT_THE_GATE = board_with((20, "Shaped requirement", "Backlog", "human"))


class PromoteTests(unittest.TestCase):
    # Superseded throughout: `promote` used to default to the architect, who
    # could declare its own work Ready. Readiness is now the human lifecycle
    # gate (ARCHITECTURE.md Appendix A.2 decision 6), so these act as `human` on a Card
    # the architect handed over.
    def test_the_human_promotes_and_hands_to_development(self):
        team, gh = producer(FakeGh(items=AT_THE_GATE, comments=[SPEC_COMMENT]))
        result = team.promote(20)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "Ready")
        self.assertEqual(result["role"], "dev")
        self.assertEqual(result["completed"], ["status_set", "role_set"])
        # Two independent semantic operations, in the documented order.
        edits = gh.calls_matching("project", "item-edit")
        self.assertIn("STATUS_READY", edits[0])
        self.assertIn("ROLE_DEV", edits[1])

    def test_status_only_readiness_is_finalized_without_another_human_command(self):
        items = board_with((20, "Shaped requirement", "Ready", "human"))
        team, gh = producer(FakeGh(items=items, comments=[SPEC_COMMENT]))
        result = team.finalize_readiness(20)
        self.assertTrue(result["ok"])
        self.assertEqual(result["role"], "dev")
        edits = gh.calls_matching("project", "item-edit")
        self.assertEqual(len(edits), 1)
        self.assertIn("ROLE_DEV", edits[0])

    def test_refuses_when_the_recorded_specification_changed(self):
        gh = FakeGh(items=AT_THE_GATE, comments=[SPEC_COMMENT])
        changed = FakeGit(specification={
            "ok": True, "path": SPEC_PATH, "commit": "f" * 40,
            "head_sha": "f" * 40, "branch": "main", "state": "TRACKED",
        })
        team, _ = producer(gh, git=changed)
        with self.assertRaisesRegex(WorkflowError, "changed after"):
            team.promote(20)
        self.assertEqual(gh.calls_matching("project", "item-edit"), [])


class PublishSpecificationTests(unittest.TestCase):
    def test_architect_publishes_on_current_branch_and_records_the_card(self):
        items = board_with((20, "Shaped requirement", "Backlog", "architect"))
        git = FakeGit()
        team, gh = producer(FakeGh(items=items), git=git)
        result = team.publish_specification(20, SPEC_PATH)
        self.assertTrue(result["ok"])
        self.assertIn(("publish_specification", 20, SPEC_PATH), git.calls)
        self.assertEqual(gh.calls_matching("pr", "create"), [])
        self.assertTrue(any(
            SPECIFICATION_MARKER in call[-1]
            for call in gh.calls_matching("issue", "comment")
        ))
    def test_manual_mode_publishes_a_spec_pr_and_records_its_exact_head(self):
        items = board_with((20, "Shaped requirement", "Backlog", "architect"))
        git = FakeGit()
        team, gh = producer(
            FakeGh(items=items), git=git, spec_merge_mode="manual"
        )
        result = team.publish_specification(20, SPEC_PATH)
        self.assertTrue(result["ok"])
        self.assertIn(
            ("publish_specification_for_review", 20, SPEC_PATH), git.calls
        )
        self.assertEqual(len(gh.calls_matching("pr", "create")), 1)
        self.assertEqual(result["specification"]["mode"], "manual")
        self.assertEqual(result["specification"]["commit"], "f" * 40)
        self.assertEqual(
            result["specification"]["pull_request"],
            f"https://github.com/{REPO}/pull/57",
        )


    def test_non_architect_is_refused_before_git_or_github(self):
        items = board_with((20, "Shaped requirement", "Backlog", "architect"))
        git = FakeGit()
        team, gh = producer(FakeGh(items=items), git=git)
        with self.assertRaises(policy.ActionForbidden):
            team.publish_specification(20, SPEC_PATH, Role.DEV)
        self.assertEqual(git.calls, [])
        self.assertEqual(gh.calls, [])

class FinalizeSpecificationMergeTests(unittest.TestCase):
    def _team(self, *, merged=True, head_sha="f" * 40):
        pr_view = {
            **FakeGh().pr_view,
            "headRefOid": head_sha,
            "baseRefName": "main",
        }
        pr_state = {
            "state": "MERGED" if merged else "OPEN",
            "mergedAt": "now" if merged else None,
            "mergeCommit": {"oid": "d" * 40} if merged else None,
        }
        git = FakeGit()
        team, gh = producer(
            FakeGh(
                items=board_with(
                    (20, "Shaped requirement", "Backlog", "architect")
                ),
                comments=[manual_spec_comment()],
                pr_view=pr_view,
                pr_state=pr_state,
            ),
            git=git,
            spec_merge_mode="manual",
        )
        return team, gh, git

    def test_confirmed_user_merge_syncs_and_records_the_base_commit(self):
        team, gh, git = self._team()
        result = team.finalize_specification_merge(20)
        self.assertTrue(result["ok"])
        self.assertEqual(result["specification"]["state"], "MERGED")
        self.assertEqual(result["specification"]["commit"], SPEC_COMMIT)
        self.assertIn(("sync_merged_specification", SPEC_PATH, "main"), git.calls)
        self.assertEqual(len(gh.calls_matching("issue", "comment")), 1)

    def test_open_specification_pr_is_refused_before_git_sync(self):
        team, _, git = self._team(merged=False)
        with self.assertRaisesRegex(WorkflowError, "must merge"):
            team.finalize_specification_merge(20)
        self.assertEqual(
            [call for call in git.calls if call[0] == "sync_merged_specification"],
            [],
        )


class PromoteAuthorityTests(unittest.TestCase):

    def test_no_agent_seat_can_promote_even_its_own_work(self):
        for seat in (Role.ANALYST, Role.ARCHITECT, Role.DEV, Role.QA, Role.LEAD):
            with self.subTest(seat=seat):
                gh = FakeGh(items=AT_THE_GATE)
                team, _ = producer(gh)
                with self.assertRaises(policy.ActionForbidden):
                    team.promote(20, "", seat)
                self.assertEqual(gh.calls_matching("project", "item-edit"), [])

    def test_refuses_a_card_owned_by_another_seat(self):
        team, _ = producer()
        with self.assertRaisesRegex(WorkflowError, "owned by"):
            team.promote(21)  # #21 is (In Review, qa)

    def test_refuses_a_card_whose_status_cannot_reach_ready(self):
        team, _ = producer(FakeGh(items=board_with((8, "Already Ready", "Ready", "human"))))
        with self.assertRaises(policy.IllegalTransition):
            team.promote(8)

    def test_the_architect_cannot_reach_ready_by_any_other_door(self):
        # The destination rule (16.1 decision 5) means closing `promote` closes
        # `create-card` and `transition` too. Assert that, rather than trust it.
        gh = FakeGh(items=AT_THE_GATE)
        team, _ = producer(gh)
        with self.assertRaises(policy.ActionForbidden):
            team.create_card("t", "b", Status.READY, Role.DEV, Role.ARCHITECT)
        with self.assertRaises(policy.ActionForbidden):
            team.transition(20, Status.READY, Role.ARCHITECT)
        self.assertEqual(gh.calls_matching("issue", "create"), [])
        self.assertEqual(gh.calls_matching("project", "item-edit"), [])


class CreateCardTests(unittest.TestCase):
    """Creating a Card writes a routing state, so policy governs both axes.

    ARCHITECTURE.md Appendix A.2 decision 4 settles that the *destination* decides which
    authority governs a Status move. `transition_card` applied that rule but
    `create_card` did not, which left the closed hole open through a second
    door: any seat allowed to create a Card could place it in any state, in any
    seat's lane, without the action or handoff row that governs getting there.
    """

    def test_the_analyst_cannot_create_a_card_already_ready(self):
        # `promote_to_ready` refuses `analyst`; reaching Ready by creation is
        # the same decision under another name.
        team, gh = producer()
        with self.assertRaisesRegex(policy.ActionForbidden, "promote to ready"):
            team.create_card("t", "b", Status.READY, Role.ARCHITECT, Role.ANALYST)
        self.assertEqual(gh.calls_matching("issue", "create"), [])

    def test_no_seat_reaches_done_by_creating_a_card(self):
        # Done means a human accepted a delivery. Nothing may start there.
        team, gh = producer()
        with self.assertRaisesRegex(WorkflowError, "cannot be created Done"):
            team.create_card("t", "b", Status.DONE, Role.HUMAN, Role.ANALYST)
        self.assertEqual(gh.calls_matching("issue", "create"), [])

    def test_the_analyst_cannot_create_a_card_in_the_development_lane(self):
        # Section 6.4: the System Analyst cannot hand directly to `dev`.
        # Creating the Card already owned by `dev` is that handoff, pre-baked.
        team, gh = producer()
        with self.assertRaises(policy.IllegalHandoff):
            team.create_card("t", "b", Status.BACKLOG, Role.DEV, Role.ANALYST)
        self.assertEqual(gh.calls_matching("issue", "create"), [])

    def test_the_architect_creates_implementation_cards_at_the_gate(self):
        # Superseded: this used to create the Card directly at Ready. The
        # architect now creates it in Backlog owned by `human`, awaiting the
        # readiness decision.
        team, gh = producer()
        result = team.create_card("t", "b", Status.BACKLOG, Role.HUMAN, Role.ARCHITECT)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "Backlog")
        self.assertEqual(result["role"], "human")

    def test_a_seat_may_keep_the_card_it_creates(self):
        # Self-assignment is not a handoff, so it must not trip the matrix --
        # an architect authoring its own documentation Card is the normal case.
        team, _ = producer()
        result = team.create_card(
            "spec", "b", Status.BACKLOG, Role.ARCHITECT, Role.ARCHITECT
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["role"], "architect")


class DecomposeTests(unittest.TestCase):
    def test_creates_flat_ready_cards_and_summarises_on_the_parent(self):
        team, gh = producer(FakeGh(comments=[SPEC_COMMENT]))
        result = team.decompose(
            20,
            [
                {"title": "Parser core", "body": "Acceptance: parses JSON."},
                {"title": "Parser errors", "body": "Acceptance: reports position."},
            ],
            SPEC_PATH,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["created"]), 2)
        self.assertTrue(result["summary_comment_posted"])
        # Superseded: children used to be created at (Ready, dev), which put
        # them past the readiness gate the architect may not open. They now
        # wait at (Backlog, human) for a per-Card approval, which is what the
        # reference project's first gate always meant.
        for entry in result["created"]:
            self.assertEqual(entry["status"], "Backlog")
            self.assertEqual(entry["role"], "human")
        # Each child body carries the spec pointer and its provenance.
        bodies = [call[-1] for call in gh.calls_matching("issue", "create")]
        for body in bodies:
            self.assertIn("Decomposed from #20", body)
            self.assertIn(SPECIFICATION_MARKER, body)
            self.assertIn(DECOMPOSED_CHILD_MARKER, body)

    def test_a_decomposed_child_can_pass_readiness_from_its_inherited_spec(self):
        gh = FakeGh(comments=[SPEC_COMMENT])
        team, _ = producer(gh)
        result = team.decompose(
            20, [{"title": "Parser core", "body": "Acceptance: parses JSON."}]
        )
        self.assertTrue(result["ok"])
        gh.comments.clear()  # prove the child body, not the parent's comment, is used
        gh.items = board_with((42, "Parser core", "Backlog", "human"))
        promoted = team.promote(42)
        self.assertTrue(promoted["ok"])
        self.assertEqual(promoted["status"], "Ready")

    def test_retry_reuses_children_when_the_parent_summary_comment_failed(self):
        gh = FakeGh(
            comments=[SPEC_COMMENT],
            fail_on={"issue comment": ("temporary failure", 1)},
        )
        team, _ = producer(gh)
        children = [{"title": "Parser core", "body": "Acceptance: parses JSON."}]
        first = team.decompose(20, children)
        self.assertFalse(first["ok"])
        self.assertTrue(first["partial"])
        gh.items = board_with(
            (20, "Shaped requirement", "Backlog", "architect"),
            (42, "Parser core", "Backlog", "human"),
        )
        second = team.decompose(20, children)
        self.assertTrue(second["ok"])
        self.assertTrue(second["created"][0]["reused"])
        self.assertEqual(len(gh.calls_matching("issue", "create")), 1)

    def test_only_the_architect_may_split_work(self):
        team, gh = producer(FakeGh(comments=[SPEC_COMMENT]))
        with self.assertRaises(policy.ActionForbidden):
            team.decompose(20, [{"title": "t", "body": "b"}], SPEC_PATH, Role.DEV)
        self.assertEqual(gh.calls_matching("issue", "create"), [])

    def test_refuses_without_a_published_specification(self):
        gh = FakeGh()
        team, _ = producer(gh)
        with self.assertRaises(WorkflowError):
            team.decompose(20, [{"title": "t", "body": "b"}])

    def test_refuses_an_empty_decomposition(self):
        team, _ = producer()
        with self.assertRaisesRegex(WorkflowError, "at least one"):
            team.decompose(20, [], SPEC_PATH)


class BriefTests(unittest.TestCase):
    def test_groups_by_role_lane(self):
        team, _ = producer()
        report = team.brief()
        self.assertIn("dev", report["lanes"])
        self.assertIn("qa", report["lanes"])
        self.assertIn("(no Role)", report["lanes"])

    def test_counts_work_in_progress_excluding_blocked(self):
        team, _ = producer()
        board = team.brief()["board"]
        # In Progress #23 + In Review #21 and #22 = 3. Blocked #9 excluded.
        self.assertEqual(board["wip"], 3)
        self.assertFalse(board["over_wip"])

    def test_the_human_merge_gate_outranks_everything_else(self):
        team, _ = producer()
        report = team.brief()
        self.assertIn("#22", report["recommendation"])
        self.assertIn("Merge gate first", report["recommendation"])

    def test_surfaces_cards_that_cannot_be_routed(self):
        team, _ = producer()
        problems = team.brief()["data_quality"]
        self.assertEqual([card["number"] for card in problems], [10])
        self.assertIn("nothing will pick it up", problems[0]["problem"])

    def test_handoff_counts_are_opt_in(self):
        team, gh = producer()
        team.brief()
        self.assertEqual(gh.calls_matching("issue", "view"), [])
        self.assertFalse(team.brief()["handoff_counts_included"])

    def test_opting_in_surfaces_cards_near_the_cap(self):
        marker = "<!-- agent-teams:handoff -->"
        gh = FakeGh(comments=[marker] * 5)
        team, _ = producer(gh)
        report = team.brief(with_handoffs=True)
        self.assertTrue(report["handoff_counts_included"])
        self.assertTrue(report["near_handoff_cap"])
        self.assertEqual(report["near_handoff_cap"][0]["handoff_count"], 5)

    def test_over_wip_is_recommended_once_the_merge_gate_is_clear(self):
        # The merge gate deliberately outranks work in progress, so this needs
        # a board with nothing waiting on the human.
        items = {
            "items": [
                {
                    "id": f"ITEM_{n}", "status": "In Progress", "role": "dev",
                    "content": {"number": n, "repository": REPO,
                                "title": f"Build {n}", "url": "u"},
                }
                for n in (30, 31, 32)
            ]
        }
        team, _ = producer(FakeGh(items=items), wip_limit=2)
        recommendation = team.brief()["recommendation"]
        self.assertIn("Work in progress is 3", recommendation)
        self.assertIn("limit of 2", recommendation)


class TriageTests(unittest.TestCase):
    def test_groups_blocked_cards_by_the_seat_that_owes_a_decision(self):
        team, _ = producer()
        report = team.triage()
        self.assertEqual(report["blocked_total"], 1)
        self.assertEqual([c["number"] for c in report["by_responsible_seat"]["dev"]], [9])

    def test_flags_blocked_cards_with_no_owner_first(self):
        items = {
            "items": [
                {
                    "id": "ITEM_5", "status": "Blocked",
                    "content": {"number": 5, "repository": REPO, "title": "Orphan",
                                "url": "u"},
                }
            ]
        }
        team, _ = producer(FakeGh(items=items))
        report = team.triage()
        self.assertEqual([c["number"] for c in report["unowned_blocked"]], [5])
        self.assertIn("Unowned Blocked", report["recommendation"])


class VerificationQueueTests(unittest.TestCase):
    def test_lists_only_deliveries_awaiting_a_verdict(self):
        team, _ = producer()
        report = team.verification_queue()
        self.assertEqual([c["number"] for c in report["queue"]], [21])
        self.assertEqual(report["queue_depth"], 1)

    def test_emits_one_kickoff_prompt_per_card(self):
        team, _ = producer()
        prompt = team.verification_queue()["queue"][0]["kickoff_prompt"]
        self.assertIn("[role:qa]", prompt)
        self.assertIn("[board-card:#21]", prompt)

    def test_inspection_never_mutates(self):
        team, gh = producer()
        team.verification_queue()
        self.assertEqual(gh.calls_matching("project", "item-edit"), [])
        self.assertEqual(gh.calls_matching("issue", "comment"), [])


class BootstrapTests(unittest.TestCase):
    def test_each_seat_gets_its_own_orientation(self):
        team, _ = producer()
        expected = {
            Role.ANALYST: "needs_clarification",
            Role.ARCHITECT: "awaiting_shaping",
            Role.QA: "verification_queue",
            Role.LEAD: "lanes",
        }
        for seat, key in expected.items():
            self.assertIn(key, team.bootstrap(seat)["seat_view"], seat)

    def test_the_architect_sees_work_waiting_on_it(self):
        team, _ = producer()
        view = team.bootstrap(Role.ARCHITECT)["seat_view"]
        self.assertEqual([c["number"] for c in view["awaiting_shaping"]], [20])

    def test_reports_missing_standing_context_rather_than_guessing(self):
        team, _ = producer()
        result = team.bootstrap(Role.LEAD, repo_root=Path("/nonexistent-root"))
        self.assertEqual(
            result["context_pointers_missing"],
            [entry["path"] for entry in result["standing_context"]],
        )

    def test_lists_the_routines_the_seat_may_run(self):
        team, _ = producer()
        self.assertIn("intake", team.bootstrap(Role.ANALYST)["routines"])
        self.assertNotIn("intake", team.bootstrap(Role.QA)["routines"])
        self.assertEqual(team.bootstrap(Role.DEV)["routines"], [])


class DispatchTests(unittest.TestCase):
    def test_refuses_a_role_that_is_not_configured_for_dispatch(self):
        team, _ = producer()
        with self.assertRaisesRegex(WorkflowError, "not dispatchable"):
            team.dispatch(Role.ANALYST)

    def test_orders_by_configured_role_then_card_number(self):
        team, _ = producer()
        self.assertEqual([c["number"] for c in team.dispatch()], [8, 12])

    def test_dispatch_never_mutates(self):
        team, gh = producer()
        team.dispatch()
        self.assertEqual(gh.calls_matching("project", "item-edit"), [])

    def test_kickoff_states_the_expected_pair_for_staleness_checks(self):
        # The receiving session compares this against the live board; a
        # mismatch means the kickoff is stale and must not be worked from.
        team, _ = producer()
        prompt = next(e["prompt"] for e in team.dispatch() if e["number"] == 12)
        self.assertIn("[expected:(Ready, dev)]", prompt)
        queue_prompt = team.verification_queue()["queue"][0]["kickoff_prompt"]
        self.assertIn("[expected:(In Review, qa)]", queue_prompt)


class NextActionsTests(unittest.TestCase):
    def test_plans_architect_dev_resume_and_qa_as_bounded_spawns(self):
        items = board_with(
            (3, "Shape", "Backlog", "architect"),
            (4, "Build", "Ready", "dev"),
            (5, "Fix", "In Progress", "dev"),
            (6, "Verify", "In Review", "qa"),
        )
        team, _ = producer(FakeGh(items=items))
        result = team.next_actions()
        actions = {entry["number"]: entry for entry in result["actions"]}
        self.assertEqual(set(actions), {3, 4, 5, 6})
        self.assertEqual(actions[3]["routine"], "authoring-spec")
        self.assertEqual(actions[4]["routine"], "consuming-card")
        self.assertIn("Resume", actions[5]["prompt"])
        self.assertEqual(actions[6]["routine"], "verifying-delivery")
        for entry in actions.values():
            self.assertEqual(entry["kind"], "spawn")
            self.assertIn(f"[board-card:#{entry['number']}]", entry["prompt"])
            self.assertEqual(entry["skill"], f"agent-teams:{entry['routine']}")
            self.assertIn(f"[skill:{entry['skill']}]", entry["prompt"])

    def test_reports_only_the_two_human_gates(self):
        acceptance = ACCEPTANCE_MARKER + "\n\n```json\n" + json.dumps({
            "acceptance": "protected_change", "head_sha": "a" * 40,
            "policy_version": "test", "reasons": ["protected file"],
        }) + "\n```"
        items = board_with(
            (20, "Ready decision", "Backlog", "human"),
            (21, "QA exception", "In Review", "human"),
        )
        team, _ = producer(FakeGh(
            items=items, comments=[SPEC_COMMENT, acceptance]
        ))
        result = team.next_actions()
        self.assertEqual(result["actions"], [])
        gates = {entry["number"]: entry["gate"] for entry in result["human_gates"]}
        self.assertEqual(gates, {20: "readiness", 21: "qa_exception"})
        readiness = next(g for g in result["human_gates"] if g["number"] == 20)
        self.assertEqual(readiness["field"], "Status")
        self.assertEqual(readiness["value"], "Ready")
        self.assertNotIn("command", readiness)

    def test_confirmed_eligible_merge_becomes_automatic_reconciliation(self):
        acceptance = ACCEPTANCE_MARKER + "\n\n```json\n" + json.dumps({
            "acceptance": "eligible", "head_sha": "a" * 40,
            "policy_version": "test", "reasons": ["green"],
        }) + "\n```"
        merged = {"state": "MERGED", "mergedAt": "now",
                  "mergeCommit": {"oid": "d" * 40}}
        team, _ = producer(FakeGh(
            items=board_with((21, "Delivery", "In Review", "qa")),
            comments=[acceptance], pr_state=merged,
        ))
        actions = team.next_actions()["actions"]
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["kind"], "reconcile")
        self.assertEqual(actions[0]["argv"], ["reconcile-done", "21"])

    def test_armed_exact_head_is_monitored_in_the_current_session(self):
        acceptance = ACCEPTANCE_MARKER + "\n\n```json\n" + json.dumps({
            "acceptance": "eligible", "head_sha": "a" * 40,
            "policy_version": "test", "reasons": ["green"],
        }) + "\n```"
        pr_view = {
            **FakeGh().pr_view,
            "autoMergeRequest": {"enabledAt": "now"},
        }
        team, _ = producer(FakeGh(
            items=board_with((21, "Delivery", "In Review", "qa")),
            comments=[acceptance],
            pr_state={"state": "OPEN", "mergedAt": None},
            pr_view=pr_view,
        ), monitor_poll_seconds=9)
        action = team.next_actions()["actions"][0]
        self.assertEqual(action["kind"], "monitor")
        self.assertEqual(action["poll_after_seconds"], 9)

    def test_next_actions_exposes_the_configured_recovery_policy(self):
        team, _ = producer(
            FakeGh(items=[]),
            recovery={
                "max_retries": 3,
                "initial_backoff_seconds": 2,
                "backoff_multiplier": 3,
                "max_backoff_seconds": 10,
            },
        )
        result = team.next_actions()
        self.assertEqual(result["config_revision"], team.config.revision)
        self.assertEqual(
            result["recovery_policy"],
            {
                "max_retries": 3,
                "initial_backoff_seconds": 2.0,
                "backoff_multiplier": 3.0,
                "max_backoff_seconds": 10.0,
                "retry_delays_seconds": [2.0, 6.0, 10.0],
            },
        )

    def test_unarmed_eligible_acceptance_retries_the_controller(self):
        acceptance = ACCEPTANCE_MARKER + "\n\n```json\n" + json.dumps({
            "acceptance": "eligible", "head_sha": "a" * 40,
            "policy_version": "test", "reasons": ["green"],
        }) + "\n```"
        team, _ = producer(FakeGh(
            items=board_with((21, "Delivery", "In Review", "qa")),
            comments=[acceptance],
            pr_state={"state": "OPEN", "mergedAt": None},
        ))
        action = team.next_actions()["actions"][0]
        self.assertEqual(action["kind"], "controller")
        self.assertEqual(action["argv"], ["accept", "21"])

    def test_manual_merge_mode_exposes_an_explicit_human_gate(self):
        acceptance = ACCEPTANCE_MARKER + "\n\n```json\n" + json.dumps({
            "acceptance": "eligible", "head_sha": "a" * 40,
            "policy_version": "test", "reasons": ["green"],
        }) + "\n```"
        team, _ = producer(
            FakeGh(
                items=board_with((21, "Delivery", "In Review", "qa")),
                comments=[acceptance],
                pr_state={"state": "OPEN", "mergedAt": None},
            ),
            merge_mode="manual",
        )
        result = team.next_actions()
        self.assertEqual(result["actions"], [])
        self.assertEqual(len(result["human_gates"]), 1)
        gate = result["human_gates"][0]
        self.assertEqual(gate["gate"], "manual_merge")
        self.assertEqual(
            gate["pull_request"], f"https://github.com/{REPO}/pull/57"
        )

    def test_manual_spec_mode_waits_at_an_exact_pull_request_gate(self):
        pr_view = {
            **FakeGh().pr_view,
            "headRefOid": "f" * 40,
            "baseRefName": "main",
        }
        team, _ = producer(
            FakeGh(
                items=board_with(
                    (20, "Shaped requirement", "Backlog", "architect")
                ),
                comments=[manual_spec_comment()],
                pr_view=pr_view,
                pr_state={"state": "OPEN", "mergedAt": None},
            ),
            spec_merge_mode="manual",
        )
        result = team.next_actions()
        self.assertEqual(result["actions"], [])
        self.assertEqual(result["human_gates"][0]["gate"], "spec_merge")
        self.assertEqual(
            result["human_gates"][0]["pull_request"],
            f"https://github.com/{REPO}/pull/57",
        )

    def test_merged_manual_spec_becomes_a_controller_finalization(self):
        pr_view = {
            **FakeGh().pr_view,
            "headRefOid": "f" * 40,
            "baseRefName": "main",
        }
        team, _ = producer(
            FakeGh(
                items=board_with(
                    (20, "Shaped requirement", "Backlog", "architect")
                ),
                comments=[manual_spec_comment()],
                pr_view=pr_view,
                pr_state={
                    "state": "MERGED", "mergedAt": "now",
                    "mergeCommit": {"oid": "d" * 40},
                },
            ),
            spec_merge_mode="manual",
        )
        action = team.next_actions()["actions"][0]
        self.assertEqual(action["kind"], "controller")
        self.assertEqual(action["argv"], ["finalize-spec-merge", "20"])

    def test_changed_head_returns_to_fresh_qa_evidence(self):
        acceptance = ACCEPTANCE_MARKER + "\n\n```json\n" + json.dumps({
            "acceptance": "eligible", "head_sha": "z" * 40,
            "policy_version": "test", "reasons": ["green"],
        }) + "\n```"
        team, _ = producer(FakeGh(
            items=board_with((21, "Delivery", "In Review", "qa")),
            comments=[acceptance],
        ))
        action = team.next_actions()["actions"][0]
        self.assertEqual(action["kind"], "spawn")
        self.assertIn("head changed", action["prompt"])

    def test_changed_head_removes_a_stale_human_exception_automatically(self):
        acceptance = ACCEPTANCE_MARKER + "\n\n```json\n" + json.dumps({
            "acceptance": "protected_change", "head_sha": "z" * 40,
            "policy_version": "test", "reasons": ["protected"],
        }) + "\n```"
        team, _ = producer(FakeGh(
            items=board_with((21, "Delivery", "In Review", "human")),
            comments=[acceptance],
        ))
        result = team.next_actions()
        self.assertEqual(result["human_gates"], [])
        self.assertEqual(result["actions"][0]["kind"], "controller")
        self.assertEqual(
            result["actions"][0]["argv"], ["refresh-verification", "21"]
        )

    def test_ready_work_waits_when_board_wip_is_full(self):
        team, _ = producer(FakeGh(items=board_with(
            (4, "Build", "Ready", "dev"),
            (5, "Active", "In Progress", "dev"),
        )), wip_limit=1)
        result = team.next_actions()
        self.assertNotIn(4, [action["number"] for action in result["actions"]])
        self.assertIn("work-in-progress", next(
            entry["reason"] for entry in result["waiting"] if entry["number"] == 4
        ))

    def test_malformed_human_lanes_are_not_advertised_as_approval_gates(self):
        team, _ = producer(FakeGh(items=board_with(
            (20, "No spec", "Backlog", "human"),
            (21, "No acceptance", "In Review", "human"),
        )))
        result = team.next_actions()
        self.assertEqual(result["human_gates"], [])
        self.assertEqual({entry["number"] for entry in result["waiting"]}, {20, 21})

    def test_only_one_direct_spec_author_runs_at_a_time(self):
        team, _ = producer(FakeGh(items=board_with(
            (2, "First", "Backlog", "architect"),
            (3, "Second", "Backlog", "architect"),
        )))
        result = team.next_actions()
        self.assertEqual([action["number"] for action in result["actions"]], [2])
        self.assertIn("serialized", result["waiting"][0]["reason"])

    def test_returned_analyst_card_is_clarified_not_re_intaked(self):
        team, gh = producer(FakeGh(items=board_with(
            (7, "Clarify export", "Backlog", "analyst"),
        )))
        action = team.next_actions()["actions"][0]
        self.assertIn("Never run intake", action["prompt"])
        self.assertEqual(action["routine"], "clarifying-card")
        self.assertEqual(action["skill"], "agent-teams:clarifying-card")
        result = team.clarify(7, "CSV means RFC 4180 with a UTF-8 header row.")
        self.assertTrue(result["ok"])
        self.assertEqual(result["role"], "architect")
        self.assertEqual(gh.calls_matching("issue", "create"), [])

    def test_completed_decomposition_does_not_respawn_the_architect(self):
        team, _ = producer(FakeGh(
            items=board_with((20, "Parent", "Backlog", "architect")),
            comments=[SPEC_COMMENT, DECOMPOSITION_MARKER],
        ))
        result = team.next_actions()
        self.assertEqual(result["actions"], [])
        self.assertIn("decomposition is complete", result["waiting"][0]["reason"])

    def test_human_status_edit_becomes_an_automatic_readiness_handoff(self):
        team, _ = producer(FakeGh(
            items=board_with((20, "Ready decision", "Ready", "human")),
            comments=[SPEC_COMMENT],
        ))
        action = team.next_actions()["actions"][0]
        self.assertEqual(action["kind"], "controller")
        self.assertEqual(action["argv"], ["finalize-readiness", "20"])

    def test_unmet_hard_dependency_is_not_dispatched(self):
        items = board_with(
            (2, "Prerequisite", "In Progress", "dev"),
            (4, "Dependent", "Ready", "dev"),
            (5, "Independent", "Ready", "dev"),
        )
        team, _ = producer(FakeGh(
            items=items, issue_bodies={4: "depends-on: #2"}
        ), wip_limit=0)
        result = team.next_actions()
        action_numbers = {entry["number"] for entry in result["actions"]}
        self.assertIn(5, action_numbers)
        self.assertNotIn(4, action_numbers)
        dependent = next(
            entry for entry in result["waiting"] if entry["number"] == 4
        )
        self.assertEqual(dependent["dependencies"], [2])

    def test_blocked_card_spawns_one_bounded_lead_triage_stage(self):
        team, _ = producer(FakeGh(items=board_with(
            (9, "Blocked delivery", "Blocked", "architect"),
        )))
        action = team.next_actions()["actions"][0]
        self.assertEqual(action["role"], "lead")
        self.assertEqual(action["routine"], "triaging-board")
        self.assertIn("[expected:(Blocked, architect)]", action["prompt"])


WORKER_SEATS = ("architect", "analyst", "dev", "qa", "lead")


class WorkerSkillLoadingTests(unittest.TestCase):
    def test_every_seat_worker_loads_one_selected_skill_instead_of_preloading_all(self):
        agents_dir = Path(__file__).parents[1] / "agents"
        for seat in WORKER_SEATS:
            with self.subTest(seat=seat):
                worker = (agents_dir / f"{seat}-worker.md").read_text(
                    encoding="utf-8"
                )
                frontmatter = worker.split("---", 2)[1]
                self.assertIn(f"name: {seat}-worker", frontmatter)
                self.assertIn("Skill", frontmatter)
                self.assertNotIn("\nskills:", frontmatter)
                self.assertIn("invoke exactly", worker)
                self.assertIn("[skill:agent-teams:<name>]", worker)

    def test_no_generic_worker_remains(self):
        agents_dir = Path(__file__).parents[1] / "agents"
        self.assertFalse((agents_dir / "agent-teams-worker.md").exists())
        self.assertEqual(
            sorted(p.stem for p in agents_dir.glob("*.md")),
            sorted(f"{seat}-worker" for seat in WORKER_SEATS),
        )

    def test_spawn_actions_name_the_seat_specific_worker_agent(self):
        team, _ = producer(FakeGh(items=board_with(
            (9, "Blocked delivery", "Blocked", "architect"),
        )))
        action = team.next_actions()["actions"][0]
        self.assertEqual(action["kind"], "spawn")
        self.assertEqual(action["role"], "lead")
        self.assertEqual(action["agent"], "agent-teams:lead-worker")

    def test_dispatch_skill_obeys_the_external_recovery_policy(self):
        skill = (
            Path(__file__).parents[1]
            / "skills"
            / "dispatching-work"
            / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("recovery_policy", skill)
        self.assertIn("retry_delays_seconds", skill)
        self.assertIn("manual_merge", skill)
        self.assertIn("spec_merge", skill)
        self.assertIn("config_revision", skill)
        self.assertIn("discard every unstarted action", skill)
        self.assertNotIn("retry that identical action at most once", skill)
        self.assertNotIn("Keep that policy for this run", skill)

    def test_authoring_skill_stops_at_a_manual_specification_merge(self):
        skill = (
            Path(__file__).parents[1]
            / "skills"
            / "authoring-spec"
            / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("spec_merge_mode: manual", skill)
        self.assertIn("finalize-spec-merge", skill)
        self.assertIn("Do not hand off or decompose yet", skill)



class ReleaseClaimTests(unittest.TestCase):
    """Recovery for abandoned claims: branch delete -> Ready -> comment."""

    def test_release_deletes_the_branch_then_readies_then_comments(self):
        team, gh = producer()
        outcome = team.release_claim(23, "claim/23-active-build", Role.HUMAN)
        self.assertTrue(outcome["ok"])
        self.assertEqual(
            outcome["completed"],
            ["branch_deleted", "status_set", "release_comment"],
        )
        deletes = gh.calls_matching("api", "-X")
        self.assertEqual(len(deletes), 1)
        self.assertIn(f"repos/{REPO}/git/refs/heads/claim/23-active-build", deletes[0])
        edits = gh.calls_matching("project", "item-edit")
        self.assertEqual(len(edits), 1)
        self.assertIn("STATUS_READY", edits[0])
        self.assertEqual(len(gh.calls_matching("issue", "comment")), 1)
        self.assertIn("claim/23-active-build", outcome["comment"])

    def test_every_agent_seat_is_refused_before_any_call(self):
        for seat in (Role.ANALYST, Role.ARCHITECT, Role.DEV, Role.QA, Role.LEAD):
            with self.subTest(seat=seat):
                team, gh = producer()
                with self.assertRaises(policy.ActionForbidden):
                    team.release_claim(23, "claim/23-active-build", seat)
                self.assertEqual(gh.calls, [])

    def test_refuses_a_card_that_is_not_in_progress(self):
        # Backlog -> Ready via release-claim would bypass the promote spec
        # gate; Ready -> Ready would be a no-op lie. Both refuse.
        team, gh = producer()
        with self.assertRaisesRegex(WorkflowError, "recovers abandoned claims"):
            team.release_claim(12, "claim/12-implement-parser", Role.HUMAN)
        self.assertEqual(gh.calls_matching("api", "-X"), [])
        self.assertEqual(gh.calls_matching("project", "item-edit"), [])

    def test_refuses_to_delete_a_mainline_branch(self):
        team, gh = producer()
        with self.assertRaisesRegex(WorkflowError, "never a mainline"):
            team.release_claim(23, "main", Role.HUMAN)
        self.assertEqual(gh.calls, [])

    def test_requires_a_branch_name(self):
        team, gh = producer()
        with self.assertRaisesRegex(WorkflowError, "--branch"):
            team.release_claim(23, "   ", Role.HUMAN)
        self.assertEqual(gh.calls, [])

    def test_flags_a_released_card_no_seat_will_dispatch(self):
        gh = FakeGh(items=board_with((30, "Orphaned build", "In Progress", "human")))
        team, _ = producer(gh)
        outcome = team.release_claim(30, "claim/30-orphaned-build", Role.HUMAN)
        self.assertTrue(outcome["ok"])
        self.assertIn("not a dispatchable seat", outcome["note"])


if __name__ == "__main__":
    unittest.main()
