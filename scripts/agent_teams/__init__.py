"""Deterministic services behind the agent-teams Producer skills.

The public entry point stays ``scripts/producer_board.py``. This package holds
the layers that entry point composes:

``model``      validated domain values (Role, Status, Card, Handoff, Verdict)
``policy``     pure legality: transitions, handoff authority, caps, seat actions
``config``     consuming-repo configuration and its validation
``github``     GitHub CLI invocation, pagination, and error classification
``board``      semantic board operations over the configured Project
``workflows``  multi-step transactions with explicit partial-failure recovery

Dependency direction is strictly downward. ``policy`` and ``model`` import
nothing from this package's upper layers and never touch the network, which is
what makes the authority rules exhaustively testable without GitHub.
"""

__all__ = ["board", "config", "github", "model", "policy", "workflows"]
