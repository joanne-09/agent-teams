# The eight review dimensions

<!-- Derived from gstack `/review` (specialist dispatch, deduplication,
     multi-specialist confirmation, the conditional red-team pass) and
     board-superpowers `reviewing-pr-queue`. MIT. See ATTRIBUTION.md. -->

All eight must appear in the verdict's `review_dimensions`. A pass missing one
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

**`test-strength`** — Not "are there tests". Would any of them fail if the
implementation were wrong? See the test-strength section of the SKILL body.

## The three bundles

Where the session supports independent passes, dispatch **three**, not eight.

One agent per dimension sounds like the finest granularity, but each pass needs
the whole diff, so eight passes copy it eight times — and several dimensions
answer nearly the same question, so much of what comes back is the same finding
in different words. `design` and `architecture` both ask whether this belongs
here; `compatibility` and `cross-file` both follow the callers.

Group them so the members of a bundle genuinely inform each other and the
bundles are genuinely independent:

| Pass | Dimensions | The question it answers |
|---|---|---|
| `structure` | `design` · `architecture` · `cross-file` | Does it belong in this system, in this shape? |
| `behaviour` | `correctness` · `edge-cases` · `compatibility` | Does it do the right thing, including at the edges? |
| `risk` | `security` · `test-strength` | Can it be broken, and would we find out? |

`cross-file` sits with `structure` rather than `behaviour` on purpose: compound
risk is a shape problem, and the pass already holding the architecture in mind
is the one that will see it.

All eight dimensions still appear in the verdict. The bundles decide who looks,
not what counts as looked at.

## Running them as bounded passes

Give each pass a distinct lens rather than running the same review several
times. Redundancy finds the same things twice; diversity finds different
things.

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
eight dimensions is a complete review.

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
