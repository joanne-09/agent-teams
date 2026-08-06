# Skill migration — adopting external skill content

This document tracks the one-by-one upgrade of agent-teams Producer skills
with content derived from three MIT-licensed sources, and records exactly what
was adopted, what was rewired, and what was deliberately rejected in each
migration. Licensing and per-file derivation markers live in
[`ATTRIBUTION.md`](../ATTRIBUTION.md).

## Sources

| Source | License | Role in this migration |
|---|---|---|
| [board-superpowers](https://github.com/PanQiWei/board-superpowers) | MIT (c) 2026 PanQiWei | Only source that overlaps our Producer skills (board management) |
| [superpowers](https://github.com/obra/superpowers) | MIT (c) 2025 Jesse Vincent | Engineering discipline — maps to the future dev Consumer skill (M4) |
| [gstack](https://github.com/garrytan/gstack) | MIT (c) 2026 Garry Tan | Review/QA discipline — maps to the future qa verification skill (M5) |

## Ground rules (apply to every migration)

1. **Derive, never depend.** Adopted content is adapted text inside our own
   skill files. No skill references `superpowers:*` or `gstack:/*` at runtime;
   a grep for those prefixes across `skills/` must return nothing.
2. **Mutations rewire to our CLI.** Every board mutation in adopted text is
   replaced with the corresponding `scripts/producer_board.py` command and our
   result-envelope handling (`"ok": true`, `completed`/`recovery`).
3. **Our invariants win.** Where the source conflicts with agent-teams
   authority rules (human-only readiness, no decompose-at-intake, prose
   governance vs `policy.py` code enforcement, survey/judge separation), the
   source text is rejected, and the rejection is recorded here.
4. **Attribution.** Each derived file carries a header comment naming the
   source; `ATTRIBUTION.md` carries the notice.

## Migration plan and status

| Our skill | Source | Status |
|---|---|---|
| `intaking-requirement` | board-superpowers `intaking-requirement` | **Done** (2026-08-06) |
| `briefing-board` | board-superpowers `briefing-daily` | **Done** (2026-08-06) |
| `triaging-board` | board-superpowers `triaging-board` | **Done** (2026-08-06, incl. new `release-claim` CLI command) |
| `using-agent-teams` | board-superpowers `using-board-superpowers` (fragments) | **Done** (2026-08-06) |
| `inspecting-queue` | board-superpowers `reviewing-pr-queue` (observations only) | **Done** (2026-08-06) |
| `authoring-spec` | set aside for now | — |
| `dispatching-work` | set aside for now (no counterpart exists) | — |

---

## 1. `intaking-requirement` (2026-08-06)

Source: `reference/board-superpowers/skills/intaking-requirement/SKILL.md`
(252 lines) + `references/scope-shape-judgment.md`,
`references/spec-first-checklist.md`. Ours grew 71 → 123 lines.

### Adopted

- **Shape judgment** (new workflow step 3): top-down table — roadmap-level →
  stop, no Card; multi-card (2+ independent capabilities, or >~5 estimated
  internal chunks — their empirical trigger) → one Card with the expected
  split stated for the architect; single card → proceed. Includes the
  walking-skeleton hint for brand-new surfaces and the override rule (human
  disputes the shape call → defer, record the override in the Card's notes).
- **Spec awareness** (new step 5, heavily adapted — see Rewired).
- **"When not to intake"** (new section): the tiny-fix escape (no Card for a
  one-line change) and the decline policy (conflicts with stated
  premises/non-goals → decline with rationale; human override is recorded).
- **Frontmatter routing description**: casual-phrasing triggers
  ("I've been thinking about X", "found a bug") and do-NOT-use
  disambiguation pointing at briefing/triaging/dispatching. Improves intent
  routing, which matches on descriptions.

### Rewired

- Their multi-card outcome routes straight to `decomposing-into-milestones`
  at intake. Ours creates **one** Card and informs the architect's later
  decomposition via body + handoff — our flow requires a merged spec before
  any split.
- Their sibling routes collapsed: "direction question" → surface to the
  human, no Card yet; "architecture decision" → recorded as an open question
  for the architect, never as an acceptance criterion; "design exploration" →
  stays in the analyst conversation.
- Their six-row spec-first table collapsed to two rules, because our promote
  gate already enforces spec-before-implementation globally: (a) spec-only
  work gets "land this document" as its Goal; (b) embedded design decisions
  become open questions, not pre-decided ACs.

### Rejected

- **Status → Ready at intake** (their Direct card creation step 4). Violates
  the human-only readiness gate. Ours stays `(Backlog, architect)`.
- **The 5-step classify/audit governance sequence.** Our `policy.py` enforces
  authority in code before any GitHub call — stronger than prose governance.
- **All sibling-plugin routing and `composing-siblings` machinery.**
- **Creator-trace shell helper** (`bsp_render_creator_trace_block`) — our
  intake command owns the durable record.

### Kept from ours

Partial-failure recovery (`completed`/`recovery` envelope), the
don't-invent-a-spec-pointer rule, the returned-Card section, all four
invariants, and the exact `producer_board.py intake` invocation. None of
these exist in the source.

---

## 2. `briefing-board` (2026-08-06)

Source: `reference/board-superpowers/skills/briefing-daily/SKILL.md`
(253 lines). Ours grew 68 → 143 lines. All five proposed adoptions approved
by the user before editing.

### Adopted

- **Fixed report template**: their exact-format markdown discipline (per-group
  counts, one line per Card, omit empty groups, no preamble, one screen)
  restructured onto our lanes — human queues lead and always display in full,
  In Progress / In Review / Blocked full, Ready top-3 + "(+N more)", Backlog
  count only. Unroutable Cards (missing Status/Role) get their own heading.
- **Recommendation ladder** for the single next action, re-ranked for our
  seats: human gate queues → triage → dispatch → intake. Their "give the next
  rung and why it ranked lower, still one at a time" rule included. Their
  rung 3 ("claim a Ready card yourself") dropped — a Producer never becomes a
  Consumer in our model.
- **Stale-work check**: >72h claim branch with ≤1 commit past the claim
  marker → flagged as an observation for triage, with their git one-liner.
  Worded against "whatever branch the handoff comments name" until the dev
  Consumer formalizes claim branches.
- **Read-failure rules**: surface errors verbatim, never synthesize board
  state from memory; note read time and re-run once on stale-looking data.
- **Card-scoped re-entry variant**: "catch me up on #N" narrows the briefing
  to one Card (pair state, last handoff, linked PR, one next action);
  distinguished from "work on #N", which is not a briefing request.
  Frontmatter triggers extended accordingly.

### Rejected

- **Sibling-plugin handoff path** (their Step 4a: `gstack:/office-hours`,
  `plan-ceo-review`, `plan-eng-review` routing) and the composing-siblings
  machinery.
- **The 5-step classify/audit governance sequence** — `policy.py` owns
  authority; the briefing additionally never mutates at all.
- **Velocity signal** — their own text warns it is a human-cadence construct;
  our design dropped sprint math deliberately.
- **Timeboxed dispatch-list variant** ("I have 2 hours" → ranked list of 3) —
  collides with our dispatch-is-a-separate-skill boundary.

### Kept from ours

The two-ways-in framing (direct request / default opening move), the
lead-with-the-human rule, `--with-handoffs` cost guidance, the
handoff-cap-means-under-specified interpretation, and all three boundaries
including observation-vs-inference labeling. None exist in the source.

---

## 3. `triaging-board` (2026-08-06) — skill + new CLI command

Source: `reference/board-superpowers/skills/triaging-board/SKILL.md`
(250 lines). Ours grew 74 → 135 lines. Approved with the decision to build
our own `release-claim` command rather than leaving the release manual.

### New code: `release-claim` (the one migration that touched Python)

Their release procedure (branch delete + Status→Ready as one atomic approval
unit) collides with our policy: `Ready` as a destination refuses every agent
seat — that is how `promote` closed the side doors. Resolution: a first-class
human-gate command.

- `producer_board.py release-claim ISSUE --branch BRANCH [--note TEXT]` —
  deletes the remote claim branch, transitions `In Progress → Ready`, posts a
  release comment. Mutation order is branch-first because the failure modes
  are asymmetric: a Ready Card with a surviving dead branch collides with the
  next claimant; an In Progress Card with no branch just waits for a re-run.
- `policy.py` gains a `release_claim` action: refused for all five agent
  seats (with a teaching refusal reason), allowed for `human` only.
- Guards: the Card must actually be In Progress (Backlog→Ready through
  release-claim would bypass the promote spec gate), and mainline branch
  names (`main`, `master`, `refs/*`) are refused outright.
- Partial-failure envelope like every other multi-step mutation: `completed`
  prefix + `recovery` recipe, never a rollback claim.
- Tests: 130 → 144 (policy refusals per seat, workflow happy path and guards,
  all three partial-failure boundaries, CLI round trip and refusal).
- README Board CLI reference updated.

### Adopted into the skill

- **Stale-claim sweep**: per In Progress Card, age + commits-past-claim-marker
  via their git one-liners; >72h no-progress → flag and note the warning on
  the Card; >7d no-progress with a prior warning → recommend release, with
  the assembled `release-claim` command handed to the human.
- **External-dependency blocker class** added to our who-owes-it routing
  table (stays Blocked with `lead`, escalation via `human`, re-checked each
  triage).
- **Evidence rule**: a Blocked Card whose comments never name the blocker is
  "evidence missing" — flagged, never classified by guesswork.
- **Blocker-spawns-a-requirement route**: a blocking question that is itself
  new work goes through intake as a new Card with a noted dependency.
- **Fixed summary template** and the **scope fence** (no backlog grooming, no
  dependency-cycle detection, no estimate calibration).

### Rejected

- **Their 30-day "suspended card" row** — no such concept in our model.
- **Sibling handoffs** (`gstack:/investigate` → our architect seat owns
  technical investigation).
- **The 5-step classify/audit governance sequence** and autonomy tables —
  `policy.py` enforces in code, and `release_claim` is now a policy row, not
  prose.
- **Lead-executed release** — theirs lets the Producer approve a release
  inline; ours hard-refuses every agent seat by policy, mirroring promote.

### Kept from ours

The who-owes-the-decision routing table and `handoff`/`transition` command
split, the handoff-cap-breach signal, "needs must be a decision, not a status
request", read-before-unblock, and the no-promote boundary — now extended to
name `release_claim` as equally refused.

---

## 4. `using-agent-teams` (2026-08-06)

Source: `reference/board-superpowers/skills/using-board-superpowers/SKILL.md`
(fragments only — the skills do different jobs). Ours grew 150 → 186 lines.

### Adopted

- **State-on-disk table**: the five places durable state lives (Project
  fields, Issues, branches, Pull Requests, config), so a fresh session
  orients without spelunking. Restated for our two-axis schema.
- **Non-signals list**: three things that look board-shaped but are not
  routing requests — general programming/git questions, quoted kickoff
  prompts, and implement-this-Card requests (Consumer work).
- **Router anti-pattern closer**: "routing that becomes work" — if the entry
  skill starts writing procedure inline, stop; every procedure belongs to
  the skill that owns it.

### Rejected

- **Their hook-based reliable gate** (dep check → state probe → `INVOKE:`
  marker) — we have no hooks by design; `bootstrap --role` is the one-command
  equivalent.
- **Their role/routine catalog structure** — routes to their skills; ours
  already has the seat table.
- Everything about sibling-plugin signal capture in its original
  cross-plugin sense.

### Kept from ours

The plain-language-in/seat-selection framing, never-infer-`human` with its
honesty note, bootstrap rules, orientation-as-default, the will-not-do list,
and the safety envelope section. The never-infer-`human` boundary has no
counterpart in the source at all.

---

## 5. `inspecting-queue` (2026-08-06)

Source: `reference/board-superpowers/skills/reviewing-pr-queue/SKILL.md` +
`references/review-queue-detail.md` (guards only — deliberately near-zero
change). Ours grew 67 → 91 lines.

### Adopted

- **Observation guards**, reframed as report-never-act: draft Pull Requests
  listed separately and not ordered for verification; out-of-band deliveries
  (head branch does not match the handoff-named branch) surfaced without
  judgment; Status mismatches surfaced for triage without transitioning;
  unreadable Card bodies reported rather than inferring acceptance-criteria
  state from the Pull Request text.

### Rejected — and why this migration is intentionally small

Their skill validates contracts and routes Cards back to In Progress; ours
deliberately only surveys and orders. Merging their judging half would
collapse the survey/judge independence our qa design rests on. Their
contract-validation logic, verdict-adjacent routing, and sibling escalations
(`gstack:/review`, `superpowers:requesting-code-review`) are deferred to the
future `verifying-delivery` Consumer skill, where they belong.

### Kept from ours

Everything else, including the independence argument itself, which the
source does not have.
