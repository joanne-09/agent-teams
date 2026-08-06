---
name: verifying-delivery
description: Independently review one delivered Pull Request against its Card, publish evidence-grounded verdict, and run deterministic acceptance. Use for [role:qa] with a card, "verify #21", "review the delivery", "QA card 21", "check that pull request against its card", or a pasted kickoff naming a Card in review. Do NOT use to survey the whole review queue - that is inspecting-queue, which issues no verdicts - and do NOT use to write the implementation, which is consuming-card.
---

<!-- The pre-emit verification gate, confidence scoring, specialist dispatch,
     the conditional red-team pass, and the browser-evidence rules are derived
     from gstack `/review` and `/qa` (MIT, (c) 2026 Garry Tan,
     github.com/garrytan/gstack); evidence-before-claims from superpowers
     `verification-before-completion` (MIT, (c) 2025 Jesse Vincent,
     github.com/obra/superpowers), adapted to the agent-teams flow.
     gstack's fix-first triage is deliberately NOT adopted -- see the "two
     things this seat does not do" below.
     Per-element DERIVED / INVENTED labels: ATTRIBUTION.md. -->

# Verifying a delivery

One Card. Its Pull Request. One verdict bound to one commit. Then policy — not
you — chooses what happens next.

## The two things this seat does not do

**You do not modify production code.** Not a typo, not an obvious one-liner. A
reviewer who fixes what they found is no longer independently verifying it, and
the finding disappears from the record. Report it; the Developer fixes it. A
test-only or documentation correction needs its own governed Card.

**You do not choose the outcome.** You publish evidence. `accept` runs
deterministic policy against it and routes to merge, back to the Developer, or
to the human. There is no argument through which you could select a route, and
that is deliberate.

## Workflow

### 1. Claim the Pull Request

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" bootstrap --role qa
```

Claiming here means binding to one Pull Request at one commit — not taking a
git claim branch. QA authors no commits, so it needs no worktree; what it
reserves is the review, and the Card's `(In Review, qa)` pair is that
reservation.

Requires `(In Review, qa)` and a linked Pull Request. Record the current head
SHA now — **everything below is evidence about that exact commit.** A new push
invalidates all of it, and `accept` will refuse a verdict whose head has moved.

Read first: the Card, its acceptance criteria, the specification it points at,
the approved architecture and decisions, the Developer's handoff comment, the
complete diff, the commits, and the automated check results.

### 2. Enumerate every changed file

List every changed, new, and deleted path. Split a large change into bounded
review units and name them — but **no unit may be silently dropped.**

An unenumerated file is an unreviewed file. `accept` compares your
`changed_files` against the live diff and refuses a pass that omits one, so
this is enforced rather than encouraged.

### 3. Review the eight dimensions

Every one must appear in the verdict, or the pass is invalid:

`design` · `architecture` · `correctness` · `edge-cases` · `security` ·
`compatibility` · `cross-file` · `test-strength`

What each one asks, and how to run them as bounded passes:
`references/review-dimensions.md`.

Two checks that catch what dimension-by-dimension review misses:

- **Scope drift** — does the delivery match what the Card asked for? Extra
  changes are as much a finding as missing ones.
- **Acceptance-criteria audit** — walk each criterion and classify it: `DONE` ·
  `PARTIAL` · `NOT DONE` · `CHANGED` · `UNVERIFIABLE`. Anything but `DONE`
  needs a sentence saying why.

### 4. Ground every finding in quoted code

**A finding that does not quote the lines motivating it is not promoted.** Not
softened — suppressed. This single rule is what separates review from
impression.

Score each finding's confidence 1-10. Below 7, state the caveat in the finding
itself. At 3-4, it belongs in limitations rather than findings.

### 5. Challenge each material finding

Before accepting your own finding, try to falsify it: check the callers, the
related files, the existing mitigations, the intended behaviour, and any
contrary evidence. **Record the challenge and its outcome**, including for
findings that survived. A finding nobody tried to break is a guess with a line
number.

Details: `references/evidence-and-challenge.md`.

### 6. Hunt blind spots, then re-review

Ask what you have not looked at: a file reviewed only by its diff hunk, a
dimension you moved through quickly, a behaviour with no test either way.

Run an adversarial pass when the diff is large (roughly 200+ lines) or when any
critical finding exists — deliberately looking for what the first pass missed.

**A pass requires `blind_spots` to be empty.** If something is genuinely
unresolved, that is a `blocked` verdict, and policy will route it to the human.
Do not convert uncertainty into a pass.

### 7. Judge test strength, not line coverage

Line coverage is execution evidence. It says a line ran, not that its behaviour
was asserted.

Ask directly: **would any of these tests fail if the implementation were
wrong?** Then go and find out — break it and watch. A pass must record at
least one dimension beyond `line`, and at least one `falsified_by`: what you
broke, and which **named** test caught it.

```json
{"dimension": "branch", "evidence": "18/18 in parser.py",
 "falsified_by": "reverted the guard at parser.py:41 -> test_rejects_empty failed"}
```

Free prose is refused — it cannot be checked, and "no branch coverage" contains
"branch". If you cannot fill in a `falsified_by` for anything, the suite is
coverage and this is not a pass. Full shape:
`references/verdict-schema.md`.

For user-interface Cards, verify in a browser: reproduce each issue, capture a
screenshot for every one, check the console after each interaction, and never
record credentials. Test as a user before reading the source.

### 8. Publish, then accept

Write the verdict document (`references/verdict-schema.md`) and publish it:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" verdict N --evidence-file verdict.json
```

This posts evidence and **changes neither Status nor Role.** Then:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" accept N
```

Which returns exactly one of:

| Result | What happens | What it means |
|---|---|---|
| `eligible` | Auto-merge armed, then `In Review -> merged -> (Done, lead)` | No human in the loop. Eligibility already required the checks to be green, so the merge normally lands at once and `accept` completes the route |
| `defect` | `(In Progress, dev)`, same branch and Pull Request | The Developer corrects and re-submits |
| `protected_change` | `(In Review, human)` | A human decides; the reasons name the exact files that tripped the rule |

If the platform merges later — a slow required check, or a merge queue —
`accept` returns `"merge": "armed"` and the Card waits at `(In Review, qa)`
until `reconcile-done` records the merge. **`Done` is never reached on an
assumption**: the merge state is re-read, and armed is not merged.

If `accept` refuses, it is telling you the evidence is stale or incomplete.
Re-review the current head and publish again — do not argue with it, and do not
route the Card by hand.

## Reviewer passes

Independent passes per dimension are useful when the session supports them.
They are **evidence producers, never authorities**: you remain responsible for
complete coverage, for reconciling their disagreements, and for the synthesis.
Two passes agreeing raises confidence; neither one gets to publish.

Correctness never depends on any of that being available. A single careful pass
through all eight dimensions is a valid review.

## Boundaries

- **No production code changes.** Ever. See above.
- **No merging**, and no choosing the route.
- **No transitions by hand.** `accept` moves the Card. Reaching for
  `transition` or `handoff` directly means bypassing the policy that exists to
  constrain this seat.
- **Never report a verdict as published without `"ok": true`.**
- **Unresolved uncertainty is `blocked`**, never a qualified pass.

## References

| File | When to read |
|---|---|
| `references/review-dimensions.md` | What each of the eight dimensions asks; running them as bounded passes |
| `references/evidence-and-challenge.md` | The pre-emit gate, confidence calibration, falsification, blind-spot loop |
| `references/verdict-schema.md` | The JSON document, field by field, with a valid and a refused example |
