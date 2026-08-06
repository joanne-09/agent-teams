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
| `review_dimensions` | pass | All eight. A missing one refuses |
| `test_strength` | pass | Structured entries (see below). At least one dimension beyond `line`, and at least one `falsified_by` |
| `blind_spots` | pass | Must be empty. Unresolved uncertainty is `blocked`, not a qualified pass |
| `design_baseline` | recommended | Specification, architecture, and decision identifiers reviewed against |
| `design_conformance` | recommended | requirement -> implementation evidence -> test evidence |
| `findings` | as applicable | Reproducible expected-versus-actual, with quoted code |
| `challenges` | as applicable | The falsification attempt per finding, and its outcome |
| `limitations` | recommended | What you did not check, and why |
| `next_role` | recommended | Your read of who should act. Advisory: policy decides the route |

`next_role` is deliberately advisory. It records your judgment for a human
reading the Issue; it does not influence `accept`.

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
    "security", "compatibility", "cross-file", "test-strength"
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
    "src/export.py:88 recomputes the delimiter on every row rather than hoisting it. Confidence 9, read directly. Cosmetic: no behavioural difference, noted for a future cleanup."
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
  "blind_spots": ["did not review the migration"]
}
```

Five refusals, all reported at once:

1. **`head_sha` does not match the live head** — the evidence describes a
   commit that is no longer there.
2. **Six review dimensions missing** — `design`, `architecture`, `edge-cases`,
   `compatibility`, `cross-file`, `test-strength`.
3. **`changed_files` omits files the diff touches** — each one is named in the
   refusal.
4. **`test_strength` is line coverage only, and carries no `falsified_by`** —
   two separate refusals. Line coverage is execution evidence, not
   behavioural proof, and nothing here shows a test would have caught a
   broken implementation.
5. **`blind_spots` is not empty** — this is a `blocked` verdict, not a pass.

`checks: ["tests pass"]` would also not survive review: it names no command and
no output.

## Fail and blocked

A `fail` needs a current `head_sha`, at least one check, and reproducible
findings. It does not need complete dimension coverage — you found the defect,
and completing the review of code that is about to change is wasted effort.

A `blocked` needs a current `head_sha` and its reason recorded in
`blind_spots`. Policy routes it to the human as a protected change.
