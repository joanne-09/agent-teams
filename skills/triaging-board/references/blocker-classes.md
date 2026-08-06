<!-- Derived near-verbatim from board-superpowers `triaging-board`
     references/triage-detail.md (MIT, (c) 2026 PanQiWei,
     github.com/PanQiWei/board-superpowers). Routing outcomes are adapted to
     agent-teams seats, and the two-step release is replaced by our single
     policy-gated `release-claim` command. -->

# Blocker classes and release evidence — triaging-board reference

Read this at workflow steps 4–5 when classifying a blocker or assembling
release evidence.

## Indicator phrases per blocker class

1. **External-dependency** — waiting on another team, service, or vendor.
   Indicators: "waiting for team X", "waiting for service Y to ship",
   "blocked on external PR #N". Handling: stays Blocked with `lead`; surface
   to `human` if it needs escalation; re-check each triage.
2. **Decision-pending** — a seat needs to decide something before work can
   continue. Indicators: "need arch decision on", "blocked pending direction
   from", "A/B unresolved". Handling: route to the seat that owes the
   decision (usually `architect`; `human` for business or authority calls).
   If the decision maps to a fresh requirement, run intake for it as a new
   Card and note the dependency.
3. **Stale-block** — the blocker resolved long ago but the Card was never
   moved. Indicators: the blocker note mentions a dependency that has since
   shipped, a decision that was made in a PR thread, or a date more than 7
   days old with no update. Handling: propose the transition back to the
   prior Status.

## Stale-block evidence criteria

Any ONE of these is sufficient to classify as stale-block and propose the
unblock:

- the dependency named in the blocker comment has a merged PR or a "done"
  status in its own thread;
- the decision named has been recorded in an ADR or a Card comment;
- the last update to the Card is more than 7 days old and the owning seat has
  not commented since.

A Blocked Card matching none of these, and with no blocker note at all, is
**evidence missing** — flag it and ask for the note; never classify it by
guesswork.

## Stale-claim thresholds

For each claim branch: compute age and progress (git commands in SKILL.md
step 5).

1. Older than 72 hours with no progress beyond the claim marker: **flag**,
   and note the warning on the Card so the next triage can see it.
2. Older than 7 days with no progress AND the owner was previously notified:
   **recommend release**.

If the age computation fails (no commits, shallow clone): note the failure
and flag the branch as *potentially* stale. Do NOT recommend release without
evidence.

## Assembling the release recommendation

The release is one command, and it is the human's — `release_claim` refuses
every agent seat:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" release-claim <number> \
  --branch <claim-branch> \
  --note "<age>, <commit count> commits past the claim marker; owner flagged on <date>"
```

The `--note` is the evidence trail: age, commit count, and when the owner was
warned. One command replaces the source's two separate mutations (branch
delete, then Status flip) precisely so the pair can never be half-approved —
the command's own partial-failure envelope reports if GitHub fails midway.
