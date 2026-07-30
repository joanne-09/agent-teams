"""One base for every expected failure in this package.

Expected failures are refusals, missing configuration, and GitHub problems --
things a Producer session should report cleanly and stop on. They are
deliberately distinguishable from programming errors, which should keep their
traceback rather than be flattened into a tidy JSON envelope.
"""

from __future__ import annotations


class AgentTeamsError(RuntimeError):
    """An expected configuration, validation, policy, or GitHub failure."""
