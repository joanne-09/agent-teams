---
name: clarifying-card
description: Resolve one named requirement question on an existing GitHub Project Card returned to the analyst, record the answer, and hand the same Card back to architecture. Use for [routine:clarifying-card], [role:analyst] with [board-card:#N] at (Backlog, analyst), "clarify this returned card", or "answer the architect's question on card N". Do NOT use for a new requirement (intaking-requirement), technical design (authoring-spec), or general blocked work (triaging-board).
---

<!-- The clarification discipline is derived from superpowers `brainstorming`
     (MIT, (c) 2025 Jesse Vincent) and the preserve-one-Card routing rule from
     board-superpowers `intaking-requirement` (MIT, (c) 2026 PanQiWei),
     adapted to agent-teams. See ATTRIBUTION.md. -->

# Clarify one returned Card

Resolve one question without recreating, redesigning, or widening the Card.
The existing Issue and its comment history remain the durable requirement
record.

## Workflow

1. Bootstrap as `analyst`:

   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" bootstrap --role analyst
   ```

2. Require one bound Card at exactly `(Backlog, analyst)`. Compare the kickoff's
   expected pair with the live board. If it moved, stop as stale; never change
   the board to match the prompt.

3. Read the Card, its comments, and the latest handoff. Identify the architect's
   named unresolved question. Investigate repository evidence first, then use
   bounded primary-source research when the answer depends on external facts.
   Do not restart the full intake interview or make an architecture decision.

4. Write a compact clarification note containing:

   - the question being answered;
   - the evidence or source;
   - the answer or constraint;
   - the acceptance-criteria impact, if any.

5. Save the note to a temporary UTF-8 file and run:

   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" clarify N +     --note-file "<temporary-file>"
   ```

   The command comments on the existing Card and hands that same Card from
   `analyst` to `architect`.

6. Require `"ok": true`, report the durable result, and stop. A partial result
   is fix-forward evidence: follow only its recovery instructions.

## Boundaries

- Never run `intake` or create a replacement Issue.
- Never move the Card to `Ready` or bypass architecture.
- Never ask the human to copy a prompt into another session.
- If a genuinely unavailable business fact is required, record the exact
  durable blocker instead of inventing an answer.
