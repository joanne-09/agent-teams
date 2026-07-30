---
name: briefing-board
description: Read the whole GitHub Project by Role lane and report team flow, work in progress, blocked work, the human merge queue, and one recommended next action. Use for [role:em], "morning briefing", "board overview", "what is the team doing", "what should I look at", or "status of the board".
---

# Briefing the board

The Engineering Manager's whole-team view. Read-only: this routine reports
flow, it does not change it.

## Workflow

1. Bootstrap as `em` (see `agent-teams:using-agent-teams`).
2. Read the board:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" brief
```

Add `--with-handoffs` when you suspect a Card is ping-ponging. It costs one
extra API call per Card, so it is off by default — use it when the question is
"why is this taking so long", not every morning.

3. Report, in this order:
   - board size and work in progress against the limit;
   - each Role lane with its Cards and routing states;
   - Blocked Cards;
   - the human merge queue;
   - Cards approaching the handoff cap, if you asked for them;
   - Cards that cannot be routed at all;
   - the single recommended next action.

4. Stop. Dispatch is a separate routine.

## How to read what comes back

- **The human lane outranks everything.** A verified Card waiting on a merge
  blocks every downstream seat. Say so plainly rather than burying it.
- **Work in progress over the limit is a real signal**, not a warning to
  dismiss. Starting more work when nothing is finishing makes it worse.
- **A Card with no Role will never be picked up.** Nothing dispatches it and
  nothing escalates it; it simply sits there. Treat missing Role or Status as
  a defect to fix, not a cosmetic gap.
- **Cards near the handoff cap are under-specified**, not unlucky. The fix is
  to route them to the architect, not around the loop again.

## Boundaries

- Do not transition or hand off Cards here. Briefing observes; `handoff` and
  `transition` change things, and mixing them makes the report untrustworthy.
- Do not recommend more than one next action. A list of five priorities is
  not a priority.
- Distinguish what you observed from what you infer. "#22 has been in the
  human lane since the last briefing" is an observation; "the human is the
  bottleneck" is an inference. Label the second as such.
