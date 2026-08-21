"""Tests for protected classification, verdict validation, and acceptance.

The acceptance decision table is asserted row by row rather than sampled, for
the same reason the transition and authority tables are: this layer touches
no network, so covering the edges is cheap, and a merge route reached by an
unasserted path is exactly the class of hole that sampling misses.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from agent_teams import policy  # noqa: E402
from agent_teams.config import DEFAULT_PROTECTED_PATHS, Config  # noqa: E402
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
        test_strength=(
            {"dimension": "branch", "evidence": "14/14 in parser.py",
             "falsified_by": "reverted the guard -> test_rejects_empty failed"},
            {"dimension": "negative", "evidence": "malformed header rejected"},
        ),
        checks=("python -m unittest discover: 145 passed",),
        findings=(),
        challenges=(),
        blind_spots=(),
        limitations="",
        next_role=Role.QA,
    )
    base.update(overrides)
    return Verdict(**base)


def a_fail(**overrides):
    base = dict(
        verdict="fail", card=42, head_sha="a" * 40,
        pull_request="https://example.invalid/pull/57",
        checks=("python -m unittest discover: 3 failed",),
        findings=("parser.parse crashes on an empty header",),
        next_role=Role.DEV,
    )
    base.update(overrides)
    return Verdict(**base)


def facts(**overrides):
    """The live Pull Request facts the evaluator reads. Plain data, no I/O."""
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


class GlobTests(unittest.TestCase):
    """fnmatch has no `**`, and a protected rule that silently fails to span
    directories would be worse than no rule at all."""

    def test_double_star_spans_directory_separators(self):
        self.assertTrue(policy.path_matches("a/b/c/auth/login.py", "**/auth/**"))

    def test_single_star_does_not_span_separators(self):
        self.assertFalse(policy.path_matches("src/deep/file.py", "src/*.py"))
        self.assertTrue(policy.path_matches("src/file.py", "src/*.py"))

    def test_leading_double_star_matches_at_the_root(self):
        self.assertTrue(policy.path_matches("package.json", "**/package.json"))
        self.assertTrue(policy.path_matches("web/package.json", "**/package.json"))

    def test_trailing_double_star_matches_nested_files(self):
        self.assertTrue(
            policy.path_matches(".github/workflows/ci.yml", ".github/workflows/**")
        )
        self.assertTrue(
            policy.path_matches(".github/workflows/a/b.yml", ".github/workflows/**")
        )

    def test_exact_path_matches_only_itself(self):
        self.assertTrue(policy.path_matches("CLAUDE.md", "CLAUDE.md"))
        self.assertFalse(policy.path_matches("docs/CLAUDE.md", "CLAUDE.md"))

    def test_dots_are_literal_not_wildcards(self):
        self.assertFalse(policy.path_matches("CLAUDEXmd", "CLAUDE.md"))

    def test_regex_metacharacters_in_a_path_are_not_interpreted(self):
        self.assertFalse(policy.path_matches("a+b.py", "a.py"))

    def test_a_partial_match_does_not_count(self):
        # The pattern is anchored at both ends; a substring hit is not a match.
        self.assertFalse(policy.path_matches("vendor/CLAUDE.md.bak", "CLAUDE.md"))


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

    def test_several_categories_are_all_reported(self):
        changed = ["scripts/agent_teams/policy.py", "skills/x/SKILL.md"]
        self.assertEqual(
            policy.classify_protected(changed, DEFAULT_PROTECTED_PATHS),
            ("agent-instructions", "authority-and-policy"),
        )

    def test_windows_separators_are_normalised(self):
        self.assertEqual(
            policy.classify_protected(
                ["scripts\\agent_teams\\policy.py"], DEFAULT_PROTECTED_PATHS
            ),
            ("authority-and-policy",),
        )

    def test_an_empty_change_set_matches_nothing(self):
        self.assertEqual(policy.classify_protected([], DEFAULT_PROTECTED_PATHS), ())

    def test_matches_report_the_exact_paths_per_category(self):
        # The human reading an escalation must not have to open the diff to
        # find which files tripped the rule.
        matches = policy.protected_matches(
            ["README.md", "scripts/agent_teams/policy.py", "docs/ARCHITECTURE.md"],
            DEFAULT_PROTECTED_PATHS,
        )
        self.assertEqual(
            matches,
            {
                "architecture-and-design": ("docs/ARCHITECTURE.md",),
                "authority-and-policy": ("scripts/agent_teams/policy.py",),
            },
        )

    def test_matched_paths_are_sorted_and_deduplicated(self):
        matches = policy.protected_matches(
            ["skills/b/SKILL.md", "skills/a/SKILL.md", "skills/a/SKILL.md"],
            DEFAULT_PROTECTED_PATHS,
        )
        self.assertEqual(
            matches["agent-instructions"], ("skills/a/SKILL.md", "skills/b/SKILL.md")
        )

    def test_a_path_matching_two_patterns_in_one_category_is_listed_once(self):
        matches = policy.protected_matches(
            ["CLAUDE.md"], {"agent-instructions": ("CLAUDE.md", "*.md")}
        )
        self.assertEqual(matches["agent-instructions"], ("CLAUDE.md",))

    def test_classify_protected_still_returns_categories(self):
        self.assertEqual(
            policy.classify_protected(
                ["scripts/agent_teams/policy.py"], DEFAULT_PROTECTED_PATHS
            ),
            ("authority-and-policy",),
        )

    def test_this_plans_own_spec_directory_is_protected(self):
        # Changing the approved design baseline is a human decision.
        self.assertEqual(
            policy.classify_protected(
                ["docs/specs/2026-08-06-consumer-flow-design.md"],
                DEFAULT_PROTECTED_PATHS,
            ),
            ("architecture-and-design",),
        )


class VerdictContractTests(unittest.TestCase):
    def test_a_complete_pass_constructs(self):
        self.assertEqual(a_pass().verdict, "pass")

    def test_looks_good_is_not_a_verdict(self):
        with self.assertRaisesRegex(DomainError, "not a verdict"):
            a_pass(checks=())

    def test_an_unknown_verdict_value_is_rejected(self):
        with self.assertRaises(DomainError):
            a_pass(verdict="lgtm")

    def test_every_verdict_must_name_the_head_it_reviewed(self):
        # Evidence not bound to a commit cannot be checked for staleness.
        with self.assertRaisesRegex(DomainError, "head"):
            a_pass(head_sha="")

    def test_a_pass_must_enumerate_the_files_it_reviewed(self):
        with self.assertRaisesRegex(DomainError, "changed file"):
            a_pass(changed_files=())

    def test_a_blocked_verdict_may_omit_checks_and_files(self):
        blocked = Verdict(
            verdict="blocked", card=42, head_sha="b" * 40,
            pull_request="https://example.invalid/pull/1",
            blind_spots=("cannot reach the staging database",),
            next_role=Role.HUMAN,
        )
        self.assertEqual(blocked.verdict, "blocked")

    def test_a_blocked_verdict_still_needs_a_head(self):
        with self.assertRaises(DomainError):
            Verdict(verdict="blocked", card=42)

    def test_round_trips_through_dict(self):
        original = a_pass()
        self.assertEqual(Verdict.from_dict(original.to_dict()), original)

    def test_from_dict_tolerates_absent_optional_fields(self):
        restored = Verdict.from_dict(
            {"verdict": "blocked", "card": 42, "head_sha": "c" * 40}
        )
        self.assertEqual(restored.changed_files, ())
        self.assertIsNone(restored.next_role)


class AcceptanceContractTests(unittest.TestCase):
    def test_only_three_acceptance_values_exist(self):
        self.assertEqual(Acceptance.VALUES, ("eligible", "defect", "protected_change"))

    def test_an_unknown_acceptance_value_is_rejected(self):
        with self.assertRaises(DomainError):
            Acceptance(acceptance="merge-it", head_sha="a" * 40, policy_version="1")

    def test_the_envelope_carries_the_deciding_policy_version(self):
        result = Acceptance(
            acceptance="eligible", head_sha="a" * 40, policy_version="1",
            reasons=("all required checks green",),
        )
        self.assertEqual(result.to_dict()["policy_version"], "1")
        self.assertEqual(result.to_dict()["reasons"], ["all required checks green"])

    def test_verdict_and_acceptance_do_not_convert_into_each_other(self):
        # The separation is structural, not merely prose: QA writes one type,
        # policy writes the other. A conversion method would be the seam
        # through which a reviewer could select its own route.
        self.assertFalse(hasattr(Acceptance, "to_verdict"))
        self.assertFalse(hasattr(Verdict, "to_acceptance"))
        self.assertNotIn("acceptance", a_pass().to_dict())


class VerdictValidationTests(unittest.TestCase):
    """Stage 1: every reason this evidence cannot be acted on, at once."""

    def _problems(self, verdict, head="a" * 40, changed=None):
        return policy.validate_verdict(
            verdict, head, changed if changed is not None else facts()["changed_files"]
        )

    def test_a_current_complete_pass_has_no_problems(self):
        self.assertEqual(self._problems(a_pass()), [])

    def test_a_head_mismatch_is_a_problem(self):
        self.assertTrue(any("head" in p for p in self._problems(a_pass(), head="b" * 40)))

    def test_a_missing_review_dimension_is_named(self):
        verdict = a_pass(review_dimensions=REQUIRED_DIMENSIONS[:-1])
        self.assertTrue(any("test-strength" in p for p in self._problems(verdict)))

    def test_an_unresolved_blind_spot_is_a_problem(self):
        verdict = a_pass(blind_spots=("did not review the migration",))
        self.assertTrue(any("blind spot" in p for p in self._problems(verdict)))

    def test_an_unenumerated_changed_file_is_named(self):
        problems = self._problems(
            a_pass(),
            changed=("src/parser.py", "tests/test_parser.py", "src/sneaky.py"),
        )
        self.assertTrue(any("sneaky" in p for p in problems))

    def test_reviewing_more_files_than_changed_is_not_a_problem(self):
        # A verdict may name a file the diff no longer touches; only the
        # reverse -- an unreviewed change -- is unsafe.
        self.assertEqual(self._problems(a_pass(), changed=("src/parser.py",)), [])

    def test_line_coverage_alone_is_not_test_strength(self):
        verdict = a_pass(test_strength=(
            {"dimension": "line", "evidence": "98%"},
        ))
        self.assertTrue(any("line execution" in p for p in self._problems(verdict)))

    def test_free_text_cannot_satisfy_the_test_strength_rule(self):
        # The rule this replaces was a substring search over free text, so
        # "NO branch coverage was measured" satisfied it -- the token was
        # present. Evidence must be structured, or it is not checkable.
        for prose in (
            "branch",
            "line coverage 98%; NO branch coverage was measured",
            "line coverage 98%; there are no negative tests",
            "we did not do mutation testing",
            "integration untested",
        ):
            problems = self._problems(a_pass(test_strength=(prose,)))
            self.assertTrue(problems, f"free text accepted: {prose!r}")

    def test_an_unknown_dimension_is_rejected(self):
        verdict = a_pass(test_strength=(
            {"dimension": "vibes", "evidence": "felt thorough",
             "falsified_by": "n/a"},
        ))
        self.assertTrue(any("vibes" in p for p in self._problems(verdict)))

    def test_a_pass_needs_a_dimension_beyond_line(self):
        verdict = a_pass(test_strength=(
            {"dimension": "line", "evidence": "98%",
             "falsified_by": "reverted x -> test_y failed"},
        ))
        self.assertTrue(any("line execution" in p for p in self._problems(verdict)))

    def test_a_pass_needs_at_least_one_falsification(self):
        # The slide's rule: a covered line must have its intended behaviour
        # verified, not merely executed. The only operational proof of that is
        # that breaking the implementation broke a named test.
        verdict = a_pass(test_strength=(
            {"dimension": "branch", "evidence": "18/18 in parser.py"},
        ))
        problems = self._problems(verdict)
        self.assertTrue(any("falsified_by" in p for p in problems), problems)

    def test_a_falsification_must_name_a_test_that_failed(self):
        verdict = a_pass(test_strength=(
            {"dimension": "branch", "evidence": "18/18", "falsified_by": "yes"},
        ))
        self.assertTrue(any("falsified_by" in p for p in self._problems(verdict)))

    def test_a_complete_structured_test_strength_passes(self):
        verdict = a_pass(test_strength=(
            {"dimension": "branch", "evidence": "18/18 in parser.py",
             "falsified_by": "reverted the guard at parser.py:41 -> "
                             "test_rejects_empty failed"},
            {"dimension": "negative", "evidence": "empty and malformed inputs"},
        ))
        self.assertEqual(self._problems(verdict), [])

    def test_every_problem_is_reported_together(self):
        # One re-review should teach QA everything it must redo.
        verdict = a_pass(
            review_dimensions=("correctness",),
            blind_spots=("did not review the migration",),
            test_strength=("line: 98%",),
        )
        problems = self._problems(verdict, head="z" * 40)
        self.assertGreaterEqual(len(problems), 4)

    def test_a_fail_verdict_need_not_be_complete(self):
        self.assertEqual(self._problems(a_fail(), changed=("src/parser.py",)), [])

    def test_a_stale_fail_verdict_is_still_a_problem(self):
        self.assertTrue(self._problems(a_fail(), head="z" * 40))


class AcceptanceTableTests(unittest.TestCase):
    """Stage 2: the routing table, row by row."""

    def test_row_3_fail_routes_to_defect(self):
        result = policy.evaluate_acceptance(a_fail(), facts(), a_config())
        self.assertEqual(result.acceptance, "defect")

    def test_row_4_blocked_routes_to_protected_change(self):
        verdict = Verdict(
            verdict="blocked", card=42, head_sha="a" * 40, pull_request="p",
            blind_spots=("cannot reach staging",), next_role=Role.HUMAN,
        )
        result = policy.evaluate_acceptance(verdict, facts(), a_config())
        self.assertEqual(result.acceptance, "protected_change")
        self.assertTrue(any("staging" in r for r in result.reasons))

    def test_row_5_a_protected_path_routes_to_protected_change_on_a_clean_pass(self):
        changed = ("scripts/agent_teams/policy.py",)
        result = policy.evaluate_acceptance(
            a_pass(changed_files=changed), facts(changed_files=changed), a_config()
        )
        self.assertEqual(result.acceptance, "protected_change")
        self.assertTrue(any("authority-and-policy" in r for r in result.reasons))

    def test_row_5_names_the_exact_files_that_need_the_human(self):
        # The slide's contract: QA states exactly which files, decision, or
        # risk needs the human -- not merely which category was tripped.
        changed = ("src/parser.py", "scripts/agent_teams/policy.py",
                   "docs/ARCHITECTURE.md")
        result = policy.evaluate_acceptance(
            a_pass(changed_files=changed), facts(changed_files=changed), a_config()
        )
        reason = " ".join(result.reasons)
        self.assertIn("scripts/agent_teams/policy.py", reason)
        self.assertIn("docs/ARCHITECTURE.md", reason)
        # and does not implicate the file that tripped nothing
        self.assertNotIn("src/parser.py", reason)

    def test_row_5_outranks_green_checks(self):
        # A protected change is not made safe by passing tests.
        changed = ("skills/consuming-card/SKILL.md",)
        result = policy.evaluate_acceptance(
            a_pass(changed_files=changed), facts(changed_files=changed), a_config()
        )
        self.assertEqual(result.acceptance, "protected_change")

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
        self.assertTrue(any("test=FAILURE" in r for r in result.reasons))

    def test_row_7_a_missing_required_check_routes_to_defect(self):
        # Absent is not green. A check that never ran proves nothing.
        result = policy.evaluate_acceptance(
            a_pass(), facts(checks={"build": "SUCCESS"}), a_config()
        )
        self.assertEqual(result.acceptance, "defect")

    def test_row_7_ignores_checks_that_are_not_required(self):
        result = policy.evaluate_acceptance(
            a_pass(),
            facts(checks={"build": "SUCCESS", "test": "SUCCESS", "lint": "FAILURE"}),
            a_config(),
        )
        self.assertEqual(result.acceptance, "eligible")

    def test_row_8_a_draft_pull_request_routes_to_defect(self):
        result = policy.evaluate_acceptance(a_pass(), facts(draft=True), a_config())
        self.assertEqual(result.acceptance, "defect")

    def test_row_8_an_unmergeable_pull_request_routes_to_defect(self):
        result = policy.evaluate_acceptance(a_pass(), facts(mergeable=False), a_config())
        self.assertEqual(result.acceptance, "defect")

    def test_a_merged_pull_request_is_not_asked_whether_it_is_mergeable(self):
        # Session-8 live finding: after a merge GitHub reports
        # ``mergeable: UNKNOWN`` indefinitely. A post-merge re-verify must
        # route to eligible (and then reconcile), not to defect or to waiting.
        merged = facts(state="MERGED", merged=True, mergeable=False,
                       mergeable_state="UNKNOWN")
        result = policy.evaluate_acceptance(a_pass(), merged, a_config())
        self.assertEqual(result.acceptance, "eligible")
        self.assertEqual(policy.acceptance_wait_reasons(a_pass(), merged, a_config()), ())

    def test_an_open_pull_request_with_unknown_mergeability_still_waits(self):
        pending = facts(state="OPEN", merged=False, mergeable=False,
                        mergeable_state="UNKNOWN")
        reasons = policy.acceptance_wait_reasons(a_pass(), pending, a_config())
        self.assertTrue(any("mergeability" in reason for reason in reasons))

    def test_row_9_a_clean_current_complete_pass_is_eligible(self):
        result = policy.evaluate_acceptance(a_pass(), facts(), a_config())
        self.assertEqual(result.acceptance, "eligible")
        self.assertEqual(result.head_sha, "a" * 40)
        self.assertEqual(result.policy_version, policy.ACCEPTANCE_POLICY_VERSION)

    def test_the_decision_always_carries_reasons(self):
        cases = [
            (a_pass(), facts(), a_config()),
            (a_fail(), facts(), a_config()),
            (a_pass(), facts(mergeable=False), a_config()),
            (a_pass(), facts(), a_config(required_checks=[])),
        ]
        for verdict, fact, config in cases:
            self.assertTrue(policy.evaluate_acceptance(verdict, fact, config).reasons)

    def test_the_decision_is_bound_to_the_live_head_not_the_verdicts(self):
        result = policy.evaluate_acceptance(a_pass(), facts(head_sha="c" * 40), a_config())
        self.assertEqual(result.head_sha, "c" * 40)

    def test_evaluation_performs_no_input_mutation(self):
        fact = facts()
        snapshot = dict(fact)
        policy.evaluate_acceptance(a_pass(), fact, a_config())
        self.assertEqual(fact, snapshot)


class MergeFloorTests(unittest.TestCase):
    """Decision 8 removes routine human review, not the no-agent-merge rule."""

    def test_direct_merge_remains_refused_for_every_agent_seat(self):
        for seat in (Role.ANALYST, Role.ARCHITECT, Role.DEV, Role.QA, Role.LEAD):
            with self.assertRaises(policy.ActionForbidden, msg=str(seat)):
                policy.check_action("merge_pull_request", seat)

    def test_direct_merge_is_still_a_hard_floor(self):
        self.assertIn("merge_pull_request", policy.HARD_FLOORS)

    def test_no_seat_at_all_may_request_the_merge_controller(self):
        # Arming auto-merge is a consequence of an eligible acceptance, never
        # an action a session requests. The row exists so that "no seat may
        # request it" is an assertion rather than an absence.
        for seat in Role:
            with self.assertRaises(policy.ActionForbidden, msg=str(seat)):
                policy.check_action("request_automated_merge", seat)

    def test_the_refusal_names_the_route_that_does_exist(self):
        with self.assertRaises(policy.ActionForbidden) as caught:
            policy.check_action("request_automated_merge", Role.QA)
        self.assertIn("accept", str(caught.exception))
