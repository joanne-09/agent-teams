"""The configuration vocabulary is exported, so consumers stop copying it.

`tests/test_config_vocabulary.py` made a rename checkable *inside this
repository*. It cannot reach the dashboard, which keeps its own hand-written
list of our setting names in `server/lib/agent-teams/config-schema.js` — a file
whose header says, in as many words, *"Keep this file in sync with that doc."*
A comment where a check should be. That copy has now drifted twice: it wrote
`merge_mode` after the rename, and it told users old names were "still loaded
and rewritten" after they had been retired.

Telling the dashboard to try harder is not a mechanism. Removing the copy is.
So `config.vocabulary()` emits what is *true of the code* — which keys exist,
their types, defaults, enumerations, which are required, which seat may
override what, and which names are retired — every value derived from `Config`
itself rather than restated. A consumer renders it; nobody retypes it.

The split is deliberate and is the one that file already claims for itself:

* **Facts about the code** — key names, types, defaults, options, retirements.
  Ours. Exported. Impossible to drift, because they are read off the dataclass.
* **Wording and layout** — section titles, help text, which fields are
  "advanced". The consumer's. Never ours.

These tests pin the first half: everything derived, nothing restated, and the
export covering exactly what `Config` accepts.

See docs/decisions/2026-09-04-governing-the-config-vocabulary.md.
"""

import sys
import unittest
from dataclasses import fields
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from agent_teams.config import (  # noqa: E402
    Config, MERGE_METHODS, MERGE_MODES, RETIRED_KEYS, ROLE_CONFIG_KEYS,
    SPEC_MERGE_MODES, vocabulary,
)


class ExportShapeTests(unittest.TestCase):
    def setUp(self):
        self.v = vocabulary()
        self.by_key = {s["key"]: s for s in self.v["settings"]}

    def test_it_carries_the_four_sections_a_consumer_needs(self):
        for name in ("settings", "retired", "role_keys", "recovery_fields"):
            self.assertIn(name, self.v)

    def test_every_setting_declares_the_fields_a_form_needs(self):
        for setting in self.v["settings"]:
            for name in ("key", "type", "required", "default", "options"):
                self.assertIn(name, setting, setting)

    def test_it_is_json_serialisable(self):
        """It crosses a process boundary as JSON, so tuples must already be lists."""
        import json
        json.loads(json.dumps(self.v))


class CoversExactlyWhatConfigAcceptsTests(unittest.TestCase):
    """The export and `Config` are the same vocabulary, both directions.

    A key `Config` accepts but the export omits is a setting no consumer can
    offer. A key the export names but `Config` rejects is a form that writes
    files the plugin refuses.
    """

    def setUp(self):
        self.v = vocabulary()
        self.exported = {s["key"] for s in self.v["settings"]}
        # `recovery` is exported flattened, as `recovery.<field>`, because that
        # is the shape a form edits. Compare on the top-level name.
        self.top = {k.split(".", 1)[0] for k in self.exported}

    def test_every_config_field_is_exported(self):
        missing = sorted({f.name for f in fields(Config)} - self.top)
        self.assertEqual(missing, [], f"not exported: {missing}")

    def test_nothing_is_exported_that_config_does_not_accept(self):
        phantom = sorted(self.top - {f.name for f in fields(Config)})
        self.assertEqual(phantom, [], f"exported but not a Config field: {phantom}")

    def test_recovery_is_flattened_into_editable_leaves(self):
        self.assertIn("recovery.max_retries", self.exported)
        self.assertIn("recovery.initial_backoff_seconds", self.exported)


class DerivedNotRestatedTests(unittest.TestCase):
    """Every value is read off `Config`; none is typed a second time.

    This is the whole point. A second copy of a default is a second thing to
    forget, which is the defect this export exists to remove -- not to relocate.
    """

    def setUp(self):
        self.by_key = {s["key"]: s for s in vocabulary()["settings"]}

    def test_defaults_match_the_dataclass(self):
        live = Config(repo="a/b", project_owner="a", project_number=1)
        for name in ("wip_limit", "handoff_cap", "workspace", "claim_ttl_hours",
                     "code_pr_merge_mode", "code_pr_merge_method",
                     "spec_pr_merge_mode"):
            self.assertEqual(
                self.by_key[name]["default"], getattr(live, name),
                f"{name} default was restated instead of derived",
            )

    def test_recovery_defaults_match_the_dataclass(self):
        live = Config(repo="a/b", project_owner="a", project_number=1).recovery
        self.assertEqual(
            self.by_key["recovery.max_retries"]["default"], live.max_retries
        )

    def test_the_three_required_settings_are_marked_required(self):
        required = {s["key"] for s in vocabulary()["settings"] if s["required"]}
        self.assertEqual(required, {"repo", "project_owner", "project_number"})

    def test_enumerations_come_from_the_module_constants(self):
        self.assertEqual(
            self.by_key["code_pr_merge_method"]["options"], list(MERGE_METHODS)
        )
        self.assertEqual(
            self.by_key["code_pr_merge_mode"]["options"], list(MERGE_MODES)
        )
        self.assertEqual(
            self.by_key["spec_pr_merge_mode"]["options"], list(SPEC_MERGE_MODES)
        )

    def test_a_non_enum_setting_offers_no_options(self):
        self.assertEqual(self.by_key["wip_limit"]["options"], [])

    def test_types_are_the_widget_kinds_a_form_can_render(self):
        self.assertEqual(self.by_key["repo"]["type"], "string")
        self.assertEqual(self.by_key["wip_limit"]["type"], "int")
        self.assertEqual(self.by_key["dispatch_roles"]["type"], "string[]")
        self.assertEqual(self.by_key["status_overrides"]["type"], "json")
        self.assertEqual(
            self.by_key["recovery.initial_backoff_seconds"]["type"], "float"
        )
        self.assertEqual(self.by_key["code_pr_merge_mode"]["type"], "enum")


class RetirementTravelsWithTheVocabularyTests(unittest.TestCase):
    """A consumer must be able to say what an old name became.

    The dashboard's stale note was wrong precisely because it described the
    retirement from memory. Ship the mapping and it cannot be described wrongly.
    """

    def test_every_retired_name_is_exported_with_its_replacement(self):
        self.assertEqual(vocabulary()["retired"], dict(RETIRED_KEYS))

    def test_no_retired_name_is_offered_as_a_setting(self):
        exported = {s["key"] for s in vocabulary()["settings"]}
        for old in RETIRED_KEYS:
            self.assertNotIn(old, exported)


class PerSeatOverridesTravelTooTests(unittest.TestCase):
    """Which seat may override what is a fact about the code, not a layout."""

    def test_role_keys_match_the_authority_table(self):
        self.assertEqual(
            vocabulary()["role_keys"],
            {seat: list(keys) for seat, keys in ROLE_CONFIG_KEYS.items()},
        )

    def test_recovery_fields_are_listed_so_a_consumer_can_compose_them(self):
        v = vocabulary()
        self.assertIn("max_retries", v["recovery_fields"])
        # A consumer builds `roles.<seat>.recovery.<field>` from these two.
        self.assertIn("qa", v["role_keys"])
        self.assertIn("recovery", v["role_keys"]["qa"])


if __name__ == "__main__":
    unittest.main()
