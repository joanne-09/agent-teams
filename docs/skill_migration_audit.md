# Skill migration — per-item coverage audit

Companion to [`skill_migration.md`](./skill_migration.md). That file records
each migration at summary level; this one proves per-item coverage: every
section, table, and rule in the three board-superpowers sources is listed
with a disposition, so nothing was dropped silently.

Dispositions: **verbatim** (copied with at most naming changes) · **adapted**
(their idea, our terms/routing) · **restored** (added in the 2026-08-06
coverage pass, having been over-compressed in the first migration) ·
**rejected** (deliberately not carried; reason given).

Source root: `reference/board-superpowers/skills/`.

---

## 1. `intaking-requirement`

### Source: `intaking-requirement/SKILL.md`

| Item | Disposition | Where / why |
|---|---|---|
| Frontmatter trigger list + casual-phrasing rule + do-NOT-use disambiguation | adapted | Our frontmatter description (triggers merged with ours; do-NOT-use targets our skills) |
| `when_to_use` duplicate block | rejected | Our skill format has one description field |
| Required sub-skills block (board-canon, operating-kanban, composing-siblings, classify/audit) | rejected | No skill mesh: `producer_board.py` + `policy.py` replace all four |
| Overview: 4-step pipeline, "intake is NOT a design session", pipeline-is-a-loop | adapted | Our intro ("gateway, not a design session") + steps 2–5; loop collapses because we never route out to siblings |
| Step 1 acknowledge (repeat back, one clarifying question) | adapted | Our steps 2 and 4 |
| Step 2 shape judgment + G4 conflict rule ("just make one card" override, record in Notes) | adapted | Our step 3 table + override rule; full trigger detail in `references/shape-judgment.md` (restored) |
| Step 3 spec-first check (6 rows) | adapted | Rows 1+6 generalized into our step 5 + `references/spec-awareness.md`; rows 2–5 are their project's own subsystems (SKILLS.md edges, action_id/autonomy schema, hook grammar, host-local state) — rejected as project-specific, the generalized "schema change / cross-area" rows in spec-awareness.md cover the class |
| Step 4 route-or-create: direction question → office-hours/ceo-review | adapted | "Surface to the human, no Card yet" (our step 3 roadmap row + When-not-to-intake) |
| Step 4: architecture decision → plan-eng-review | adapted | Open question for the architect (our step 5) |
| Step 4: design sharpening → brainstorming, re-enter loop | adapted | Stays in the analyst conversation (our step 4; shape-judgment.md Table 3 "rambling notes" row) |
| Step 4: multi-card → decomposing-into-milestones | adapted | One Card + expected split for the architect (invariant: no decompose at intake) |
| Direct card creation: body schema (thin pointer / Goal / AC / out of scope / dependencies / notes) | adapted | Our step 6 body list; Spec pointer deliberately excluded (our don't-invent-a-spec-pointer rule) |
| Direct card creation: show draft before creating | adapted | Our step 7 "announce the mutation" |
| Direct card creation: creator-trace marker (`bsp_render_creator_trace_block`) | rejected | Our intake command owns the durable record |
| Direct card creation: set Status **Ready** | rejected | Violates the human-only readiness gate; ours lands `(Backlog, architect)` |
| 5-step governance sequence ("How mutating actions are handled") | rejected | `policy.py` refuses in code before any GitHub call |
| Decline policy (conflict with premises, conscious override, record in Notes) | adapted | Our "When not to intake" second bullet |
| When NOT to route: tiny-fix escape | adapted | Our "When not to intake" first bullet |
| Cross-plugin handoff syntax | rejected | No sibling routing exists to surface |
| Autonomy defaults table (A/R per action) | rejected | Superseded by `policy.py` action rows |
| Failure mode: shape-conflict override | restored | `references/spec-awareness.md` § Failure modes |
| Failure mode: spec-precondition skip recorded in Notes | restored | Same table |
| Failure mode: create_card fails → surface verbatim, show draft, no blind retry | restored | Same table, merged with our envelope rules |
| Failure mode: sibling unavailable → degrade | rejected | No siblings to be unavailable |

### Source: `references/scope-shape-judgment.md`

| Item | Disposition | Where / why |
|---|---|---|
| Primary-source vocabulary (Cohn / Patton / Cockburn / Denne) + no-cadence-inheritance note | restored (near-verbatim) | `references/shape-judgment.md` |
| Table 1, all four rows with full triggers | restored (triggers verbatim; outcomes adapted to one-Card-at-intake) | Same file |
| ">5 chunks" empirical rationale | restored (verbatim) | Same file |
| Walking-skeleton hint | restored (verbatim, retargeted as a note to the architect) | Same file |
| Table 2 cross-card mechanisms (milestone field / hard / soft / label) + umbrella-card substitute | restored (adapted: umbrella = our decompose parent; Milestone-field row folded into the umbrella row's anti-pattern) | Same file |
| Table 3 when-to-invoke-decomposition (5 rows incl. pure-refactor skip) | restored (adapted: architect-time expectation, not intake-time routing) | Same file |

### Source: `references/spec-first-checklist.md`

| Item | Disposition | Where / why |
|---|---|---|
| "Why spec-first" rationale | restored (near-verbatim, seats renamed) | `references/spec-awareness.md` § Why |
| Six-row trigger table | adapted / partially rejected | Generalized rows in spec-awareness.md table; their rows 2–5 are project-specific (see SKILL.md audit above) |
| Same-PR vs separate-PR choice | restored (near-verbatim) | spec-awareness.md § Sequencing |
| Row-6 spec-only work ("the Goal IS the spec") | adapted | Our step 5 + § Sequencing |
| Anti-pattern: mid-implementation discovery | restored (verbatim) | spec-awareness.md § Anti-patterns |
| Anti-pattern: change-impact matrix is binding | rejected | We have no change-impact matrix |
| Anti-pattern: backfilling spec is archaeology | restored (verbatim) | spec-awareness.md § Anti-patterns |
| `docs/plans/<feature>/` scaffolding lifecycle | rejected | Their gitignored plan-workspace convention; our specs live in the repo via spec PRs |

### Source: `references/intake-decision-tree.md`

| Item | Disposition | Where / why |
|---|---|---|
| Table 1 pre-card sibling routing (6 rows) + routing flow diagram | rejected | Sibling routing; our equivalents are recorded per-route in the SKILL.md audit above |
| "Triggers vs phrasings — match by signal type" rule | adapted | Frontmatter casual-phrasing sentence; the router matches descriptions |
| Table 2 manager-locked vs consumer-deferred (8 rows) | restored (generalized: their subsystem rows → our schema/envelope/policy rows) | spec-awareness.md locked-vs-deferrable table |
| Red-line list (9 items, never deferrable) | restored (generalized to agent-teams: policy code, board schema, spec gate, envelopes, manifests, ADRs) | spec-awareness.md § Red lines |
| Mid-implementation red-line encounter → stop, surface, suspend | restored (adapted: record blocker, hand to architect) | spec-awareness.md § Red lines closing rule |
| Table 3 design-left-to-consumer AC template | restored (near-verbatim; consumer→dev, card-body-sync step reference replaced with "Card records the option once delivered") | spec-awareness.md § Template |

---

## 2. `briefing-board`

### Source: `briefing-daily/SKILL.md`

| Item | Disposition | Where / why |
|---|---|---|
| Frontmatter triggers + casual phrasing + do-NOT-use | adapted | Our description (already rich; "catch me up" forms added) |
| Overview: three questions (where / wrong / next) | adapted | Our intro + workflow |
| Required sub-skills block | rejected | `producer_board.py brief` replaces the mesh |
| "Does NOT merge/transition/create" boundary | adapted | Our Boundaries (predates migration) |
| Step 1 read via operating-kanban + settings resolution | adapted | Our `brief` command |
| Step 2 exact-format markdown template | adapted | Our template, restructured onto lanes with human queues first |
| Hot-card ordering + Backlog collapse >5 | restored (rationale verbatim; ordering extended with human-queues rank 1) | `references/formats.md` § Hot-cards |
| Single-consumer simplified format | restored (adapted to single-operator) | formats.md § Single-operator |
| Step 3 WIP-cap flag per consumer | adapted | WIP header line + read-rules bullet (our WIP is board-wide; per-consumer caps need the dev seat) |
| Step 3 stale-claim heuristic + git commands | adapted | SKILL.md § Stale work; exact computation restored in formats.md |
| Step 4 recommendation ladder (4 rungs) | adapted | Re-ranked for our seats; their "claim a Ready card" rung rejected (Producer never becomes Consumer) |
| One-sentence, no-menu rule | verbatim in spirit | SKILL.md § The one recommended action |
| Step 4a extended orientation (sibling handoffs) | rejected | Direction questions go to the human; no siblings |
| Governance sequence for rare admin actions | rejected | Briefing never mutates at all (stronger than their rule) |
| Context-switch reload variant + orientation-vs-resume distinction | adapted | SKILL.md § Catching up on one Card; output format restored in formats.md |
| Timeboxed dispatch list ("I have 2 hours" → top 3) | rejected | Collides with dispatch-is-a-separate-skill |
| Velocity signal | rejected | Their own text calls it a human-cadence construct; our design dropped sprint math |
| Failure modes (5 rows) | restored (full table, adapted) | formats.md § Failure modes |
| Tone and format rules | restored (near-verbatim) | formats.md § Tone; core rules also in SKILL.md template intro |

### Source: `references/daily-detail.md`

| Item | Disposition | Where / why |
|---|---|---|
| Empty-board format + no-padding rule | restored (adapted) | formats.md § Empty board |
| Single-consumer format + drop-suffix rule | restored (adapted) | formats.md § Single-operator |
| Stale-claim computation (3 conditions, both git commands, 0-or-1 rationale) | restored (verbatim commands) | formats.md § Stale-claim age computation |
| Context-reload truncated format + firing condition | restored (adapted to our pair state) | formats.md § Context reload |
| Hot-cards ordering list | restored | formats.md § Hot-cards |
| WIP count reference (per-consumer cap, Blocked excluded) | adapted | Blocked-excluded lives in `policy.py`/board-wide WIP; per-consumer caps deferred until the dev seat exists |
| Tone section | restored (near-verbatim) | formats.md § Tone |

---

## 3. `triaging-board`

### Source: `triaging-board/SKILL.md`

| Item | Disposition | Where / why |
|---|---|---|
| Frontmatter triggers ("stale claims", "ghost branches", "abandoned work") + do-NOT-use | adapted | Our description |
| Overview: two questions (blocked / stale) | adapted | Our intro |
| Required sub-skills block | rejected | CLI + policy replace the mesh |
| "Does NOT resolve blockers itself"; Producer decides | adapted | Our Rules + Boundaries |
| Step 1 scan Blocked + read blocker note | adapted | Our steps 2–3 |
| 3-class blocker schema (external / decision / stale) | adapted | Merged into our who-owes-the-decision table; indicator phrases restored in `references/blocker-classes.md` |
| Decision-pending → intake when it maps to a fresh requirement | adapted | Our routing-table row "blocking question is itself a new requirement" |
| Step 2 stale-claim scan (`git branch -r --list`, age + progress commands) | adapted | Our step 5 (branch discovery via handoff comments until claim naming is uniform; commands kept) |
| Interpretation thresholds (0/1 commits; 72h flag; 7d + notified → release) | verbatim | Our step 5 + blocker-classes.md |
| Step 3 recommended-actions table (6 rows) | adapted | Rows map to our routing table + step 5; suspended-card row rejected (below) |
| Suspended card > 30 days row | rejected | No `suspended` label in our model |
| Step 4 release procedure (branch delete + transition as separate audited actions) | adapted | Replaced by the single policy-gated `release-claim` command (human-only); asymmetric-failure ordering documented in `workflows.py` |
| Governance sequence + autonomy defaults (R-class rows) | rejected | `release_claim` and `promote_to_ready` are policy rows in code |
| "Both actions proposed together as one atomic unit, never separately" | adapted | Strengthened: one command, so half-approval is impossible |
| Summary format | adapted | Our step 7 template |
| Sibling handoff 1 (decision needs investigation → gstack investigate) | rejected | Technical investigation is the architect seat's job |
| Sibling handoff 2 (blocker generates fresh requirement → intake) | adapted | Our routing-table row (kept; it was never really a sibling call) |
| Failure mode: empty Blocked scan → proceed to stale sweep | adapted | Implicit in our step order; "Triage clean" message covers the empty end state |
| Failure mode: no blocker note → evidence missing, do not classify | adapted | Our step 3 evidence rule |
| Failure mode: age computation fails → flag, never release without evidence | restored | Our step 5 inline + blocker-classes.md |
| Failure mode: investigate inconclusive | rejected | No sibling investigation call exists |
| Not-covered list (grooming, cycles, estimates, velocity) | adapted | Our Boundaries third bullet |

### Source: `references/triage-detail.md`

| Item | Disposition | Where / why |
|---|---|---|
| Blocker investigation steps ("Blocked: waiting on X" note location) | adapted | Our step 3 read-the-comments rule |
| Indicator phrases for all three classes | restored (verbatim) | blocker-classes.md § Indicator phrases |
| Stale-block evidence criteria + "Any ONE is sufficient" | restored (verbatim) | blocker-classes.md § Stale-block evidence |
| Stale-claim release steps (flag → notify → recommend) | verbatim | SKILL.md step 5 |
| Release shell sequence (push --delete, then transition) | adapted | One `release-claim` command; blocker-classes.md § Assembling the release recommendation |
| Separate audit entries per mutation | adapted | The command's single envelope records all steps (`completed` list) |
| Suspended-card review (3 rules) | rejected | No `suspended` label in our model |
| Not-covered list + v1.x deferral rationale | adapted | Our Boundaries; deferral rationale ("staying narrow keeps it fast") kept in spirit |

---

## 4. `authoring-spec` (from `decomposing-into-milestones`)

### Source: `decomposing-into-milestones/SKILL.md`

| Item | Disposition | Where / why |
|---|---|---|
| Frontmatter triggers ("split into cards", "break into milestones", 拆-phrasings) | adapted | English triggers merged into our description; the Chinese phrasings route through intent matching anyway |
| `argument-hint` / artifact-path arguments | rejected | Our input is the merged spec, not an artifact argument |
| Overview: discipline-skill framing, gates as refusal conditions | verbatim in spirit | Our Job 3 preamble + `references/decomposition-gates.md` intro |
| "Composes sibling skills; composition is permanent" | rejected | The anti-invariant of our design |
| When-to-use / when-NOT (single-card edits, pure refactors, pre-decomposed batches) | adapted | Thin-spec rule in Job 3; single-card is Job 2; pure-refactor exemption folded into V-letter note (architect counts as customer) |
| Mermaid decision tree | rejected | Diagram of the pipeline we adapted; prose carries it |
| The Iron Law | verbatim | decomposition-gates.md § The Iron Law |
| Step 1 ingest (file / dir / stdin modes, 50-file cap, EOF paste protocol, <30-line bounce) | rejected except the thin-artifact rule | Carrier mechanics; "spec with no distinct capabilities = single Card" kept in Job 3 |
| Step 1 optional `gstack:/plan-eng-review` arch lock | rejected | Architecture validation is this seat's own job |
| Step 2 identify capabilities (1.5-2× overshoot heuristic) | rejected | Process detail below our altitude; the gates catch what matters |
| Step 3 vertical-slicing gate (4 anti-patterns as refusals) | verbatim | decomposition-gates.md § Vertical slicing (all 5 mistakes incl. solution-over-requirements) |
| Step 4 INVEST gate (per-letter refusals) | verbatim | decomposition-gates.md § INVEST |
| Step 5 size calibration + L-ceiling split rule | verbatim | decomposition-gates.md § Size calibration |
| Step 6 dep graph (hard / soft / depended-on-by; ASCII rendering) | adapted | decomposition-gates.md § Dependencies; rendering detail dropped |
| Step 7 synthesize batch (bodies + outline narrative + batch summary; no per-card prompts) | adapted | Our children-JSON flow is the batch artifact; single-message discipline inherent |
| Step 8 batch propose → ack → create → audit (action_id 1, creator-trace, transition to Ready) | rejected | `decompose` command owns creation + partial reporting; **Ready-at-creation violates the human gate** — ours land `(Backlog, human)` |
| Common Rationalizations table (7 rows) | verbatim in substance | Rows folded into the gates' refuse-when lines and the Iron Law; the "INVEST is for human teams" answer is the AI-recalibration section |
| Red Flags — STOP list (title phrases, trailing wire-up, unilateral split, spike ratio; INVEST letter flags) | verbatim | decomposition-gates.md red-flag phrases + per-letter refusal criteria |
| Verification checklist (7 items) | adapted | decomposition-gates.md § Checklist; schema row replaced by our body conventions, Ready replaced by `(Backlog, human)` |
| "How mutating actions are handled" governance sequence | rejected | `policy.py` + `decompose` envelope |
| Required sub-skills block | rejected | No skill mesh |
| Failure modes: artifact too short / no clear capabilities | adapted | Thin-spec rule; "do NOT force a decomposition through fog" kept in spirit |
| Failure modes: INVEST loop >3 / reslice loop >3 escalation | verbatim in substance | decomposition-gates.md § Escalation + Job 3 closing rule |
| Failure modes: dep cycle refuses batch | verbatim | decomposition-gates.md § Dependencies |
| Failure modes: batch >10 soft-warn | verbatim | decomposition-gates.md § Escalation |
| Failure modes: partial `gh issue create` | adapted | `decompose` already reports created/failed + duplicate warning (pre-existing ours) |
| Failure modes: pre-existing card with same title | rejected | Our intake dedupe rule covers the class at the earlier boundary |
| Worked-example pointer | rejected | See oauth-walkthrough row below |

### Source: `references/invest-checklist.md`

| Item | Disposition | Where / why |
|---|---|---|
| Wake source citation + refusal-conditions framing | verbatim | decomposition-gates.md header + § INVEST |
| Per-letter Wake quotes + refusal conditions + operationalizations | adapted (refusal criteria and key nuances verbatim; quotes compressed) | decomposition-gates.md § INVEST — kept: declared-coupling escape valve (I), token-promising-a-conversation + scope-fixed-details-negotiable (N), architect-counts-as-customer (V), spike-vs-TBD (E), E+S-are-one-gate, verification-capacity ceiling (S), feeling-words + operationalized non-functionals (T) |
| Pairwise independence walk ("could B be claimed before A is Done?") | adapted | Folded into the I refusal line |
| Reframe playbook table | verbatim | decomposition-gates.md § Reframe playbook |
| "Two or more letters fail = structural" | verbatim | Same section, closing line |
| AI-orchestration reframe table + no-canonical-source caveat | adapted (compressed to the two letters that actually shift) | decomposition-gates.md § AI-orchestration recalibration, marked as source's original framing |

### Source: `references/decomposition-patterns.md`

| Item | Disposition | Where / why |
|---|---|---|
| Cohn source citations + Hamburger/Lawrence non-canon caveat | adapted | Header cites Cohn; the non-canon community supplements were never carried, nothing to caveat |
| Upward pointer / walking-skeleton enforcement note | adapted | Walking-skeleton lives in intake's shape-judgment.md; the layer-only/wire-up refusals enforce it here |
| SPIDR: all five axes with use-when / refuse-when | verbatim in substance (examples compressed to one per axis) | decomposition-gates.md § SPIDR |
| Five splitting mistakes (incl. #3 solution-over-requirements, missing from the main-skill table) | verbatim | decomposition-gates.md § Vertical slicing |
| Business pattern catalog (9-row shape → axis table) | near-verbatim | decomposition-gates.md § Shape catalog |
| Worked-example pointer | rejected | See oauth-walkthrough row |

### Source: `references/size-calibration.md`

| Item | Disposition | Where / why |
|---|---|---|
| 4-bin table + no-XL/no-points/no-hours | verbatim | decomposition-gates.md § Size calibration |
| Ceiling rule + review-fatigue rationale | verbatim (compressed) | Same section |
| Little's Law / batch-size math (Reinertsen, Anderson) | rejected | Rationale prose; one-line citation kept, full argument in the reference clone |
| Fowler #NoEstimates exegesis | rejected | Same; the operative conclusion (coarse bins, no points) is the table itself |
| AI-cadence reframe (verification-capacity bottleneck; what stays platform-agnostic) | adapted | decomposition-gates.md § AI-orchestration recalibration |
| 100x time/scope acceleration + very-large-cohesive-PR allowance | rejected | Contradicts our one-Card-one-PR ceiling discipline; noted here so the divergence is conscious |
| Calibration drift signs (30% XS / 30% L / mean-LOC bands) | verbatim | decomposition-gates.md § Size calibration, closing paragraph |

### Source: `references/card-schema.md`

| Item | Disposition | Where / why |
|---|---|---|
| Entire file (their converged body schema, thin-pointer block, audit-trail marker) | rejected | Our Card body conventions are established in intake/decompose; their markers belong to their governance |

### Source: `references/oauth-walkthrough.md`

| Item | Disposition | Where / why |
|---|---|---|
| Entire file (5-card OAuth worked example) | rejected (user decision 2026-08-06) | Keeps the skill bounded; the example remains available in the reference clone if a training artifact is ever wanted |

---

## 5. `dispatching-work` — no source

No counterpart exists in board-superpowers, superpowers, or gstack (their
dispatch is Mode-2 Consumer spawning — a different mechanism, recorded in
`skill_migration.md` § 7). Nothing to audit; the skill is closed as-is.

---

## 8. `consuming-card` (new skill)

### Source: board-superpowers `consuming-card/SKILL.md`

| Item | Disposition | Where / why |
|---|---|---|
| Frontmatter triggers + do-NOT-use disambiguation | adapted | Our frontmatter; do-NOT-use points at the six Producer skills and `verifying-delivery` |
| 23-node journey encoding (A1-A3, B1-B5, C1-C4, D1-D3, E1-E2, F1, G1-G5) | rejected | Project-internal node codes; our lifecycle is ARCHITECTURE 7.1 and needs no second vocabulary |
| G4 Mode topology (Mode-1 architect-spawned / Mode-2 Producer-spawned) | rejected | Dispatch renders prompts and stops; no Producer spawns a Consumer |
| G4 Mode-2 R-class callback protocol (4-step propose/report/evaluate/re-spawn) | rejected | Same; no subagent depth budget to manage |
| G4 Mode-2 procedural fallback table (12 sibling rows) | rejected | No sibling mesh |
| Required sub-skills block (6 same-plugin skills) | rejected | `producer_board.py` + `policy.py` replace all six |
| F1 claim: card-number resolution, ambiguous -> ask | adapted | Our step 1 |
| F1 claim: Status MUST be Ready, unmet depends-on -> stop | adapted | Our step 1; enforced in code by `_bound_card` |
| F1 claim: `claim-card.sh` 4-step transaction | rewired | `producer_board.py claim`; claim-first compensation order and race-lost envelope are ours |
| F1 claim: enter the worktree, do NOT return to repo root | verbatim (path adapted) | Our step 2 + `references/claim-and-worktree.md` |
| F2 B1 plan synthesis via `superpowers:writing-plans` | rewired | Plan bounded to this Card, inline; no sibling call |
| F2 B2 TDD cycle via `superpowers:test-driven-development` | adapted (content inlined) | `references/tdd-discipline.md` |
| F2 B3 TDD-skip refusal | verbatim | Our step 4 refusals |
| F2 B4 cross-card refusal | verbatim | Our step 4 refusals |
| F2 B5 permission-boundary via classifying-actions | rejected | `policy.py` checks before the first GitHub call |
| F2 in-flight blocker -> Blocked + comment | adapted | Our "When you are blocked", plus the what-tried / what-needed / where-the-work-is contract |
| F3 iron law: never open a PR without the full verification chain | adapted | Our step 5 |
| F3 C1-C4 sibling verification chain | rejected as calls; adapted as content | Independent review is `verifying-delivery`'s job; the evidence requirement is ours |
| F3 "Common rationalizations to reject" (3 rows) | adapted | Merged into `references/tdd-discipline.md` |
| F4 D1+D2 pre-flight: AC checkboxes terminal, bare `[ ]` forbidden | verbatim | `references/pr-contract.md`; enforced by `acceptance_criteria_problems` |
| F4 D1: `submit-pr.sh`, auto-appended `Closes #N`, never raw `gh pr create` | rewired | `producer_board.py submit-pr`; trailer required by `validate_pr_body` |
| F4 D3 rework: same worktree, no new branch | verbatim | Our "When QA returns a defect" |
| F4 E1 post-merge cleanup; webhook Status flip; 5-minute lag | rewired | `reconcile-done` confirms MERGED explicitly rather than trusting a webhook |
| F4 E2 crash path: surface partial state, heartbeat audit row, leave worktree | adapted (audit row dropped) | Blocked preserves claim and worktree |
| G1-G3 governance (audit row per mutation, R-class propose-await, A-class gate) | rejected | `policy.py` |
| v1.x roadmap stubs | rejected | Their maintenance backlog |

### Source: board-superpowers `enforcing-pr-contract/`

| Item | Disposition | Where / why |
|---|---|---|
| Contract A: three-section PR shape | adapted | Extended to our five sections (ARCHITECTURE 9.5) |
| Contract A: `## Automated Verification` required and non-empty | verbatim | `validate_pr_body` |
| Contract A: Human Verification optional but not filler | verbatim | `validate_pr_body` + `_FILLER` |
| `references/filler-detection.md` phrase list | adapted | Our `_FILLER` tuple; phrases generalised |
| Contract B: every AC terminal at submit | verbatim | `acceptance_criteria_problems` |
| Contract C: auto-close keyword validation | adapted | `Closes #<issue>` required by `validate_pr_body` |
| `references/taste.md` | rejected | House style guidance, not a contract |

### Source: superpowers (4 skills)

| Item | Disposition | Where / why |
|---|---|---|
| TDD Iron Law, delete-and-restart, no keep-as-reference | verbatim | `references/tdd-discipline.md` |
| Red-Green-Refactor with mandatory verify-red | verbatim (Python examples) | Same |
| TDD rationalizations table (13 rows) | adapted (7 kept) | Same; TypeScript-tooling rows dropped |
| TDD good/bad test examples | adapted | Replaced by "name the production change that would make this fail" |
| verification-before-completion: Iron Law + 5-step gate | verbatim | SKILL step 5 + reference |
| verification-before-completion: claim/requires/not-sufficient table | adapted | Same; agent-delegation row kept |
| verification-before-completion: red-flag and rationalization tables | adapted | Compressed into the evidence section |
| using-git-worktrees: never work at repo root; worktrees outside the tree; rationale | adapted | `references/claim-and-worktree.md` |
| using-git-worktrees: native-tool-first detection, ignore check | rejected | Our worktree path is computed from Card identity by `claim` |
| finishing-a-development-branch: cleanup-after-merge discipline | adapted | `reconcile-done` + removal guards |

---

## 9. `verifying-delivery` (new skill)

### Source: gstack `/review`

| Item | Disposition | Where / why |
|---|---|---|
| Pre-emit verification gate (quote the lines, or the finding is suppressed) | verbatim | `references/evidence-and-challenge.md`; the highest-value adoption in this migration |
| Confidence calibration 1-10, below 7 caveated, 3-4 to appendix | adapted | Same; 3-4 routes to `limitations` |
| Specialist dispatch by domain, parallel, independent checklists | adapted | `references/review-dimensions.md`, as bounded passes |
| Finding deduplication + confidence boost on multi-pass confirmation | verbatim | Same |
| Red-team conditional (200+ line diffs, or a critical finding exists) | verbatim | SKILL step 6 |
| Scope-drift detection (delivered vs stated intent) | verbatim | SKILL step 3 |
| Plan-completion audit: DONE / PARTIAL / NOT DONE / CHANGED / UNVERIFIABLE | adapted | Retargeted from plan files to Card acceptance criteria |
| Critical safety pass (SQL injection, races, LLM trust boundaries, shell injection, enum completeness) | adapted | Folded into the `security` and `correctness` dimensions |
| Platform / base-branch detection, branch validation | rejected | `_bound_card` + `Board.pull_request` own this |
| **Fix-first triage: AUTO-FIX mechanical items, batch ASK items** | **rejected** | 7.4 forbids QA touching production code. A reviewer that fixes removes the finding from the record along with the defect, and no independent evidence of either survives |
| Test stub generation (specialists propose skeletons) | rejected | Writing tests is the Developer's delivery |
| Adversarial review via Codex | rejected | No Codex surface on this branch |
| Greptile comment classification and reply routing | rejected | No such integration |
| Telemetry, `cross_project_learnings`, `artifacts_sync_mode` | rejected | Out-of-band data flow no consuming repo opts into by installing a board plugin |
| `checkpoint_mode` continuous auto-commits | rejected | A reviewer that commits is a reviewer that writes code |
| `explain_level`, `question_tuning` | rejected | Carrier tuning, not review discipline |
| PR quality score 0-10; output structure (scope check, P0-P3, GATE PASS/FAIL) | adapted / partially rejected | Severity and evidence structure adopted into the verdict; the score is never an acceptance input |

### Source: gstack `/qa`

| Item | Disposition | Where / why |
|---|---|---|
| "Repro is everything" - every issue needs at least one screenshot | verbatim | SKILL step 7 |
| Verify before documenting (retry once to confirm) | verbatim | Same |
| Never include credentials; write `[REDACTED]` | verbatim | Same |
| Check the console after every interaction | verbatim | Same |
| Test as a user; never read source first | verbatim | Same |
| Tier selection (`--quick` / standard / `--exhaustive`) | rejected | Severity is a verdict field, not a run mode |
| Fix loop (locate -> fix -> atomic commit -> re-test -> classify) | **rejected** | Same reason as fix-first triage |
| Health score rubric (weighted categories, severity deductions) | rejected | Never an acceptance input |
| WTF-likelihood self-regulation, 50-fix hard cap | rejected | Only meaningful if QA fixes, which it does not |
| `.gstack/qa-reports/` output tree, `baseline.json` | rejected | Our evidence lives on the Pull Request and the Issue |
| Framework-specific notes (Next.js, Rails, WordPress, SPA) | rejected | Consuming-repo specific |

### Source: superpowers + board-superpowers

| Item | Disposition | Where / why |
|---|---|---|
| `verification-before-completion`: evidence before claims | adapted | `references/evidence-and-challenge.md` closing section |

> **Corrected 2026-08-06.** Rows for `reviewing-pr-queue` and `requesting-code-review` were removed: those sources were cited without being read, and nothing in `verifying-delivery` derives from them. See ATTRIBUTION.md > Provenance labels > "Not used, and previously over-claimed".
