# The verdict document

The JSON file `verdict --evidence-file` reads. Validated before it is
published, and validated again by `accept` against the live Pull Request.

## Fields

| Field | Required for | Meaning |
|---|---|---|
| `verdict` | all | `pass`, `fail`, or `blocked` |
| `card` | all | Issue number |
| `head_sha` | all | The exact head reviewed. Evidence not bound to a commit cannot be checked for staleness |
| `pull_request` | all | Pull Request URL |
| `checks` | pass, fail | Commands run and their output. "Looks good" is not a verdict |
| `changed_files` | pass | Every changed path. An unenumerated file is an unreviewed file |
| `review_dimensions` | pass | All nine. A missing one refuses |
| `test_strength` | pass | Structured entries (see below). At least one dimension beyond `line`, and at least one `falsified_by` |
| `browser_evidence` | pass, when the diff touches `ui_paths` | What was actually done in a browser (see below). Absent on a user-facing pass is a refusal |
| `blind_spots` | pass | Must be empty. Unresolved uncertainty is `blocked`, not a qualified pass |
| `design_baseline` | recommended | Specification, architecture, and decision identifiers reviewed against |
| `design_conformance` | recommended | requirement -> implementation evidence -> test evidence |
| `findings` | as applicable | Objects, not sentences. Each names `severity`, `dimension`, `confidence`, `evidence`, optionally `smell`; prose refuses (see below) |
| `challenges` | as applicable | The falsification attempt per finding, and its outcome |
| `spec_change_requests` | as applicable | Defects whose cause is the specification, not the code. Each names `document`, `clause`, `conflict`, `suggested_change`; a missing field refuses. Routes the Card to the human |
| `limitations` | recommended | What you did not check, and why |
| `next_role` | recommended | Your read of who should act. Advisory: policy decides the route |

`next_role` is deliberately advisory. It records your judgment for a human
reading the Issue; it does not influence `accept`.

## `findings` is structured, and why

Each entry is an object, not a sentence:

```json
{"severity": "medium", "dimension": "architecture", "confidence": 8,
 "evidence": "board.py:88 reads Config._raw directly; every other caller goes through Config.role_for()",
 "smell": "Inappropriate Intimacy"}
```

- `severity` — one of the four below. Required.
- `dimension` — which of the nine lenses found it. Required, and outside the
  nine it refuses: a finding filed under a tenth name cannot be reconciled
  against the `review_dimensions` list that `accept` already checks.
- `confidence` — 1-10. Required. **Below 5 refuses**, naming `limitations`:
  the finding is not worthless, it is filed in the wrong place, and deleting
  it is the failure mode `references/evidence-and-challenge.md` warns about.
- `evidence` — the quoted code and the expected-versus-actual. Required; a
  finding that quotes nothing is an impression, and step 4 does not promote it.
- `smell` — optional, and **when present must be a name from
  `references/code-smells.md`**. That is "do not invent entries", enforced.
  Most findings have no smell; a plain logic bug has none. Requiring the field
  would manufacture exactly the invented labels the rule forbids.

Prose is refused outright, for the reason `test_strength` was: this field
carried its severity as a `[high]` prefix in free text, so an inflated tag, a
severity word that meant whatever the writer wanted, and a smell coined on the
spot were all indistinguishable from the real thing to every consumer
downstream. Accepting both shapes was considered and rejected — a permissive
reader turns a loud failure into a quiet wrong answer.

What is deliberately **not** checked is that a smell's catalogue section
matches the finding's `dimension`. The catalogue files each smell under the
dimension most likely to notice it, not the only one that may; a `design` pass
can legitimately report Duplicated Code.

## Severity, and why it is not confidence

`severity` is one of four values:

```text
critical  data loss, a security hole, or a crash on a normal path
high      a broken feature, or an edge case that will be reached
medium    a performance or resource concern, a gap in error handling,
          a maintainability problem with a named smell
low       style, naming, a nit worth recording and not worth blocking
```

**Severity and confidence are different axes and both are needed.** Confidence
says how sure you are the finding is real; severity says what it costs if it
is. A confidence-9 naming nit and a confidence-5 data-loss bug are not
comparable on one number, and ranking by confidence alone puts the nit first.

Two rules keep the vocabulary honest. The first is enforced; the second cannot
be, and knowing which is which matters:

- **A `critical` or `high` finding on a `pass` is a contradiction, and
  `accept` refuses it.** If the finding would send the Card back to the
  Developer, the verdict is `fail`. A pass may carry `medium` and `low`
  findings; that is what they are for. The refusal names `fail` rather than
  asking you to soften the finding — the finding is the honest part of the
  verdict, and the verdict value is the part disagreeing with it.
- **The tag is not a mood.** `critical` means the four words above. No
  validator can tell an inflated severity from a real one, so this one rests
  on the reader — which is exactly why `evidence` is required: the next reader
  checks the claim against the code you quoted.

Structuring this field was recorded as owed in
`docs/decisions/2026-09-04-adopting-open-code-review.md` and paid the same day;
the reasoning is in `docs/decisions/2026-09-04-structuring-findings.md`.
A `path` and line range as a separate field, as OpenCodeReview's comment shape
has, is still not done — `evidence` carries the location as text today.

Where a finding matches a named design smell, name it:
`references/code-smells.md`.

## `test_strength` is structured, and why

Each entry is an object, not a sentence:

```json
{"dimension": "branch",
 "evidence": "18/18 in parser.py",
 "falsified_by": "reverted the guard at parser.py:41 -> test_rejects_empty failed"}
```

- `dimension` — one of `line`, `branch`, `scenario`, `mutation`,
  `integration`, `property`, `negative`. A value outside that set is refused.
- `evidence` — what was measured or asserted. Required.
- `falsified_by` — what you broke, and which **named** test caught it.

A pass needs **at least one dimension beyond `line`** and **at least one
`falsified_by`**.

Prose is refused outright, and the reason is worth stating plainly: an earlier
version of this rule searched free text for one of six words, so
`"line coverage 98%; NO branch coverage was measured"` satisfied it — the
token `branch` was present. A check that a word appears is precisely the error
this rule exists to catch: treating execution as proof.

`falsified_by` is the load-bearing field. Coverage tells you a line ran.
Only breaking the implementation and watching a named test fail tells you the
line's behaviour is actually asserted. If you cannot fill this in for any
dimension, the suite is coverage and the verdict is not a pass.

## `browser_evidence`, and when it is required

Required of a **pass** whose `changed_files` match the configured `ui_paths`
(see `docs/CONFIGURATION.md`). Not required otherwise: a mandatory browser
section on a parser change is theatre, and a `fail` already stops the delivery.

```json
"browser_evidence": {
  "tool": "playwright",
  "base_url": "http://localhost:5173",
  "flows": [
    {"name": "search by destination",
     "steps": ["filled #search with 'Taoyuan'",
               "clicked button[type=submit]",
               "read 3 result rows, all containing 'Taoyuan'"],
     "result": "pass",
     "screenshot": "evidence/search.png"}
  ],
  "input_validation": [
    {"field": "#search", "input": "'; DROP TABLE stores;--",
     "expected": "rejected inline, no request sent",
     "actual": "rejected inline", "result": "pass"},
    {"field": "#radius", "input": "-1",
     "expected": "rejected with a range message",
     "actual": "accepted; returned every store", "result": "fail"}
  ],
  "console": {"errors": [], "warnings": ["favicon 404"]}
}
```

- `flows` — at least one, each with a `name` and **at least two `steps`**.
  Opening a page and screenshotting it is the incidental check this field
  exists to replace, so one step is not a flow.
- `input_validation` — at least one field fed invalid or garbage input, each
  case carrying `field`, `input`, `expected`, and `actual`. The second example
  above is what a real finding looks like: the case is recorded whether it
  passed or not.
- `console` — required, including an `errors` list. **An empty list is a
  finding; an absent one is a gap.** Empty says you looked and it was quiet.
  The live ES-module blank page was a console error sitting behind a fully
  green test suite.

Free prose is refused, for the same reason as in `test_strength`: "clicked
around, looked fine" cannot be checked.

The procedure that produces this block is `references/browser-pass.md`. On a
user-facing Card it is normally run by a `qa-browser-worker` that never sees
the diff, and folded in here verbatim.

## A pass that validates

```json
{
  "verdict": "pass",
  "card": 21,
  "head_sha": "9f2c1ab4de5607891234abcd5678ef9012345678",
  "pull_request": "https://github.com/acme/widgets/pull/57",
  "design_baseline": ["docs/specs/csv-export.md", "ARCHITECTURE 9.5"],
  "review_dimensions": [
    "design", "architecture", "correctness", "edge-cases",
    "security", "compatibility", "cross-file", "resource-safety",
    "test-strength"
  ],
  "changed_files": [
    "src/parser.py", "src/export.py", "tests/test_parser.py"
  ],
  "design_conformance": [
    "AC1 exports headers -> export.write_header -> test_writes_header",
    "AC2 rejects empty input -> parser.parse guard -> test_rejects_empty"
  ],
  "test_strength": [
    {"dimension": "branch", "evidence": "18/18 in parser.py",
     "falsified_by": "reverted the guard at parser.py:41 -> test_rejects_empty failed"},
    {"dimension": "negative", "evidence": "empty, malformed, and duplicate-header inputs asserted"},
    {"dimension": "integration", "evidence": "export -> parse round trip over a 10k-row fixture"}
  ],
  "checks": [
    "python -m unittest discover -s tests: 326 passed, 0 failures",
    "reverted parser.py:41 guard -> test_rejects_empty failed as expected"
  ],
  "findings": [
    {"severity": "low", "dimension": "design", "confidence": 9,
     "evidence": "src/export.py:88 recomputes the delimiter on every row rather than hoisting it. No behavioural difference; noted for a future cleanup."}
  ],
  "challenges": [
    "suspected src/export.py:88 also wrote a header for empty result sets, which the spec forbids. Checked both callers of write_header and read test_empty_export. outcome: refuted -- report.py filters empty sets before the call, and the test asserts the omission. Lowered out of findings."
  ],
  "blind_spots": [],
  "limitations": "Excel rendering not verified; no Windows Office available.",
  "next_role": "qa"
}
```

Two things to notice.

**A pass may carry findings.** A pass means the delivery is acceptable, not
that nothing was observed. Cosmetic observations belong here; a defect severe
enough to block belongs in a `fail`. If a finding would send the Card back to
the Developer, the verdict is `fail`, not a pass with a caveat.

**The `challenges` entry records a finding that did not survive.** That is the
process working, and it is worth writing down: it tells the next reader the
question was asked and answered, so they do not re-raise it.

## A pass that is refused, and why

```json
{
  "verdict": "pass",
  "card": 21,
  "head_sha": "0000000000000000000000000000000000000000",
  "review_dimensions": ["correctness", "security"],
  "changed_files": ["src/parser.py"],
  "test_strength": [{"dimension": "line", "evidence": "98%"}],
  "checks": ["tests pass"],
  "findings": [
    "[high] the parser drops the trailing row",
    {"severity": "high", "dimension": "correctness", "confidence": 8,
     "evidence": "parser.py:61 returns before the final flush",
     "smell": "Off-by-one"}
  ],
  "blind_spots": ["did not review the migration"]
}
```

Eight refusals, all reported at once:

1. **`head_sha` does not match the live head** — the evidence describes a
   commit that is no longer there.
2. **Seven review dimensions missing** — `design`, `architecture`,
   `edge-cases`, `compatibility`, `cross-file`, `resource-safety`,
   `test-strength`.
3. **`changed_files` omits files the diff touches** — each one is named in the
   refusal.
4. **`test_strength` is line coverage only, and carries no `falsified_by`** —
   two separate refusals. Line coverage is execution evidence, not
   behavioural proof, and nothing here shows a test would have caught a
   broken implementation.
5. **`findings[0]` is free text** — the refusal names the four required keys.
   The `[high]` prefix is exactly the prose tag the structured field replaced.
6. **`findings[1]` names a smell outside the catalogue** — *Off-by-one* is a
   real bug and a plausible-sounding label, which is why the rule is
   membership rather than judgment. Describe it plainly instead.
7. **The pass carries a `high` finding** — reported even though the finding is
   otherwise well-formed. A defect that returns the Card to the Developer
   means the verdict is `fail`.
8. **`blind_spots` is not empty** — this is a `blocked` verdict, not a pass.

`checks: ["tests pass"]` would also not survive review: it names no command and
no output.

Note that refusals 6 and 7 apply to a finding that a reader would call good.
That is deliberate: the validator checks the shape of the evidence, never
whether the reviewer was right.

## `spec_change_requests`, and what it is not

For a defect the Developer cannot fix because the **specification** is wrong.

```json
"spec_change_requests": [
  {"document": "docs/specs/2026-08-28-store-search.md",
   "clause": "AC4",
   "conflict": "AC4 requires a visible error when the data files fail to load, but AC2 specifies loading them as an ES module over file://, which Chrome and Safari block before any handler runs. Both cannot hold.",
   "suggested_change": "replace the ES-module load in AC2 with a classic script plus an explicit fetch, so the failure is observable and AC4 is reachable"}
]
```

All four fields are required and validated. The reason is the same as
everywhere else in this schema: an entry the architect cannot diff is a
complaint. "The spec is wrong" names no document; "AC3 contradicts AC5" names
no fix.

**It is not a route.** Present, it makes `accept` return `protected_change` and
the Card reaches the human, who approves it to the architect or rejects it with
a recorded reason. It is not a fourth verdict value and it does not select an
outcome -- `docs/specs/**` was always a protected category, so changing a
specification was always a human decision. What was missing was any way for QA
to *say so*.

**It is not the place for a design preference.** The test is whether some
implementation could satisfy every criterion at once. If one could, the finding
is about the code.

**It may sit on a `pass`.** "This ships, and the specification still needs
correcting" is worth saying. Such a pass does not auto-merge; a person looks
first, which is the intended cost of asserting the baseline was wrong.

## Fail and blocked

A `fail` needs a current `head_sha`, at least one check, and reproducible
findings. It does not need complete dimension coverage — you found the defect,
and completing the review of code that is about to change is wasted effort.

A `blocked` needs a current `head_sha` and its reason recorded in
`blind_spots`. Policy routes it to the human as a protected change.
