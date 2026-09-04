"""The QA -> specification feedback loop.

Before 2026-09-04 a Quality Assurance finding had exactly one destination:
`fail` routed to `defect` routed to `dev`. When the defect's cause was the
*specification*, that sent it to the one seat forbidden from changing a
specification. What actually happened live was that a person edited the
document by hand and approved their own edit, with nothing on the Card saying
a request had ever been made.

These tests pin the four properties that make the new route trackable rather
than merely possible:

1. a request routes to the human lane whatever the verdict value;
2. a request the architect cannot diff is refused before it is published;
3. no agent seat, `lead` included, may approve one;
4. a Card whose specification is disputed offers no merge button.

See docs/decisions/2026-09-04-qa-spec-feedback-loop.md.
"""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).parent))

from agent_teams import policy  # noqa: E402
from agent_teams.board import Board  # noqa: E402
from agent_teams.config import Config  # noqa: E402
from agent_teams.errors import AgentTeamsError  # noqa: E402
from agent_teams.model import (  # noqa: E402
    ACCEPTANCE_MARKER, REQUIRED_DIMENSIONS, Role, SPEC_CHANGE_MARKER,
    VERDICT_MARKER, Verdict,
)
from agent_teams.workflows import Consumer, Producer  # noqa: E402
from fake_gh import FakeGh, FakeGit, REPO, board_with  # noqa: E402


A_REQUEST = {
    "document": "docs/specs/2026-08-28-store-search.md",
    "clause": "AC4",
    "conflict": (
        "AC4 requires a visible error when the data files fail to load, but "
        "AC2 specifies loading them as an ES module over file://, which "
        "Chrome and Safari block before any handler runs. The two criteria "
        "cannot both hold."
    ),
    "suggested_change": (
        "replace the ES-module load in AC2 with a classic script plus an "
        "explicit fetch, so the failure is observable and AC4 is reachable"
    ),
}


def a_config(**overrides):
    base = {"repo": REPO, "project_owner": "acme", "project_number": 1}
    base.update(overrides)
    return Config.from_dict(base)


def a_pass(**overrides):
    base = dict(
        verdict="pass",
        card=21,
        pull_request=f"https://github.com/{REPO}/pull/57",
        head_sha="a" * 40,
        review_dimensions=tuple(REQUIRED_DIMENSIONS),
        changed_files=("src/search.js",),
        test_strength=(
            {"dimension": "branch", "evidence": "12/12",
             "falsified_by": "broke the guard -> test_rejects_empty failed"},
        ),
        checks=("python -m unittest discover: 43 passed",),
        next_role=Role.QA,
    )
    base.update(overrides)
    return Verdict(**base)


def a_fail(**overrides):
    base = dict(
        verdict="fail",
        card=21,
        pull_request=f"https://github.com/{REPO}/pull/57",
        head_sha="a" * 40,
        checks=("python -m unittest discover: 1 failed",),
        findings=({
            "severity": "high", "dimension": "correctness", "confidence": 9,
            "evidence": "the error banner never renders",
        },),
        next_role=Role.DEV,
    )
    base.update(overrides)
    return Verdict(**base)


def pr_facts(**overrides):
    base = {
        "head_sha": "a" * 40,
        "changed_files": ("src/search.js",),
        "checks": {"test": "SUCCESS"},
        "draft": False,
        "mergeable": True,
        "merged": False,
    }
    base.update(overrides)
    return base


def _block(marker, payload):
    return marker + "\n\n```json\n" + json.dumps(payload) + "\n```"


def verdict_comment(verdict):
    return _block(VERDICT_MARKER, verdict.to_dict())


def protected_acceptance(head_sha="a" * 40):
    return _block(ACCEPTANCE_MARKER, {
        "acceptance": "protected_change", "head_sha": head_sha,
        "policy_version": "test", "reasons": ["specification in conflict"],
    })


# --------------------------------------------------------------- the route


class SpecChangeRoutingTests(unittest.TestCase):
    """`evaluate_acceptance` sends a specification conflict to the human."""

    def _route(self, verdict, **pr_overrides):
        return policy.evaluate_acceptance(
            verdict, pr_facts(**pr_overrides), a_config()
        )

    def test_a_fail_without_a_request_still_routes_to_dev(self):
        """The regression guard. The ordinary defect path is unchanged."""
        self.assertEqual(self._route(a_fail()).acceptance, "defect")

    def test_a_fail_carrying_a_request_routes_to_the_human_not_to_dev(self):
        """The whole point: `dev` may not change a specification.

        Routing this to `defect` is what the system did before, and it is why
        the Card bounced or a person repaired the document off the record.
        """
        acceptance = self._route(a_fail(spec_change_requests=(A_REQUEST,)))
        self.assertEqual(acceptance.acceptance, "protected_change")

    def test_a_pass_carrying_a_request_does_not_become_eligible(self):
        """"The delivery is fine and the spec is still wrong" is allowed to be
        said -- and it is not allowed to auto-merge.

        QA is asserting the baseline this delivery was built against is wrong.
        A person should see that before it lands, and `protected_change` is
        already the lane where a person decides.
        """
        acceptance = self._route(a_pass(spec_change_requests=(A_REQUEST,)))
        self.assertEqual(acceptance.acceptance, "protected_change")

    def test_the_reasons_name_the_document_and_the_clause(self):
        """A route nobody can read is not a trackable flow."""
        acceptance = self._route(a_fail(spec_change_requests=(A_REQUEST,)))
        joined = " ".join(acceptance.reasons)
        self.assertIn("docs/specs/2026-08-28-store-search.md", joined)
        self.assertIn("AC4", joined)

    def test_the_request_is_checked_before_the_fail_branch(self):
        """Ordering, asserted directly because it is the behaviour change.

        A specification conflict is usually reported on a `fail`, so a branch
        placed after the `fail` check would never be reached in the common
        case and the feature would look implemented while doing nothing.
        """
        verdict = a_fail(spec_change_requests=(A_REQUEST,))
        self.assertNotEqual(self._route(verdict).acceptance, "defect")

    def test_a_blocked_verdict_with_a_request_names_the_specification(self):
        """`blocked` already reached the human; what changes is *why*."""
        verdict = Verdict(
            verdict="blocked", card=21, head_sha="a" * 40,
            blind_spots=("cannot tell which criterion governs",),
            spec_change_requests=(A_REQUEST,),
        )
        acceptance = self._route(verdict)
        self.assertEqual(acceptance.acceptance, "protected_change")
        self.assertIn("specification", " ".join(acceptance.reasons))


# ----------------------------------------------------------- the validation


class SpecChangeValidationTests(unittest.TestCase):
    """A request the architect cannot act on is refused before publication."""

    def _problems(self, verdict):
        return policy.validate_verdict(
            verdict, "a" * 40, ("src/search.js",), a_config()
        )

    def test_a_complete_request_validates(self):
        self.assertEqual(self._problems(a_pass(spec_change_requests=(A_REQUEST,))), [])

    def test_a_verdict_without_requests_is_unaffected(self):
        """Occasional finding, not a section every verdict must fill in."""
        self.assertEqual(self._problems(a_pass()), [])

    def test_a_missing_field_is_named(self):
        for field in ("document", "clause", "conflict", "suggested_change"):
            with self.subTest(field=field):
                incomplete = {k: v for k, v in A_REQUEST.items() if k != field}
                problems = self._problems(
                    a_pass(spec_change_requests=(incomplete,))
                )
                self.assertTrue(
                    any(field in problem for problem in problems),
                    f"{field} was not named in {problems}",
                )

    def test_prose_instead_of_objects_is_refused(self):
        """Same rule as test_strength: a sentence cannot be checked."""
        problems = self._problems(
            a_pass(spec_change_requests=("the spec is wrong",))
        )
        self.assertTrue(problems)

    def test_a_request_on_a_fail_is_still_validated(self):
        """`validate_verdict` returns early for a non-pass verdict.

        A specification conflict is *most often* reported on a fail, so the
        check has to run before that early return or the validation would be
        dead code exactly where it matters.
        """
        problems = self._problems(
            a_fail(spec_change_requests=({"document": "docs/specs/x.md"},))
        )
        self.assertTrue(any("clause" in problem for problem in problems))

    def test_every_malformed_request_is_reported_in_one_pass(self):
        problems = self._problems(a_pass(spec_change_requests=(
            {"document": "docs/specs/a.md"},
            {"document": "docs/specs/b.md"},
        )))
        self.assertTrue(any("[0]" in problem for problem in problems))
        self.assertTrue(any("[1]" in problem for problem in problems))


# ------------------------------------------------------------- the authority


class SpecChangeAuthorityTests(unittest.TestCase):
    def test_no_agent_seat_may_approve_a_specification_change(self):
        """Including `lead`, and the reason is not symmetry.

        An agent seat that could reopen a specification on its own reading
        could rewrite the baseline it is judged against, which is what the
        design-conformance dimension rests on.
        """
        for seat in (Role.ANALYST, Role.ARCHITECT, Role.DEV, Role.QA, Role.LEAD):
            with self.subTest(seat=seat):
                with self.assertRaises(policy.ActionForbidden):
                    policy.check_action("approve_specification_change", seat)

    def test_the_human_may(self):
        decision = policy.check_action(
            "approve_specification_change", Role.HUMAN
        )
        self.assertTrue(decision.permitted)

    def test_the_refusal_teaches_the_route_that_does_exist(self):
        with self.assertRaises(policy.ActionForbidden) as caught:
            policy.check_action("approve_specification_change", Role.QA)
        message = str(caught.exception)
        self.assertIn("spec_change_requests", message)

    def test_it_is_not_a_hard_floor(self):
        """Nothing merges here, so it does not join the merge floor.

        Recorded as an assertion rather than an absence: HARD_FLOORS is the
        set whose refusals no override may widen, and quietly adding to it
        would change what `check_action` says without changing any behaviour
        a test would otherwise notice.
        """
        self.assertNotIn("approve_specification_change", policy.HARD_FLOORS)
        self.assertIn("merge_pull_request", policy.HARD_FLOORS)


# --------------------------------------------------------------- the command


class ApproveSpecChangeTests(unittest.TestCase):
    def _consumer(self, comments, role="human", status="In Review"):
        config = a_config()
        gh = FakeGh(
            items=board_with((21, "Delivery", status, role)),
            comments=comments,
        )
        return Consumer(config, Board(config, gh=gh), git=FakeGit()), gh

    def _comments(self, verdict=None):
        verdict = verdict or a_fail(spec_change_requests=(A_REQUEST,))
        return [verdict_comment(verdict), protected_acceptance()]

    def test_it_hands_the_card_to_the_architect(self):
        consumer, _ = self._consumer(self._comments())
        result = consumer.approve_spec_change(21, Role.HUMAN)
        self.assertTrue(result["ok"])
        self.assertEqual(result["role"], "architect")
        self.assertEqual(result["status"], "In Progress")

    def test_it_records_the_approved_request_on_the_card(self):
        """The trackability requirement, stated as an assertion.

        The team lead's instruction was that the human approval stays and the
        *record* is what has to change. A route that moved the Card without
        writing down which request was approved would satisfy the mechanics
        and miss the point entirely.
        """
        consumer, gh = self._consumer(self._comments())
        consumer.approve_spec_change(21, Role.HUMAN)
        posted = "\n".join(
            call[-1] for call in gh.calls_matching("issue", "comment")
        )
        self.assertIn(SPEC_CHANGE_MARKER, posted)
        self.assertIn("docs/specs/2026-08-28-store-search.md", posted)
        self.assertIn("AC4", posted)

    def test_it_records_the_surface_the_person_used(self):
        consumer, gh = self._consumer(self._comments())
        consumer.approve_spec_change(21, Role.HUMAN, origin="dashboard")
        posted = "\n".join(
            call[-1] for call in gh.calls_matching("issue", "comment")
        )
        self.assertIn("dashboard", posted)

    def test_it_refuses_an_agent_seat(self):
        consumer, gh = self._consumer(self._comments())
        with self.assertRaises(policy.ActionForbidden):
            consumer.approve_spec_change(21, Role.LEAD)
        # Authority is checked before the first GitHub call, so a refusal
        # costs nothing and leaves no partial state.
        self.assertEqual(gh.calls_matching("project", "item-edit"), [])

    def test_it_refuses_a_protected_change_carrying_no_request(self):
        """And points at the command that does apply.

        These are the two different things a person can do with a
        protected-change Card, and confusing them is how a delivery gets
        merged when what QA asked for was a specification revision.
        """
        consumer, _ = self._consumer(
            [verdict_comment(a_pass()), protected_acceptance()]
        )
        with self.assertRaises(AgentTeamsError) as caught:
            consumer.approve_spec_change(21, Role.HUMAN)
        self.assertIn("approve-exception", str(caught.exception))

    def test_it_refuses_when_there_is_no_protected_change_acceptance(self):
        consumer, _ = self._consumer(
            [verdict_comment(a_fail(spec_change_requests=(A_REQUEST,)))]
        )
        with self.assertRaises(AgentTeamsError):
            consumer.approve_spec_change(21, Role.HUMAN)

    def test_it_requires_the_human_lane(self):
        consumer, _ = self._consumer(self._comments(), role="qa")
        with self.assertRaises(AgentTeamsError):
            consumer.approve_spec_change(21, Role.HUMAN)


# ------------------------------------------------------------------ the gate


class SpecChangeGateTests(unittest.TestCase):
    def _producer(self, comments):
        config = a_config()
        gh = FakeGh(
            items=board_with((21, "Delivery", "In Review", "human")),
            comments=comments,
        )
        return Producer(config, Board(config, gh), git=FakeGit()), gh

    def test_a_disputed_specification_offers_the_spec_change_gate(self):
        team, _ = self._producer([
            verdict_comment(a_fail(spec_change_requests=(A_REQUEST,))),
            protected_acceptance(),
        ])
        gates = team.next_actions()["human_gates"]
        self.assertEqual([gate["gate"] for gate in gates], ["spec_change"])
        self.assertEqual(gates[0]["argv"], ["approve-spec-change", "21"])

    def test_it_does_not_offer_a_merge_button(self):
        """Deliberate, not an omission.

        The delivery was built against a baseline QA says is wrong, so
        "approve it anyway" is not one of the two honest answers. A surface
        drawing a merge button here would be offering an authority the route
        does not grant.
        """
        team, _ = self._producer([
            verdict_comment(a_fail(spec_change_requests=(A_REQUEST,))),
            protected_acceptance(),
        ])
        gates = team.next_actions()["human_gates"]
        self.assertNotIn(
            "approve-exception", json.dumps([g["argv"] for g in gates])
        )

    def test_the_gate_carries_the_requests_so_a_surface_can_show_them(self):
        team, _ = self._producer([
            verdict_comment(a_fail(spec_change_requests=(A_REQUEST,))),
            protected_acceptance(),
        ])
        gate = team.next_actions()["human_gates"][0]
        self.assertEqual(len(gate["spec_change_requests"]), 1)
        self.assertEqual(gate["spec_change_requests"][0]["clause"], "AC4")

    def test_a_protected_change_without_a_request_is_still_qa_exception(self):
        """The regression guard for the branch that already existed."""
        team, _ = self._producer([
            verdict_comment(a_pass()), protected_acceptance(),
        ])
        gates = team.next_actions()["human_gates"]
        self.assertEqual([gate["gate"] for gate in gates], ["qa_exception"])
        self.assertEqual(gates[0]["argv"], ["approve-exception", "21"])

    def test_a_stale_head_does_not_withdraw_the_spec_change_gate(self):
        """Unlike the merge exception, and for a reason worth stating.

        `qa_exception` binds to an exact reviewed commit, so a new push
        invalidates it. This gate merges nothing: the specification is wrong
        whichever commit is currently on the branch, and withdrawing the
        request because the developer pushed again would lose the finding.
        """
        team, _ = self._producer([
            verdict_comment(a_fail(spec_change_requests=(A_REQUEST,))),
            protected_acceptance(head_sha="9" * 40),
        ])
        gates = team.next_actions()["human_gates"]
        self.assertEqual([gate["gate"] for gate in gates], ["spec_change"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
