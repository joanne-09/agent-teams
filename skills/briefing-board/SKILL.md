---
name: briefing-board
description: Orient a session on the current project state. Reads the whole GitHub Project by Role lane and reports team flow, work in progress, blocked work, what is waiting on the human, and one recommended next action. This is the default opening move of any agent-teams session and the user may also ask for it directly at any time. Use for "brief me", "orientation", "where are we", "what is going on", "what should I do next", "morning briefing", "board overview", "status of the board", "what is the team doing", "catch me up", "what's up on the board", "catch me up on #N" (single-Card variant), a session opening with no specific request, or [role:lead].
---

<!-- The report template, recommendation ladder, stale-work check, and
     read-failure rules are derived from board-superpowers `briefing-daily`
     (MIT, (c) 2026 PanQiWei, github.com/PanQiWei/board-superpowers), adapted
     to the agent-teams flow. See ATTRIBUTION.md. -->

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

1. Bootstrap as `lead` (see `agent-teams:using-agent-teams`).
2. Read the board:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" brief
```

Add `--with-handoffs` when you suspect a Card is ping-ponging. It costs one
extra API call per Card, so it is off by default — use it when the question is
"why is this taking so long", not every morning.

3. Render the report in the fixed template below.
4. Recommend exactly one next action from the ladder below.
5. Stop. Dispatch is a separate routine.

## The report template

Straight to the data — no preamble, one screen, no scroll. Omit groups with
zero items. If every group is empty, say the board is empty and recommend
intake.

```markdown
## Board — <YYYY-MM-DD> · <N> Cards · WIP <n>/<limit>

### Waiting on the human (<count>)
- #<N> <title> — readiness decision, at (Backlog, human) for <age>
- #<N> <title> — merge decision, PR #<P>, at (In Review, human)

### In Progress (<count>)
- #<N> <title> — (In Progress, <role>), last activity <age>

### In Review (<count>)
- #<N> <title> — PR #<P>, (In Review, <role>)

### Blocked (<count>)
- #<N> <title> — blocker: <one line>, waiting on <role>

### Ready (<count>)
- #<N> <title>
- (+<N> more)

### Backlog (<count> Cards)
```

Collapse rules: the human queues, In Progress, In Review, and Blocked always
display in full; Ready shows the top three by dispatch order with a
"(+N more)" trailer; Backlog is a count only. Cards with a missing Status or
Role get their own line under a `### Unroutable` heading — see below.

Edge formats — the empty board, the single-operator board, the one-Card
context reload, and the full failure-mode table — are in
`references/formats.md`.

## The one recommended action

Pick the first rung that applies, and state it as one sentence with the Card
numbers that justify it:

1. **A human queue is non-empty** → recommend that decision: "Recommend:
   promote decision on #9 and #10 — nothing downstream moves until Ready."
2. **Blocked Cards exist** → recommend triage.
3. **Ready Cards exist** → recommend dispatch.
4. **Otherwise** → recommend intake; the board has capacity for new work.

Do not list alternatives. If the user declines the recommendation and asks
what else, give the next rung and say why it ranked lower — still one at a
time.

## Stale work

For each In Progress Card with a work branch, check whether anything has
happened since the claim:

```bash
git log origin/<branch> --not main --oneline | wc -l
```

A count of 0 (or 1, when the claim itself is an empty marker commit) with the
branch older than 72 hours is a stale claim. Flag it as an observation —
"#12 — no commits in 4d" — and let triage decide what to do about it. The
briefing never releases a claim or touches a branch. Until the dev Consumer
seat lands, branch naming is not yet uniform; check whatever branch the
Card's handoff comments name.

## How to read what comes back

- **The human lane outranks everything.** A verified Card waiting on a merge
  blocks every downstream seat. Say so plainly rather than burying it.
- **Work in progress over the limit is a real signal**, not a warning to
  dismiss. Starting more work when nothing is finishing makes it worse — flag
  it and route the investigation to triage; do not fix it from here.
- **A Card with no Role will never be picked up.** Nothing dispatches it and
  nothing escalates it; it simply sits there. Treat missing Role or Status as
  a defect to fix, not a cosmetic gap.
- **Cards near the handoff cap are under-specified**, not unlucky. The fix is
  to route them to the architect, not around the loop again.

## If the read fails

- **The command errors**: surface the error verbatim and stop. Never
  synthesize a board state from memory or an earlier briefing — a wrong
  report is worse than no report.
- **The data looks stale** (a Card you just watched move shows its old pair):
  say when the data was read and re-run once before drawing conclusions;
  GitHub Project reads can lag a mutation by a few seconds.

## Catching up on one Card

"Catch me up on #N" narrows the briefing to that Card instead of the whole
board: its current `(Status, Role)` pair, the most recent handoff comment,
its PR if one is linked, and the one next action for that Card. This is an
orientation request — "work on #N" or "claim #N" is not, and routes to the
seat that owns the Card instead.

## Boundaries

- Do not transition or hand off Cards here. Briefing observes; `handoff` and
  `transition` change things, and mixing them makes the report untrustworthy.
- Do not recommend more than one next action. A list of five priorities is
  not a priority.
- Distinguish what you observed from what you infer. "#22 has been in the
  human lane since the last briefing" is an observation; "the human is the
  bottleneck" is an inference. Label the second as such.
