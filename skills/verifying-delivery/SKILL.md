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
git claim branch. QA authors no commits; what it reserves is the review, and
the Card's `(In Review, qa)` pair is that reservation.

**Never switch the shared checkout.** `git checkout <branch>`, `git switch`,
and `gh pr checkout` in the repository root are forbidden for this seat: the
coordinator and every other worker run from that checkout, and a root left on
the Pull Request branch sends their next commit to the wrong branch (this
happened live; the lead's spec re-publish landed on the PR branch). Reading
the diff needs no checkout at all (`gh pr diff`, `gh pr view --json files`).
When you must execute the code under review — run its tests, open the page —
do it in a detached review worktree at the exact head, outside the
repository, and remove it when the verdict is published:

```bash
# <workspace> is the config's `workspace` (default ../.worktrees); <n> the Card
git fetch origin "<head_sha>"
git worktree add --detach "<workspace>/review-<n>" "<head_sha>"
# ... run tests / open the page from <workspace>/review-<n> ...
git worktree remove --force "<workspace>/review-<n>"
```

Detached on purpose: a worktree on the claim branch would let an accidental
commit move the head you are reviewing, which would invalidate your own
verdict. If `git status` in the repository root is not on its default branch
when you start, stop and report it as a blocker rather than "fixing" it — that
is someone else's state.

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

### 7b. Browser evidence, which this seat does not gather

**You do not open a browser.** For a user-facing Card the browser pass is run
by the `qa-browser-worker` you dispatch (see "Reviewer passes"), and its
`browser_evidence` block comes back as data for you to fold into your verdict.

That split is deliberate. The browser worker gets the Card, the specification,
and the running application — **not the diff**. A reviewer who has read the
implementation tests what the implementation does; a reviewer who has read only
the acceptance criteria tests what the product promised, and only the second
one finds a promise that was never implemented at all. Running both halves
yourself collapses that back into a single perspective and buys nothing.

One exception: **if no browser worker was dispatched** — the carrier does not
expose it, or this session cannot spawn — load `references/browser-pass.md`
and run the pass yourself. Exactly one of the two happens per Card, never both.

`accept` refuses a **pass** whose changed files match the configured
`ui_paths` and which carries no `browser_evidence`, the same way it refuses a
pass with no `falsified_by`. Backend-only and documentation-only Cards are
unaffected.

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
`accept` returns `"merge": "armed"`. The coordinating session observes it via
`next-actions` and runs `reconcile-done` automatically after GitHub confirms the
exact head is merged. **`Done` is never reached on an assumption**: armed is not
merged.

If `accept` refuses, it is telling you the evidence is stale or incomplete.
Re-review the current head and publish again — do not argue with it, and do not
route the Card by hand.

## Reviewer passes

You are the only seat that publishes a verdict. Everything below produces
**evidence for you to reconcile**; none of it gets to publish, route, or move a
Card. Two passes agreeing raises confidence. Two passes disagreeing is a
finding worth challenging, not a tie to break by majority.

Correctness never depends on any of this being available. **A single careful
pass through all eight dimensions, with the browser pass run yourself, is a
complete and valid review.** Dispatch what the session supports; do the rest
inline.

### Three review passes, not eight

The eight dimensions are lenses over one diff, so one agent per dimension would
copy the whole diff eight times to get findings that substantially overlap —
`design` and `architecture` answer nearly the same question, as do
`compatibility` and `cross-file`. Group them into three bundles whose members
genuinely inform each other and which are genuinely independent of one another:

| Pass | Dimensions | The question it answers |
|---|---|---|
| `structure` | `design` · `architecture` · `cross-file` | Does it belong in this system, in this shape? |
| `behaviour` | `correctness` · `edge-cases` · `compatibility` | Does it do the right thing, including at the edges? |
| `risk` | `security` · `test-strength` | Can it be broken, and would we find out? |

Each pass gets the Card, the specification, the diff, and its own bundle from
`references/review-dimensions.md`. Each returns findings with quoted code and
confidence scores. You deduplicate, challenge, and synthesise.

### The browser pass

For a user-facing Card, dispatch a `qa-browser-worker` as well. Give it the
Card, the specification, and the head SHA — **never the diff, and never your
findings.** Its blindness is the whole reason it is a separate agent, and it is
enforced by what you put in the prompt.

It returns a `browser_evidence` block. Fold it in verbatim; do not re-run it,
and do not soften it because your code read disagreed.

### Talking to them

Use `SendMessage` to brief a pass and to answer its questions, and read what it
sends back. Two rules keep this from becoming the token sink it can easily be:

- **Send references, not contents.** A file path, a Card number, a head SHA. Do
  not paste the diff into a message — the worker can read it.
- **One round trip per pass by default.** Brief it, get findings back. A second
  exchange needs a reason: a specific disagreement to resolve, or a question
  whose answer changes the finding. "Any update?" is not a reason.

The conversation is recorded and readable afterwards, which is much of its
value: an agent's reasoning that never leaves its own context cannot be
audited when it turns out to be wrong.

### What stays yours

- **Completeness.** A pass returning nothing for its bundle means it found
  nothing, which you verify rather than assume.
- **Deduplication.** The same defect from three passes is one finding at higher
  confidence, not three findings.
- **The verdict.** One head, one verdict, published by you.

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
| `references/review-dimensions.md` | What each of the eight dimensions asks; the three bundles they group into |
| `references/evidence-and-challenge.md` | The pre-emit gate, confidence calibration, falsification, blind-spot loop |
| `references/verdict-schema.md` | The JSON document, field by field, with a valid and a refused example |
| `references/browser-pass.md` | **Only** when no browser worker was dispatched and you must run the pass yourself |
