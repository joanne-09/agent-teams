---
name: dispatching-work
description: Read Ready GitHub Project Cards and render deterministic kickoff prompts by Role for an Lead. Use for [role:lead], "dispatch work", "assign the queue", "who should work next", or "start the team".
---

# Dispatching work

Produce a dispatch queue. **This routine does not start anything.** A human, a
terminal, a scheduled job, or a bounded subagent consumes the rendered prompts.

## Workflow

1. Bootstrap as `lead`.
2. Check capacity before selecting work:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" brief
```

If work in progress is already over the limit, say so and recommend finishing
or unblocking instead. Dispatching past the cap is a deliberate decision with a
stated reason, not a default.

3. Read the Ready queue:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" dispatch --format json
```

4. Present entries in the returned order. Each carries:
   - the seat;
   - Issue number and title;
   - the Issue URL;
   - a kickoff prompt containing `[role:<seat>]`, `[board-card:#<number>]`,
     and the expected `(Status, Role)` pair — the receiving session compares
     that pair against the live board and stops if the kickoff has gone stale.

5. Explain a skipped Card only when it helps the Tech Lead act — a
   Ready Card with no Role, for instance, is a defect worth naming.

## Handing prompts to a carrier

A rendered prompt only works in a session that has this plugin loaded — pasted
into a bare session, `[role:...]` is inert text and the model improvises.
Whoever starts the session (usually the human, in a fresh terminal):

- launch with the plugin (`claude --plugin-dir <path-to-agent-teams>`, or the
  team alias that does this);
- paste the kickoff **verbatim** — the tokens are the binding, not decoration;
- **one prompt per session.** One Card = one Consumer session = one Pull
  Request; pasting two kickoffs into one session breaks the boundary that
  makes deliveries reviewable.

Prompts age. If dispatch was hours ago, re-run it rather than pasting an old
prompt — the expected-pair check will catch a stale one, but rendering fresh
costs less than a session that boots only to refuse.

## Rules

- **Dispatch only Cards whose Status is Ready** and whose Role is a configured
  dispatch seat.
- **Never infer a missing Role.** A Card with no Role is a data-quality
  problem to report, not a gap to fill by guessing.
- **Never change Role or Status while dispatching.** Selection is read-only;
  mixing in mutation makes the queue untrustworthy.
- **Say "prompt rendered", never "session started".** These are different
  events, and reporting one as the other is how a board drifts from reality.
- **Refuse to dispatch a seat with no legal next action** on that Card. The
  concrete case observed in testing: a `(Ready, qa)` Card — qa consumes
  `(In Review, qa)`, so a Ready Card in qa's lane is a data-quality
  observation to report, not an entry to render.
- An empty queue is a valid result. Report it plainly and say what would fill
  it — usually work waiting on the architect, or a merge waiting on the human.

## Ordering

Deterministic, so two Tech Leads reading the same board get the same
queue: configured seat order first, then ascending Card number. Do not
re-sort by your own judgement of importance — if the priority is wrong, fix it
on the board where the next session can see it.
