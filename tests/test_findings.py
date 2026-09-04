"""Findings as validated structure rather than prose.

Until 2026-09-04 `Verdict.findings` was `tuple[str, ...]` and policy never
looked inside it. Everything the review skill said about a finding -- carry a
severity, carry a confidence, name the smell if it has one, do not invent a
smell that isn't in the catalogue, never pass a delivery carrying a `high`
finding -- was a rule a reader could check and a validator could not. The
`test_strength` field had already made this exact journey for the same exact
reason, and its docstring records why: a check that a word appears in prose is
not a check.

These tests pin the properties that make the vocabulary enforceable:

1. prose is refused outright, and the refusal names what to write instead;
2. `severity`, `dimension` and `smell` are closed sets, so a finding is
   comparable to another reviewer's finding and to the same defect next Card;
3. a confidence too low to act on belongs in `limitations`, not `findings`;
4. a `pass` carrying a `critical` or `high` finding is a contradiction and is
   refused -- the one rule here that changes an outcome rather than a format;
5. the catalogue in `references/code-smells.md` and the catalogue in
   `model.py` are the same catalogue, checked mechanically.

Property 5 is not bureaucracy. A vocabulary documented in one place and
enforced from another is precisely the shape of the `merge_mode` rename that
sat half-applied for a week (docs/traces/2026-09-04-merge-mode-evidence-
chain.md): the skill said one thing, the code said another, and a green suite
was positive evidence that nothing was wrong.

See docs/decisions/2026-09-04-structuring-findings.md.
"""

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from agent_teams import policy  # noqa: E402
from agent_teams.model import (  # noqa: E402
    CODE_SMELLS, REQUIRED_DIMENSIONS, SEVERITIES, Role, Verdict,
)

REPO_ROOT = Path(__file__).parents[1]
CODE_SMELLS_DOC = (
    REPO_ROOT / "skills" / "verifying-delivery" / "references" / "code-smells.md"
)


def a_finding(**overrides):
    """One complete, valid finding. Tests override a single key at a time."""
    base = {
        "severity": "medium",
        "dimension": "architecture",
        "confidence": 8,
        "evidence": (
            "board.py:88 reads Config._raw directly; every other caller goes "
            "through Config.role_for()"
        ),
        "smell": "Inappropriate Intimacy",
    }
    base.update(overrides)
    return {k: v for k, v in base.items() if v is not None}


def a_pass(**overrides):
    base = dict(
        verdict="pass",
        card=42,
        pull_request="https://github.com/acme/widgets/pull/57",
        head_sha="a" * 40,
        review_dimensions=tuple(REQUIRED_DIMENSIONS),
        changed_files=("src/parser.py",),
        test_strength=(
            {"dimension": "branch", "evidence": "14/14 in parser.py",
             "falsified_by": "reverted the guard -> test_rejects_empty failed"},
        ),
        checks=("python -m unittest discover: 145 passed",),
        next_role=Role.QA,
    )
    base.update(overrides)
    return Verdict(**base)


def a_fail(**overrides):
    base = dict(
        verdict="fail",
        card=42,
        head_sha="a" * 40,
        pull_request="https://github.com/acme/widgets/pull/57",
        checks=("python -m unittest discover: 3 failed",),
        findings=(a_finding(severity="high", dimension="correctness",
                            smell=None),),
        next_role=Role.DEV,
    )
    base.update(overrides)
    return Verdict(**base)


def problems(verdict, changed=("src/parser.py",)):
    return policy.validate_verdict(verdict, "a" * 40, changed)


# ------------------------------------------------------- the shape of one


class FindingStructureTests(unittest.TestCase):
    """A finding is an object with checkable parts, or it is refused."""

    def test_a_valid_structured_finding_is_accepted(self):
        self.assertEqual(problems(a_pass(findings=(a_finding(),))), [])

    def test_prose_is_refused_and_names_what_to_write_instead(self):
        """The refusal has to teach, because the writer is an agent.

        `RETIRED_KEYS` established the pattern this session: an error that
        names its replacement is repairable in one pass; an error that only
        says 'no' sends the reviewer back to the documentation.
        """
        found = problems(a_pass(findings=("the parser crashes on empty input",)))
        self.assertTrue(any("free text" in p for p in found), found)
        joined = " ".join(found)
        for expected in ("severity", "dimension", "confidence", "evidence"):
            self.assertIn(expected, joined)

    def test_a_finding_missing_evidence_is_refused(self):
        """Step 4 of the skill: a finding that quotes nothing is not promoted."""
        found = problems(a_pass(findings=(a_finding(evidence="   "),)))
        self.assertTrue(any("evidence" in p for p in found), found)

    def test_every_problem_is_reported_at_once(self):
        """One pass, everything wrong with it -- the file's standing rule."""
        found = problems(a_pass(findings=(
            a_finding(severity="blocker", dimension="vibes", smell="Config Rot"),
        )))
        joined = " ".join(found)
        self.assertIn("blocker", joined)
        self.assertIn("vibes", joined)
        self.assertIn("Config Rot", joined)

    def test_each_bad_finding_is_identified_by_index(self):
        found = problems(a_pass(findings=(a_finding(), "prose")))
        self.assertTrue(any("findings[1]" in p for p in found), found)


class ClosedVocabularyTests(unittest.TestCase):
    """Severity, dimension and smell are closed sets or they are taste."""

    def test_an_unknown_severity_is_refused_and_the_four_are_named(self):
        found = problems(a_pass(findings=(a_finding(severity="blocker"),)))
        joined = " ".join(found)
        self.assertIn("blocker", joined)
        for value in SEVERITIES:
            self.assertIn(value, joined)

    def test_an_unknown_dimension_is_refused(self):
        """The nine are the dimensions the verdict must already cover.

        A finding filed under a tenth name cannot be reconciled against the
        `review_dimensions` list, which is the list `accept` checks.
        """
        found = problems(a_pass(findings=(a_finding(dimension="style"),)))
        self.assertTrue(any("style" in p for p in found), found)

    def test_a_smell_outside_the_catalogue_is_refused(self):
        """`code-smells.md`: 'Do not invent entries.' Now enforced.

        A private vocabulary is worse than none, because it looks shared.
        """
        found = problems(a_pass(findings=(a_finding(smell="Config Rot"),)))
        self.assertTrue(any("Config Rot" in p for p in found), found)

    def test_a_finding_without_a_smell_is_accepted(self):
        """Most findings have no smell. A plain logic bug is not one.

        Requiring the field would manufacture exactly the invented labels the
        rule above refuses.
        """
        self.assertEqual(problems(a_pass(findings=(a_finding(smell=None),))), [])

    def test_a_smell_is_not_forced_to_match_the_finding_dimension(self):
        """Deliberately unenforced, and worth pinning so it stays deliberate.

        The catalogue files each smell under the dimension most likely to
        notice it, not the only one that may. A `design` pass can see
        Duplicated Code, catalogued under `cross-file`. Refusing that pairing
        would buy tidiness and cost true findings.
        """
        self.assertEqual(
            problems(a_pass(findings=(
                a_finding(dimension="design", smell="Duplicated Code"),
            ))),
            [],
        )


class ConfidenceTests(unittest.TestCase):
    """SKILL.md step 4 scored confidence in prose. Now it is a field."""

    def test_a_missing_confidence_is_refused(self):
        found = problems(a_pass(findings=(a_finding(confidence=None),)))
        self.assertTrue(any("confidence" in p for p in found), found)

    def test_a_confidence_outside_one_to_ten_is_refused(self):
        found = problems(a_pass(findings=(a_finding(confidence=11),)))
        self.assertTrue(any("confidence" in p for p in found), found)

    def test_a_confidence_too_low_to_act_on_belongs_in_limitations(self):
        """The skill already said so: 'At 3-4, it belongs in limitations.'

        The refusal names `limitations` because the finding is not worthless
        -- it is filed in the wrong place, and deleting it is the failure mode
        `evidence-and-challenge.md` warns about: a dropped finding reaches
        nobody and nobody learns it was dropped.
        """
        found = problems(a_pass(findings=(a_finding(confidence=3),)))
        self.assertTrue(any("limitations" in p for p in found), found)

    def test_a_confidence_of_five_is_accepted(self):
        self.assertEqual(problems(a_pass(findings=(a_finding(confidence=5),))), [])


# ------------------------------------------------------- the rule with teeth


class PassSeverityGateTests(unittest.TestCase):
    """A `pass` carrying a `critical` or `high` finding is a contradiction.

    This is the one rule in this file that changes an outcome rather than a
    format. `verdict-schema.md` stated it and nothing enforced it, so the
    cheapest way to ship a delivery with a serious finding was to write
    `pass` above it.
    """

    def test_a_pass_carrying_a_critical_finding_is_refused(self):
        found = problems(a_pass(findings=(a_finding(severity="critical"),)))
        self.assertTrue(any("critical" in p for p in found), found)

    def test_a_pass_carrying_a_high_finding_is_refused(self):
        found = problems(a_pass(findings=(a_finding(severity="high"),)))
        self.assertTrue(any("high" in p for p in found), found)

    def test_the_refusal_says_the_verdict_should_be_fail(self):
        """Not 'delete the finding'. The finding is the honest part."""
        found = problems(a_pass(findings=(a_finding(severity="high"),)))
        self.assertTrue(any("fail" in p for p in found), found)

    def test_a_pass_carrying_medium_and_low_findings_is_accepted(self):
        """What `pass` with findings is for. Most smells live here."""
        self.assertEqual(
            problems(a_pass(findings=(
                a_finding(severity="medium"), a_finding(severity="low"),
            ))),
            [],
        )

    def test_a_fail_carrying_a_critical_finding_is_not_refused_for_that(self):
        """The gate is about the contradiction, not about severity itself."""
        found = problems(a_fail(findings=(a_finding(severity="critical"),)))
        self.assertFalse(
            any("contradiction" in p or "should be `fail`" in p for p in found),
            found,
        )


class FailFindingsAreValidatedTests(unittest.TestCase):
    """Structure is checked on a `fail` too, and the ordering is the reason.

    `validate_verdict` returns early for any non-`pass` value. A `fail`'s
    findings are the payload that routes to the Developer, so validating them
    only on a `pass` would leave the one verdict value whose findings are
    actually acted on entirely unchecked -- the same ordering bug
    `_spec_change_problems` was placed before the early return to avoid.
    """

    def test_prose_findings_on_a_fail_are_refused(self):
        found = problems(a_fail(findings=("boom",)))
        self.assertTrue(any("free text" in p for p in found), found)

    def test_a_valid_fail_has_no_problems(self):
        self.assertEqual(problems(a_fail()), [])


class DefectReasonTests(unittest.TestCase):
    """The Developer reads the acceptance reason, so it must survive."""

    def test_the_defect_reason_carries_severity_and_evidence(self):
        verdict = a_fail(findings=(a_finding(
            severity="critical", dimension="correctness",
            evidence="parser.parse crashes on an empty header", smell=None,
        ),))
        acceptance = policy.evaluate_acceptance(
            verdict,
            {"merged": False, "state": "OPEN", "mergeable_state": "CLEAN",
             "changed_files": ["src/parser.py"], "checks": {}},
            None,
        )
        reason = " ".join(acceptance.reasons)
        self.assertIn("critical", reason)
        self.assertIn("empty header", reason)

    def test_a_fail_with_no_findings_still_says_so(self):
        """Regression guard: the old renderer's empty case must not be lost."""
        verdict = a_fail(findings=())
        acceptance = policy.evaluate_acceptance(
            verdict,
            {"merged": False, "state": "OPEN", "mergeable_state": "CLEAN",
             "changed_files": ["src/parser.py"], "checks": {}},
            None,
        )
        self.assertIn("no finding recorded", " ".join(acceptance.reasons))


# ------------------------------------------------- the catalogue is one thing


class CatalogueSyncTests(unittest.TestCase):
    """`code-smells.md` and `model.CODE_SMELLS` are the same catalogue.

    Checked mechanically because the alternative is the failure this session
    spent its first item tracing: a vocabulary written in a skill, enforced in
    code, and allowed to drift apart with the suite still green.
    """

    def _documented(self):
        """Every smell named in a catalogue table row of the reference.

        Table rows only. The 'not in this catalogue' section deliberately uses
        bullets, so an excluded smell is not read back in as a member.
        """
        text = CODE_SMELLS_DOC.read_text(encoding="utf-8")
        return {
            match.group(1).strip()
            for match in re.finditer(r"^\|\s*\*\*(.+?)\*\*\s*\|", text, re.M)
        }

    def test_the_reference_names_at_least_one_smell(self):
        """Guards the parser itself: an empty set would make the next test
        pass for the wrong reason."""
        self.assertGreater(len(self._documented()), 10)

    def test_every_documented_smell_is_enforceable(self):
        undocumented = self._documented() - set(CODE_SMELLS)
        self.assertEqual(undocumented, set())

    def test_every_enforceable_smell_is_documented(self):
        """The direction that matters more: a name policy accepts but the
        reviewer cannot look up is a name nobody will use correctly."""
        self.assertEqual(set(CODE_SMELLS) - self._documented(), set())

    def test_the_smells_the_lead_named_are_in_the_catalogue(self):
        """The two examples from the 2026-08-28 review, pinned by name.

        They are why the catalogue exists; a refactor that quietly dropped
        either would remove the vocabulary's original warrant.
        """
        self.assertIn("Inappropriate Intimacy", CODE_SMELLS)
        self.assertIn("Shotgun Surgery", CODE_SMELLS)


if __name__ == "__main__":
    unittest.main()
