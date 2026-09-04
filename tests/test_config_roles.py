"""Per-role operational configuration, and the merge-mode renames.

Two changes from the 2026-08-21 team-lead review live here.

First, retry and merge behaviour is scoped per role. The reasoning was that
architect, dev, qa, and the merge executor behave as independent people with
independent failure modes, so one global retry budget cannot express "the
architect gets two attempts, QA gets three". Top-level values remain the
default; ``roles`` overrides them field by field, so a role that only wants a
different ``max_retries`` does not have to restate the whole schedule.

Second, ``spec_merge_mode`` and ``merge_mode`` were judged unreadable next to
each other -- neither name says which Pull Request it governs. They are now
``spec_pr_merge_mode`` and ``code_pr_merge_mode``.

The old names were accepted and rewritten for two weeks. Since 2026-09-04 they
are **refused**, with the error naming the key to write instead: a rename the
tooling keeps absorbing is a rename nothing downstream is forced to notice, and
that is how the dashboard spent a week writing a key the plugin no longer
stored. See ``docs/decisions/2026-09-04-retiring-renamed-config-keys.md``.
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).parent))

from agent_teams.config import (  # noqa: E402
    Config, ConfigError, RecoveryConfig, ROLE_CONFIG_SEATS,
)


def config(**overrides):
    base = {"repo": "acme/widgets", "project_owner": "acme", "project_number": 1}
    base.update(overrides)
    return Config.from_dict(base)


class RoleRecoveryTests(unittest.TestCase):
    def test_absent_roles_block_gives_every_seat_the_global_schedule(self):
        subject = config(recovery={"max_retries": 4})
        for seat in ROLE_CONFIG_SEATS:
            self.assertEqual(subject.recovery_for(seat).max_retries, 4, seat)

    def test_role_override_applies_to_that_seat_only(self):
        subject = config(
            recovery={"max_retries": 1},
            roles={"qa": {"recovery": {"max_retries": 3}}},
        )
        self.assertEqual(subject.recovery_for("qa").max_retries, 3)
        self.assertEqual(subject.recovery_for("dev").max_retries, 1)
        self.assertEqual(subject.recovery_for("architect").max_retries, 1)

    def test_override_is_field_by_field_not_wholesale_replacement(self):
        """A role naming one field must inherit the rest of the schedule.

        Wholesale replacement would silently reset backoff to the dataclass
        default, so a role asking for one more retry would also, invisibly,
        get a different delay.
        """
        subject = config(
            recovery={
                "max_retries": 1,
                "initial_backoff_seconds": 7.0,
                "backoff_multiplier": 3.0,
                "max_backoff_seconds": 90.0,
            },
            roles={"dev": {"recovery": {"max_retries": 2}}},
        )
        resolved = subject.recovery_for("dev")
        self.assertEqual(resolved.max_retries, 2)
        self.assertEqual(resolved.initial_backoff_seconds, 7.0)
        self.assertEqual(resolved.backoff_multiplier, 3.0)
        self.assertEqual(resolved.max_backoff_seconds, 90.0)

    def test_role_delays_are_computed_from_the_resolved_schedule(self):
        subject = config(
            recovery={"initial_backoff_seconds": 5.0, "backoff_multiplier": 2.0},
            roles={"qa": {"recovery": {"max_retries": 3}}},
        )
        self.assertEqual(
            subject.recovery_for("qa").retry_delays_seconds(), (5.0, 10.0, 20.0)
        )

    def test_unknown_seat_is_refused_and_names_the_valid_seats(self):
        with self.assertRaises(ConfigError) as caught:
            config(roles={"wizard": {"recovery": {"max_retries": 1}}})
        message = str(caught.exception)
        self.assertIn("wizard", message)
        self.assertIn("merge_master", message)

    def test_recovery_for_rejects_an_unknown_seat_at_call_time(self):
        with self.assertRaises(ValueError):
            config().recovery_for("wizard")

    def test_roles_block_does_not_disturb_dispatch_roles(self):
        """`roles` and `dispatch_roles` are different lists, and were briefly
        the same local variable.

        The first draft of the parser reused the name, so a `roles` block
        silently overwrote the dispatch allow-list with its own seat keys. A
        block naming only valid seats produced no error at all -- the board
        just quietly stopped dispatching two of three roles. Asserted here
        because nothing else in the suite would notice.
        """
        subject = config(roles={"qa": {"recovery": {"max_retries": 2}}})
        self.assertEqual(subject.dispatch_roles, ("architect", "dev", "qa"))

    def test_role_recovery_is_validated_like_the_global_one(self):
        with self.assertRaisesRegex(ConfigError, r"roles\.qa\.recovery\.max_retries"):
            config(roles={"qa": {"recovery": {"max_retries": -1}}})

    def test_every_role_problem_is_reported_together(self):
        """Validation reports all defects at once; this must hold per role too."""
        with self.assertRaises(ConfigError) as caught:
            config(roles={
                "qa": {"recovery": {"max_retries": -1}},
                "dev": {"recovery": {"backoff_multiplier": 0.5}},
            })
        message = str(caught.exception)
        self.assertIn("roles.qa.recovery.max_retries", message)
        self.assertIn("roles.dev.recovery.backoff_multiplier", message)


class RoleKeyOwnershipTests(unittest.TestCase):
    """A key must be refused under a role that does not consume it.

    Silently ignoring it is the failure this whole change exists to prevent:
    the team lead's complaint was that you cannot tell which agent reads which
    field, and a field that parses but does nothing is the worst version of
    that.
    """

    def test_architect_owns_the_spec_pull_request_mode(self):
        subject = config(roles={"architect": {"spec_pr_merge_mode": "manual"}})
        self.assertEqual(subject.effective_spec_pr_merge_mode(), "manual")

    def test_dev_may_not_set_the_spec_pull_request_mode(self):
        with self.assertRaises(ConfigError) as caught:
            config(roles={"dev": {"spec_pr_merge_mode": "manual"}})
        message = str(caught.exception)
        self.assertIn("spec_pr_merge_mode", message)
        self.assertIn("architect", message)

    def test_merge_master_owns_the_code_pull_request_settings(self):
        subject = config(roles={"merge_master": {
            "code_pr_merge_mode": "manual", "code_pr_merge_method": "rebase",
        }})
        self.assertEqual(subject.effective_code_pr_merge_mode(), "manual")
        self.assertEqual(subject.effective_code_pr_merge_method(), "rebase")

    def test_qa_may_not_set_the_code_merge_method(self):
        with self.assertRaises(ConfigError) as caught:
            config(roles={"qa": {"code_pr_merge_method": "rebase"}})
        message = str(caught.exception)
        self.assertIn("code_pr_merge_method", message)
        self.assertIn("merge_master", message)

    def test_role_merge_values_are_validated_against_the_same_vocabulary(self):
        with self.assertRaisesRegex(ConfigError, "roles.architect.spec_pr_merge_mode"):
            config(roles={"architect": {"spec_pr_merge_mode": "whenever"}})
        with self.assertRaisesRegex(ConfigError, "roles.merge_master"):
            config(roles={"merge_master": {"code_pr_merge_method": "fast-forward"}})

    def test_effective_values_fall_back_to_the_top_level_default(self):
        subject = config(
            spec_pr_merge_mode="manual",
            code_pr_merge_mode="manual",
            code_pr_merge_method="rebase",
        )
        self.assertEqual(subject.effective_spec_pr_merge_mode(), "manual")
        self.assertEqual(subject.effective_code_pr_merge_mode(), "manual")
        self.assertEqual(subject.effective_code_pr_merge_method(), "rebase")


class MergeModeRenameTests(unittest.TestCase):
    def test_new_names_parse(self):
        subject = config(
            spec_pr_merge_mode="manual",
            code_pr_merge_mode="manual",
            code_pr_merge_method="merge",
        )
        self.assertEqual(subject.spec_pr_merge_mode, "manual")
        self.assertEqual(subject.code_pr_merge_mode, "manual")
        self.assertEqual(subject.code_pr_merge_method, "merge")

    # Superseded 2026-09-04. Four tests here previously pinned the opposite
    # behaviour: `test_legacy_names_still_parse`,
    # `test_legacy_names_are_dropped_on_save`,
    # `test_new_name_wins_when_both_are_present`, and
    # `test_legacy_names_are_validated_against_the_same_vocabulary`. They were
    # correct for a compatibility window that has now been closed
    # deliberately -- the window let the dashboard write `merge_mode` for a
    # week while the plugin stored `code_pr_merge_mode`, and the user's merge
    # choice appeared to revert on every reload with nothing failing anywhere.
    # See docs/decisions/2026-09-04-retiring-renamed-config-keys.md.

    def test_a_retired_name_is_refused_rather_than_translated(self):
        for old, current in (
            ("spec_merge_mode", "spec_pr_merge_mode"),
            ("merge_mode", "code_pr_merge_mode"),
            ("merge_method", "code_pr_merge_method"),
        ):
            with self.subTest(old=old):
                with self.assertRaises(ConfigError) as caught:
                    config(**{old: "manual"})
                self.assertIn(old, str(caught.exception))
                self.assertIn(current, str(caught.exception))

    def test_a_retired_name_is_not_silently_ignored(self):
        """The refusal is the whole point; an ignored key is the failure mode.

        Unknown keys are dropped by `from_dict`, so deleting the alias without
        adding this rule would have made `{"merge_mode": "manual"}` mean
        `code_pr_merge_mode="automatic"` -- a file that reads as though it were
        honoured and is not. That is strictly worse than the compatibility it
        replaced, which is why retirement is an error and not a deletion.
        """
        with self.assertRaises(ConfigError):
            config(merge_mode="manual")

    def test_every_retired_name_is_reported_in_one_pass(self):
        """Six re-runs of `doctor` to learn six renames is tooling failing you."""
        with self.assertRaises(ConfigError) as caught:
            config(
                spec_merge_mode="manual",
                merge_mode="manual",
                merge_method="rebase",
            )
        message = str(caught.exception)
        for name in ("spec_merge_mode", "merge_mode", "merge_method"):
            self.assertIn(name, message)

    def test_a_retired_name_is_refused_even_beside_its_replacement(self):
        """Both names present is exactly what a half-migrated writer emits.

        Previously the current name silently won. Silently winning is how the
        writer never found out it was still emitting the dead one.
        """
        with self.assertRaisesRegex(ConfigError, "spec_merge_mode"):
            config(spec_merge_mode="manual", spec_pr_merge_mode="direct")

    def test_a_retired_name_is_refused_inside_a_roles_block(self):
        with self.assertRaises(ConfigError) as caught:
            config(roles={"merge_master": {"merge_method": "rebase"}})
        message = str(caught.exception)
        self.assertIn("roles.merge_master.'merge_method'", message)
        self.assertIn("code_pr_merge_method", message)

    def test_a_retired_role_key_does_not_also_report_as_an_unknown_setting(self):
        """One mistake, one message. Two would send the reader hunting a second."""
        with self.assertRaises(ConfigError) as caught:
            config(roles={"merge_master": {"merge_method": "rebase"}})
        self.assertNotIn("has no setting", str(caught.exception))

    def test_round_trip_preserves_roles(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            original = config(roles={
                "qa": {"recovery": {"max_retries": 3}},
                "merge_master": {"code_pr_merge_method": "rebase"},
            })
            original.write(path)
            self.assertEqual(Config.load(path), original)

    def test_empty_roles_block_is_omitted_from_written_config(self):
        self.assertNotIn("roles", config().to_dict())

    def test_revision_changes_when_only_a_role_override_changes(self):
        """The dashboard's live-reload signal must see a per-role edit."""
        before = config().revision
        after = config(roles={"qa": {"recovery": {"max_retries": 9}}}).revision
        self.assertNotEqual(before, after)

    def test_revision_is_computed_from_the_current_vocabulary_only(self):
        # Superseded 2026-09-04: this asserted that a legacy-named file and a
        # current-named one hash identically, which only had meaning while both
        # loaded. The property that still matters is that `revision` is a
        # function of the resolved settings, so the dashboard's live-reload
        # signal fires on a real change and not on a spelling.
        first = config(spec_pr_merge_mode="manual", code_pr_merge_mode="manual")
        second = config(code_pr_merge_mode="manual", spec_pr_merge_mode="manual")
        self.assertEqual(first.revision, second.revision)
        self.assertNotEqual(first.revision, config().revision)


class RecoveryConfigMergeTests(unittest.TestCase):
    def test_merged_returns_a_new_schedule_without_mutating_the_base(self):
        base = RecoveryConfig(max_retries=1, initial_backoff_seconds=5.0)
        merged = base.merged({"max_retries": 3})
        self.assertEqual(merged.max_retries, 3)
        self.assertEqual(merged.initial_backoff_seconds, 5.0)
        self.assertEqual(base.max_retries, 1)


class UiPathTests(unittest.TestCase):
    def test_defaults_cover_the_common_web_front_end_shapes(self):
        subject = config()
        for path in ("src/App.tsx", "index.html", "src/ui/map.vue", "app.css"):
            self.assertTrue(subject.is_ui_path(path), path)

    def test_backend_and_documentation_paths_are_not_user_interface(self):
        subject = config()
        for path in ("src/server.py", "docs/spec.md", "README.md"):
            self.assertFalse(subject.is_ui_path(path), path)

    def test_repository_patterns_extend_rather_than_replace_the_defaults(self):
        subject = config(ui_paths=["templates/**"])
        self.assertTrue(subject.is_ui_path("templates/home.jinja"))
        self.assertTrue(subject.is_ui_path("src/App.tsx"))

    def test_ui_paths_must_be_a_list(self):
        with self.assertRaisesRegex(ConfigError, "ui_paths"):
            config(ui_paths="src/**")


if __name__ == "__main__":
    unittest.main()
