"""Producer routine behaviour: the four flows from ARCHITECTURE.md section 6."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).parent))

from agent_teams import policy  # noqa: E402
from agent_teams.board import Board  # noqa: E402
from agent_teams.config import Config  # noqa: E402
from agent_teams.model import Role, Status  # noqa: E402
from agent_teams.workflows import Producer, WorkflowError  # noqa: E402
from fake_gh import REPO, FakeGh, board_with  # noqa: E402

SPEC_PR = "https://github.com/acme/widgets/pull/57"


def producer(gh=None, **config_overrides):
    gh = gh or FakeGh()
    base = {"repo": REPO, "project_owner": "acme", "project_number": 1}
    base.update(config_overrides)
    config = Config.from_dict(base)
    return Producer(config, Board(config, gh)), gh


class SpecGateTests(unittest.TestCase):
    """The settled M2 decision: Ready requires a durable specification."""

    def test_merged_pull_request_satisfies_the_merged_policy(self):
        team, _ = producer()
        gate = team.check_spec_gate(SPEC_PR)
        self.assertTrue(gate["satisfied"])
        self.assertEqual(gate["state"], "MERGED")

    def test_open_pull_request_is_refused_under_the_merged_policy(self):
        gh = FakeGh(pr_state={"state": "OPEN", "mergedAt": None})
        team, _ = producer(gh)
        gate = team.check_spec_gate(SPEC_PR)
        self.assertFalse(gate["satisfied"])
        # The refusal must name the escape hatch, not just say no.
        self.assertIn("spec_completion=merged", gate["explanation"])
        self.assertIn("spec_completion=opened", gate["explanation"])

    def test_open_pull_request_satisfies_the_opened_policy(self):
        gh = FakeGh(pr_state={"state": "OPEN", "mergedAt": None})
        team, _ = producer(gh, spec_completion="opened")
        self.assertTrue(team.check_spec_gate(SPEC_PR)["satisfied"])

    def test_closed_unmerged_is_refused_under_both_policies(self):
        gh = FakeGh(pr_state={"state": "CLOSED", "mergedAt": None})
        for completion in ("merged", "opened"):
            team, _ = producer(FakeGh(pr_state=gh.pr_state), spec_completion=completion)
            gate = team.check_spec_gate(SPEC_PR)
            self.assertFalse(gate["satisfied"], completion)

    def test_a_durable_path_needs_no_pull_request_lookup(self):
        team, gh = producer()
        gate = team.check_spec_gate("docs/architecture/0007-parser.md")
        self.assertTrue(gate["satisfied"])
        self.assertEqual(gate["state"], "pointer")
        self.assertEqual(gh.calls_matching("pr", "view"), [])

    def test_a_bare_number_is_read_as_a_pull_request(self):
        team, gh = producer()
        self.assertTrue(team.check_spec_gate("#57")["satisfied"])
        self.assertEqual(len(gh.calls_matching("pr", "view")), 1)

    def test_no_reference_refuses(self):
        team, _ = producer()
        gate = team.check_spec_gate("")
        self.assertFalse(gate["satisfied"])
        self.assertIn("--spec", gate["explanation"])


#: A Card the architect has already shaped and handed to the human for the
#: readiness decision -- the state `promote` now expects to act on.
AT_THE_GATE = board_with((20, "Shaped requirement", "Backlog", "human"))


class PromoteTests(unittest.TestCase):
    # Superseded throughout: `promote` used to default to the architect, who
    # could declare its own work Ready. Readiness is now the human lifecycle
    # gate (ARCHITECTURE.md Appendix A.2 decision 6), so these act as `human` on a Card
    # the architect handed over.
    def test_the_human_promotes_and_hands_to_development(self):
        team, gh = producer(FakeGh(items=AT_THE_GATE))
        result = team.promote(20, SPEC_PR)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "Ready")
        self.assertEqual(result["role"], "rd")
        self.assertEqual(result["completed"], ["status_set", "role_set"])
        # Two independent semantic operations, in the documented order.
        edits = gh.calls_matching("project", "item-edit")
        self.assertIn("STATUS_READY", edits[0])
        self.assertIn("ROLE_RD", edits[1])

    def test_refuses_when_the_specification_is_not_durable(self):
        gh = FakeGh(items=AT_THE_GATE, pr_state={"state": "OPEN", "mergedAt": None})
        team, _ = producer(gh)
        with self.assertRaises(WorkflowError):
            team.promote(20, SPEC_PR)
        self.assertEqual(gh.calls_matching("project", "item-edit"), [])

    def test_no_agent_seat_can_promote_even_its_own_work(self):
        for seat in (Role.ANALYST, Role.ARCHITECT, Role.RD, Role.QA, Role.EM):
            with self.subTest(seat=seat):
                gh = FakeGh(items=AT_THE_GATE)
                team, _ = producer(gh)
                with self.assertRaises(policy.ActionForbidden):
                    team.promote(20, SPEC_PR, seat)
                self.assertEqual(gh.calls_matching("project", "item-edit"), [])

    def test_refuses_a_card_owned_by_another_seat(self):
        team, _ = producer()
        with self.assertRaisesRegex(WorkflowError, "owned by"):
            team.promote(21, SPEC_PR)  # #21 is (In Review, qa)

    def test_refuses_a_card_whose_status_cannot_reach_ready(self):
        team, _ = producer(FakeGh(items=board_with((8, "Already Ready", "Ready", "human"))))
        with self.assertRaises(policy.IllegalTransition):
            team.promote(8, SPEC_PR)

    def test_the_architect_cannot_reach_ready_by_any_other_door(self):
        # The destination rule (16.1 decision 5) means closing `promote` closes
        # `create-card` and `transition` too. Assert that, rather than trust it.
        gh = FakeGh(items=AT_THE_GATE)
        team, _ = producer(gh)
        with self.assertRaises(policy.ActionForbidden):
            team.create_card("t", "b", Status.READY, Role.RD, Role.ARCHITECT)
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
        with self.assertRaisesRegex(policy.ActionForbidden, "reconcile done"):
            team.create_card("t", "b", Status.DONE, Role.HUMAN, Role.ANALYST)
        self.assertEqual(gh.calls_matching("issue", "create"), [])

    def test_the_analyst_cannot_create_a_card_in_the_development_lane(self):
        # Section 6.4: the System Analyst cannot hand directly to `rd`.
        # Creating the Card already owned by `rd` is that handoff, pre-baked.
        team, gh = producer()
        with self.assertRaises(policy.IllegalHandoff):
            team.create_card("t", "b", Status.BACKLOG, Role.RD, Role.ANALYST)
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
        team, gh = producer()
        result = team.decompose(
            20,
            [
                {"title": "Parser core", "body": "Acceptance: parses JSON."},
                {"title": "Parser errors", "body": "Acceptance: reports position."},
            ],
            SPEC_PR,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["created"]), 2)
        self.assertTrue(result["summary_comment_posted"])
        # Superseded: children used to be created at (Ready, rd), which put
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

    def test_only_the_architect_may_split_work(self):
        team, gh = producer()
        with self.assertRaises(policy.ActionForbidden):
            team.decompose(20, [{"title": "t", "body": "b"}], SPEC_PR, Role.RD)
        self.assertEqual(gh.calls_matching("issue", "create"), [])

    def test_refuses_without_a_durable_specification(self):
        gh = FakeGh(pr_state={"state": "OPEN", "mergedAt": None})
        team, _ = producer(gh)
        with self.assertRaises(WorkflowError):
            team.decompose(20, [{"title": "t", "body": "b"}], SPEC_PR)

    def test_refuses_an_empty_decomposition(self):
        team, _ = producer()
        with self.assertRaisesRegex(WorkflowError, "at least one"):
            team.decompose(20, [], SPEC_PR)


class BriefTests(unittest.TestCase):
    def test_groups_by_role_lane(self):
        team, _ = producer()
        report = team.brief()
        self.assertIn("rd", report["lanes"])
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
                    "id": f"ITEM_{n}", "status": "In Progress", "role": "rd",
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
        self.assertEqual([c["number"] for c in report["by_responsible_seat"]["rd"]], [9])

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
            Role.EM: "lanes",
        }
        for seat, key in expected.items():
            self.assertIn(key, team.bootstrap(seat)["seat_view"], seat)

    def test_the_architect_sees_work_waiting_on_it(self):
        team, _ = producer()
        view = team.bootstrap(Role.ARCHITECT)["seat_view"]
        self.assertEqual([c["number"] for c in view["awaiting_shaping"]], [20])

    def test_reports_missing_standing_context_rather_than_guessing(self):
        team, _ = producer()
        result = team.bootstrap(Role.EM, repo_root=Path("/nonexistent-root"))
        self.assertEqual(
            result["context_pointers_missing"],
            [entry["path"] for entry in result["standing_context"]],
        )

    def test_lists_the_routines_the_seat_may_run(self):
        team, _ = producer()
        self.assertIn("intake", team.bootstrap(Role.ANALYST)["routines"])
        self.assertNotIn("intake", team.bootstrap(Role.QA)["routines"])
        self.assertEqual(team.bootstrap(Role.RD)["routines"], [])


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


if __name__ == "__main__":
    unittest.main()
