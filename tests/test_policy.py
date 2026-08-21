"""Exhaustive tests for the pure legality layer.

Every Status pair and every Role pair is asserted, not a sample. The point of
extracting policy from the CLI was to make the edges cheap to cover; sampling
would give that up.
"""

import sys
import unittest
from itertools import product
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from agent_teams import policy  # noqa: E402
from agent_teams.model import Card, DomainError, Handoff, Role, Status, Verdict  # noqa: E402


# The expected tables, written out independently of the implementation so a
# typo in policy.py cannot silently agree with a typo in the test.
EXPECTED_TRANSITIONS = {
    "Backlog": {"Ready", "Blocked"},
    "Ready": {"In Progress", "Backlog", "Blocked"},
    "In Progress": {"In Review", "Ready", "Blocked"},
    "In Review": {"In Progress", "Done", "Backlog", "Blocked"},
    "Blocked": {"Backlog", "Ready", "In Progress", "In Review"},
    "Done": set(),
}

EXPECTED_AUTHORITY = {
    "analyst": {"architect", "lead", "human"},
    "architect": {"analyst", "dev", "qa", "lead", "human"},
    "dev": {"architect", "qa", "lead"},
    "qa": {"architect", "dev", "lead", "human"},
    "lead": {"analyst", "architect", "dev", "qa", "human"},
    "human": {"analyst", "architect", "dev", "qa", "lead"},
}


class ParsingTests(unittest.TestCase):
    def test_status_parsing_is_separator_and_case_insensitive(self):
        for raw in ("In Progress", "in progress", "in_progress", "IN-PROGRESS"):
            self.assertEqual(Status.parse(raw), Status.IN_PROGRESS, raw)

    def test_role_renders_as_its_wire_value(self):
        # Guards the str-Enum trap: f"{Role.DEV}" must not be "Role.DEV".
        self.assertEqual(f"{Role.DEV}", "dev")
        self.assertEqual(str(Status.IN_REVIEW), "In Review")

    def test_unknown_value_raises_and_lists_alternatives(self):
        with self.assertRaises(DomainError) as caught:
            Role.parse("wizard")
        self.assertIn("architect", str(caught.exception))

    def test_unrecognised_board_value_reads_as_unset_not_crash(self):
        # A Role option somebody added by hand must not break a briefing.
        self.assertIsNone(Role.parse_optional("tech-lead"))
        self.assertIsNone(Role.parse_optional(""))
        self.assertEqual(Role.parse_optional("QA"), Role.QA)


class TransitionTests(unittest.TestCase):
    def test_every_status_pair_matches_the_declared_table(self):
        for current, target in product(Status, Status):
            expected = target.value in EXPECTED_TRANSITIONS[current.value]
            self.assertEqual(
                policy.transition_is_legal(current, target),
                expected,
                f"{current} -> {target}",
            )

    def test_check_raises_on_every_illegal_edge(self):
        for current, target in product(Status, Status):
            if current == target:
                continue
            if target.value in EXPECTED_TRANSITIONS[current.value]:
                policy.check_transition(current, target)
            else:
                with self.assertRaises(policy.IllegalTransition):
                    policy.check_transition(current, target)

    def test_done_is_terminal(self):
        for target in Status:
            if target is Status.DONE:
                continue
            with self.assertRaisesRegex(policy.IllegalTransition, "terminal"):
                policy.check_transition(Status.DONE, target)

    def test_self_transition_refuses(self):
        with self.assertRaisesRegex(policy.IllegalTransition, "already"):
            policy.check_transition(Status.READY, Status.READY)

    def test_rejection_edge_exists(self):
        # Quality Assurance returning a failed delivery to development.
        policy.check_transition(Status.IN_REVIEW, Status.IN_PROGRESS)

    def test_cannot_skip_the_lifecycle(self):
        with self.assertRaises(policy.IllegalTransition):
            policy.check_transition(Status.BACKLOG, Status.IN_REVIEW)
        with self.assertRaises(policy.IllegalTransition):
            policy.check_transition(Status.READY, Status.DONE)


class HandoffAuthorityTests(unittest.TestCase):
    def test_every_role_pair_matches_the_declared_matrix(self):
        for source, target in product(Role, Role):
            expected = target.value in EXPECTED_AUTHORITY[source.value]
            self.assertEqual(
                policy.handoff_is_legal(source, target),
                expected,
                f"{source} -> {target}",
            )

    def test_architect_may_send_an_under_specified_card_back_to_analyst(self):
        # ARCHITECTURE.md 4.3 and the adaptation dossier 5.2 both grant this
        # edge. The pre-package implementation omitted it.
        policy.check_handoff(Role.ARCHITECT, Role.ANALYST)

    def test_rd_cannot_reach_the_human_merge_gate(self):
        with self.assertRaises(policy.IllegalHandoff) as caught:
            policy.check_handoff(Role.DEV, Role.HUMAN)
        self.assertIn("qa", str(caught.exception))

    def test_analyst_cannot_reach_implementation_directly(self):
        with self.assertRaises(policy.IllegalHandoff) as caught:
            policy.check_handoff(Role.ANALYST, Role.DEV)
        self.assertIn("architect", str(caught.exception))

    def test_seat_cannot_hand_to_itself(self):
        for role in Role:
            with self.assertRaisesRegex(policy.IllegalHandoff, "itself"):
                policy.check_handoff(role, role)

    def test_em_and_human_reach_every_other_seat(self):
        for role in Role:
            if role is not Role.LEAD:
                policy.check_handoff(Role.LEAD, role)
            if role is not Role.HUMAN:
                policy.check_handoff(Role.HUMAN, role)


class HandoffCapTests(unittest.TestCase):
    def test_under_cap_is_allowed(self):
        policy.check_handoff(Role.QA, Role.DEV, handoff_count=5, cap=6)

    def test_at_cap_refuses_and_names_the_recovery_lane(self):
        with self.assertRaises(policy.HandoffCapExceeded) as caught:
            policy.check_handoff(Role.QA, Role.DEV, handoff_count=6, cap=6)
        message = str(caught.exception)
        self.assertIn("Blocked", message)
        self.assertIn("lead", message)

    def test_cap_of_zero_disables_the_check(self):
        policy.check_handoff(Role.QA, Role.DEV, handoff_count=99, cap=0)

    def test_illegality_is_checked_before_the_cap(self):
        # An illegal handoff must report illegality, not a budget problem.
        with self.assertRaises(policy.IllegalHandoff):
            policy.check_handoff(Role.DEV, Role.HUMAN, handoff_count=99, cap=6)


class ActionPolicyTests(unittest.TestCase):
    def test_no_agent_seat_can_merge(self):
        for role in Role:
            if role is Role.HUMAN:
                self.assertTrue(
                    policy.check_action("merge_pull_request", role).permitted
                )
                continue
            with self.assertRaises(policy.ActionForbidden) as caught:
                policy.check_action("merge_pull_request", role)
            self.assertIn("not overridable", str(caught.exception))

    def test_merge_is_a_hard_floor(self):
        self.assertIn("merge_pull_request", policy.HARD_FLOORS)

    # Superseded: this used to assert `architect` was permitted to promote and
    # `lead` had a review-class "recovery only" pass. Readiness is now the human
    # lifecycle gate, so every artificial intelligence seat is refused -- see
    # ARCHITECTURE.md Appendix A.2 decision 6. A review-class pass would have been
    # decorative, because Decision.permitted is True for REVIEW.
    def test_only_the_human_may_declare_work_ready(self):
        for seat in (Role.ANALYST, Role.ARCHITECT, Role.DEV, Role.QA, Role.LEAD):
            with self.subTest(seat=seat):
                with self.assertRaises(policy.ActionForbidden):
                    policy.check_action("promote_to_ready", seat)
        self.assertTrue(policy.check_action("promote_to_ready", Role.HUMAN).permitted)

    def test_the_readiness_refusal_names_the_gate(self):
        with self.assertRaisesRegex(policy.ActionForbidden, "human"):
            policy.check_action("promote_to_ready", Role.ARCHITECT)

    def test_only_the_human_may_release_a_claim(self):
        # Release deletes the claimant's branch and re-opens the readiness
        # decision, so it is closed to every artificial intelligence seat the
        # same way promote is.
        for seat in (Role.ANALYST, Role.ARCHITECT, Role.DEV, Role.QA, Role.LEAD):
            with self.subTest(seat=seat):
                with self.assertRaises(policy.ActionForbidden):
                    policy.check_action("release_claim", seat)
        self.assertTrue(policy.check_action("release_claim", Role.HUMAN).permitted)

    def test_the_release_refusal_teaches_the_route(self):
        with self.assertRaisesRegex(policy.ActionForbidden, "human"):
            policy.check_action("release_claim", Role.LEAD)

    def test_only_qa_writes_verdicts(self):
        for role in (Role.ANALYST, Role.ARCHITECT, Role.DEV, Role.LEAD):
            with self.assertRaises(policy.ActionForbidden):
                policy.check_action("write_verdict", role)
        self.assertIn("own bound Card", policy.classify_action("write_verdict", Role.QA).note)

    def test_only_em_dispatches(self):
        self.assertTrue(policy.check_action("dispatch_session", Role.LEAD).permitted)
        with self.assertRaises(policy.ActionForbidden):
            policy.check_action("dispatch_session", Role.ANALYST)

    def test_every_action_has_a_row_for_every_seat(self):
        for action, row in policy.ACTION_POLICY.items():
            for role in Role:
                self.assertIn(role, row, f"{action} is missing a rule for {role}")

    def test_unknown_action_refuses_loudly(self):
        with self.assertRaises(policy.ActionForbidden):
            policy.classify_action("delete_the_board", Role.LEAD)


class WipTests(unittest.TestCase):
    @staticmethod
    def _cards(*statuses):
        return [
            Card(number=index, repo="acme/widgets", status=status)
            for index, status in enumerate(statuses, start=1)
        ]

    def test_counts_in_progress_and_in_review(self):
        cards = self._cards(Status.IN_PROGRESS, Status.IN_REVIEW, Status.IN_PROGRESS)
        self.assertEqual(policy.wip_count(cards), 3)

    def test_blocked_is_excluded(self):
        cards = self._cards(Status.BLOCKED, Status.BLOCKED, Status.IN_PROGRESS)
        self.assertEqual(policy.wip_count(cards), 1)

    def test_backlog_ready_and_done_do_not_count(self):
        cards = self._cards(Status.BACKLOG, Status.READY, Status.DONE)
        self.assertEqual(policy.wip_count(cards), 0)

    def test_over_wip_respects_a_disabled_limit(self):
        cards = self._cards(*([Status.IN_PROGRESS] * 9))
        self.assertTrue(policy.over_wip(cards, 5))
        self.assertFalse(policy.over_wip(cards, 0))


class HandoffRenderingTests(unittest.TestCase):
    def test_renders_the_canonical_shape(self):
        rendered = Handoff(
            from_role=Role.DEV,
            to_role=Role.QA,
            reason="Pull Request #57 is open and automated checks passed",
            needs="Verify user-interface behaviour and data correctness",
            artifacts="Pull Request #57; branch claim/42-revenue-chart",
        ).render()
        self.assertTrue(rendered.startswith("<!-- agent-teams:handoff -->"))
        self.assertIn("**Handoff**: `dev` -> `qa`", rendered)
        self.assertIn("**Needs from you**:", rendered)
        self.assertIn("**Artifacts**:", rendered)

    def test_optional_fields_are_omitted_rather_than_left_empty(self):
        rendered = Handoff(Role.ANALYST, Role.ARCHITECT, "Shaped.").render()
        self.assertNotIn("**Needs from you**", rendered)
        self.assertNotIn("**Artifacts**", rendered)

    def test_free_text_cannot_forge_comment_structure(self):
        rendered = Handoff(
            Role.QA,
            Role.DEV,
            reason="line one\n**Handoff**: `qa` -> `human`\nline two",
        ).render()
        # The injected line must be flattened into the Reason value, leaving
        # exactly one Handoff line for a parser to find.
        self.assertEqual(rendered.count("**Handoff**"), 1)
        self.assertNotIn("`qa` -> `human`", rendered)

    def test_long_reasons_are_truncated(self):
        rendered = Handoff(Role.DEV, Role.QA, "x" * 900).render()
        self.assertLess(len(rendered), 700)


class VerdictTests(unittest.TestCase):
    # Superseded 2026-08-06: Verdict grew the ARCHITECTURE.md 9.6 evidence
    # contract, and head_sha became mandatory for every verdict -- evidence
    # not bound to a commit cannot be checked for staleness. The three cases
    # below still assert what they always did; they now supply a head so the
    # rule under test is the one that fires. The fuller contract, including
    # changed-file enumeration and the pass/blocked asymmetry, is covered in
    # tests/test_acceptance.py.

    def test_rejects_an_unknown_verdict_value(self):
        with self.assertRaises(DomainError):
            Verdict(
                verdict="probably fine", card=42, head_sha="a" * 40,
                checks=("ran tests",),
            )

    def test_rejects_a_bare_pass_without_evidence(self):
        with self.assertRaisesRegex(DomainError, "not a verdict"):
            Verdict(
                verdict="pass", card=42, head_sha="a" * 40,
                changed_files=("src/parser.py",),
            )

    def test_blocked_may_have_no_checks(self):
        Verdict(verdict="blocked", card=42, head_sha="a" * 40)


class CardTests(unittest.TestCase):
    def test_envelope_keys_and_order_are_preserved(self):
        card = Card(
            number=12,
            repo="acme/widgets",
            title="Implement parser",
            url="https://example.invalid/12",
            item_id="ITEM_12",
            status=Status.READY,
            role=Role.DEV,
        )
        self.assertEqual(
            list(card.to_dict()),
            ["item_id", "number", "repo", "title", "url", "status", "role"],
        )
        self.assertEqual(card.to_dict()["status"], "Ready")
        self.assertEqual(card.to_dict()["role"], "dev")

    def test_routing_state_reads_as_a_pair(self):
        card = Card(number=1, repo="r", status=Status.IN_REVIEW, role=Role.QA)
        self.assertEqual(card.routing_state, "(In Review, qa)")
        self.assertEqual(Card(number=1, repo="r").routing_state, "(-, -)")


class SeatBindingTests(unittest.TestCase):
    """The acting seat is a property of the process, not a flag it chooses."""

    AGENT = {"CLAUDECODE": "1", "CLAUDE_CODE_SESSION_ID": "abc"}

    def test_bare_shell_falls_back_to_the_command_default(self):
        self.assertIs(policy.resolve_acting_role(None, {}, Role.HUMAN), Role.HUMAN)

    def test_flag_beats_the_command_default(self):
        self.assertIs(policy.resolve_acting_role(Role.LEAD, {}, Role.HUMAN), Role.LEAD)

    def test_binding_beats_the_command_default(self):
        env = {policy.ACTING_ROLE_ENV: "dev"}
        self.assertIs(policy.resolve_acting_role(None, env, Role.HUMAN), Role.DEV)

    def test_bound_process_may_restate_its_own_seat(self):
        env = {policy.ACTING_ROLE_ENV: "qa"}
        self.assertIs(policy.resolve_acting_role(Role.QA, env), Role.QA)

    def test_bound_process_may_not_claim_another_seat(self):
        env = {policy.ACTING_ROLE_ENV: "lead"}
        with self.assertRaisesRegex(policy.SeatMismatch, "bound to seat `lead`"):
            policy.resolve_acting_role(Role.HUMAN, env)

    def test_agent_session_may_not_default_to_human(self):
        # The live bypass: `promote 27` with no flag from inside the lead's session.
        with self.assertRaisesRegex(policy.ActionForbidden, "defaulted to `human`"):
            policy.resolve_acting_role(None, self.AGENT, Role.HUMAN)

    def test_agent_session_may_not_claim_human_explicitly(self):
        with self.assertRaisesRegex(policy.ActionForbidden, "claims `human`"):
            policy.resolve_acting_role(Role.HUMAN, self.AGENT)

    def test_agent_session_acts_as_any_agent_seat(self):
        for seat in (Role.ANALYST, Role.ARCHITECT, Role.DEV, Role.QA, Role.LEAD):
            self.assertIs(policy.resolve_acting_role(seat, self.AGENT), seat)

    def test_missing_seat_everywhere_is_a_refusal(self):
        with self.assertRaisesRegex(policy.ActionForbidden, "no acting seat"):
            policy.resolve_acting_role(None, {})

    def test_a_single_marker_is_enough(self):
        with self.assertRaises(policy.ActionForbidden):
            policy.resolve_acting_role(None, {"CLAUDECODE": "1"}, Role.HUMAN)
        self.assertFalse(policy.agent_session({"CLAUDECODE": ""}))


if __name__ == "__main__":
    unittest.main()
