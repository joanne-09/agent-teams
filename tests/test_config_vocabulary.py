"""The configuration vocabulary is one vocabulary, and it is checkable.

This is the repair for what `docs/traces/2026-09-04-merge-mode-evidence-chain.md`
found. That trace followed one change -- the 2026-08-21 rename of `merge_mode`
into `spec_pr_merge_mode` and `code_pr_merge_mode` -- and could not answer a
single one of the team lead's four questions, because the change never became a
Card, a specification, a Pull Request, or a verdict. It was typed into a session
and committed by hand.

The trace named three reasons. This file closes the one that is a mechanism
rather than a scope decision:

**A configuration change reaches five consumers and nothing checks that it
reached them.** One setting, five places that name it, three of them missed --
and each miss was found later by a different accident, on a different day, by a
different person. None was found by a check, because no check existed.

So the tests here are that check. In the order they matter:

1. `RetiredNameSweepTests` -- a retired name may appear only where the
   retirement itself is the subject. Anywhere else it is a consumer that was
   missed. **This is the test that would have failed on 2026-08-27**, the day
   of the rename, instead of on 2026-09-04 when someone went looking.
2. `VocabularyIsOneVocabularyTests` -- `Config`'s fields and the settings
   tables in `docs/CONFIGURATION.md` are the same set, checked both ways. A
   key the code accepts and the reference does not document is unreachable; a
   key the reference documents and the code rejects is a lie.
3. `EverySettingNamesItsConsumerTests` -- the `Consumed by` column is never
   empty. "You could not tell which agent read which setting" is the sentence
   that started the whole rename.
4. `VocabularyIsGovernedTests` -- changing the vocabulary routes to a human,
   which is the link between a Card and a specification that did not exist.

The technique is deliberately the same one `tests/test_findings.py` uses for
the code-smell catalogue: compare the document and the code mechanically, in
both directions, with a guard so an empty parse cannot pass for the wrong
reason. It was proven on a different vocabulary the same day.

See docs/decisions/2026-09-04-governing-the-config-vocabulary.md.
"""

import re
import sys
import unittest
from dataclasses import fields
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from agent_teams.config import (  # noqa: E402
    Config, DEFAULT_PROTECTED_PATHS, RETIRED_KEYS,
)

REPO_ROOT = Path(__file__).parents[1]
CONFIGURATION_DOC = REPO_ROOT / "docs" / "CONFIGURATION.md"

#: The header every settings table in the reference carries. Anchoring on it
#: keeps the parser off the merge-matrix and per-seat tables, whose first
#: column is a value rather than a setting name.
SETTINGS_TABLE_HEADER = "| Setting | Values | Default | Consumed by | Meaning |"

#: Two audiences, two rules, and the asymmetry is the point.
#:
#: An agent reading ``skills/`` or ``agents/`` cannot tell narration from
#: instruction. A retired key named anywhere in those files is a key some seat
#: will use, so the rule there is absolute -- which is exactly the miss that
#: survived nine days in ``skills/authoring-spec/SKILL.md``.
AGENT_FACING_ROOTS = ("scripts", "skills", "agents", ".claude-plugin")

#: ``config.py`` holds ``RETIRED_KEYS`` itself: the machinery that refuses the
#: old names has to be able to spell them.
AGENT_FACING_EXEMPT = ("scripts/agent_teams/config.py",)

#: A human reading ``docs/`` can tell "this was renamed" from "set this". So
#: prose may name an old key freely -- a document that could not would be
#: unable to explain what happened -- but a **settings-table row** may not
#: define one, because a row is the shape a live setting has. The single
#: exception is a row that also names the replacement: that is a migration
#: table, and it is the one place a retired name belongs in a first cell.
HUMAN_FACING_ROOTS = ("docs",)
HUMAN_FACING_FILES = ("README.md", "CLAUDE_TESTING.md")

#: Records of the retirement, where even a settings-shaped mention is history
#: rather than instruction.
HUMAN_FACING_EXEMPT = ("docs/decisions", "docs/traces", "docs/plans")

SWEPT_SUFFIXES = {".py", ".md", ".json", ".yaml", ".yml", ".js"}


def _documented_settings():
    """Every row of every settings table, as (name, consumed_by).

    Rows are taken only from tables carrying SETTINGS_TABLE_HEADER, and only
    while the table continues, so the reference's other tables -- the merge
    matrix, the per-seat table -- cannot leak value names into the vocabulary.
    """
    rows: list[tuple[str, str]] = []
    in_table = False
    for line in CONFIGURATION_DOC.read_text(encoding="utf-8").splitlines():
        if line.strip() == SETTINGS_TABLE_HEADER:
            in_table = True
            continue
        if not in_table:
            continue
        if not line.startswith("|"):
            in_table = False
            continue
        if set(line.replace("|", "").strip()) <= {"-", " "}:
            continue  # the ---|--- separator
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        match = re.match(r"^`([a-z_]+)`$", cells[0])
        if match:
            rows.append((match.group(1), cells[3] if len(cells) > 3 else ""))
    return rows


def _files_under(roots, suffixes=SWEPT_SUFFIXES):
    found: list[Path] = []
    for root in roots:
        base = REPO_ROOT / root
        if not base.is_dir():
            continue
        found.extend(
            path for path in base.rglob("*")
            if path.is_file() and path.suffix in suffixes
        )
    return found


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _under(relative: str, prefixes) -> bool:
    return any(relative == p or relative.startswith(p + "/") for p in prefixes)


def _names(line: str, key: str) -> bool:
    return re.search(rf"(?<![a-z_]){re.escape(key)}(?![a-z_])", line) is not None


def _first_cell(line: str) -> str:
    if not line.lstrip().startswith("|"):
        return ""
    cells = line.strip().strip("|").split("|")
    return cells[0].strip() if cells else ""


def agent_facing_offences() -> list[str]:
    """Any mention at all, in anything a seat reads as instruction."""
    offences = []
    for path in _files_under(AGENT_FACING_ROOTS):
        relative = _relative(path)
        if _under(relative, AGENT_FACING_EXEMPT):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            for old, current in RETIRED_KEYS.items():
                if _names(line, old):
                    offences.append(
                        f"{relative}:{number} names {old!r}; a seat reading "
                        f"this will use it. Say {current!r}."
                    )
    return offences


def human_facing_offences() -> list[str]:
    """A settings-table row defining a retired key, without its replacement."""
    offences = []
    paths = _files_under(HUMAN_FACING_ROOTS) + [
        REPO_ROOT / name for name in HUMAN_FACING_FILES
    ]
    for path in paths:
        if not path.is_file():
            continue
        relative = _relative(path)
        if _under(relative, HUMAN_FACING_EXEMPT):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            for old, current in RETIRED_KEYS.items():
                if _first_cell(line) != f"`{old}`":
                    continue
                if _names(line, current):
                    continue  # a migration row: old -> new, which is correct
                offences.append(
                    f"{relative}:{number} documents {old!r} as a live "
                    f"setting; it was renamed to {current!r}."
                )
    return offences


# ------------------------------------------------- the check that was missing


class RetiredNameSweepTests(unittest.TestCase):
    """A retired name outside the retirement machinery is a missed consumer."""

    def test_the_sweep_actually_reads_the_files_that_matter(self):
        """Guard. An empty sweep would make every test below pass for nothing."""
        agent_files = {_relative(p) for p in _files_under(AGENT_FACING_ROOTS)}
        self.assertGreater(len(agent_files), 20)
        self.assertIn(
            "skills/authoring-spec/SKILL.md", agent_files,
            "the sweep must cover the skill where a miss survived nine days",
        )
        human_files = {_relative(p) for p in _files_under(HUMAN_FACING_ROOTS)}
        self.assertIn("docs/CONFIGURATION.md", human_files)
        self.assertTrue(
            any(f.startswith("docs/specs/") for f in human_files),
            "the sweep must cover docs/specs/ -- the longest-surviving miss",
        )

    def test_no_seat_is_ever_told_a_retired_name(self):
        """The check that would have failed on 2026-08-27, the day of the rename.

        Every offence is reported at once rather than first-one-wins, for the
        same reason ``validate_verdict`` reports every problem at once: a sweep
        that names one consumer per run makes the person run it five times.
        """
        offences = agent_facing_offences()
        self.assertEqual(
            offences, [],
            "retired names are still reachable by an agent: "
            + "; ".join(offences),
        )

    def test_no_document_defines_a_retired_name_as_a_live_setting(self):
        offences = human_facing_offences()
        self.assertEqual(
            offences, [],
            "documentation still presents retired keys as settings: "
            + "; ".join(offences),
        )

    def test_the_approved_specification_names_no_retired_key(self):
        """Pinned separately because this is the consumer that lasted longest.

        `docs/specs/**` is a protected path: a delivery touching it routes to
        a human. The rename changed the exact subject matter that document
        governs *without touching the file*, so the protection never engaged.
        Protection is on the path; the authority it guards is the content --
        which is why this test exists rather than trusting the path rule.
        """
        offences = [o for o in human_facing_offences()
                    if o.startswith("docs/specs/")]
        self.assertEqual(offences, [], "; ".join(offences))

    def test_a_migration_row_is_allowed_to_name_both(self):
        """The one shape a retired name belongs in a first cell.

        Pinned so that tightening the rule later cannot silently make the
        rename tables in CONFIGURATION.md unwritable -- a reference that
        cannot say "this became that" is how a migration goes unnoticed.
        """
        self.assertEqual(_first_cell("| `merge_mode` | `code_pr_merge_mode` |"),
                         "`merge_mode`")
        self.assertTrue(
            _names("| `merge_mode` | `code_pr_merge_mode` |",
                   "code_pr_merge_mode")
        )


# -------------------------------------------------- one vocabulary, both ways


class VocabularyIsOneVocabularyTests(unittest.TestCase):
    """`Config` and the reference document describe the same settings."""

    def setUp(self):
        self.documented = {name for name, _ in _documented_settings()}
        self.declared = {f.name for f in fields(Config)}

    def test_the_settings_tables_were_found(self):
        """Guard the parser before trusting either direction below."""
        self.assertGreater(len(self.documented), 10)
        self.assertIn("code_pr_merge_mode", self.documented)

    def test_every_setting_the_code_accepts_is_documented(self):
        missing = sorted(self.declared - self.documented)
        self.assertEqual(
            missing, [],
            "settings accepted by Config but absent from CONFIGURATION.md; a "
            "setting nobody can look up is a setting nobody will set "
            "correctly: " + ", ".join(missing),
        )

    def test_every_documented_setting_is_really_accepted(self):
        """The direction that catches a rename half-applied.

        A reference naming a key the code no longer accepts is exactly what
        the approved specification did for nine days.
        """
        phantom = sorted(self.documented - self.declared)
        self.assertEqual(
            phantom, [],
            "documented in CONFIGURATION.md but not a Config field: "
            + ", ".join(phantom),
        )


class EverySettingNamesItsConsumerTests(unittest.TestCase):
    """Which agent reads which setting is recorded, for every setting.

    "You could not tell which agent read which setting" is the complaint the
    whole rename came from. The reference has a `Consumed by` column; nothing
    checked that it was ever filled in.
    """

    def test_no_setting_is_documented_without_a_consumer(self):
        blank = [name for name, consumer in _documented_settings()
                 if not consumer.strip()]
        self.assertEqual(blank, [], "settings with no consumer recorded: "
                                    + ", ".join(blank))


# ------------------------------------------------ the link that did not exist


class VocabularyIsGovernedTests(unittest.TestCase):
    """Changing the vocabulary is a change a human approves.

    The trace's link 2 -- Card to specification -- had no mechanism at all: a
    configuration change touched no governed artifact, so nothing routed it to
    anybody. Protecting the two files that *are* the vocabulary gives that link
    the mechanism it was missing. It does not make the change impossible; it
    makes it visible, through the human gate that already exists.
    """

    def _protected(self):
        return {glob for globs in DEFAULT_PROTECTED_PATHS.values()
                for glob in globs}

    def test_the_configuration_reference_is_protected(self):
        self.assertIn("docs/CONFIGURATION.md", self._protected())

    def test_the_configuration_code_is_protected(self):
        self.assertIn("scripts/agent_teams/config.py", self._protected())

    def test_protection_is_not_silently_droppable(self):
        """Regression guard on the surrounding rule, not on this change.

        Repository policy may add protected patterns and may not remove one.
        If that ever stops holding, protecting these two files buys nothing.
        """
        self.assertTrue(DEFAULT_PROTECTED_PATHS)
        for category, globs in DEFAULT_PROTECTED_PATHS.items():
            self.assertTrue(globs, f"default category {category!r} is empty")


if __name__ == "__main__":
    unittest.main()
