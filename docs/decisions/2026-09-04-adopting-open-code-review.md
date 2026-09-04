# Adopting from OpenCodeReview instead of rebuilding

**Date**: 2026-09-04
**Status**: Accepted, implemented on `mvp/producer-from-scratch`, not yet run live
**Decides**: todo item 5 from the 2026-08-28 review — *"don't reinvent the
wheel; survey the best-known code-review skills and reference one directly, for
example Alibaba's recently open-sourced one. The four-aspect design is good, so
see how they cover things and fold it in."*
**Amends**: [`2026-08-27-qa-decomposition.md`](./2026-08-27-qa-decomposition.md)
(axis B gains a ninth dimension; the three bundles are unchanged)

## What was surveyed, and how

[`alibaba/open-code-review`](https://github.com/alibaba/open-code-review)
(Apache-2.0) — the `ocr` CLI, described as Alibaba Group's internal code-review
assistant for the past two years. It ships a Claude Code plugin with two
skills, so it is directly comparable to what we built.

Read at `main`, 2026-09-04, fetched as raw source rather than summarised:

- `skills/open-code-review/SKILL.md` and
  `skills/open-code-review-delegate/SKILL.md`
- `internal/config/rules/rule_docs/default.md` — the language-agnostic default
  ruleset, which is where its *coverage* is actually defined
- `internal/config/template/prompts/main_task_system.md`,
  `plan_task_system.md`, `review_filter_task_system.md`
- the repository tree (801 files) for the shape of the ruleset library

Per this repository's standing rule — **never cite a source you have not
read** — every claim below is from those files.

## What it is

A hybrid: a deterministic Go pipeline (file selection, rule resolution,
diff grouping, comment re-location) around an LLM that produces line-level
comments. Two modes matter to us:

- **`ocr review`** — OCR calls its own configured LLM endpoint.
- **`ocr delegate`** — OCR does *only* the deterministic engineering (`preview`
  for the file list and ref metadata, `rule` for the resolved per-file rules)
  and the host agent performs the review itself with its own tools. No LLM
  configured on the OCR side at all.

Its comment shape is `path` · `content` · `start_line` / `end_line` ·
`category` (bug / security / performance / maintainability / test / style /
documentation / other) · `severity` (critical / high / medium / low).

Its default ruleset is five headings: **Correctness** (logic, boundaries,
exception handling, thread-safety), **Security** (injection, XSS, sensitive
data, permission checks), **Performance** (N+1, unnecessary loops, *resource
release*), **Maintainability** (clarity, naming, conformance to existing style
and architecture), **Test Coverage** (critical paths, boundary cases). On top
of that sit 50-odd per-language rule documents.

## The gap analysis

### What it covers that we did not

| Theirs | Our position before | Verdict |
|---|---|---|
| **Performance and resource release** as a first-class category | **No dimension asked either question.** A leak is not `correctness` (the logic is right, the tests pass) and not `security` until someone notices the exhaustion is reachable | **Adopted** as the ninth dimension, `resource-safety` |
| **Severity** (`critical`/`high`/`medium`/`low`) per comment, output ranked by it | Confidence 1-10 only — a different axis. Ranking by confidence puts a certain nit above an uncertain data-loss bug | **Adopted** as a prose convention now, structured field recorded as follow-up |
| **Category** per comment, machine-readable `path` + line range | Findings are free strings. We require *quoted* code, which is stronger evidence but not machine-readable | **Deferred** — see "What was not adopted" |
| **Asymmetric false-positive rule** — a separate filter pass that removes only comments the diff *proves* wrong, because a dropped correct finding is destroyed silently while a kept wrong one costs seconds | Our `challenges` step falsifies findings, but is run by the same reviewer who raised them and states no asymmetry | **Adopted** into `references/evidence-and-challenge.md` |
| **Thread-safety** named explicitly under correctness | `edge-cases` says "concurrent" in a list of nine words | **Folded** into `resource-safety` (locks, releases) and left in `edge-cases` |
| **50+ per-language rulesets** | None | **Not adopted, and not reproducible.** This is two years of accumulated institutional knowledge; writing our own would be exactly the wheel-reinvention the lead warned against |
| **A plan phase at 50 changed lines** — risk analysis producing a severity-ranked issue list *before* the main review | Our adversarial pass triggers at ~200 lines and runs *after*, asking "what did the first pass miss" | **Not adopted** — different purpose, and ours is the one gstack's evidence supports. Noted as a comparison |

> **Amended 2026-09-04, later the same day.** Rows 2 and 3 above read
> as written at the time. `findings` has since become a validated object
> carrying `severity`, `dimension`, `confidence`, `evidence` and an
> optional catalogue `smell`, so severity is no longer a prose convention
> and the category is machine-readable. The `path` + line range remains
> deferred. See `2026-09-04-structuring-findings.md`.

### What we cover that it does not

Recorded because the lead's framing was "fold theirs in", and folding in
without knowing what is ours risks losing it:

- **The delivery is never run.** OCR reads diffs. It has no browser pass, no
  spec-blind reviewer, and no evidence that did not come from reading the
  Developer's work. That is the entire 2026-08-21 complaint, and it is the half
  the QA decomposition was built to answer.
- **`falsified_by`.** OCR asks whether critical paths have tests. It does not
  ask whether those tests would fail if the implementation were wrong.
- **Verdict/Acceptance separation.** OCR emits advice. Nothing in it decides a
  merge, and nothing prevents a reviewer choosing its own route because there is
  no route to choose.
- **Design-baseline conformance.** Reviewing against an approved specification
  and recorded architecture decisions has no counterpart; its `--background` is
  free-text business context.
- **Machine-enforced completeness.** `accept` compares `changed_files` against
  the live diff and refuses a pass that omits one. OCR's equivalent is a prompt
  instruction and a self-reported `coverage_rate`.

The honest summary: **OCR is a better code reader; agent-teams is a better
gate.** Those are different products, and the overlap is narrower than the word
"code review" suggests.

## Decision

### 1. Not a runtime dependency

`ocr` is **not** installed, required, or invoked by anything here. Three
reasons, in order:

1. **The standing invariant.** "agent-teams calls no other plugin; correctness
   never depends on a sibling being installed." That is not a preference — it
   is why `grep -rE "superpowers:|gstack:/" skills/` is a required check.
2. **The dependency floor.** This plugin is Python standard library only, no
   install step. `ocr` needs `npm install -g` and, in `review` mode, a
   configured LLM endpoint and API key in a consuming repository.
3. **It would sit inside the wrong seat.** OCR reviews a diff. The seat that
   most needed help is the browser worker, which is *forbidden* the diff.

**It is a legitimate optional accelerator**, and `ocr delegate` is the mode to
use if anyone tries it: its `preview` and `rule` sub-commands are deterministic
and LLM-free, so a `structure` or `risk` pass could take its file list and
resolved rules and still produce our verdict, under our evidence rules. That is
a future experiment with a clear shape, not a plan.

### 2. Coverage folded in, three changes

**`resource-safety` is the ninth required dimension.** Added to
`model.REQUIRED_DIMENSIONS`, so a pass omitting it is refused by `accept` like
any other. Placed in the **`risk`** bundle (now `security` · `resource-safety` ·
`test-strength`): a leak and an injection ask the same question — what happens
when this is used harder than the happy path — and it puts the dimension next to
`test-strength`, which is where the awkward truth lives, since exhaustion
defects are the ones a unit suite is least likely to have asserted.

Two rules stop it becoming speculative micro-optimisation: name the resource
and the leaking path, and back an asymptotic claim with the quoted loop.

**Severity, on every finding.** `[critical]` / `[high]` / `[medium]` / `[low]`,
with the rule that severity and confidence are different axes and a
`critical`/`high` finding on a `pass` is a contradiction.

**The asymmetric drop rule.** Proof, not doubt, removes a finding. Placed in
`evidence-and-challenge.md` next to the challenge procedure, aimed
specifically at the moment the reviewer reconciles three helper passes —
deduplication is not the same operation as dismissal.

### 3. Code smells as a named vocabulary

`references/code-smells.md` — not from OCR, but from the team lead's aside in
the same review, and it belongs to the same problem. A `structure` finding that
says "this feels wrong" cannot be challenged, deduplicated, or compared across
Cards; one that says *Shotgun Surgery* can. Fowler and Beck's catalogue is
thirty years old, widely taught, and stable, which is what makes it usable as a
closed shared set rather than one reviewer's taste.

It also gives the lead's two examples a home: connections never released is
`resource-safety`; private state leaking out until it is a security hole is
*Inappropriate Intimacy* under `architecture`.

### 4. The four-aspect design is kept

The lead's instruction was explicit that it is good and the question was
coverage. Nothing about the `structure` / `behaviour` / `risk` / `browser`
split changes. `risk` gains one dimension; the bundles, the spawn shape, the
one-verdict-authority rule, and the fallbacks are all untouched.

## What was not adopted, and why

**Structured findings.** OCR's `{path, start_line, end_line, category,
severity}` is better than our list of strings, and it is the obvious next step.
Not done here because `Verdict.findings` is `tuple[str, ...]` throughout
`model.py`, `policy.py`, `board.py`, the CLI, and every test fixture, and
changing its type belongs in its own change with its own tests — not bundled
into a coverage decision. **Recorded as owed.**

> **Paid, same day.** `findings` is now a validated object carrying
> `severity`, `dimension`, `confidence`, `evidence` and an optional catalogue
> `smell`; prose refuses, and so does a `pass` carrying a `critical` or `high`
> finding. See `docs/decisions/2026-09-04-structuring-findings.md`. The
> `path` / line-range field is still not separated out — `evidence` carries
> the location as text.

**The per-language rulesets.** Deliberately. Writing our own would be the
reinvention we were told to avoid; if per-language rules are wanted, that is
the argument for `ocr delegate`, not for a home-grown catalogue.

**The plan-before-review phase.** Ours runs after and asks a different
question. Adopting both would mean three passes over every diff above 50 lines
for a benefit nobody has measured here.

## Licensing, which differs from every prior source

OpenCodeReview is **Apache-2.0**. The three existing sources are MIT. Apache-2.0
additionally requires that a derivative **state that changes were made**;
`ATTRIBUTION.md` now does so and points here, and this record is the statement.

Nothing was copied verbatim. What was taken is *coverage* — a category of
question nobody here was asking — restated in this repository's own terms and
its own enforcement shape.

## What would falsify this

- **`resource-safety` produces nothing but noise across several Cards.** Then
  it is a dimension nobody can answer from a diff, and it should move into the
  browser pass or be dropped rather than left as a box to tick.
- **Severity tags inflate.** If everything arrives `high`, the vocabulary has
  stopped carrying information and needs the structured field with validation,
  not more prose.
- **The asymmetric rule buries the verdict in low-confidence findings.** Then
  the bar is wrong, and `limitations` is not being used as the pressure valve
  it was meant to be.
- **Someone runs `ocr delegate` on a real Card and it finds what our three
  passes missed.** That is the strongest argument for making it a real, if
  optional, part of the flow — and it is a cheap experiment nobody has run.
