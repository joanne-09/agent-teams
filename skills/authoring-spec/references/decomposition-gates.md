# Decomposition gates — INVEST, vertical slicing, sizing

<!-- Derived from board-superpowers `decomposing-into-milestones` and its
     references (MIT, (c) 2026 PanQiWei,
     github.com/PanQiWei/board-superpowers), adapted to the agent-teams flow:
     children land at (Backlog, human), never Ready; creation runs through
     `producer_board.py decompose`. See ATTRIBUTION.md. -->

Read this file during Job 3, before writing the children JSON. The gates are
**refusal conditions**, not steps: a child that fails one is not created —
reframe, reslice, or split until it passes, or leave the work as one Card.

Primary sources: Wake, "INVEST in Good Stories, and SMART Tasks" (2003,
xp123.com); Cohn, "Five Simple But Powerful Ways to Split User Stories" and
"Five Story-Splitting Mistakes" (mountaingoatsoftware.com); sizing informed by
Reinertsen (2009) and Fowler's StoryCounting.

## The Iron Law

> Every child Card MUST pass the INVEST 6-letter gate AND clear all four
> vertical-slicing anti-patterns. Failing either is a refusal — the Card does
> not get created. Reframe, reslice, or split until it passes; never wave it
> through. A card that limps through the gate creates downstream pain that
> costs more than reframing the story up front would have.

## INVEST — six refusal conditions (Wake 2003)

- **I — Independent.** Refuses when two children overlap conceptually or
  cannot be claimed in any order, AND no `depends-on` declares the coupling.
  Independence is an ideal, not absolute: declared coupling is the escape
  valve — *silent* coupling is what is refused.
- **N — Negotiable.** Refuses when the body reads as an explicit contract —
  paragraphs of implementation prose, a procedural recipe. A Card is "a token
  promising a future conversation": acceptance criteria are post-conditions
  on the finished world ("login persists the session token"), never steps to
  type. Scope is fixed; details are negotiable.
- **V — Valuable.** Refuses when merging the child alone improves no
  user-visible or developer-visible state. Layer-only slices typically fail
  here. "Customer" includes the architect — internal tooling counts when it
  improves the loop.
- **E — Estimable.** Refuses when the body contains "TBD", "figure out",
  "we'll see", "depends on what we find". A knowledge gap gets a **spike** —
  a small research Card whose acceptance criterion is "we have a written
  answer to question X". Spikes are legitimate; "TBD" Cards are not.
- **S — Small.** Refuses past the L ceiling (below). E and S are one gate in
  practice: bigness itself causes inestimability.
- **T — Testable.** Refuses when acceptance criteria contain feeling-words —
  "feels good", "works well", "is reasonable", "looks correct" — or a bare
  "tests pass" without naming which tests check which behavior. Each
  criterion is checkable by a script or by an explicit human observation.
  Non-functional criteria are operationalized: "page loads under 200ms p50"
  is testable; "loads quickly" is not.

### Reframe playbook — fix the failed letter without restarting

| Failed letter | Reframe move |
|---|---|
| **I** | Add explicit `depends-on` to declare the coupling, or merge the cards if coupling is too tight. |
| **N** | Strip implementation detail from the body; restate acceptance criteria as post-conditions. |
| **V** | Find a vertical seam; restate the card so its merge changes observable state. |
| **E** | Split a spike out as a separate small card; let it land first. |
| **S** | Split via a SPIDR axis — Paths, Data, or Rules are the most productive. |
| **T** | Replace feeling-words with concrete checks; if no concrete check exists, the criterion is not about observable behavior. |

Two or more letters failing means the shape is structurally wrong — restart
the slicing, not the wording.

### The AI-orchestration recalibration

(Original framing by the source, not canon.) Independence, Negotiability,
Value, and Testability are platform-agnostic — a layer-only card is just as
broken whoever implements it. Two letters recalibrate under AI cadence:

- **S**: "a few person-weeks" is meaningless; the ceiling is set by **human
  verification capacity** — what the human can review in one sitting —
  because an agent can produce a 5000-line PR in seconds that nobody can
  verify.
- **E**: sizing is the 4-bin calibration below, not time.

## Vertical slicing — Cohn's splitting mistakes as refusals

1. **Layer-only decomposition** — frontend / backend / schema / DB-only
   cards. "Stories that don't deliver any value to users on their own."
   Refuse; reslice via SPIDR.
2. **Trailing "wire-it-up"** — a final card whose only purpose is
   integrating the previous N layer cards. Refuse; the integration belongs
   inside each slice.
3. **Solution over requirements** — the body specifies HOW rather than WHAT.
   Refuse; restate as post-conditions.
4. **Excessive spike extraction** — more than about 1 spike per N cards
   signals risk aversion, not knowledge gaps. Trim to genuine unknowns.
5. **Premature rule implementation** — the first card bundles every business
   rule. Refuse; ship the core with minimum rules, layer the rest (SPIDR-R).

**Red-flag phrases** — a child title containing "frontend", "backend",
"schema", "DB", "API layer", or "wire up" fails the gate on sight.

## SPIDR — the re-slicing axes

- **S — Spike**: research card answering one named question. Use for real
  knowledge gaps; refuse when the team knows the answer and is stalling.
- **P — Paths**: split by alternative user paths ("pay by card" / "pay by
  transfer"). Use when each path ships alone; refuse when the paths are
  sequential dependencies — that is a `depends-on` chain, not a split.
- **I — Interfaces**: split by surface (CLI first, UI later; plain form
  first, enhanced later). Refuse when the surfaces are trivial shells over
  one logic — that is a layer split in disguise.
- **D — Data**: restrict formats or ranges first ("US ZIP only", "one video
  container"), defer the rest. Refuse when restriction breaks the feature
  entirely.
- **R — Rules**: defer business-rule enforcement ("signup now, rate-limit
  later"). Refuse when a deferred rule is critical to the core value
  (deferring auth on a paid endpoint).

### Shape catalog — starting axis by capability shape

| Capability shape | Recommended axis | Typical cards |
|---|---|---|
| New feature | Paths + Rules | 3-5 |
| Data model migration | Spike + Rules + Data | 2-4 |
| New surface (CLI / API / UI) | Interfaces + Paths | 4-8 |
| Refactor with new capability | Spike + Paths (old, new, cutover) | 3 |
| Bug fix across surfaces | Paths per surface | 2-4 |
| Dependency upgrade | Spike + Rules + Interfaces | 3-6 |
| Feature flag introduction | Paths (on / off) + Rules (rollout) | 2-3 |
| CRUD on a new entity | Paths (C/R/U/D) + Rules deferred | 4-5 |
| Async job / background task | Spike + Paths (success / failure / retry) | 3-4 |

## Size calibration — four bins, one ceiling

| Bin | Diff | Files | Pattern |
|---|---|---|---|
| **XS** | < 50 LOC | 1-2 | typo / wire-up / one-line config |
| **S** | 50-200 LOC | 3-5 | one isolated change set — **the target** |
| **M** | 200-400 LOC | 5-10 | one feature surface |
| **L** | 400-500 LOC | up to 15 | one feature crossing 2-3 surfaces — **the ceiling** |

No XL, no story points, no hours. The ceiling is empirical: ~500 LOC and 15
files is where a human can still verify a PR in one sitting; past it, review
fatigue produces rubber-stamping and cross-file checks fail silently. **A
candidate past the ceiling is by definition more than one slice** — find the
SPIDR axis that separates it.

Drift signs, checked informally: >30% of cards landing XS (bands too
generous), >30% landing L (slicing failing), mean LOC creeping above ~350
(too few seams) or below ~80 (over-slicing; review overhead amortizes badly).

## Dependencies between children

- `depends-on: #N` — hard; the child cannot start until #N is Done.
- `depends-on (soft): #M` — preference, either order ships.
- `depended-on-by: #K` — informational mirror on the prerequisite.

Long hard chains (>3) are a missed decomposition. A cycle refuses the whole
batch — one member is mis-sliced. (Notation is a body convention, not yet
schema-enforced.)

## Escalation — when the gates loop

- **Three failed reframes of one candidate**: it is structurally wrong —
  often not a card at all (research that belongs in a spike, or a
  cross-cutting concern that belongs in the spec). Surface it with the
  failing letter and the attempts.
- **Three failed reslices**: the capability is genuinely large; the strategy
  decision (for example, flag-gated successive slices) belongs to the human.
- **Batch larger than ~10**: the spec is probably multi-feature — say so
  before creating anything.

## Checklist before running `decompose`

- [ ] Every child passes all six INVEST letters.
- [ ] No child is layer-only or wire-up-only.
- [ ] Every child sized XS/S/M/L; none past the L ceiling.
- [ ] Dependencies declared on the dependent card; no cycles.
- [ ] Acceptance criteria operationalized — no feeling-words, no bare
      "tests pass".
- [ ] Out of scope explicit where a reader would otherwise assume.
- [ ] The children land at `(Backlog, human)` — the batch proposes; the
      human's `promote` disposes, one child at a time.
