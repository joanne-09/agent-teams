# Structuring findings, and giving the smell catalogue to the seats that read code

**Date**: 2026-09-04
**Status**: accepted, implemented, not yet exercised on a live Card
**Supersedes**: the "recorded as owed" note in
`docs/decisions/2026-09-04-adopting-open-code-review.md`

## The problem being solved

The intern asked a question the same day the smell catalogue landed: *does
Quality Assurance actually use the code-smell concepts to verify the
Developer's work?* Tracing it produced two answers, and neither was the one
the documents implied.

**First, the catalogue was attached to the wrong seat.** `SKILL.md` briefed
the three review passes with "the Card, the specification, the diff, and its
own bundle from `references/review-dimensions.md`". The passes are the seats
that read the code. `references/code-smells.md` appeared only in the reference
table belonging to the reconciling seat — the one that deduplicates and
challenges *findings other agents already produced*. A vocabulary that arrives
after the looking is over cannot change what was looked for. The one path by
which a pass could meet the catalogue was a cross-reference inside a longer
document, in a section about naming rather than in the section describing how
a pass is run.

**Second, everything the catalogue said was unenforceable.** `Verdict.findings`
was `tuple[str, ...]` and `policy` never looked inside it. "Do not invent
entries", "score the confidence 1-10", "a `critical` or `high` finding on a
`pass` is a contradiction" — each was a rule a reader could check and no
validator could. `verdict-schema.md` said so plainly: *"The tag is a prose
convention today, not a validated field."*

The second problem has a precedent that settles it. `test_strength` made this
exact journey for this exact reason, and its docstring records the failure that
forced it: a rule that searched free prose for one of six words accepted
`"line coverage 98%; NO branch coverage was measured"`, because the token
`branch` was present. Checking that a word appears is not checking.

## The two halves, and why only one of them can be enforced

**The reading path cannot be validated, and pretending otherwise would be the
worse error.** No check can establish that a reviewer looked for Feature Envy.
A validator sees what was written, never what was sought. So this half is
brief content and nothing more: the `structure` pass is given the `design`,
`architecture` and `cross-file` sections, the `risk` pass the
`resource-safety` and `test-strength` sections, stated in `SKILL.md`,
`references/review-dimensions.md`, and `agents/qa-worker.md`.

**The written form can be validated, and now is.** A finding is an object:

```json
{"severity": "medium", "dimension": "architecture", "confidence": 8,
 "evidence": "board.py:88 reads Config._raw directly; every other caller goes through Config.role_for()",
 "smell": "Inappropriate Intimacy"}
```

`severity`, `dimension`, `confidence` and `evidence` are required; `smell` is
optional and, when present, must be in `model.CODE_SMELLS`.

## Options considered

### A. Leave findings as prose, strengthen the wording

Rejected. The wording was already strong and already ignored by everything
downstream. This is the option that had been in force since the field existed,
and the intern's question is the evidence it does not work: the material was
present, correct, and unreachable.

### B. Accept both prose and objects during a transition

Rejected, and for the reason `RETIRED_KEYS` established earlier the same day:
a permissive reader converts a loud failure into a quiet wrong answer. A tuple
of strings and a tuple of objects are both valid Python here, so a prose entry
would sail past every check and be silently exempt from the severity gate —
the exemption being available to exactly the reviewer least inclined to
structure their finding.

### C. Structure the field, refuse prose (**chosen**)

Eight call sites across four test files, one renderer in `policy.py`, and the
schema documentation. That is the whole blast radius; the dashboard does not
consume `findings`.

## Decision

Four rules now refuse, where before they advised:

1. **Prose refuses**, naming the four required keys.
2. **`severity`, `dimension` and `smell` are closed sets.** A smell outside
   `CODE_SMELLS` is refused by name — "do not invent entries", enforced. A
   private vocabulary is worse than none, because it looks shared.
3. **`confidence` below 5 refuses**, naming `limitations`. The skill already
   said a 3-4 finding belongs there. The refusal says *move*, never *delete*:
   `references/evidence-and-challenge.md` is explicit that a dropped finding
   reaches nobody and nobody learns it was dropped.
4. **A `pass` carrying a `critical` or `high` finding refuses.** This is the
   only rule here that changes an outcome rather than a format, and it closes
   a real hole: the cheapest way to ship a delivery with a serious finding was
   to write `pass` above it. The refusal names `fail` rather than asking for
   the finding to be softened, because the finding is the honest part of the
   verdict.

### What is deliberately not enforced

**The pairing of `smell` with `dimension`.** The catalogue files each smell
under the dimension most likely to notice it, not the only one permitted to
report it; a `design` pass can legitimately see Duplicated Code. Enforcing the
pairing would buy tidiness and cost true findings. Pinned by a test so it stays
a decision rather than an oversight.

**Severity inflation.** No validator distinguishes an inflated `critical` from
a real one. That rule rests on the reader, which is precisely why `evidence` is
required: the next reader can check the claim against the quoted code.

**A separate `path` / line-range field**, as OCR's comment shape has. Still
owed. `evidence` carries the location as text today.

## Filling the gaps in the catalogue itself

`code-smells.md` described itself as "Not exhaustive", and the audit against
Fowler ch. 3 found entries that matter here. Added: **Mysterious Name** (this
repository has already paid for one — `merge_mode` said nothing about what was
merged, which is why it was renamed, and the rename is what got lost),
**Temporary Field**, **Lazy Element**, **Message Chains** (the pair to the
already-present Middle Man), **Global Data** and **Mutable Data** (the records
here are frozen dataclasses on purpose), and **Repeated Switches**.

A **"deliberately not in this catalogue"** section was added, which is the more
useful half. **Comments** is excluded because Fowler's smell is comments used
as deodorant, whereas this codebase writes long comments explaining *why* a
rule exists and several are the only record of a decision — importing the
entry would arm reviewers against the house style. **Data Class** is excluded
because field-only records are the intended architecture here, behaviour
living in `policy`. **Refused Bequest** and **Alternative Classes with
Different Interfaces** are excluded because there is almost no inheritance in
this codebase, and an entry that can never legitimately fire trains reviewers
to force matches. **Loops** is excluded as a Python style preference the
`resource-safety` entries already cover where it costs something.

## Cost, paid immediately

27 tests in `tests/test_findings.py`; the suite goes 566 → 593. Disabling the
two policy hooks fails 14 of the 27, so they are not vacuous. Eight fixtures
across four existing test files were converted from prose findings.

Four of the new tests compare `references/code-smells.md` against
`model.CODE_SMELLS` in **both** directions, with a guard test so an empty parse
cannot make them pass for the wrong reason. This is the most valuable test in
the file and the least obviously necessary: a vocabulary documented in one
place and enforced from another, allowed to drift with the suite still green,
is the precise shape of the failure
`docs/traces/2026-09-04-merge-mode-evidence-chain.md` spent this session
tracing. Adding a smell to the reference without adding it to the tuple now
fails the suite.

## What would falsify this

- A real review producing a finding that matches no catalogue entry and is
  genuinely a smell. The catalogue is closed, not complete; that is an entry to
  add, and the sync test makes adding it a two-file change on purpose.
- The severity gate refusing a verdict a human then approves unchanged. That
  would mean `pass` with a `high` finding is a state the process actually
  needs, and the gate is wrong rather than strict.
- A reviewer downgrading `high` to `medium` to get a `pass` through. The gate
  would then have bought nothing and taught evasion; the visible symptom is
  severity distribution collapsing into `medium`.

**None of this has run on a live Card.** It is tests, refusals, and documents —
the same caveat that covers everything built since 2026-08-27.
