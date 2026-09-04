# The QA → specification feedback loop

**Date**: 2026-09-04
**Status**: Accepted, implemented on `mvp/producer-from-scratch`, not yet run live
**Decides**: todo item 3 from the 2026-08-28 review
**Related**:
[`2026-08-27-qa-decomposition.md`](./2026-08-27-qa-decomposition.md) (what QA
looks at), this record (where its findings can go)

## The problem being solved

The team lead asked, live in the 2026-08-28 review: *if QA finds a problem, can
it throw the issue back to the specification or the architect to redesign and
re-run the pipeline?*

The answer was no. Every QA finding routed to **`dev`**:

```text
verdict fail  ->  acceptance defect  ->  (In Progress, dev)
```

He followed up: *might the problem sometimes be in the specification itself?
Opened specifications often conflict.* And it had already happened. A live
Card's AC4 required a visible error when the data files failed to load, while
AC2 specified loading them as an ES module over `file://` — which Chrome and
Safari block before any handler can run. Both criteria could not hold. QA
found it, correctly traced it to the design rather than to the developer's
work, and **there was no mechanism**: a person edited the specification by
hand, and the same person approved their own edit. Nothing on the Card recorded
that a request had been made, by whom, or on what evidence.

His instruction was precise, and it is the constraint this design is built
around: **keep the human approval step — make the request and its approval a
recorded, trackable flow.**

## What already existed, and what did not

Worth separating, because the gap was narrower than it looked.

**Already there:**

- `HANDOFF_AUTHORITY[Role.QA]` includes `Role.ARCHITECT`. QA has always been
  permitted to hand a Card to the architect.
- `policy.REFUSAL_REASONS` already contains *"route specification defects
  through the architect"* — as the explanation for why QA may not hand to
  `analyst`.
- `LEGAL_TRANSITIONS`' own comment calls `In Review -> Backlog` the
  "specification defect" route.
- `docs/specs/**` is a **protected path category**, so changing a specification
  was already a human decision by construction.

**Not there:** any workflow that used any of it. The authority existed, the
vocabulary existed, and no command, gate, verdict field, or acceptance route
connected them. QA could not *say* the specification was wrong in a way
anything downstream would read.

That shaped the design: what was missing was a way to say it, not a new place
to say it.

## Options considered

### A. A fourth acceptance value, `spec_defect`

The obvious shape. Rejected. `Acceptance` is deliberately closed over three
values and its docstring says so; a fourth means every consumer — the
dashboard, the runbook, `next_actions`, the gate list, the decision table —
grows a branch. And it would be a *second* human lane doing what
`protected_change` already does, since a specification change is by definition
a change to a protected category. The cost is real and buys a distinction that
belongs in the reasons, not the type.

### B. A `blocked` verdict with the reason in `blind_spots`

Free today: `blocked` already routes to `protected_change`. Rejected because it
is exactly the status quo. `blind_spots` is prose, so nothing can tell a
specification conflict from "I ran out of time", the human sees no suggested
change, the architect gets nothing to act on, and there is no record that
survives as anything but a paragraph. That is the situation the lead was asking
us to fix.

### C. Let QA edit the specification and open a PR

Rejected outright. The reviewer that may not fix the code may certainly not fix
the design it is judged against. `verifying-delivery`'s first boundary exists
because a reviewer who fixes what they found is no longer independently
verifying it — and design conformance is precisely the dimension that collapses
if the reviewer can move the baseline.

### D. A validated verdict field that routes through the existing human lane (**chosen**)

## Decision

### `Verdict.spec_change_requests`, structured and validated

```json
"spec_change_requests": [
  {"document": "docs/specs/2026-08-28-store-search.md",
   "clause": "AC4",
   "conflict": "AC4 requires a visible error when the data files fail to load, but AC2 specifies loading them as an ES module over file://, which Chrome and Safari block before any handler runs. Both cannot hold.",
   "suggested_change": "replace the ES-module load in AC2 with a classic script plus an explicit fetch, so the failure is observable and AC4 is reachable"}
]
```

All four fields required; `validate_verdict` refuses a verdict missing any of
them, naming which. The same reasoning as `test_strength` and
`browser_evidence`: *"the spec is wrong"* names no document, *"AC3 contradicts
AC5"* names no fix, and neither can be diffed. Every malformed entry is
reported in one pass.

Validated **before** the early return for non-pass verdicts. A specification
conflict is most often reported on a `fail`, which is the verdict value that
skips the rest of those rules — a check placed after it would have been dead
code exactly where it matters. Pinned by
`test_a_request_on_a_fail_is_still_validated`.

### The route is `protected_change`, and QA still does not choose it

`evaluate_acceptance` gains one branch, **before** the `fail` branch:

```python
if verdict.spec_change_requests:
    return result("protected_change", ...)      # names each document and clause
```

Ordering is the behaviour change and is asserted directly. Placed after `fail`,
the branch would be unreachable in the common case and the feature would look
implemented while doing nothing.

The `Verdict` / `Acceptance` separation survives intact. QA supplies a field of
evidence; policy decides what it means. There is still no field through which
QA could name an outcome.

### It may accompany a `pass`, and such a pass does not auto-merge

"This ships, and the specification still needs correcting" is a real thing to
say, and forbidding it would push QA into either failing a good delivery or
staying quiet — the second of which is what happened before.

The cost is deliberate: asserting that the baseline was wrong means a person
looks before the delivery lands. The tension is real and worth naming, because
it creates a mild incentive to keep quiet to let a Card through. Real QA
organisations have the same tension and answer it culturally, not
structurally. **Watch for it** — see falsification below.

### `approve-spec-change N`, human-only

Mirrors `approve-exception` in shape and differs in three ways that all follow
from the same fact — this route merges nothing:

| | `approve-exception` | `approve-spec-change` |
|---|---|---|
| What it does | Merges the exact reviewed head, reconciles to `Done` | Hands the Card to `(In Progress, architect)` |
| Head check | Required; a new push invalidates the exception | **None** — a specification is wrong whichever commit is on the branch |
| `HARD_FLOORS` | Yes, via `merge_pull_request` | No; nothing merges |
| Seat | Human only | Human only |

Human-only despite not being a merge, and the reason is not symmetry: an agent
seat able to reopen a specification on its own reading could rewrite the
baseline it is judged against. `lead` is refused along with the rest, and the
refusal names the route that does exist.

Status moves to `In Progress` alongside the Role. Leaving it `In Review` would
show a Card under review by a seat that reviews nothing.

### The gate offers no merge button

A Card carrying a specification-change request emits a `spec_change` gate
instead of `qa_exception`, not in addition to it. The delivery was built against
a baseline QA says is wrong, so *"approve it anyway"* is not one of the honest
answers — and a dashboard drawing a merge button here would be offering an
authority the route does not grant.

The human's two answers are: approve the request to the architect, or reject it
and record why. Both leave a trail; that was the requirement.

## What makes it trackable, which was the actual ask

Four artifacts, all on the Card, all machine-readable:

1. **The request** — inside the verdict comment, structured, bound to a head.
2. **The route** — the acceptance comment, naming each document and clause.
3. **The approval** — an `agent-teams:spec-change-approval` block recording
   which requests were approved and **from which surface** (terminal or
   dashboard, via `AGENT_TEAMS_HUMAN_ORIGIN`).
4. **The handoff** — the standard handoff comment to `architect`, saying the
   defect is in the named documents rather than in the implementation.

Compare the incident that prompted this: a person edited a file and approved
their own edit, and none of the four existed.

## Cost

One verdict field, one acceptance branch, one board method, one workflow
method, one CLI subcommand, one gate kind. 28 tests in
`tests/test_spec_feedback.py`; suite 538 → 566.

Falsification check run rather than assumed: disabling the two policy hooks
fails 11 of the 28, so the tests are not asserting behaviour that was already
there.

## What would falsify this

- **QA never uses it.** The most likely failure. A field nobody fills in is
  worse than absent, because it looks like the problem is solved. If several
  Cards go by where the specification was genuinely at fault and the request
  was never raised, the gap is in the reviewer's instructions, not the
  mechanism.
- **QA uses it to escape hard reviews.** "The spec is ambiguous" as a way to
  route a Card away rather than review it. The four required fields are the
  defence; if they are being filled in with restatements, the fields are not
  enough and the request needs a challenge step of its own.
- **The `pass` + request combination becomes a way to avoid merging.** Or the
  reverse — QA suppresses requests to avoid delaying a merge. Either would show
  up as a suspicious correlation between verdict value and request presence.
- **The architect rewrites rather than amends.** Then the approved request
  becomes untraceable to its effect, and the record is a record of nothing.
  `authoring-spec` says amend; nothing enforces it.
- **Nobody ever rejects a request.** If every request is approved, the human
  approval is a rubber stamp and the gate is ceremony. The lead asked for the
  human step specifically; it earns its place only if it is sometimes a "no".

None of this has run live. The next full run on the new dataset is the first
real test — as it is for the QA decomposition it sits on top of.
