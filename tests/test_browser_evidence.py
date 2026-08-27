"""Browser evidence: required of a QA pass on a user-facing delivery.

The 2026-08-21 review found QA too thin. It re-ran the Developer's own unit
tests and took the occasional screenshot, which duplicates what the Developer
already did before handing over. What caught the one bug unit tests missed --
a blank page from an ES-module version mismatch -- was a screenshot, and the
team lead's point was that such a check should be standard rather than
incidental.

Prose in a skill cannot make it standard: a model can skip an instruction and
still publish a pass. So a pass whose diff touches user-facing files is refused
without recorded browser evidence, exactly the way a pass is already refused
without a `falsified_by`. Backend-only and documentation-only deliveries are
untouched -- a mandatory browser section on a parser change would be theatre,
and theatre is what this rule exists to prevent.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from agent_teams import policy  # noqa: E402
from agent_teams.config import Config  # noqa: E402
from agent_teams.model import REQUIRED_DIMENSIONS, Role, Verdict  # noqa: E402


def config(**overrides):
    base = {"repo": "acme/widgets", "project_owner": "acme", "project_number": 1}
    base.update(overrides)
    return Config.from_dict(base)


def browser_evidence(**overrides):
    """A complete, valid browser pass. Tests remove one part at a time."""
    base = {
        "tool": "playwright",
        "base_url": "http://localhost:5173",
        "flows": [
            {
                "name": "search by destination",
                "steps": [
                    "filled #search with 'Taoyuan'",
                    "clicked button[type=submit]",
                    "read 3 result rows",
                ],
                "result": "pass",
                "screenshot": "evidence/search.png",
            },
        ],
        "input_validation": [
            {
                "field": "#search",
                "input": "'; DROP TABLE stores;--",
                "expected": "rejected with an inline message, no request sent",
                "actual": "rejected with an inline message",
                "result": "pass",
            },
        ],
        "console": {"errors": [], "warnings": ["favicon 404"]},
    }
    base.update(overrides)
    return base


def a_pass(**overrides):
    base = dict(
        verdict="pass",
        card=42,
        pull_request="https://github.com/acme/widgets/pull/57",
        head_sha="a" * 40,
        review_dimensions=tuple(REQUIRED_DIMENSIONS),
        changed_files=("src/App.tsx", "tests/test_app.tsx"),
        design_conformance=("AC1 -> App.search -> test_searches",),
        test_strength=(
            {"dimension": "branch", "evidence": "14/14 in App.tsx",
             "falsified_by": "removed the guard -> test_rejects_empty failed"},
        ),
        checks=("npm test: 18 passed",),
        blind_spots=(),
        next_role=Role.QA,
        browser_evidence=browser_evidence(),
    )
    base.update(overrides)
    return Verdict(**base)


def problems(verdict, changed=None, **config_overrides):
    return policy.validate_verdict(
        verdict,
        verdict.head_sha,
        changed if changed is not None else verdict.changed_files,
        config=config(**config_overrides),
    )


class UiDeliveryTests(unittest.TestCase):
    def test_a_complete_browser_pass_validates(self):
        self.assertEqual(problems(a_pass()), [])

    def test_a_user_facing_pass_without_browser_evidence_is_refused(self):
        found = problems(a_pass(browser_evidence=None))
        self.assertTrue(found)
        self.assertIn("browser", " ".join(found).casefold())
        self.assertIn("src/App.tsx", " ".join(found))

    def test_the_refusal_names_the_files_that_made_it_user_facing(self):
        """A reviewer must not have to guess why the rule fired."""
        found = " ".join(problems(
            a_pass(
                changed_files=("src/App.tsx", "src/api.py"),
                browser_evidence=None,
            ),
        ))
        self.assertIn("src/App.tsx", found)
        self.assertNotIn("src/api.py", found)

    def test_a_flow_of_fewer_than_two_steps_is_not_a_flow(self):
        """Loading a page is not clicking through it.

        One step is the screenshot QA already took, which is the behaviour
        this rule was written to replace.
        """
        found = problems(a_pass(browser_evidence=browser_evidence(
            flows=[{"name": "opened the page", "steps": ["navigated to /"]}],
        )))
        self.assertTrue(any("step" in text for text in found))

    def test_no_flows_at_all_is_refused(self):
        found = problems(a_pass(browser_evidence=browser_evidence(flows=[])))
        self.assertTrue(any("flow" in text for text in found))

    def test_an_unnamed_flow_is_refused(self):
        found = problems(a_pass(browser_evidence=browser_evidence(
            flows=[{"steps": ["a", "b"]}],
        )))
        self.assertTrue(any("name" in text for text in found))

    def test_invalid_input_probing_is_required(self):
        """The team lead asked for this by name: feed the field garbage."""
        found = problems(a_pass(browser_evidence=browser_evidence(
            input_validation=[],
        )))
        self.assertTrue(any("input_validation" in text for text in found))

    def test_an_input_case_must_record_expected_and_actual(self):
        found = problems(a_pass(browser_evidence=browser_evidence(
            input_validation=[{"field": "#search", "input": "!!!"}],
        )))
        self.assertTrue(any("actual" in text for text in found))

    def test_console_state_must_be_recorded_even_when_clean(self):
        """An absent console block and a clean one are different claims.

        Empty means "I looked and it was quiet". Absent means "I did not
        look", and the ES-module blank page was exactly a console error behind
        a green test suite.
        """
        found = problems(a_pass(browser_evidence=browser_evidence(console=None)))
        self.assertTrue(any("console" in text for text in found))

        clean = a_pass(browser_evidence=browser_evidence(
            console={"errors": [], "warnings": []},
        ))
        self.assertEqual(problems(clean), [])

    def test_browser_evidence_must_be_an_object(self):
        found = problems(a_pass(browser_evidence="I clicked around, looked fine"))
        self.assertTrue(any("object" in text for text in found))

    def test_repository_ui_patterns_extend_the_rule(self):
        found = problems(
            a_pass(changed_files=("templates/home.jinja",), browser_evidence=None),
            ui_paths=["templates/**"],
        )
        self.assertTrue(any("browser" in text for text in found))


class NonUiDeliveryTests(unittest.TestCase):
    def test_a_backend_pass_needs_no_browser_evidence(self):
        self.assertEqual(
            problems(a_pass(
                changed_files=("src/parser.py", "tests/test_parser.py"),
                browser_evidence=None,
            )),
            [],
        )

    def test_a_documentation_pass_needs_no_browser_evidence(self):
        self.assertEqual(
            problems(a_pass(
                changed_files=("docs/USAGE.md",), browser_evidence=None,
            )),
            [],
        )

    def test_a_fail_verdict_is_never_asked_for_browser_evidence(self):
        """Only a pass carries the completeness burden.

        A `fail` stops the delivery anyway; demanding full evidence to report a
        defect would push a reviewer towards a pass.
        """
        failing = Verdict(
            verdict="fail", card=42, head_sha="a" * 40,
            pull_request="https://example.invalid/pull/57",
            changed_files=("src/App.tsx",),
            checks=("npm test: 2 failed",),
            findings=("the search box submits an empty query",),
            next_role=Role.DEV,
        )
        self.assertEqual(problems(failing), [])


class BackwardCompatibilityTests(unittest.TestCase):
    def test_validation_without_a_config_skips_the_browser_rule(self):
        """`config` is optional so the two-stage contract stays callable.

        policy sits below config in the dependency order and reads it
        duck-typed; a caller that has no config still gets every other check.
        """
        found = policy.validate_verdict(
            a_pass(browser_evidence=None), "a" * 40, ("src/App.tsx",)
        )
        self.assertEqual(found, [])

    def test_browser_evidence_round_trips_through_the_verdict_document(self):
        original = a_pass()
        restored = Verdict.from_dict(original.to_dict())
        self.assertEqual(restored.browser_evidence, original.browser_evidence)

    def test_a_verdict_document_without_the_field_still_parses(self):
        payload = a_pass().to_dict()
        payload.pop("browser_evidence")
        self.assertIsNone(Verdict.from_dict(payload).browser_evidence)


class SeatContractTests(unittest.TestCase):
    """The QA split is only real if the instructions enforce it.

    Policy can require browser evidence, but nothing in code can stop two
    agents from both gathering it, or stop the blind reviewer from reading the
    diff. Those boundaries live in prose, so they are asserted as prose.
    """

    def _read(self, *parts):
        return (Path(__file__).parents[1].joinpath(*parts)).read_text(
            encoding="utf-8"
        )

    def test_the_browser_procedure_lives_in_exactly_one_file(self):
        """Two copies would drift, and drift here means duplicated QA work."""
        skill = self._read("skills", "verifying-delivery", "SKILL.md")
        self.assertIn("You do not open a browser", skill)
        self.assertIn("references/browser-pass.md", skill)
        # The procedure itself must not be restated in the skill body.
        for instruction in ("Feed every input field", "read the console after"):
            self.assertNotIn(instruction, skill)

    def test_the_reviewer_keeps_a_fallback_so_the_split_is_not_load_bearing(self):
        skill = self._read("skills", "verifying-delivery", "SKILL.md")
        self.assertIn("if no browser worker was dispatched", skill.casefold())
        self.assertIn("never both", skill.casefold())

    def test_the_browser_worker_is_told_not_to_read_the_diff(self):
        worker = self._read("agents", "qa-browser-worker.md")
        self.assertIn("not given the diff", worker)
        self.assertIn("publish", worker)

    def test_the_browser_worker_cannot_publish_a_verdict(self):
        """It has no Write, no Edit, and no Skill-independent mutation path.

        A helper that could publish would give one head two verdicts.
        """
        frontmatter = self._read("agents", "qa-browser-worker.md").split("---", 2)[1]
        self.assertNotIn("Write", frontmatter)
        self.assertNotIn("Edit", frontmatter)
        self.assertIn("SendMessage", frontmatter)

    def test_only_the_qa_worker_may_spawn_helpers(self):
        agents = Path(__file__).parents[1] / "agents"
        for path in agents.glob("*-worker.md"):
            frontmatter = path.read_text(encoding="utf-8").split("---", 2)[1]
            tools = [t.strip() for t in frontmatter.split("tools:")[1]
                     .splitlines()[0].split(",")]
            if path.stem == "qa-worker":
                self.assertIn("Agent", tools, path.stem)
            else:
                self.assertNotIn("Agent", tools, path.stem)

    def test_messaging_discipline_is_stated_where_it_is_used(self):
        """The meeting flagged inter-agent chatter as its own token sink."""
        for text in (
            self._read("skills", "verifying-delivery", "SKILL.md"),
            self._read("agents", "qa-worker.md"),
        ):
            self.assertIn("references, not contents", text)
            self.assertIn("round trip", text)


if __name__ == "__main__":
    unittest.main()
