<!-- Derived near-verbatim from board-superpowers `briefing-daily`
     references/daily-detail.md and SKILL.md formatting sections (MIT,
     (c) 2026 PanQiWei, github.com/PanQiWei/board-superpowers), adapted to
     agent-teams commands and lanes. -->

# Report formats — briefing-board reference

Edge-case formats and formatting rationale for the briefing. The SKILL.md
template covers the normal board; this file covers the corners.

## Empty board

If the read returns zero Cards in every group:

```markdown
## Board — <YYYY-MM-DD>

The board is empty. Run intake when you have a new requirement.
```

Do not pad with "(0)" lines per group — terse is better when there is nothing
to report.

## Single-operator board

When one human runs the whole board (our test and demo boards), the WIP and
gate logic is unchanged but the rendering simplifies: drop any "by <owner>"
suffix — there is only one person it could be. Card lines keep age and pair
state only:

```markdown
### In Progress (1)
- #12 Implement briefing skill — (In Progress, dev), last activity 2h ago
```

## Stale-claim age computation

A claim branch is stale when all three hold: the branch exists on origin, it
is older than 72 hours (first commit timestamp), and the commit count beyond
the initial claim marker is zero. The claim itself typically adds one commit;
ignore it.

```bash
# Commits on the claim branch not on main -- 0 or 1 means no work landed:
git log origin/<branch> --not main --oneline | wc -l
# Age -- the first commit's timestamp:
git log origin/<branch> --not main --format="%cr" | tail -1
```

## Context reload — the one-Card format

When the user references a specific Card with orientation language ("catch me
up on #N"), narrow the output:

```markdown
## Context reload — #<N> <title>

**Pair**: (<Status>, <Role>)
**Last handoff**: <from> -> <to> — <one-line reason> (<age>)
**Linked PR** (if any): #<P> — <state>

**Recommended next action**: <one sentence>
```

This truncated format fires on orientation desire ("what's the status of
#N", "where did we leave off on #N") — NOT resume desire ("work on #N",
"claim #N"), which is not a briefing request and routes to the seat that owns
the Card.

## Hot-cards display ordering

Cards in flight deserve more visual weight than the Backlog. Ordering:

1. Waiting on the human (gates — nothing downstream moves without them)
2. In Progress (active work)
3. In Review (needs a verdict or a merge decision)
4. Blocked (needs unblocking)
5. Ready (queued but not started — top 3, then "(+N more)")
6. Backlog (collapsed to a single line: "Backlog: 12 Cards.")

## Failure modes

| Situation | Correct handling |
|-----------|-----------------|
| The board read fails (network, auth) | Surface the failure verbatim. Do NOT synthesize a board state from memory or an earlier briefing. "Board read failed: <error>. Fix the connection before proceeding." |
| The data looks stale (a Card you just watched move shows its old pair) | Note when the data was read; re-run once after a few seconds — GitHub Project reads can lag a mutation. |
| WIP exceeds the limit but no stale claims explain it | Flag the cap violation. Do NOT attempt to release claims or transition Cards. Route the investigation to triage. |
| The user ignores the recommendation and asks for the next one | Give the next rung of the ladder and explain why it ranked lower. Still surface only ONE at a time. |
| All groups are empty (fresh project) | Use the empty-board format above and recommend intake. |

## Tone

The briefing is for a busy operator. Go straight to the data — no preamble
("Here is your morning briefing:"). Skip groups with zero items unless all
are zero. Sentence fragments are fine: "In Progress: 2 Cards, both moving."
One screen, no scroll.
