"""The property that lets agent-teams govern its own changes safely.

Gap (A) of `docs/traces/2026-09-04-merge-mode-evidence-chain.md` is that this
plugin does not run its own work through its own pipeline. The objection to
closing it sounds fatal at first: **the QA that reviews a change to
`policy.py` runs on `policy.py`.** A diff that breaks `validate_verdict` would
be waved through by the very code it broke, and the suite could be green
because the assertions were edited with it.

That objection is wrong here, and this file is why. Every seat invokes
``${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py`` -- the **installed**
plugin, which is the last *merged* version -- while the code under review sits
in the Pull Request and its detached worktree. Old plugin reviews new plugin.
It is the compiler bootstrap: you compile the new compiler with the old one,
and a defect in the new source cannot excuse itself.

That property currently holds by convention, and convention is what this
session has spent all day finding the cost of. A single skill rewritten to call
a repository-relative `scripts/producer_board.py` would silently turn
self-review into self-excusing, and nothing would notice -- the suite would
stay green, because nothing looks.

So it is checked here. What is *not* checkable, and lives in
`docs/decisions/2026-09-04-self-hosting-the-pipeline.md` as a written rule:
the installed plugin is only ever updated *after* a merge. Installing an
unmerged build is how you hand the fixed point back.

See docs/decisions/2026-09-04-self-hosting-the-pipeline.md.
"""

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from agent_teams.config import DEFAULT_PROTECTED_PATHS  # noqa: E402

REPO_ROOT = Path(__file__).parents[1]

#: Where a seat reads its instructions. Documentation is deliberately excluded:
#: `docs/CONFIGURATION.md` shows a consuming user an absolute install path,
#: which is correct there and would be wrong in a skill.
SEAT_INSTRUCTION_ROOTS = ("skills", "agents")

#: A line that actually runs the entry point, as opposed to naming it in prose.
#: "run every `producer_board.py` command with ..." is guidance; only a real
#: invocation can bind the wrong copy.
INVOCATION = re.compile(r"(^|[\s`])(python[0-9.]*|py)\s+\S*producer_board\.py")

#: The plugin's own authority. A change here routes to a human even under
#: self-hosting, which is the belt to the fixed point's braces.
AUTHORITY_FILES = (
    "scripts/agent_teams/policy.py",
    "scripts/agent_teams/model.py",
    "scripts/agent_teams/workflows.py",
    "scripts/agent_teams/git.py",
)


def _invocations():
    """Every executable invocation in a seat's instructions, with its file."""
    found = []
    for base in SEAT_INSTRUCTION_ROOTS:
        for path in sorted((REPO_ROOT / base).rglob("*.md")):
            for number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1
            ):
                if INVOCATION.search(line):
                    found.append((path.relative_to(REPO_ROOT).as_posix(), number, line))
    return found


class BootstrapFixedPointTests(unittest.TestCase):
    """A seat runs the installed plugin, never the checkout under review."""

    def test_the_scan_finds_the_invocations_it_is_meant_to_guard(self):
        """Guard. An empty scan would make the rule below vacuous."""
        found = _invocations()
        self.assertGreater(len(found), 15, "the scan found almost no invocations")
        files = {relative for relative, _, _ in found}
        self.assertTrue(
            any(f.startswith("skills/verifying-delivery/") for f in files),
            "the QA skill is the one that most needs the fixed point",
        )

    def test_every_invocation_runs_the_installed_plugin(self):
        offences = [
            f"{relative}:{number} {line.strip()[:90]}"
            for relative, number, line in _invocations()
            if "CLAUDE_PLUGIN_ROOT" not in line
        ]
        self.assertEqual(
            offences, [],
            "a seat would run the checkout under review instead of the "
            "installed plugin, so a defect in the diff could approve itself: "
            + "; ".join(offences),
        )


class AuthorityStaysAtTheHumanGateTests(unittest.TestCase):
    """Self-hosting does not put the plugin's own authority on autopilot.

    The fixed point makes self-review sound; this keeps it *supervised*. A
    change to the four files that decide who may do what routes to a person
    whatever the review said, which is what makes "run our own work through our
    own pipeline" a smaller decision than it first appears.
    """

    def test_the_authority_code_is_protected(self):
        protected = {g for globs in DEFAULT_PROTECTED_PATHS.values() for g in globs}
        for name in AUTHORITY_FILES:
            self.assertIn(name, protected, f"{name} must route to a human")

    def test_the_vocabulary_is_protected_too(self):
        """Added the same day; pinned here because self-hosting is what makes
        it matter -- this is the category a config change would travel through."""
        protected = {g for globs in DEFAULT_PROTECTED_PATHS.values() for g in globs}
        self.assertIn("scripts/agent_teams/config.py", protected)
        self.assertIn("docs/CONFIGURATION.md", protected)


if __name__ == "__main__":
    unittest.main()
