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
| `authoring-spec` | board-superpowers `decomposing-into-milestones` | **Done** (2026-08-06) |
| `dispatching-work` | none — no counterpart; hardened from our own live-test findings | **Done** (2026-08-06) |
| `consuming-card` | board-superpowers `consuming-card` + `enforcing-pr-contract`; superpowers TDD/verification/worktrees | **Done** (2026-08-06, new skill) |
| `verifying-delivery` | gstack `/review` + `/qa`; superpowers `requesting-code-review`; board-superpowers `reviewing-pr-queue` | **Done** (2026-08-06, new skill) |
| `intaking-requirement` (2nd pass: clarification loop) | superpowers `brainstorming` (elicitation phase only) | **Done** (2026-08-06) |

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

---

## 6. `authoring-spec` (2026-08-06)

Source: `reference/board-superpowers/skills/decomposing-into-milestones/`
(SKILL.md 287 lines + 5 reference files, 801 lines). Ours: SKILL.md 136 → 172
lines + new `references/decomposition-gates.md` (~180 lines). All adoption
lands in Job 3 (decompose); Jobs 1-2 and the gate sections are untouched.

### Adopted

- **The Iron Law and both gates as refusal conditions**: the INVEST 6-letter
  gate (Wake 2003 wording — per-letter refusal criteria, the
  declared-coupling escape valve, negotiable-means-details-not-scope, spikes
  legitimate / "TBD" not, E+S as one gate) and Cohn's splitting mistakes
  (layer-only, trailing wire-up, solution-over-requirements, spike overload,
  premature rules) with the red-flag title phrases.
- **Reframe playbook** (verbatim table) and the **AI-orchestration
  recalibration** (verification-capacity ceiling; marked as the source's
  original framing, not canon).
- **SPIDR axes** with use-when / refuse-when pairs, and the **shape catalog**
  (capability shape → starting axis → typical card count, near-verbatim).
- **Size calibration**: XS/S/M/L bins, the ~500-LOC / 15-file ceiling with
  its review-fatigue rationale, no-XL/no-points/no-hours, drift signs.
- **Dependency notation** (hard / soft / depended-on-by; cycles refuse the
  batch) — still a body convention pending Joanne's schema blessing.
- **Escalation rules**: 3 failed reframes = structurally wrong; 3 failed
  reslices = human strategy decision; batch >~10 = say so first; thin spec =
  single Card, do not force a split.
- **Pre-`decompose` checklist**, retargeted to `(Backlog, human)`.

### Rejected

- **Ready-at-creation** (their Step 8 creates cards then immediately
  transitions them to Ready) — ours land at `(Backlog, human)`; the human
  promotes each child individually.
- **Step 8 governance machinery** (action_id resolution, classify/audit
  dispatch, creator-trace prepending) — `producer_board.py decompose` owns
  batch creation, partial-failure reporting, and provenance.
- **Artifact-ingest mechanics** (file/dir/stdin modes, 50-file cap, EOF
  paste protocol) — carrier mechanics; our input is the merged spec.
- **Sibling calls** (`superpowers:writing-plans`, `gstack:/plan-eng-review`,
  `superpowers:brainstorming` fallback) and the mermaid decision tree.
- **`references/card-schema.md`** — their body schema; ours is established.
- **`references/oauth-walkthrough.md`** (5-card worked example) — skipped by
  user decision to keep the skill bounded; available in the reference clone.
- **Sizing rationale prose** (Little's Law math, Fowler #NoEstimates
  exegesis) — kept as one-line rationale; the full argument stays in the
  reference clone.

### Kept from ours

The three-jobs-one-per-session structure, the send-back-to-analyst move, the
readiness-gate section (`spec_completion=merged`), children at
`(Backlog, human)` with flat provenance, and all four boundaries.

### Live-test addendum (2026-08-06, oil-map run)

Job 1 step 5 said "Open one Pull Request linking the Issue"; the architect
linked it with `Closes #12`, which would have auto-closed the Card on merge —
mid-lifecycle, with the gate and implementation still ahead. Caught at the
human merge gate. Step 5 now mandates `Spec for #<number>` and forbids
closing keywords in spec Pull Requests (they belong to implementation PRs
only), with a matching boundary line: the human gate should only have to
click merge.

---

## 7. `dispatching-work` (2026-08-06) — no source; hardened from live-test findings

No counterpart exists in any of the three sources. board-superpowers'
"dispatch" is a different mechanism entirely: the Producer spawns a Consumer
subagent (their Mode-2), with a 4-step R-class callback protocol for actions
the subagent may not take autonomously. Ours deliberately renders kickoff
prompts and stops — "prompt rendered", never "session started" — with
deterministic ordering (configured seat order, then Card number).

Three additions, all grounded in our own live-test observations rather than
any source:

- **Expected-pair stamp in the kickoff** (code: `workflows._kickoff`): every
  rendered prompt now carries `[expected:(<Status>, <Role>)]`, making the
  router's existing "stale kickoff — say so and stop" rule executable by the
  receiving session. One new test (145 total). This is also the preflight
  input the future Consumer lifecycle validates (ARCHITECTURE §7.1).
- **Carrier-handoff section** (prose): kickoffs are inert without the plugin
  loaded (`--plugin-dir` — the first live-test "routing failure" was exactly
  this launch mistake); paste verbatim; one prompt per session (one Card =
  one Consumer = one PR); re-render rather than pasting aged prompts.
- **Named inconsistent-pair case** (prose): the observed `(Ready, qa)` silent
  kickoff — a Ready Card in a seat that consumes `(In Review, qa)` is a
  data-quality observation, not a dispatchable entry.

**Recorded for the future**: if a carrier ever auto-starts Consumer sessions,
their Mode-2 callback protocol (subagent proposes → reports → Producer
evaluates against overrides → re-spawns with the approved action) is the
design to adapt, together with their warning that the dance is expensive and
overnight-dispatch cards should be mostly auto-class.

---

## 8. `consuming-card` (2026-08-06) — new skill

Sources: `reference/board-superpowers/skills/consuming-card/` (SKILL.md, read in full;
its `references/stage-*.md` were NOT consulted) and `enforcing-pr-contract/`
(SKILL.md + `references/filler-detection.md`); superpowers 6.2.0
`test-driven-development`, `verification-before-completion`, and
`using-git-worktrees`. (`finishing-a-development-branch` was cited in an
earlier revision and is not a source -- it was read only after this skill was
written.) New: SKILL.md 173
lines + three references (290 lines).

### Adopted

- **Four-stage spine** (claim → implement → verify → submit) from their F1-F4,
  flattened to our one Consumer lifecycle (ARCHITECTURE §7.1) so the Developer
  and Architect-documentation routines share it rather than duplicating it.
- **TDD Iron Law and Red-Green-Refactor** verbatim in force: no production code
  without a failing test, mandatory verify-red, delete-and-restart on
  code-first, "delete means delete" including the keep-as-reference escape.
  Their rationalizations table adopted near-verbatim, retargeted to Python.
- **Evidence-before-claims gate** from `verification-before-completion`: the
  five-step gate function and the claim/requires/not-sufficient table,
  including "linter passed is not tests pass" and "an agent reporting success
  is not verification".
- **Two refusal reflexes** from their B3/B4: no TDD bypass because a change
  feels obvious, no edits to files this Card does not own.
- **PR three-section contract** extended to our five sections, plus their
  filler-detection list for Human Verification items and the
  acceptance-criteria terminal-state rule (`[x]` or `[!]<reason>`; bare `[ ]`
  refuses).
- **Worktree isolation discipline** from `using-git-worktrees`: never work at
  the repo root, worktrees outside the repo tree, and their rationale (editors
  and file watchers scan repo-internal worktrees).

### Rewired

- Their `claim-card.sh` and `submit-pr.sh` become `producer_board.py claim` and
  `submit-pr`; the result envelope, partial-failure recovery, and race-lost
  handling are ours.
- Their post-merge webhook assumption ("card Status flips to Done; surface lag
  after 5 min") becomes explicit confirmation via `reconcile-done`, which
  refuses unless the Pull Request is actually MERGED.
- Their branch naming `claim/<kanban-id>-<key-slug>-<title-slug>` collapses to
  `claim/<n>-<slug>`; we have one board per repository, so the kanban id has
  nothing to disambiguate.

### Rejected

- **Fix-first / auto-fix behaviour** — not present in their Consumer, but
  present in gstack `/review`, which their C1 chain invokes. See section 9.
- **Audit rows** (`auditing-actions`, the two-entry propose/resolve rule) and
  the **`classifying-actions` A/R/N autonomy matrix** — `policy.py` refuses in
  code before any GitHub call, which is stronger than prose governance and
  needs no BYO database.
- **Mode-2 subagent callback protocol** (the 4-step propose → report →
  evaluate → re-spawn dance) — our dispatch renders kickoff prompts and stops;
  no Producer spawns a Consumer, so there is no depth-1 budget to manage.
- **Every runtime sibling invocation** — their C1-C4 handoffs call
  `superpowers:*` and `gstack:/*` by namespace. Invariant 10: a grep for those
  prefixes across `skills/` must return nothing.
- **`composing-siblings` machinery** and the procedural-fallback table — no
  sibling mesh to be compatible with.
- **`gstack:/codex` cross-platform review** (their C2) — no Codex surface on
  this branch.

### Kept from ours

The `[expected:(Status, Role)]` staleness check, live-board-wins, the
race-lost-is-not-retried rule, the partial-failure envelope with its
never-replay-creation warning, the escalation ladder, the human gates, and the
`"ok": true` reporting rule. None exist in the sources.

---

## 9. `verifying-delivery` (2026-08-06) — new skill, the first gstack migration

Sources: gstack `/review/SKILL.md` and `/qa/SKILL.md` (fetched from
github.com/garrytan/gstack, MIT confirmed at source); superpowers
`verification-before-completion`. (`requesting-code-review` and
board-superpowers `reviewing-pr-queue` were cited in an earlier revision and
are not sources -- see ATTRIBUTION.md > Provenance labels.) New:
SKILL.md 175 lines + three references (310 lines).

This is the migration `inspecting-queue` deliberately deferred to: that skill
surveys and orders, and merging gstack's judging half into it would have
collapsed the survey/judge independence the qa design rests on.

### Adopted from gstack `/review`

- **Pre-emit verification gate** — the highest-value rule adopted in this whole
  migration. A finding must quote the specific code lines motivating it or it
  is suppressed, not softened. Their framing (unverified findings drop in
  confidence and are held out of the main output) kept intact.
- **Confidence calibration 1-10**, with their thresholds: below 7 carries a
  caveat, 3-4 moves to an appendix — ours routes 3-4 to `limitations`.
- **Specialist dispatch by dimension**, deduplication across passes, and
  confidence-boosting when multiple passes confirm the same issue. Reframed:
  passes are evidence producers, never nested authorities.
- **Conditional red-team pass** on diffs of roughly 200+ lines or when a
  critical finding exists, with their framing that its job is finding what the
  first review missed rather than re-reviewing.
- **Scope-drift detection** — delivered versus stated intent, in both
  directions.
- **Plan-completion audit vocabulary** — `DONE` / `PARTIAL` / `NOT DONE` /
  `CHANGED` / `UNVERIFIABLE`, retargeted from their plan files to our Card
  acceptance criteria.

### Adopted from gstack `/qa`

Browser-verification discipline for interface Cards: repro is everything, every
issue carries a screenshot, verify before documenting, never record
credentials, check the console after every interaction, and test as a user
before reading the source.

### Rejected — and this one is the headline

- **Fix-first triage** (their step 7: AUTO-FIX mechanical items immediately,
  batch ASK items for approval). ARCHITECTURE §7.4 forbids QA touching
  production code, and for a reason their design does not have to face: a
  reviewer that fixes what it found removes the finding from the record along
  with the defect, and no independent evidence of either survives. Our QA
  reports; the Developer fixes; the finding stays on the Pull Request.
- **Telemetry, `cross_project_learnings`, `artifacts_sync_mode`** — out-of-band
  data flow no consuming repository opts into by installing a board plugin.
- **Health score and PR quality score as authority** — useful as reported
  evidence, never as an acceptance input. `evaluate_acceptance` reads the
  decision table, not a score. A numeric gate would be exactly the "one
  language-model verdict as merge authority" the research rejected.
- **Greptile third-party comment resolution** — no such integration here.
- **`checkpoint_mode` auto-commits** — a reviewer that commits is a reviewer
  that writes code.
- **Their verdict shape** — ours is the ARCHITECTURE §9.6 contract, validated
  in `model.py` and re-validated against the live Pull Request by `accept`.

### Kept from ours

The verdict/acceptance split as two types neither of which converts into the
other, exact-head-SHA binding, the empty-`blind_spots` requirement for a pass,
the changed-file enumeration check against the live diff, the
line-coverage-is-not-test-strength rule, and the boundary that QA never selects
its own route. None of these exist in any source: gstack's reviewer reports to
a human who decides, and that is precisely the gate decision 8 replaces.

---

## 10. `intaking-requirement` second pass — clarification loop (2026-08-06)

Source: `reference/superpowers/skills/brainstorming/SKILL.md` (obra/superpowers,
MIT, (c) 2025 Jesse Vincent) — the requirement-elicitation phase only. The
first superpowers-derived content in a *Producer* skill (superpowers'
engineering discipline otherwise lands in the dev Consumer skill — see §8).

**Trigger**: PM feedback that the analyst under-clarifies — a live intake of
the dashboard requirement asked only two questions, leaving quality words
("熱門"/popular) unoperationalized for the architect. The original cap
("one or two questions, not an interview") was inherited reasoning from a
context we do not share: board-superpowers' intake could stay shallow because
it routed design sharpening out to `superpowers:brainstorming` and looped the
sharpened artifact back. We removed those routes in migration #1 but left the
conversation without a procedure. This pass supplies it — from the same skill
board-superpowers itself routes to.

### Adopted (wording kept close to the source)

- **One question per message** — "only one question per message; if a topic
  needs more exploration, break it into multiple questions."
- **Multiple choice preferred**, open-ended fine.
- **Purpose / constraints / success criteria** as the elicitation frame.
- **Context before questions** (their "explore project context" step, retargeted
  to board + repo docs).
- **Scope before detail** (their "assess scope before detailed questions",
  composed with our existing shape-judgment step 3).
- **Ambiguity check as termination criterion** (from their spec self-review):
  stop when no requirement could be read two ways and the acceptance criteria
  are third-person checkable — not after a fixed question count.

### Rewired

- Elicitation only. Their skill continues into design (propose 2-3 approaches
  → present design → design doc → `writing-plans`); ours stops at a clear
  problem statement — design is the architect seat's pipeline.
- Their scope-flag outcome routes to decomposition help; ours feeds the
  existing shape-judgment table.
- New: the operationalization table for quality words ("popular", "safe",
  "fast" → measurable or owned open question) — our framing of their
  "vague requirements" placeholder scan, extended for data-backed work
  (source, freshness, granularity, license).

### Rejected

- **HARD-GATE and the design-approval flow** — gates implementation on an
  approved design; our promote gate owns that, and design is not the analyst's.
- **Approach proposals, design-doc writing, `writing-plans` handoff, spec
  self-review as a whole** — architect territory (authoring-spec).
- **Visual companion** — browser machinery we do not ship.
- **Bringing the skill in whole** (runtime dependency or verbatim copy) was
  considered and rejected: its checklist mandates the full clarify→design→plan
  flow in one session (dissolving the analyst/architect boundary), and its
  "MUST use before any creative work" description would hijack routing from
  `intaking-requirement`.

### Kept from ours

The returned-Card loop — reframed: it backstops what questioning could not
have caught, and is no longer the rationale for asking little. The
don't-pre-decide-design rule, the shape-judgment table, and all four
invariants are unchanged.
