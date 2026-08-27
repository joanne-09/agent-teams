# QA decomposition: two axes, one verdict

**Date**: 2026-08-27
**Status**: Accepted, implemented on `mvp/producer-from-scratch`, not yet run live
**Decides**: todo item 4 from the 2026-08-21 review, which the team lead
explicitly left to the interns

## The problem being solved

The 2026-08-21 review judged QA too thin. In practice it re-ran the Developer's
own unit tests, read the diff, and took the occasional screenshot — work the
Developer had already done, by someone with more context. The one bug the unit
tests missed, a blank page from an ES-module version mismatch, was caught by a
screenshot taken incidentally rather than by design.

The team lead's reference model was a real QA organisation: a QA lead reviews
process and coverage treating the code as a black box, while the bulk of the
work is integration and load scenarios designed from the specification's
non-functional requirements, usually without the development team seeing them
first.

## What the platform actually allows

Checked against the Claude Code documentation rather than assumed, because this
repository had recorded the opposite:

- **Subagents can spawn subagents**, up to three layers below the main
  conversation, when `Agent` is in their `tools` list. The invariant "workers
  cannot spawn grandchildren" is our policy, not a platform limit.
- **`SendMessage` works between agents**, and a subagent receives a sibling
  roster naming every other agent in the session. Requires Claude Code
  v2.1.206 or later. It does not require agent teams to be enabled.
- A foreground subagent inherits `ListAgents` where cross-session messaging is
  enabled; a background one does not keep it.

## Two axes, and which one was the real problem

**Axis A — split by activity**: code review, browser testing, load testing.
Different inputs, different evidence, different tools.

**Axis B — split by lens**: the eight review dimensions, all applied to the
same diff.

These answer different questions, and conflating them was the initial mistake
in this design. Splitting the code review eight ways produces a deeper code
review whose evidence still comes entirely from reading the Developer's diff.
**The complaint was not that the review lacked depth; it was that QA produced
no independent evidence.** Axis A is what addresses it. Axis B is a quality
improvement on top.

Both are adopted, with axis A carrying the weight.

## Decision

### One verdict authority

`qa-worker` remains the only seat that publishes a verdict, runs `accept`, or
moves a Card. Everything below produces evidence for it to reconcile. One head
gets one verdict — anything else would need a rule for whose evidence wins, and
that rule is the thing `Verdict`/`Acceptance` separation exists to avoid.

### Axis A — `qa-browser-worker`, blind to the diff

For a user-facing Card, `qa-worker` dispatches one `qa-browser-worker`. It gets
the Card, the specification, and the running application at the exact head. It
does **not** get the diff.

The blindness is the point. A reviewer who has read the implementation tests
what the implementation does; a reviewer who has read only the acceptance
criteria tests what the product promised, and only the second finds a promise
nobody implemented. It mirrors how the team lead described QA designing
scenarios without the development team's input.

It walks each acceptance criterion as a named flow, feeds every input field
garbage (empty, wrong type, boundary, over-long, injection-shaped,
whitespace-only), reads the console after each interaction, and returns a
`browser_evidence` block. It publishes nothing.

Enforcement is not prose: `policy.validate_verdict` refuses a **pass** whose
changed files match the configured `ui_paths` and which carries no
`browser_evidence` — the same shape as the existing `falsified_by` rule.
Backend-only and documentation-only Cards are unaffected, and a `fail` is never
asked for it.

### Axis B — three review passes, not eight

`structure` (design · architecture · cross-file), `behaviour` (correctness ·
edge-cases · compatibility), `risk` (security · test-strength).

Eight passes would copy the whole diff eight times to get substantially
overlapping findings: `design` and `architecture` ask nearly the same question,
as do `compatibility` and `cross-file`. Three bundles keep the members
mutually informative and the bundles genuinely independent, at three copies of
the diff instead of eight. All eight dimensions still appear in the verdict;
the bundles decide who looks, not what counts as looked at.

### Load QA — deferred, not rejected

The team lead named it as real QA's largest workload, and it is. It is deferred
because it has nothing to derive from: no specification in this repository yet
carries a non-functional requirement, and a load test invented by QA without a
target is theatre. **Revisit when the first spec states a concurrency or
latency target.** That is the trigger, not a date.

### Spawned by `qa-worker`, not by the coordinator

`qa-worker` gets the `Agent` tool and spawns its own helpers. The alternative —
`next_actions` fanning out three sibling workers per Card — was rejected on
two counts: synthesis would have to happen somewhere other than the seat that
publishes the verdict, and `next_actions` would need a new fan-out action shape
where "one spawn per Card stage" is a load-bearing simplicity.

The cost is nesting, which has bitten this project once already: the CCAM
dashboard's `SubagentStop` handling completed the wrong worker when a nested
helper finished (fixed 2026-08-21). **That fix must be re-verified against
these deeper trees before trusting the dashboard's Workflows tab on a QA
run** — which is todo item 8, now with a concrete reason to run it.

### Messaging discipline

`SendMessage` for briefing and for answering a helper's question. Two rules,
because the meeting flagged inter-agent chatter as a token sink in its own
right:

- **Send references, not contents** — a path, a Card number, a head SHA. Never
  paste the diff into a message; the helper can read the repository.
- **One round trip per helper by default.** A second exchange needs a specific
  disagreement to resolve. "Any update?" is not a reason.

The audit value is real and was the lead's stated motivation: reasoning that
never leaves an agent's own context cannot be reviewed when it turns out to be
wrong.

## Cost

A user-facing Card now involves up to five QA-side contexts: the reviewer,
three review passes, one browser worker. Roughly three copies of the diff plus
one application run, against one context before.

That is a real increase and it is bounded by the Card being user-facing —
backend Cards get the reviewer and, at most, three passes. It buys the one
thing the previous arrangement could not produce at all: evidence that did not
come from reading the Developer's diff.

## Fallbacks, so none of this is load-bearing

If the carrier will not spawn helpers — the Agent tool absent, or the spawn
attempt itself erroring; discovered by attempting, not assumed (the 2026-08-28
live run showed a model will otherwise talk itself into inline work) —
`qa-worker` does the work inline: eight dimensions itself, and the browser pass
from `references/browser-pass.md`. Exactly one of "the browser worker ran it" or
"the reviewer ran it" happens per Card — never both, which is why the browser
procedure lives in exactly one file and `verifying-delivery` holds only the
exclusivity rule.

A single careful reviewer covering all eight dimensions and running the browser
pass personally remains a complete and valid review.

## What would falsify this

- The browser worker's findings turn out to duplicate the review passes rather
  than complement them — then axis A is not buying independence and the split
  should collapse back.
- The three bundles produce near-identical findings — then axis B is
  over-decomposition and the reviewer should do the eight dimensions inline.
- Nested spawning breaks dashboard attribution again and cannot be fixed —
  then move the helpers up to coordinator-spawned siblings and accept the
  `next_actions` complexity.

None of these has been observed yet: nothing here has run live. The next full
run, on the new store/venue dataset, is the first real test.
