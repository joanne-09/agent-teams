---
name: triaging-board
description: Scan Blocked GitHub Project Cards, group them by the seat that owes a decision, and route each to a legal recovery destination. Use for [role:em], "what is blocked", "triage the board", "unblock", "recovery", or "this card has been stuck".
---

# Triaging the board

Blocked work is the Engineering Manager's problem regardless of which seat
blocked it. This routine finds it, names who owes a decision, and routes it.

## Workflow

1. Bootstrap as `em`.
2. Read the blocked set:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" triage
```

3. For each Blocked Card, read the Issue and its comments before proposing
   anything:

```bash
gh issue view <number> --repo <configured-repo> --comments
```

4. Classify the blocker:

| What you find | Where it goes |
|---|---|
| A technical question or a specification gap | `architect` |
| The requirement itself is unclear or untestable | `analyst`, via `architect` |
| A business or authority decision | `human` |
| Priority, ownership, or a handoff-cap breach | stays with `em` |
| The blocker is already resolved | unblock and return it to its prior Status |

5. Announce each intended change, then route it:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" handoff <number> \
  --from-role em --to-role <seat> \
  --note "<what is blocked>" \
  --needs "<the specific decision you need>"
```

Unblocking is a separate operation, because Status and Role are independent:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" transition <number> \
  --to "In Progress" --acting-role em
```

6. Report what moved and what is still stuck, with the reason.

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
- Do not silently release another seat's work. Route it; let that seat decide.

## Boundaries

- Triage does not implement, specify, or verify anything.
- Triage does not merge, and does not promote work to Ready — readiness is the
  human's gate, and `promote_to_ready` refuses `em` like every other agent
  seat. Route a Card that looks ready to `human`, do not open the gate for it.
