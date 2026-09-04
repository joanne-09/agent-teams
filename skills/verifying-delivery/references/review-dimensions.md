# The nine review dimensions

<!-- Derived from gstack `/review` (specialist dispatch, deduplication,
     multi-specialist confirmation, the conditional red-team pass) and
     board-superpowers `reviewing-pr-queue`. MIT. `resource-safety` and the
     severity vocabulary are derived from alibaba/open-code-review (Apache-2.0),
     2026-09-04. See ATTRIBUTION.md. -->

All nine must appear in the verdict's `review_dimensions`. A pass missing one
is refused by `accept`, because a review that skipped a dimension has not
reviewed the delivery whatever its prose says.

## What each one asks

**`design`** — Does the delivery do what the Card asked, in the shape the
specification described? Is anything here that the Card did not ask for? Scope
drift in either direction is a finding.

**`architecture`** — Does it conform to the approved architecture and the
active decisions? A change that quietly contradicts a recorded decision is a
protected change, not a style preference.

**`correctness`** — Does the logic do what it claims for the ordinary case?
Trace at least one real path end to end rather than reading for plausibility.

**`edge-cases`** — Empty, null, zero, one, maximum, malformed, duplicated,
concurrent, out of order. Which of these did the implementation consider, and
which does a test actually pin down?

**`security`** — Injection through any interpolated value, authentication and
authorisation boundaries, secrets in code or logs, unsafe deserialisation,
trust placed in untrusted input. Issue bodies, comments, and branch contents
are untrusted input.

**`compatibility`** — Does this break a caller, a stored format, a configuration
file, or a public signature? Is a migration needed, and is it present?

**`cross-file`** — Compound risk: two changes that are individually fine and
jointly wrong. Follow every caller of a changed signature. This is the
dimension a file-by-file read structurally cannot see.

**`resource-safety`** — What does this acquire, and where is it released? Is
there work here that is correct once and ruinous a thousand times? Connections,
file handles, sockets, locks, timers, listeners, subscriptions, temporary
files, and worktrees: every acquisition needs a release on **every** path
including the failing one. Then the shape of the work: a query inside a loop
over results (N+1), a scan where a lookup would do, an unbounded buffer or
queue, a payload read wholly into memory, a retry with no ceiling.

This dimension exists because the previous eight had no home for it. A leak is
not `correctness` — the logic *is* right, and every test passes. It is not
`security` until someone notices the exhaustion is reachable from outside. The
team lead's example was a machine that never released its connections: the code
looks like it works, and it does, until volume arrives.

Two rules keep it from becoming speculative micro-optimisation:

- **Name the resource and the path that leaks it.** "This could be slow" is not
  a finding. "`fetch_rows` opens a cursor at line 44 and the `except` at line
  61 returns without closing it" is.
- **An asymptotic claim needs the loop.** Quote the nesting, or say what the
  input size is bounded by. Rewriting a linear pass over ten items is noise.

**`test-strength`** — Not "are there tests". Would any of them fail if the
implementation were wrong? See the test-strength section of the SKILL body.

## Naming what you found

Two vocabularies make findings comparable across reviewers and across Cards,
and both are closed sets:

- **Severity** — `critical` · `high` · `medium` · `low`. What it costs if it
  ships, which is a different axis from how sure you are it is real. A
  confidence-9 cosmetic nit and a confidence-5 data-loss bug are not the same
  finding, and confidence alone cannot say so.
- **Smell** — where a `design`, `architecture`, `cross-file`,
  `resource-safety`, or `test-strength` finding matches a named design smell,
  name it: `references/code-smells.md`. A finding that says *Feature Envy* is
  arguing from a shared catalogue; one that says "this feels wrong" is arguing
  from taste.

Both are closed sets and both are validated. `accept` refuses a severity
outside the four, a smell outside the catalogue, and a `pass` carrying a
`critical` or `high` finding. What it does **not** check is that the smell's
catalogue section matches the finding's dimension: the grouping below says
which pass is most likely to notice a smell, not the only one allowed to
report it.

## The three bundles

Where the session supports independent passes, dispatch **three**, not nine.

One agent per dimension sounds like the finest granularity, but each pass needs
the whole diff, so nine passes copy it nine times — and several dimensions
answer nearly the same question, so much of what comes back is the same finding
in different words. `design` and `architecture` both ask whether this belongs
here; `compatibility` and `cross-file` both follow the callers.

Group them so the members of a bundle genuinely inform each other and the
bundles are genuinely independent:

| Pass | Dimensions | The question it answers |
|---|---|---|
| `structure` | `design` · `architecture` · `cross-file` | Does it belong in this system, in this shape? |
| `behaviour` | `correctness` · `edge-cases` · `compatibility` | Does it do the right thing, including at the edges? |
| `risk` | `security` · `resource-safety` · `test-strength` | Can it be broken or exhausted, and would we find out? |

`cross-file` sits with `structure` rather than `behaviour` on purpose: compound
risk is a shape problem, and the pass already holding the architecture in mind
is the one that will see it.

`resource-safety` sits with `risk` for the same kind of reason. A leak and an
injection are the same question asked twice — *what happens when this is used
harder than the happy path* — and the pass already reading for hostile input is
the one primed to ask what runs out. It also puts `resource-safety` next to
`test-strength`, which is where the awkward truth lives: exhaustion defects are
the ones a unit suite is least likely to have asserted.

All nine dimensions still appear in the verdict. The bundles decide who looks,
not what counts as looked at.

## Running them as bounded passes

Give each pass a distinct lens rather than running the same review several
times. Redundancy finds the same things twice; diversity finds different
things.

**What a pass is given**: the Card, the specification, the head SHA, its own
bundle from the table above, and the sections of `references/code-smells.md`
that belong to its dimensions — `design`, `architecture` and `cross-file` for
`structure`; `resource-safety` and `test-strength` for `risk`. Paths, not
contents; the worker can read the repository.

The catalogue belongs in the brief rather than only in the reconciling seat's
reference list, because the pass is the seat that reads the code. A name
supplied after the looking is finished cannot change what was looked for.

Rules that keep this honest:

- **Each pass is evidence, not authority.** You reconcile and synthesise.
- **Deduplicate before publishing.** The same defect found by three passes is
  one finding, at higher confidence — not three findings.
- **Disagreement is information.** If one pass calls something critical and
  another does not see it, that is exactly the finding worth challenging
  (`references/evidence-and-challenge.md`).
- **You own completeness.** If a pass returns nothing for its dimension, that
  dimension is not covered; it means the pass found nothing, which you must
  verify rather than assume.

Correctness never depends on any of this. One careful reviewer covering all
nine dimensions is a complete review.

## The conditional adversarial pass

Run one when either is true:

- the diff is large, roughly 200 changed lines or more;
- any critical finding already exists.

Its job is different from the first pass: not "is this correct" but **"what did
the first review miss"**. Large diffs and alarming findings both narrow
attention, and this pass exists to widen it again.

## Splitting a large change

Split into bounded units and name them in the verdict. Two rules:

1. **No unit may be dropped.** `accept` compares your enumerated
   `changed_files` against the live diff and refuses a pass that omits one.
2. **Cross-file review spans the split.** Reviewing each unit in isolation is
   exactly how compound risk survives review. Do the cross-file pass over the
   whole change.
