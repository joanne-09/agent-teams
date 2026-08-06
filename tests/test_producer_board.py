"""Board adapter and CLI regression tests.

Descends from the original nine-test MVP suite. Four of those tests asserted
behaviour the architecture contradicts and are superseded here; each carries a
note saying what changed and why, so the supersession is auditable rather than
silent.
"""

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).parent))

import producer_board  # noqa: E402
from agent_teams import policy  # noqa: E402
from agent_teams.config import Config, ConfigError  # noqa: E402
from agent_teams.github import BoardTruncated  # noqa: E402
from agent_teams.model import Role, Status  # noqa: E402
from agent_teams.model import REQUIRED_DIMENSIONS, VERDICT_MARKER  # noqa: E402
from fake_gh import (  # noqa: E402
    FIELDS, REPO, FakeGh, FakeGit, SaturatingGh, board_with,
)


def config(**overrides):
    base = {"repo": REPO, "project_owner": "acme", "project_number": 1}
    base.update(overrides)
    return Config.from_dict(base)


class ConfigTests(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "producer.json"
            config().write(path)
            self.assertEqual(Config.load(path), config())

    def test_rejects_unknown_dispatch_role(self):
        with self.assertRaisesRegex(ConfigError, "unknown"):
            config(dispatch_roles=["wizard"])

    def test_rejects_duplicate_dispatch_roles(self):
        with self.assertRaisesRegex(ConfigError, "duplicates"):
            config(dispatch_roles=["dev", "dev"])

    def test_rejects_malformed_repo(self):
        with self.assertRaisesRegex(ConfigError, "OWNER/REPO"):
            config(repo="widgets")

    def test_rejects_empty_field_names(self):
        with self.assertRaisesRegex(ConfigError, "role_field must not be empty"):
            config(role_field="   ")

    def test_reports_every_defect_at_once(self):
        # One re-run should teach an operator everything that is wrong.
        with self.assertRaises(ConfigError) as caught:
            Config.from_dict(
                {"repo": "bad", "project_owner": "", "project_number": 0,
                 "dispatch_roles": ["wizard"], "spec_completion": "whenever"}
            )
        message = str(caught.exception)
        for expected in ("OWNER/REPO", "project_owner", "project_number",
                         "wizard", "spec_completion"):
            self.assertIn(expected, message)

    def test_spec_completion_defaults_to_merged(self):
        self.assertTrue(config().requires_merged_spec)
        self.assertFalse(config(spec_completion="opened").requires_merged_spec)


class ConsumerConfigTests(unittest.TestCase):
    """The five Consumer keys, and the one that may only grow."""

    def test_defaults_are_conservative(self):
        current = config()
        self.assertEqual(current.workspace, "../.worktrees")
        self.assertEqual(current.merge_method, "squash")
        self.assertEqual(current.required_checks, ())
        self.assertEqual(current.claim_ttl_hours, 72)

    def test_defaults_cover_every_protected_category(self):
        for category in (
            "authority-and-policy", "acceptance-and-merge",
            "github-workflows-and-credentials", "dependencies-and-manifests",
            "agent-instructions", "security-boundaries",
            "architecture-and-design",
        ):
            self.assertIn(category, config().protected_paths, category)

    def test_repository_policy_may_add_patterns_to_a_category(self):
        patterns = config(
            protected_paths={"security-boundaries": ["infra/**"]}
        ).protected_paths["security-boundaries"]
        self.assertIn("infra/**", patterns)
        self.assertIn("**/auth/**", patterns)  # the default survives

    def test_repository_policy_may_add_a_new_category(self):
        current = config(protected_paths={"billing": ["src/billing/**"]})
        self.assertIn("billing", current.protected_paths)
        self.assertIn("agent-instructions", current.protected_paths)

    def test_emptying_a_default_category_is_a_validation_error(self):
        # Section 4.5: policy may add categories, never silently remove one.
        with self.assertRaises(ConfigError) as caught:
            config(protected_paths={"agent-instructions": []})
        self.assertIn("agent-instructions", str(caught.exception))

    def test_adding_a_pattern_twice_does_not_duplicate_it(self):
        patterns = config(
            protected_paths={"agent-instructions": ["skills/**", "skills/**"]}
        ).protected_paths["agent-instructions"]
        self.assertEqual(len(patterns), len(set(patterns)))

    def test_unknown_merge_method_is_rejected(self):
        with self.assertRaisesRegex(ConfigError, "merge_method"):
            config(merge_method="cherry-pick")

    def test_workspace_must_resolve_outside_the_repository(self):
        # A repo-internal worktree gets scanned by editors and confuses which
        # checkout is canonical.
        with self.assertRaisesRegex(ConfigError, "workspace"):
            config(workspace=".worktrees")

    def test_required_checks_normalise_to_a_tuple_of_names(self):
        self.assertEqual(
            config(required_checks=["build", " test ", ""]).required_checks,
            ("build", "test"),
        )

    def test_consumer_keys_survive_a_config_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "producer.json"
            original = config(
                required_checks=["build"], merge_method="rebase",
                protected_paths={"billing": ["src/billing/**"]},
            )
            original.write(path)
            self.assertEqual(Config.load(path), original)


class BoardReadTests(unittest.TestCase):
    def setUp(self):
        self.gh = FakeGh()
        self.board = producer_board.Board(config(), self.gh)

    def test_normalises_only_configured_repo_cards(self):
        cards = self.board.cards()
        numbers = [card.number for card in cards]
        self.assertEqual(numbers, [12, 8, 9, 10, 20, 21, 22, 23])
        self.assertNotIn(99, numbers)  # belongs to acme/other
        self.assertIs(cards[0].role, Role.DEV)
        self.assertIs(cards[0].status, Status.READY)

    def test_missing_role_reads_as_unset_rather_than_a_guess(self):
        card = next(c for c in self.board.cards() if c.number == 10)
        self.assertIsNone(card.role)

    def test_json_envelope_is_unchanged(self):
        card = self.board.card(12)
        self.assertEqual(
            card.to_dict(),
            {
                "item_id": "ITEM_12",
                "number": 12,
                "repo": REPO,
                "title": "Implement parser",
                "url": f"https://github.com/{REPO}/issues/12",
                "status": "Ready",
                "role": "dev",
            },
        )


class PaginationTests(unittest.TestCase):
    """Plan M1.5: a Card past the first response page must never vanish."""

    def test_escalates_until_a_response_comes_back_short(self):
        gh = SaturatingGh(total=250)
        board = producer_board.Board(config(), gh)
        cards = board.cards()
        self.assertEqual(len(cards), 250)
        # 100 saturated -> 200 saturated -> 400 returns 250 and proves complete.
        self.assertEqual(gh.limits_requested, [100, 200, 400])

    def test_a_board_exactly_on_a_boundary_still_reads_completely(self):
        gh = SaturatingGh(total=100)
        board = producer_board.Board(config(), gh)
        self.assertEqual(len(board.cards()), 100)
        self.assertEqual(gh.limits_requested, [100, 200])

    def test_refuses_to_report_a_possibly_truncated_board(self):
        gh = SaturatingGh(total=10_000)
        board = producer_board.Board(config(), gh)
        with self.assertRaises(BoardTruncated) as caught:
            board.cards()
        # The failure must be loud. A short list would make dispatch skip real
        # work while reporting success.
        self.assertIn("partial board", str(caught.exception))


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.gh = FakeGh()
        self.board = producer_board.Board(config(), self.gh)

    def test_rejects_unauthorised_handoff(self):
        # SUPERSEDED: the original suite asserted architect -> analyst was
        # refused. Both ARCHITECTURE.md 4.3 and the adaptation dossier 5.2
        # grant that edge, so the refusal was the bug. dev -> human is the
        # genuinely illegal edge and is asserted instead.
        with self.assertRaises(policy.IllegalHandoff):
            self.board.handoff_card(12, Role.DEV, Role.HUMAN, "ready to merge")

    def test_architect_may_return_an_under_specified_card(self):
        result = self.board.handoff_card(
            8, Role.ARCHITECT, Role.ANALYST, "Acceptance criteria are not testable."
        )
        self.assertEqual(result["role"], "analyst")

    def test_handoff_updates_role_and_comments(self):
        # SUPERSEDED: the original asserted a Unicode arrow in
        # "`architect` -> `dev`". The canonical comment shape in
        # ARCHITECTURE.md 9.4 uses ASCII "->" so the comment stays parseable.
        result = self.board.handoff_card(8, Role.ARCHITECT, Role.DEV, "Spec merged.")
        self.assertEqual(result["role"], "dev")
        edit = self.gh.calls_matching("project", "item-edit")[0]
        self.assertIn("ROLE_DEV", edit)
        comment = self.gh.calls_matching("issue", "comment")[0][-1]
        self.assertIn("<!-- agent-teams:handoff -->", comment)
        self.assertIn("**Handoff**: `architect` -> `dev`", comment)

    def test_refuses_when_the_board_disagrees_about_ownership(self):
        with self.assertRaisesRegex(producer_board.BoardError, "owned by"):
            self.board.handoff_card(8, Role.DEV, Role.QA, "not my card")

    def test_counts_existing_handoffs_against_the_cap(self):
        marker = "<!-- agent-teams:handoff -->\n**Handoff**: `qa` -> `dev`"
        gh = FakeGh(comments=[marker] * 6)
        board = producer_board.Board(config(), gh)
        with self.assertRaises(policy.HandoffCapExceeded):
            board.handoff_card(8, Role.ARCHITECT, Role.DEV, "again")

    def test_unrelated_comments_do_not_count_toward_the_cap(self):
        gh = FakeGh(comments=["just a normal review note"] * 20)
        board = producer_board.Board(config(), gh)
        self.assertEqual(board.handoff_count(8), 0)


class TransitionTests(unittest.TestCase):
    def setUp(self):
        self.gh = FakeGh()
        self.board = producer_board.Board(config(), self.gh)

    def test_legal_transition_sets_status_only(self):
        # Acts as `human`: reaching Ready is the readiness gate, so the
        # destination rule now refuses the architect on this path too.
        result = self.board.transition_card(20, Status.READY, Role.HUMAN)
        self.assertEqual(result["status_before"], "Backlog")
        self.assertEqual(result["status"], "Ready")
        edits = self.gh.calls_matching("project", "item-edit")
        self.assertEqual(len(edits), 1)
        self.assertIn("STATUS_READY", edits[0])
        # Role must be untouched: the two axes are independent.
        self.assertIn("STATUS_FIELD", edits[0])
        self.assertNotIn("ROLE_FIELD", edits[0])

    def test_illegal_transition_refuses_before_touching_github(self):
        with self.assertRaises(policy.IllegalTransition):
            self.board.transition_card(20, Status.IN_REVIEW, Role.ARCHITECT)
        self.assertEqual(self.gh.calls_matching("project", "item-edit"), [])

    def test_out_of_seat_transition_refuses(self):
        with self.assertRaises(policy.ActionForbidden):
            self.board.transition_card(20, Status.READY, Role.ANALYST)


class DoctorTests(unittest.TestCase):
    def test_doctor_validates_all_six_statuses_and_six_roles(self):
        # SUPERSEDED: the original fixture carried only Backlog and Ready, and
        # doctor checked only those two. Plan M1.4 requires all six.
        result = producer_board.Board(config(), FakeGh()).doctor()
        self.assertTrue(result["ok"])
        self.assertEqual(result["project_id"], "PROJECT_ID")
        self.assertEqual(len(result["statuses_validated"]), 6)
        self.assertEqual(len(result["roles_validated"]), 6)

    def test_reports_every_missing_option_in_one_response(self):
        thin = {
            "fields": [
                {"id": "ROLE_FIELD", "name": "Role",
                 "options": [{"id": "ROLE_DEV", "name": "dev"}]},
                {"id": "STATUS_FIELD", "name": "Status",
                 "options": [{"id": "S_B", "name": "Backlog"}]},
            ]
        }

        class ThinGh(FakeGh):
            def json(self, args):
                if list(args)[:2] == ["project", "field-list"]:
                    self.calls.append(list(args))
                    return thin
                return super().json(args)

        with self.assertRaises(producer_board.BoardError) as caught:
            producer_board.Board(config(), ThinGh()).doctor()
        message = str(caught.exception)
        self.assertIn("analyst", message)
        self.assertIn("In Review", message)
        self.assertIn("Done", message)

    def test_missing_field_names_the_options_to_create(self):
        class NoRoleGh(FakeGh):
            def json(self, args):
                if list(args)[:2] == ["project", "field-list"]:
                    self.calls.append(list(args))
                    return {"fields": [FIELDS["fields"][1]]}
                return super().json(args)

        with self.assertRaises(producer_board.BoardError) as caught:
            producer_board.Board(config(), NoRoleGh()).doctor()
        self.assertIn("has no 'Role' field", str(caught.exception))


class CliTests(unittest.TestCase):
    """The CLI contract: one JSON envelope, exit 0 or 1, never a bare claim."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config_path = Path(self.tmp.name) / "config.json"
        config().write(self.config_path)

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, *argv, gh=None):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = producer_board.main(
                ["--config", str(self.config_path), *argv], gh=gh or FakeGh()
            )
        return code, out.getvalue(), err.getvalue()

    def test_init_writes_a_loadable_config(self):
        target = Path(self.tmp.name) / "fresh.json"
        out = io.StringIO()
        with redirect_stdout(out):
            code = producer_board.main(
                ["--config", str(target), "init", "--repo", REPO,
                 "--project-owner", "acme", "--project-number", "3"]
            )
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(out.getvalue())["ok"])
        self.assertEqual(Config.load(target).project_number, 3)

    def test_dispatch_filters_and_orders(self):
        code, out, _ = self._run("dispatch", "--format", "json")
        self.assertEqual(code, 0)
        queue = json.loads(out)
        self.assertEqual([entry["number"] for entry in queue], [8, 12])
        self.assertIn("[role:architect]", queue[0]["prompt"])
        self.assertIn("[board-card:#12]", queue[1]["prompt"])

    def test_dispatch_by_role(self):
        code, out, _ = self._run("dispatch", "--role", "dev", "--format", "json")
        self.assertEqual(code, 0)
        self.assertEqual([entry["number"] for entry in json.loads(out)], [12])

    def test_dispatch_skips_cards_with_no_role(self):
        _, out, _ = self._run("dispatch", "--format", "json")
        self.assertNotIn(10, [entry["number"] for entry in json.loads(out)])

    def test_list_filters_by_status(self):
        code, out, _ = self._run("list", "--status", "Blocked")
        self.assertEqual(code, 0)
        self.assertEqual([card["number"] for card in json.loads(out)], [9])

    def test_release_claim_round_trip(self):
        code, out, _ = self._run(
            "release-claim", "23", "--branch", "claim/23-active-build",
            "--note", "No commits in 8 days; claimant notified on day 3.",
        )
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["branch_deleted"], "claim/23-active-build")
        self.assertEqual(payload["status"], "Ready")

    def test_release_claim_refuses_every_agent_seat(self):
        code, _, err = self._run(
            "release-claim", "23", "--branch", "claim/23-active-build",
            "--acting-role", "lead",
        )
        self.assertEqual(code, 1)
        payload = json.loads(err)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["refusal"], "ActionForbidden")

    def test_refusal_exits_non_zero_with_a_json_error(self):
        code, _, err = self._run(
            "handoff", "12", "--from-role", "dev", "--to-role", "human",
            "--note", "please merge",
        )
        self.assertEqual(code, 1)
        payload = json.loads(err)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["refusal"], "IllegalHandoff")

    def test_transition_requires_an_acting_seat(self):
        code, _, err = self._run(
            "transition", "20", "--to", "Ready", "--acting-role", "dev"
        )
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(err)["refusal"], "ActionForbidden")

    def test_create_card_cannot_route_around_the_transition_it_performs(self):
        # `transition --to Ready --acting-role analyst` refuses, so the same
        # destination reached by creation must refuse through the same envelope
        # -- and must not leave an Issue behind on the way to the refusal.
        gh = FakeGh()
        code, _, err = self._run(
            "create-card", "--title", "t", "--body", "b",
            "--status", "Ready", "--role", "dev", "--acting-role", "analyst",
            gh=gh,
        )
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(err)["refusal"], "ActionForbidden")
        self.assertEqual(gh.calls_matching("issue", "create"), [])

    def test_brief_renders_lanes_and_a_recommendation(self):
        code, out, _ = self._run("brief")
        self.assertEqual(code, 0)
        self.assertIn("By lane", out)
        self.assertIn("Recommended next:", out)

    def test_queue_lists_only_deliveries_awaiting_a_verdict(self):
        _, out, _ = self._run("queue")
        payload = json.loads(out)
        self.assertEqual([c["number"] for c in payload["queue"]], [21])
        self.assertEqual([c["number"] for c in payload["awaiting_human"]], [22])
        self.assertIn("does not issue", payload["note"])

    def test_bootstrap_is_read_only(self):
        gh = FakeGh()
        code, out, _ = self._run("bootstrap", "--role", "lead", gh=gh)
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(payload["seat"], "lead")
        self.assertEqual(payload["mutations_performed"], [])
        self.assertEqual(gh.calls_matching("project", "item-edit"), [])
        self.assertEqual(gh.calls_matching("issue", "comment"), [])


class ConsumerCommandTests(CliTests):
    """Round-trips through main(), asserting the CLI envelope contract.

    Subclasses CliTests to reuse its tmpdir config fixture.
    """

    def _run_git(self, *argv, gh=None, git=None):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = producer_board.main(
                ["--config", str(self.config_path), *argv],
                gh=gh or FakeGh(), git=git,
            )
        return code, out.getvalue(), err.getvalue()

    def test_claim_prints_an_ok_envelope_and_exits_zero(self):
        code, out, _ = self._run_git(
            "claim", "12", "--acting-role", "dev",
            gh=FakeGh(items=board_with((12, "Implement parser", "Ready", "dev"))),
            git=FakeGit(),
        )
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(out)["ok"])

    def test_a_lost_race_exits_one_and_never_reports_success(self):
        # The failure a skill is most likely to misread. It must not exit 0.
        code, out, _ = self._run_git(
            "claim", "12", "--acting-role", "dev",
            gh=FakeGh(items=board_with((12, "x", "Ready", "dev"))),
            git=FakeGit(race_lost=True),
        )
        self.assertEqual(code, 1)
        payload = json.loads(out)
        self.assertFalse(payload["ok"])
        self.assertTrue(payload["race_lost"])
        self.assertNotIn("partial", payload)

    def test_accept_takes_only_an_issue_number(self):
        args = producer_board._build_parser().parse_args(["accept", "21"])
        self.assertEqual(args.command, "accept")
        self.assertEqual(args.issue, 21)
        # No flag exists through which a caller could steer the route.
        for forbidden in ("merge", "acceptance", "force", "route"):
            self.assertFalse(hasattr(args, forbidden), forbidden)

    def test_there_is_no_command_that_merges_a_chosen_pull_request(self):
        parser = producer_board._build_parser()
        for attempt in (["merge", "57"], ["merge-pr", "57"], ["request-merge", "57"]):
            with self.assertRaises(SystemExit, msg=str(attempt)):
                parser.parse_args(attempt)

    def test_claim_is_restricted_to_the_two_authoring_seats(self):
        parser = producer_board._build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["claim", "12", "--acting-role", "qa"])

    def test_worktree_status_is_read_only(self):
        gh = FakeGh(items=board_with((23, "Active build", "In Progress", "dev")))
        code, _, _ = self._run_git("worktree-status", gh=gh, git=FakeGit())
        self.assertEqual(code, 0)
        self.assertEqual(gh.calls_matching("project", "item-edit"), [])
        self.assertEqual(gh.calls_matching("issue", "comment"), [])

    def test_a_refusal_prints_to_stderr_and_exits_one(self):
        gh = FakeGh(items=board_with((12, "x", "Backlog", "dev")))
        code, out, err = self._run_git(
            "claim", "12", "--acting-role", "dev", gh=gh, git=FakeGit()
        )
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertFalse(json.loads(err)["ok"])

    def test_accept_routes_and_exits_zero(self):
        payload = {
            "verdict": "pass", "card": 21, "head_sha": "a" * 40,
            "pull_request": "p",
            "review_dimensions": list(REQUIRED_DIMENSIONS),
            "changed_files": ["src/parser.py", "tests/test_parser.py"],
            "test_strength": [{"dimension": "branch", "evidence": "14/14",
                               "falsified_by": "reverted the guard -> "
                                               "test_rejects_empty failed"}],
            "checks": ["unittest: 305 passed"],
            "next_role": "qa",
        }
        comment = VERDICT_MARKER + "\n\n```json\n" + json.dumps(payload) + "\n```"
        gh = FakeGh(
            items=board_with((21, "Delivery", "In Review", "qa")), comments=[comment]
        )
        code, out, _ = self._run_git("accept", "21", gh=gh, git=FakeGit())
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["acceptance"], "protected_change")
        # required_checks is empty in the default test config, so the
        # fail-closed rule fires and nothing is armed for merge.
        self.assertEqual(gh.calls_matching("pr", "merge"), [])


if __name__ == "__main__":
    unittest.main()
