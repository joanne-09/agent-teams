---
name: briefing-board
description: Orient a session on the current project state. Reads the whole GitHub Project by Role lane and reports team flow, work in progress, blocked work, what is waiting on the human, and one recommended next action. This is the default opening move of any agent-teams session and the user may also ask for it directly at any time. Use for "brief me", "orientation", "where are we", "what is going on", "what should I do next", "morning briefing", "board overview", "status of the board", "what is the team doing", a session opening with no specific request, or [role:em].
---

# Briefing the board

Orientation for the whole team. Read-only: this routine reports flow, it does
not change it.

Two ways in, and they produce the same report:

- **The user asks for it directly** — "brief me", "where are we", "what should
  I work on next". This is a first-class request, not a fallback. Answer it
  whenever it is asked, however far into a session.
- **The session opens without a specific request** — orientation is the
  default opening move. Give it unprompted rather than asking the user what
  they want.

Lead with anything waiting on the human: Cards at `(Backlog, human)` needing a
readiness decision, and `(In Review, human)` needing a merge. Everything else
on the board can move without them; those two queues cannot.

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
