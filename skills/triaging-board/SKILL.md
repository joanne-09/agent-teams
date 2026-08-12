---
name: triaging-board
description: Scan Blocked GitHub Project Cards and stale claims, group them by the seat that owes a decision, and route each to a legal recovery destination. Use for [role:lead], "what is blocked", "triage the board", "unblock", "recovery", "this card has been stuck", "stale claims", "abandoned work", or "any ghost branches". Do NOT use for overall board state (briefing-board) or new work (intaking-requirement).
---

<!-- The stale-claim sweep, external-dependency class, evidence rule, and
     summary format are derived from board-superpowers `triaging-board`
     (MIT, (c) 2026 PanQiWei, github.com/PanQiWei/board-superpowers), adapted
     to the agent-teams flow. See ATTRIBUTION.md. -->

# Triaging the board

Blocked work is the Tech Lead's problem regardless of which seat blocked it.
This routine finds stuck and abandoned work, names who owes a decision, and
routes it. It answers two questions: **what is blocked and why**, and **what
has been claimed and abandoned**.

When dispatched with `[board-card:#N]`, use bounded mode: inspect and mutate
only Card N, resolve its blocker through repository evidence and bounded
research, return it to its legal prior working state, then stop. Do not scan or
route another Card. If an external fact is unavailable, record exactly what
condition must change and leave the Card Blocked.

## Workflow

1. Bootstrap as `lead`.
2. Read the blocked set:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" triage
```

3. For each Blocked Card, read the Issue and its comments before proposing
   anything:

```bash
gh issue view <number> --repo <configured-repo> --comments
```

   A Blocked Card whose comments never name the blocker gets classified as
   **evidence missing** — flag it, ask the seat that blocked it to comment,
   and do not guess a classification for it. Indicator phrases per class and
   the stale-block evidence criteria are in `references/blocker-classes.md`.

4. Classify each blocker:

| What you find | Where it goes |
|---|---|
| A technical question or a specification gap | `architect` |
| The requirement itself is unclear or untestable | `analyst`, via `architect` |
| A business or authority question | `lead` researches repository decisions and standing context; if the fact does not exist, record the exact durable blocker |
| Waiting on something outside the repo (vendor, another team, an upstream PR) | stays Blocked with `lead`; re-check automatically and record the external condition |
| Priority, ownership, or a handoff-cap breach | stays with `lead` |
| The blocking question is itself a new requirement | run intake for it as a new Card, note the dependency; the blocked Card waits on it |
| The blocker is already resolved | unblock and return it to its prior Status |

5. Sweep for stale claims. For each In Progress Card, check the branch its
   handoff comments name:

```bash
git log origin/<branch> --not main --format="%cr" | tail -1   # age
git log origin/<branch> --not main --oneline | wc -l          # progress
```

   A count of 0 or 1 (empty claim or the initial marker only) means no work
   has landed. If the age computation fails (no commits, shallow clone), note
   the failure and flag the branch as *potentially* stale — never recommend
   release without evidence. Then:
   - **older than 72 hours, no progress** — flag it in the summary; the
     claimant may need a nudge. Note the flag on the Card so the next triage
     can see the owner was warned.
   - **older than 7 days, no progress, previously flagged** — resume it in a
     bounded Consumer session. Do not delete or re-Ready it. The durable branch
     belongs to the Card, not to the expired session; the Consumer runs
     `resume` and continues the same claim and worktree. If the remote branch
     is absent, record that concrete repository inconsistency as the blocker.

6. Announce each intended change, then route it:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" handoff <number> \
  --from-role lead --to-role <seat> \
  --note "<what is blocked>" \
  --needs "<the specific decision you need>"
```

Unblocking is a separate operation, because Status and Role are independent:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" transition <number> \
  --to "In Progress" --acting-role lead
```

7. Report the summary:

```markdown
## Triage — <YYYY-MM-DD>

### Blocked (<count>)
- #<N> <title> — <classification>: <one line>. Routed to: <seat> / recommended: <action>

### Stale claims (<count>)
- #<N> <title> — <age>, <commits> commits. Flagged / release recommended (command above)
```

If nothing is blocked or stale: "Triage clean — no Blocked Cards, no stale
claims."

## Rules

- **Every Blocked Card needs a named owner.** An unowned Blocked Card is
  invisible to every routine and is the first thing to fix.
- **"Needs from you" must be a decision, not a status request.** "Please
  advise" moves nothing. "Should this use the existing connector or a new one"
  can be answered.
- **A handoff-cap breach is the signal to stop routing.** The Card has been
  around the loop enough times to prove it is under-specified. Send it to the
  architect with the history, and say why.
- Do not unblock a Card whose blocker you have not actually read. A Status
  flip that skips the reason recreates the block one session later.
- Never delete or re-Ready a claim merely because its original session ended.
  Resume the Card-owned branch. A slow claimant and an interrupted session are
  both handled by durable Git state, not a human recovery command.

## Boundaries

- Triage does not implement, specify, or verify anything.
- Triage does not merge or promote work to Ready. It may resolve and route a
  Blocked Card, but readiness and protected QA remain the only human gates.
- Triage does not groom the Backlog, detect dependency cycles, or calibrate
  estimates. It is a health check, and staying narrow is what keeps it fast
  enough to run every session.
