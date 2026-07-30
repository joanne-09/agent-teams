# 04 — Implementation plan (milestones and cards)

> The *in what order* document. Read
> [`03-target-architecture.md`](./03-target-architecture.md) first — this
> plan assumes its design. [`05-file-change-map.md`](./05-file-change-map.md)
> tells you which files each card touches.
>
> **25 cards across 6 milestones.** Sizes use the repo's own XS/S/M/L
> calibration (`decomposing-into-milestones/references/size-calibration.md`).
> Effort is expressed in cards and sessions, not calendar days — per ADR-0010
> the repo deliberately refuses calendar estimates.

---

## 0. Before card one — five things to settle

### 0.1 Build it in this repo

Your goal doc says *"use this repo as the basic basement, i could do any
modifications."* Take that literally: **modify `board-superpowers` in
place**, keep the name, keep the git history. A pragmatic internal fork
gains nothing from a rename and loses the ability to pull upstream fixes.

### 0.2 The dashboard is a *different* repo

Two repos, two jobs:

| Repo | Role |
|---|---|
| `board-superpowers` (this one) | The plugin. The team's operating system. Where all 25 cards below land. |
| `<your>-dashboard` (new) | The product. UI + data sources. Where the *team* does its work and opens its PRs. |

The plugin gets installed into the dashboard repo; the board (GitHub
Project) belongs to the dashboard repo. Do not build the dashboard in here.

The one exception is deliberate: **dogfood milestones M0–M4 on
`board-superpowers`' own board.** The team builds itself first. That is how
you find out whether the handoff protocol works before betting a product on
it — and it is exactly what the repo's own Self-hosting section prescribes.

### 0.3 The `skills/` Process gate will block you

The most common way this plan stalls. Editing **any** file under `skills/`
is blocked at tool level by `hooks/pre-tool-use.sh` until
`example-skills:skill-creator` has been invoked **in that session**. Per
`skills/AGENTS.md`, before the first skill edit in a session you must:

1. State that the gate fires and that you are invoking the skill;
2. Invoke `example-skills:skill-creator`;
3. Read `SKILL_DEVELOPMENT.md` **in this session** ("I already know it" is
   explicitly forbidden);
4. Edit `SKILLS.md` **before** the `skills/` directory change, same PR.

15 of the 25 cards touch `skills/`. Budget for this on every one.

### 0.4 Working-tree discipline

Repo root stays on `main`. Every card is authored in a worktree:

```bash
git worktree add "$HOME/.config/superpowers/worktrees/board-superpowers/<branch>" \
  -b <branch> origin/main
```

### 0.5 Verify one external fact first

**[verify]** that `gh project field-create` can create a `SINGLE_SELECT`
field with the six seat options, on your `gh` version. Card 6 depends on it.
If it cannot, the fallback is the GitHub UI — the same fallback ADR-0001
already accepts for creating the Project itself. `gh` is currently reported
missing on this machine; install it before starting M1.

---

## 1. Milestone map

```
M0  Spec           ADR-0029/0030/0031 + contract edits          5 cards
      │                    (governance rule: spec before code)
      ▼
M1  Board plumbing Role field · handoff_card · board-canon      5 cards
      │
      ├──────────────┐
      ▼              ▼
M2  Governance   M3  Seat routing                            3 + 2 cards
    seat matrix      [role:] token · dispatcher
    audit seat
      └──────┬───────┘
             ▼
M4  Skills     3 new · 4 edit-cards                             7 cards
             │
             ▼
M5  Proof      dashboard repo · golden path · retro             3 cards
```

**Critical path:** M0 → M1 → M2 → M4 → M5. M3 runs parallel to M2.

---

## 2. M0 — Spec (5 cards)

The repo's governance rule is absolute: architecture changes land **before**
the implementation that depends on them. Skipping M0 is how the fork rots.

### Card 1 — ADR-0029: model agent seats at the plugin layer
`size:S` · deps: none

- [ ] `docs/architecture/adr/0029-agent-seats-at-plugin-layer.md` exists,
      status `accepted`
- [ ] States the **narrow** supersession: I-3 continues to hold for human
      identity; agent seats are orthogonal and never carried by GitHub user
      identity
- [ ] Names the six seats and the `Role` field
- [ ] Explicitly confirms F-C13 stakeholder routing and Producer F-03 are
      unaffected, with reasoning
- [ ] `07-cross-cutting-invariants.md` I-3 amended to point at ADR-0029

### Card 2 — ADR-0030: seat-dimension autonomy + handoff authority
`size:M` · deps: Card 1

- [ ] Marks ADR-0006 `superseded by ADR-0030` (ADR-0006 itself stays
      immutable)
- [ ] Full 2-D `(action_id, seat) → A|R|N` matrix for rows 1–14, 100–113,
      200–208, 300–305
- [ ] `seat_overrides:` schema + precedence `project > user > seat > default`
- [ ] Handoff authority matrix (03 § 5.2) with the illegal-handoff refusal
      rule
- [ ] Explicit restatement that **row 12 is `N` for every agent seat** — P6
      and I-2 preserved

### Card 3 — ADR-0031: `handoff_card` as the ninth protocol action
`size:S` · deps: Card 1

- [ ] Extends (does not supersede) ADR-0025
- [ ] Signature, the Status-independence rule, the Form A three-step
      implementation, the handoff comment shape
- [ ] Records why generic `set_card_field` was rejected

### Card 4 — Contract file edits
`size:M` · deps: Cards 2, 3

- [ ] `00-kanban-protocol.md`: 8 actions → 9
- [ ] `06-audit-log-schema.md`: `actor_seat` column + 300-block catalog +
      per-action payload sub-schemas for 300–305
- [ ] `01-ubiquitous-language.md`: **Seat**, **Handoff**, **Lane**
- [ ] `03-config-schemas.md`: `seat_overrides:`
- [ ] Change-impact matrix in `docs/architecture/AGENTS.md` gains rows for
      the new cross-file couplings

### Card 5 — Maintainer doc sync
`size:S` · deps: Card 4

- [ ] `BOARD_DEVELOPMENT.md`: the ninth action + the `Role` field
- [ ] `AGENTS.md` routing block: seat routing alongside Producer/Consumer
- [ ] `agent-team-adaptation/` docs cross-referenced from the architecture
      README so the fork's intent is discoverable

**M0 done when:** three ADRs accepted, five contract files consistent, and
nothing under `skills/` or `scripts/` has been touched yet.

---

## 3. M1 — Board plumbing (5 cards)

### Card 6 — `Role` field provisioning
`size:M` · deps: Card 4 · **[verify] `gh` first**

- [ ] New setup stage `m11_repo_ensure_role_field` in `stages-registry.yml`
      following the 5-callable contract (ADR-0014)
- [ ] Creates a `Role` `SINGLE_SELECT` field with the six seat options if
      absent; validates the option set if present
- [ ] Idempotent; `not-applicable` when the projection declares no
      seat-field capability
- [ ] UI fallback documented in `bootstrapping-repo/references/`
- [ ] Co-located pytest passes; read `SETUP_STAGES_DEVELOPMENT.md` first

### Card 7 — `read-board.sh` emits `role`
`size:S` · deps: Card 6

- [ ] Each JSON object gains `"role": "<seat>|null"`
- [ ] `--role <seat>` filter, mirroring the existing `--status` filter
- [ ] Absent field → `null`, never an error (fork must run on un-migrated
      boards)
- [ ] `shellcheck -x` clean

### Card 8 — `handoff-card.sh`
`size:M` · deps: Cards 6, 7

- [ ] Args `--card`, `--from-seat`, `--to-seat`, `--reason`, `--project`
- [ ] Three steps in order: set `Role` → post the structured handoff comment
      → write the audit row
- [ ] Refuses illegal handoffs per the authority matrix with a distinct
      non-zero exit code, before mutating anything
- [ ] Refuses past the handoff cap (default 6) with its own exit code
- [ ] Identifiers reach the embedded `python3` filter via env vars, never
      string interpolation (the injection rule `transition-card.sh` follows)
- [ ] Exit codes documented in the header comment

### Card 9 — `board-canon`: seats, handoffs, cap
`size:M` · deps: Card 8 · **Process gate**

- [ ] `references/handoff-authority.md`: the full matrix + refusal rule +
      handoff cap
- [ ] `references/card-body-schema.md`: `Role` as an orthogonal field;
      explicitly *not* a Status and *not* `Assignees`
- [ ] Body stays inside the 200–300 line atomic budget
- [ ] `SKILLS.md` catalog row lists the new reference file, same PR
- [ ] No upward calls — atomic reflexive constraint holds

### Card 10 — `operating-kanban`: dispatch `handoff_card`
`size:S` · deps: Card 9 · **Process gate**

- [ ] `references/action-dispatch.md` covers the ninth action
- [ ] `references/github-project-v2.md` maps it to `handoff-card.sh`
- [ ] Declares a `seat_field` setup capability so Card 6's stage predicate
      can consult it (the ADR-0027 pattern)

**M1 done when:** you can hand a card between two seats from the CLI, the
board shows it, the comment lands, and an illegal handoff is refused.

---

## 4. M2 — Governance (3 cards)

### Card 11 — `classifying-actions` gains the seat dimension
`size:M` · deps: Card 2 · **Process gate**

- [ ] `references/matrix.md` carries seat columns for every existing row
- [ ] `references/action-id-catalog.md` gains rows 300–305
- [ ] Body documents the two-argument call `(action_id, seat) → A|R|N`
- [ ] Missing seat → today's one-dimensional behavior (back-compatible)
- [ ] Body stays ≤ 200 lines (currently 81 — spillover goes to references)

### Card 12 — `seat_overrides` resolution
`size:M` · deps: Card 11

- [ ] `bsp_resolve_autonomy_class` in `common.sh` accepts a seat argument
- [ ] Precedence `project > user > seat > default`, with a unit test per
      precedence pair
- [ ] Unknown seat → default class + a warning; never a hard failure
- [ ] `shellcheck -x` clean

### Card 13 — Audit carries the seat
`size:M` · deps: Card 2

- [ ] `scripts/migrations/audit-v2-to-v3.sh` + `-impl.py`, mirroring the
      v1→v2 pair; adds nullable `actor_seat`; bumps `audit_schema_meta` to 3
- [ ] All three `audit-schema.*.sql` baselines include the column
- [ ] `audit-log-write.sh` gains `--actor-seat`; omitted → NULL
- [ ] `bsp_audit_local_write` jsonl shape carries it;
      `audit-flush-impl.py` passes it through
- [ ] `auditing-actions` payload templates updated (**Process gate**)
- [ ] `audit-init.sh` runs v2→v3 automatically on a v2 DB, as it already
      does for v1→v2

**M2 done when:** a handoff writes an audit row with the seat in it, and
`seat_overrides` can promote one seat's R to A without affecting others.

---

## 5. M3 — Seat routing (2 cards, parallel to M2)

### Card 14 — `[role:<seat>]` parsing and routing
`size:M` · deps: Card 1 · **Process gate**

- [ ] `using-board-superpowers` parses `[role:<seat>]` from the first
      message and binds the seat for the session
- [ ] Seat routing table lives in `references/routing.md` — the entry body
      is already over its 200-line budget at ~225
- [ ] **No token → today's behavior, byte for byte.** Regression-check the
      existing routing phrases
- [ ] `[role:rd] [board-card:#42]` routes to `consuming-card` with the seat
      bound
- [ ] Unknown seat → ask, never guess

### Card 15 — `dispatch-agent.sh`
`size:S` · deps: Card 14

- [ ] `--seat <seat>` `[--card <N>]` prints a ready-to-paste kick-off prompt
      carrying the seat token and any card token
- [ ] `--format subagent` emits the same content shaped for an `Agent` tool
      prompt
- [ ] `--format cron` emits a `claude -p` invocation
- [ ] Pure stdout, no side effects — the dispatch *decision* belongs to
      `dispatching-work`, this only renders it

**M3 done when:** pasting `[role:qa] review the queue` into a fresh session
puts that session in the QA seat.

---

## 6. M4 — Skills (7 cards)

Every card here trips the Process gate. Read `SKILL_DEVELOPMENT.md` in
session, invoke `example-skills:skill-creator`, edit `SKILLS.md` first.

### Card 16 — `dispatching-work` (EM seat)
`size:L` · deps: Cards 7, 11, 15 · **new molecular skill**

- [ ] Reads the board grouped by `Role` lane; finds cards whose seat has
      work waiting
- [ ] Applies WIP (`board-canon` formula) and the handoff cap
- [ ] Emits an ordered **dispatch queue**: seat, card, reason, kick-off
      prompt via `dispatch-agent.sh`
- [ ] Carrier-agnostic — the same queue serves human launch, one-deep
      subagent, or cron
- [ ] Refuses to dispatch a seat that has no legal action on that card
- [ ] `action_id` 303 audited per dispatch
- [ ] Body 250–450 lines; `.skill-meta.yaml` (`molecular` / `technique` /
      `claude-code-only` / `session`); `SKILLS.md` row + call-graph edge
- [ ] Regime 2 eval matrix in `evals/evals.json`

### Card 17 — `authoring-spec` (architect seat)
`size:L` · deps: Cards 9, 11 · **new molecular skill**

- [ ] Consumer-shaped: claims a spec card, works in a worktree, ends in a
      docs PR under the three-section contract
- [ ] Delegates through `composing-siblings` to `superpowers:brainstorming`,
      `superpowers:writing-plans`, `gstack:/plan-eng-review`
- [ ] Knows the difference between `docs/architecture/` (durable, committed,
      English) and `docs/plans/<feature>/` (scaffolding, gitignored)
- [ ] Hands off to `rd` on merge, or to `analyst` when the requirement is
      too thin to specify
- [ ] Refuses to write implementation code — that is RD's seat
- [ ] Body 250–450 lines; catalog + eval artifacts as Card 16

### Card 18 — `verifying-delivery` (QA seat)
`size:L` · deps: Cards 9, 11 · **new molecular skill**

- [ ] Claims a card in `(In Review, qa)`; reads the PR and the card's AC
- [ ] Runs `enforcing-pr-contract` validation, then delegates via
      `composing-siblings` to `gstack:/review`, `gstack:/qa` (UI cards),
      `gstack:/cso` (cards labelled `security`)
- [ ] Writes a **verdict** (`action_id` 304) with evidence — never a bare
      pass/fail
- [ ] Pass → handoff to `human`. Fail → handoff to `rd` with `Status` back
      to `In Progress` and specific, reproducible findings
- [ ] May open a test-only PR; may **not** modify production code
- [ ] Refuses to pass a card whose AC are not all `[x]` or `[!]`
- [ ] Body 250–450 lines; catalog + eval artifacts as Card 16

### Card 19 — EM-seat edits: `briefing-daily` + `triaging-board`
`size:S` · deps: Cards 7, 9

- [ ] `briefing-daily` groups by `Role` lane as well as `Status`; surfaces
      handoff counts approaching the cap
- [ ] `triaging-board` escalates along the §5.2 authority lines instead of
      generically "to the architect"
- [ ] Both remain read-mostly; no new mutating actions

### Card 20 — Analyst-seat edits: `intaking-requirement`
`size:S` · deps: Card 8

- [ ] Terminates in a **handoff to `architect`**, not in a bare card
- [ ] Created cards get `Role=architect`, `Status=Backlog`
- [ ] Refuses to set `Ready` — that is the architect's action (matrix row 5)
- [ ] `AGENTS.md` ↔ `intake-decision-tree.md` sync rule respected: if you
      touch one, touch both in this PR

### Card 21 — RD-path edits: `decomposing-into-milestones` + `consuming-card`
`size:S` · deps: Card 8

- [ ] `decomposing-into-milestones` sets `Role=rd` on every created card
- [ ] `consuming-card` F4 ends in a **handoff to `qa`** instead of
      terminating at "PR opened"
- [ ] `consuming-card` blocked-path escalates to `architect`, not `em`
- [ ] The other 22 nodes are untouched — keep this diff small and provable

### Card 22 — QA-seat edits: `reviewing-pr-queue` + `composing-siblings`
`size:S` · deps: Cards 8, 18

- [ ] `reviewing-pr-queue` is a QA-seat routine; on pass it hands to
      `human`, on fail to `rd`
- [ ] `composing-siblings/references/handoff-points.md` gains rows for the
      three new skills' sibling invocations
- [ ] Mode-2 procedural-fallback rules re-checked for the new call sites

**M4 done when:** all 17 skills pass `verify-skill-metadata.sh`,
`verify-skill-frontmatter.sh`, and `verify-skill-anti-patterns.sh`, and
`SKILLS.md` says 17.

---

## 7. M5 — Proof (3 cards)

### Card 23 — Stand up the dashboard repo
`size:M` · deps: M4 complete

- [ ] `<your>-dashboard` repo created; the fork installed into it
- [ ] GitHub Project created with **both** the six-option `Status` field and
      the six-option `Role` field
- [ ] `bootstrapping-repo` runs clean: all stages `applied`, including the
      new `m11` role-field stage
- [ ] Audit DB initialised at schema v3; a smoke row round-trips

### Card 24 — The golden path, end to end
`size:M` · deps: Card 23 — **this is the acceptance test for the whole plan**

Run the scenario from `00-goal.md`, one metric request, all five seats:

| Step | Seat | Expected | Board after |
|---|---|---|---|
| 1 | analyst | Intakes *"show revenue by region, last 30 days"* | `(Backlog, architect)` |
| 2 | architect | Writes the spec, decomposes into 2–3 INVEST cards | `(Ready, rd)` each |
| 3 | em | Dispatch queue names RD as next | queue emitted |
| 4 | rd | Claims, TDD via `superpowers:test-driven-development`, opens PR | `(In Review, qa)` |
| 5 | qa | `gstack:/review` + `gstack:/qa`; verdict written | `(In Review, human)` |
| 6 | human | Verifies the TODO list, merges | `(Done, —)` |

- [ ] Every step ran in its own session with only a `[role:]` kick-off — no
      human steering inside a seat
- [ ] The audit log reconstructs the whole path in one query, seat by seat
- [ ] At least one **negative** path exercised: QA rejects, card returns to
      `(In Progress, rd)`, RD fixes, QA passes
- [ ] At least one **refusal** observed: an agent attempting an action its
      seat is `N` for, and being stopped
- [ ] The trace is written up in `docs/plans/agent-team/golden-path.md`

### Card 25 — Retro and tune
`size:S` · deps: Card 24

- [ ] Handoff cap, WIP limit, and concurrency tuned against what you saw
- [ ] `seat_overrides` promotes any R that proved to be pure friction
- [ ] Audit checked for `mode=audit-dead-letter` — if present, that is the
      Postgres signal from 03 § 9
- [ ] Whatever the run taught goes into the relevant skill's references, not
      into a doc nobody reads

---

## 8. Effort

| Milestone | Cards | XS/S | M | L |
|---|---|---|---|---|
| M0 Spec | 5 | 3 | 2 | — |
| M1 Board plumbing | 5 | 2 | 3 | — |
| M2 Governance | 3 | — | 3 | — |
| M3 Seat routing | 2 | 1 | 1 | — |
| M4 Skills | 7 | 4 | — | 3 |
| M5 Proof | 3 | 1 | 2 | — |
| **Total** | **25** | **11** | **11** | **3** |

Per the repo's own sizing, one card is one Consumer session and one PR. The
three `L` cards (the new skills) are the ones that will actually take
thought; the eleven `S` cards are mostly mechanical once M0–M2 exist.

**Where the risk concentrates:** Card 6 (external `gh` dependency), Card 11
(the 2-D matrix is the most intricate single artifact), and Card 24 (the
first time all five seats run without a human in the middle).

---

## 9. Sequencing rules that keep this from rotting

1. **Spec before code.** M0 lands complete before Card 6 starts. If M1
   teaches you something that invalidates an ADR, write a superseding ADR —
   do not edit an accepted one.
2. **One card, one worktree, one PR.** The same discipline the plugin
   enforces on its users.
3. **`SKILLS.md` before `skills/`.** Same PR, ideally the preceding commit.
4. **Same-PR doc updates.** A card that makes `BOARD_DEVELOPMENT.md` or
   `SETUP_STAGES_DEVELOPMENT.md` stale fixes it in that card's PR. This is
   the rule whose violation the repo names as its primary decay mode.
5. **Keep the no-token path working.** Until M5, every change must leave the
   plugin usable with no seat token — that is how you keep dogfooding while
   half-built.
6. **Run `pre-submit-audit.sh` before every PR.** It produces the
   `## Automated Verification` section for you.

---

## 10. If you want a smaller first bite

M0–M5 is the complete build. If you would rather see something running
sooner, this subset is a genuine walking skeleton — two seats, one handoff,
end to end:

> **Cards 1, 3, 4** (spec, minus the autonomy ADR) → **6, 7, 8, 9, 10**
> (board plumbing) → **14** (seat token) → **21** (RD hands to QA) →
> **18** (the QA skill).

Ten cards. You get RD → QA handoffs working with real verdicts, on the
existing autonomy matrix. Seat-aware governance (M2), the EM seat, and the
architect seat then layer on afterwards without rework, because the `Role`
field and `handoff_card` are already in place.

The honest trade-off: without M2, seats cannot yet *refuse* out-of-seat
actions — the hierarchy is advisory until Card 11 lands.

---

*Plan only — no code modified. Reflects v0.7.0 as of 2026-07-28.*
