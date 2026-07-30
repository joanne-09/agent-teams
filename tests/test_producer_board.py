import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "producer_board.py"
SPEC = importlib.util.spec_from_file_location("producer_board", MODULE_PATH)
producer_board = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = producer_board
SPEC.loader.exec_module(producer_board)


FIELDS = {
    "fields": [
        {
            "id": "ROLE_FIELD",
            "name": "Role",
            "options": [
                {"id": f"ROLE_{name.upper()}", "name": name}
                for name in producer_board.ROLES
            ],
        },
        {
            "id": "STATUS_FIELD",
            "name": "Status",
            "options": [
                {"id": "STATUS_BACKLOG", "name": "Backlog"},
                {"id": "STATUS_READY", "name": "Ready"},
            ],
        },
    ]
}

ITEMS = {
    "items": [
        {
            "id": "ITEM_12",
            "status": "Ready",
            "role": "rd",
            "content": {
                "number": 12,
                "repository": "acme/widgets",
                "title": "Implement parser",
                "url": "https://github.com/acme/widgets/issues/12",
            },
        },
        {
            "id": "ITEM_8",
            "status": "Ready",
            "role": "architect",
            "content": {
                "number": 8,
                "repository": "acme/widgets",
                "title": "Specify parser",
                "url": "https://github.com/acme/widgets/issues/8",
            },
        },
        {
            "id": "ITEM_9",
            "status": "Blocked",
            "role": "rd",
            "content": {
                "number": 9,
                "repository": "acme/widgets",
                "title": "Blocked work",
                "url": "https://github.com/acme/widgets/issues/9",
            },
        },
        {
            "id": "ITEM_10",
            "status": "Ready",
            "content": {
                "number": 10,
                "repository": "acme/widgets",
                "title": "Missing Role",
                "url": "https://github.com/acme/widgets/issues/10",
            },
        },
        {
            "id": "ITEM_OTHER",
            "status": "Ready",
            "role": "rd",
            "content": {
                "number": 99,
                "repository": "acme/other",
                "title": "Wrong repository",
                "url": "https://github.com/acme/other/issues/99",
            },
        },
    ]
}


class FakeGh:
    def __init__(self):
        self.calls = []

    def run(self, args):
        args = list(args)
        self.calls.append(args)
        if args[:2] == ["auth", "status"]:
            return "authenticated"
        if args[:2] == ["issue", "create"]:
            return "https://github.com/acme/widgets/issues/42"
        if args[:2] in (["project", "item-edit"], ["issue", "comment"]):
            return ""
        raise AssertionError(f"unexpected gh run call: {args}")

    def json(self, args):
        args = list(args)
        self.calls.append(args)
        if args[:2] == ["project", "view"]:
            return {"id": "PROJECT_ID"}
        if args[:2] == ["project", "field-list"]:
            return FIELDS
        if args[:2] == ["project", "item-list"]:
            return ITEMS
        if args[:2] == ["project", "item-add"]:
            return {"id": "ITEM_42"}
        raise AssertionError(f"unexpected gh json call: {args}")


def config():
    return producer_board.Config(
        repo="acme/widgets",
        project_owner="acme",
        project_number=1,
    )


class ConfigTests(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "producer.json"
            config().write(path)
            self.assertEqual(producer_board.Config.load(path), config())

    def test_rejects_unknown_dispatch_role(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "producer.json"
            payload = {
                "repo": "acme/widgets",
                "project_owner": "acme",
                "project_number": 1,
                "dispatch_roles": ["wizard"],
            }
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(producer_board.ProducerError, "unknown"):
                producer_board.Config.load(path)


class BoardTests(unittest.TestCase):
    def setUp(self):
        self.gh = FakeGh()
        self.board = producer_board.Board(config(), self.gh)

    def test_normalises_only_configured_repo_cards(self):
        cards = self.board.cards()
        self.assertEqual([card["number"] for card in cards], [12, 8, 9, 10])
        self.assertEqual(cards[0]["role"], "rd")

    def test_dispatch_filters_and_orders(self):
        queue = self.board.dispatch()
        self.assertEqual([entry["number"] for entry in queue], [8, 12])
        self.assertIn("[role:architect]", queue[0]["prompt"])
        self.assertIn("[board-card:#12]", queue[1]["prompt"])

    def test_dispatch_by_role(self):
        queue = self.board.dispatch("rd")
        self.assertEqual([entry["number"] for entry in queue], [12])

    def test_rejects_unauthorised_handoff(self):
        with self.assertRaisesRegex(producer_board.ProducerError, "not allowed"):
            self.board.handoff(8, "architect", "analyst", "go backwards")

    def test_handoff_updates_role_and_comments(self):
        result = self.board.handoff(8, "architect", "rd", "Spec PR is ready.")
        self.assertEqual(result["role"], "rd")
        edit = next(call for call in self.gh.calls if call[:2] == ["project", "item-edit"])
        self.assertIn("ROLE_RD", edit)
        comment = next(call for call in self.gh.calls if call[:2] == ["issue", "comment"])
        self.assertIn("`architect` → `rd`", comment[-1])

    def test_intake_keeps_backlog_and_ends_at_architect(self):
        result = self.board.intake("Add parser", "Acceptance: parses JSON.")
        self.assertEqual(result["issue"], 42)
        self.assertEqual(result["status"], "Backlog")
        self.assertEqual(result["role"], "architect")
        edits = [call for call in self.gh.calls if call[:2] == ["project", "item-edit"]]
        selected_options = [call[-1] for call in edits]
        self.assertEqual(
            selected_options,
            ["STATUS_BACKLOG", "ROLE_ANALYST", "ROLE_ARCHITECT"],
        )

    def test_doctor_checks_required_fields(self):
        result = self.board.doctor()
        self.assertTrue(result["ok"])
        self.assertEqual(result["project_id"], "PROJECT_ID")


if __name__ == "__main__":
    unittest.main()
