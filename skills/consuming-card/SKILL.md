---
name: consuming-card
description: Claim one GitHub Project Card, implement it in an isolated worktree with test-driven development, and open exactly one Pull Request. Use for [board-card:#N], "work on card 12", "implement #47", "let me take that card", "pick up 23", "claim the parser card", or a pasted kickoff naming one Card. Do NOT use for board-wide work - that is briefing-board, triaging-board, dispatching-work, or intaking-requirement - and do NOT use to review someone else's delivery, which is verifying-delivery.
---

<!-- The stage frame, refusal reflexes, and Pull Request contract are derived
     from board-superpowers `consuming-card` and `enforcing-pr-contract` (MIT,
     (c) 2026 PanQiWei, github.com/PanQiWei/board-superpowers); the
     test-driven-development and evidence-before-claims disciplines from
     superpowers `test-driven-development`, `verification-before-completion`,
     and `using-git-worktrees` (MIT, (c) 2025 Jesse Vincent,
     github.com/obra/superpowers), adapted to the agent-teams flow.
     Per-element DERIVED / INVENTED labels: ATTRIBUTION.md. -->

# Consuming a Card

One Card. One claim. One worktree. One Pull Request. Then stop.

This skill carries the Developer routine (`(Ready, dev)` implementation Cards)
and ordinary Architect documentation deliveries at `(Ready, architect)`. Product
specifications are different: `authoring-spec` writes them directly to the
current branch before the human readiness gate, with no specification PR.

## Workflow

### 1. Bind and preflight

Resolve the Card number from `[board-card:#N]`, the first token of the
arguments, or a `#N` in the request. **Ambiguous? Ask.** Guessing which Card
someone meant is how a claim lands on the wrong work.

A kickoff prompt carries `[expected:(Status, Role)]`. Compare it against the
live board:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" bootstrap --role dev
```

**Live board state always wins.** If the pair no longer matches, the kickoff is
stale — say so and stop. Do not "fix" the board to match the prompt.

Read the Card, its comments, its dependencies, and the specification it points
at before claiming. An unmet dependency is a reason to stop and hand back to
the architect, not a detail to work around.

If the expected pair is already `(In Progress, dev)` or
`(In Progress, architect)`, materialise the durable Card claim first:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" resume N --acting-role <role>
```

Continue in the returned worktree and skip the Claim step. An interrupted
session never requires a human to release or re-dispatch the Card.

### 2. Claim

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" claim N --acting-role dev
```

This pushes the remote claim branch, opens the worktree, and moves the Card to
`In Progress` — in that order, so a lost race never leaves a mutated board.

**A lost race is a clean stop, not an error to retry.** The envelope carries
`"race_lost": true` and exits 1. Another session owns the Card. Pick up
different work; do not retry, force, or delete the other claim. The coordinator
re-reads durable state and resumes an In Progress Card in a later bounded
session; no human transports the claim.

**Work in the worktree the claim opened.** Its path is in the result. Do not
return to the repository root to make changes — that is the isolation the whole
concurrency model rests on. Details: `references/claim-and-worktree.md`.

### 3. Plan, bounded to this Card

Turn the Card's acceptance criteria into an executable plan. Bound it to this
Card: work that belongs to another Card is that Card's Consumer's job, and
doing it here makes both deliveries harder to review.

### 4. Implement through test-driven development

**No production code without a failing test first.** Red, verify it fails for
the right reason, green with the minimal code, refactor, stay green.

Wrote the code first? Delete it and start over. Not "keep it as reference" —
you will adapt it, and adapting is testing-after, which proves nothing because
you never watched the test fail.

Full discipline, including the rationalizations that most often defeat it:
`references/tdd-discipline.md`.

Two refusals apply throughout:

- **Do not bypass test-driven development because the change feels obvious.**
  Small changes hide gaps, and every acceptance criterion needs a test that
  failed first.
- **Do not edit files this Card does not own.** If a boundary crossing is
  genuinely necessary, stop and surface it rather than widening the delivery.

### 5. Verify before claiming anything

**No completion claim without fresh evidence in this message.** Not "should
pass" — run it, read the output, count the failures, then state the result.

| Claim | What it requires |
|---|---|
| Tests pass | Test command output showing 0 failures |
| Build succeeds | Build command, exit 0 |
| Bug fixed | The original symptom, re-tested |
| Requirements met | Acceptance criteria walked one by one |

"Linter passed" is not "tests pass". An agent reporting success is not
verification — check the diff yourself.

### 6. Submit

Sync the Card's acceptance criteria first: every item must be `[x]` or `[!]`
with a real reason. A bare `[ ]` at submit time means the Card still claims
work the delivery did not do, and `submit-pr` refuses it.

Write the body to a file using the five-section contract
(`references/pr-contract.md`), then:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" submit-pr N \
  --title "feat: ..." --body-file pr-body.md --acting-role dev
```

This pushes the worktree's commits to the claim branch, opens or updates
**exactly one** Pull Request for it, transitions `In Progress -> In Review`,
and hands off to `qa`. A resumed session updates the existing Pull Request
rather than opening a second. It refuses a dirty worktree (commit what
belongs in the delivery first) and refuses an empty delivery (a Pull Request
whose diff is empty means the implementation never reached the remote).

Then **stop**. Do not merge. Do not pick up another Card.

## When you are blocked

Record what you tried, what you need, and where the work is — a blocker missing
any of the three is an abandonment, not a handoff.

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" transition N --to Blocked --acting-role dev
python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" handoff N --from-role dev --to-role architect --note "..."
```

**The claim and worktree stay.** Blocked work is preserved, not discarded; a
later session resumes the same assignment.

Escalate one rung at a time: retry (bounded), hand to the owner, Blocked, then
human. Two failed attempts on one symptom means the diagnosis is wrong, not
that the fix needs another try.

## When QA returns a defect

The Card comes back as `(In Progress, dev)` on the **same** Card, branch, and
Pull Request. Resume the same worktree, correct the finding, re-verify, and
re-submit. Do not open a second Pull Request and do not start a second branch —
correction is continuation, not a new delivery.

## Boundaries

- **No merging.** Not by this seat, not by any agent seat. Deterministic policy
  decides the route after QA publishes evidence.
- **No self-promotion to Ready.** Only the human opens `Backlog -> Ready`.
- **One Card per session.** One Card, one Consumer, one Pull Request is what
  keeps a delivery reviewable and recoverable.
- **Never report a mutation as successful without `"ok": true`** in the command
  output. Expected failures print structured JSON on stderr and exit 1.
- **Read widely, mutate narrowly.** Read any Card or file you need to reason
  correctly; mutate only this Card and its claim, worktree, branch, Pull
  Request, and comments.
- **Never delete an unresolved worktree.** Cleanup happens automatically after
  a confirmed merge; `reconcile-done` remains the idempotent recovery command.

## Partial failures

A multi-step command that fails midway returns `"partial": true` with
`completed` and `recovery`. Run the `recovery` steps — do not re-run the whole
command. Pull Request creation especially is never replayed: a second call
opens a second Pull Request for one Card.

## References

| File | When to read |
|---|---|
| `references/claim-and-worktree.md` | Claim semantics, race loss, resuming an interrupted session, cleanup rules |
| `references/tdd-discipline.md` | Full Red-Green-Refactor detail and the rationalizations that defeat it |
| `references/pr-contract.md` | The five-section body, filler detection, acceptance-criteria sync |
