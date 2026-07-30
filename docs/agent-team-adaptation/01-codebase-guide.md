# 01 — board-superpowers codebase guide (understand & trace)

> **Purpose:** help you understand and trace this repo quickly. This is a map
> + cheatsheet, **not** the spec. The spec source of truth is
> [`docs/architecture/`](../../architecture/) (start at `0001-positioning.md`).
> Whenever this guide and the spec disagree, the spec wins.
>
> **What this guide covers:** §5–§9 walk through **every skill, every hook,
> and every script** in the repo and explain what each is for — so you can
> trace what the codebase actually *does*, not just where files live.
>
> §13 explains the core domain nouns (**board**, **card**, **WIP**, **claim**,
> …) in **plain English** — start there if a term is unclear.

---

## 0. The 30-second version

`board-superpowers` (v0.7.0) is a **plugin** for Claude Code and OpenAI Codex
CLI that makes parallel AI coding sessions behave like a disciplined team
instead of chaos. It is **not** a code-writer and **not** a standalone
runtime — it is a *scheduling + enforcement layer* that sits on top of two
other plugins (`superpowers` for the TDD loop, `gstack` for design/QA/review/
security) and coordinates work through **your own GitHub Project board**.

The thesis (see `0001-positioning.md`): in an AI era the human architect's
scarce resource is **attention**, not coding throughput. So the plugin lets
one architect run N parallel "Consumer" sessions against one "Producer"
session, walk away, and come back to a queue of reviewable PRs — each
carrying a `## Human Verification TODO` checklist. Verifying that checklist
is the architect's remaining job.

- **Two roles:** Producer (the "Manager" — keeps the board healthy, never
  writes code) and Consumer (the "Implementer" — claims one card, delivers
  one PR). The human is the **Architect**.
- **Truth source:** your GitHub Project v2. The plugin owns no parallel
  state store.
- **14 skills** in 3 layers (1 entry → 7 molecular → 6 atomic).
- **3 hooks** (SessionStart, PreToolUse, PostToolUse) + **~20 bash scripts**
  + a Python setup-stages engine.
- **Dual-platform:** Claude Code + Codex CLI (mostly parity; a few CC-only
  features like Mode-2 subagent spawning and the skills/ edit-gate hooks).

---

## 1. Navigation cheatsheet (read this first)

| If you want to… | Read this |
|---|---|
| Understand what the plugin is *for* and what it refuses to do | `docs/architecture/0001-positioning.md` + `README.md` |
| Understand the core nouns (**board**, **card**, **WIP**, **claim**, …) in plain English | §13 below |
| Get the end-user pitch + a "typical day" walkthrough | `README.md` |
| See the canonical spec reading order | `docs/architecture/README.md` |
| Know what skills exist and how they compose | §5 + §6 below; `SKILLS.md` (source of truth) |
| Know what each skill actually does | §6 below (every skill, elaborated) |
| Know what each hook does | §7 below |
| Know what each script does | §9 below (every script, elaborated) |
| Understand how a session routes | §8 below + `skills/using-board-superpowers/SKILL.md` + `hooks/session-start.sh` |
| Understand the board contract (states, actions, projections) | `docs/architecture/0005-contracts/00-kanban-protocol.md` + `skills/board-canon/SKILL.md` |
| Understand autonomy / approval / governance | `docs/architecture/adr/0006-…-autonomy-boundary.md` + `skills/classifying-actions/SKILL.md` |
| Understand the audit log | `docs/architecture/0005-contracts/06-audit-log-schema.md` + `skills/auditing-actions/SKILL.md` + `scripts/audit-log-write.sh` |
| Understand subagents / agent teams / Mode-2 | `MULTI_AGENT_DEVELOPMENT.md` |
| Understand setup / bootstrap / upgrade reconvergence | `SETUP_STAGES_DEVELOPMENT.md` + `skills/bootstrapping-repo/SKILL.md` + `scripts/stages-registry.yml` |
| Understand the Kanban/board layer deeply | `BOARD_DEVELOPMENT.md` |
| Learn how to author or edit a skill | `SKILL_DEVELOPMENT.md` + `skills/AGENTS.md` |
| Learn the design methodology for new skills/surfaces | `FEATURE_DESIGN_METHODOLOGY.md` |
| Understand plugin/hook/script platform contracts | `PLUGIN_DEVELOPMENT.md` |
| Find *why* a specific decision was made | `docs/architecture/adr/<NNNN>-<title>.md` (read in numeric order) |
| Find a bash helper function | `scripts/lib/common.sh` (grep for `bsp_`) |
| See the operational rules for maintainers | `AGENTS.md` (repo root) |

---

## 2. What this repo is

A dual-platform plugin built on three pillars (`README.md` § "The three
pillars"):

1. **Substrate commitment** — truth lives on *your* board (GitHub Project
   today; Linear/Jira via the Kanban Protocol tomorrow). Never a hosted
   backend, DB, or web UI.
2. **Methodology embedded as code** — INVEST every card, vertical slices,
   pull-based work, one-PR-per-session, soft WIP, XS/S/M/L sizing, retro
   from PR notes. No sprint, no story points, no velocity, no standup.
3. **Composition is permanent** — never reimplements TDD/QA/review/
   brainstorming/security; those belong to `superpowers` and `gstack`.
   `board-superpowers` only *schedules* them into routines.

**What it explicitly does NOT do** (`0001-positioning.md` § Non-goals):
no backend/DB/web UI; no reimplementation of upstream disciplines; no CI
replacement; no story points/velocity/per-architect KPIs; no agent
self-merging PRs (humans merge); no hosted install; no methodology-extension
marketplace; no cross-team/fleet view at v1.

---

## 3. Repo layout map

```
board-superpowers/
├── .claude-plugin/plugin.json        # CC plugin manifest (v0.7.0)
├── .codex-plugin/plugin.json         # Codex CLI plugin manifest (v0.7.0)
├── AGENTS.md                         # maintainer guide (operational; @-includes SKILLS.md)
├── CLAUDE.md                         # one-line shim → AGENTS.md (so CC auto-loads it)
├── SKILLS.md                         # SOURCE OF TRUTH for the 14-skill topology
├── README.md / README.zh-CN.md       # end-user overview (EN + 简体中文)
├── PLUGIN_DEVELOPMENT.md             # platform contracts: hooks, bash, manifest, CC+Codex
├── MULTI_AGENT_DEVELOPMENT.md        # subagent / agent-team / Mode-2 contracts (CC ↔ Codex)
├── SKILL_DEVELOPMENT.md              # how to author a skill (frontmatter, skeletons, anti-patterns)
├── SETUP_STAGES_DEVELOPMENT.md       # the setup-stages system (registry, lifecycle, config items)
├── BOARD_DEVELOPMENT.md              # the Kanban/board layer (protocol, projections, lifecycle)
├── FEATURE_DESIGN_METHODOLOGY.md     # how to decide what becomes a SKILL (3-stage derivation)
├── docs/
│   ├── architecture/                 # ★ the SPEC — single source of truth
│   │   ├── 0001-positioning.md       # what we're for / not for
│   │   ├── 0002-product-features-and-flows/   # features + user flows (per-section files)
│   │   ├── 0003-domain-model/        # ubiquitous language, bounded contexts, aggregates, events
│   │   ├── 0004-component-architecture.md     # how hooks/scripts/skills compose
│   │   ├── 0005-contracts/           # every cross-component contract (kanban, scripts, hooks, …)
│   │   ├── 0006-failure-modes.md     # known failure modes + recovery
│   │   ├── 0007-observability.md     # runtime health surfaces
│   │   ├── 0008-test-architecture.md # what's tested at which layer
│   │   └── adr/                       # 28 decision records (0001..0028), read in order
│   └── agent-team-adaptation/        # ← THIS directory (your adaptation notes; not spec)
├── skills/                           # the agent's action system — 14 SKILLs (see §5–§6)
│   └── <name>/{SKILL.md, references/*.md, .skill-meta.yaml}
├── scripts/                          # bash tooling + Python stage executors (see §9)
│   ├── lib/common.sh                 # the mega-library (all bsp_* helpers)
│   ├── stages_lib/                   # 54 Python files: 22 stage executors + helpers + tests
│   ├── stages-registry.yml           # 22 setup stages across 10 modules (M1–M10)
│   └── *.sh                          # ~20 bash scripts (claim/create/transition/audit/…)
├── hooks/                            # hooks.json + session-start/pre-tool-use/post-tool-use.sh (see §7)
└── tests/                            # ~50 hermetic shell tests (unit + e2e); integration gated
```

A few non-obvious facts:
- `CLAUDE.md` and every nested `CLAUDE.md` are **one-line shims** that
  `@`-include the sibling `AGENTS.md`. Edit the `AGENTS.md`, never the shim.
- The six companion docs at the root (`PLUGIN_DEVELOPMENT.md`, etc.) are
  **referenced by name, not `@`-prefixed**, so they don't ride into every
  session. Open them on demand with `Read`.
- `SKILLS.md` is `@`-included from `AGENTS.md`, so it **does** ride into
  every session as standing context — it is the always-loaded skill catalog.

---

## 4. The spec reading order (canonical)

From `docs/architecture/README.md`. Read in this order; each later doc hangs
off the earlier ones.

1. `0001-positioning.md` — what we're for, who we're for, what we're not.
2. `0002-product-features-and-flows/` — feature catalog + user journeys.
3. `0003-domain-model/` — entities, bounded contexts, aggregates, events, invariants.
4. `0004-component-architecture.md` — how surfaces (hooks/scripts/skills/external plugins) compose.
5. `0005-contracts/` — every cross-component contract, pinned + versioned.
6. `0006-failure-modes.md` — known failure modes, signals, recovery, ownership.
7. `0007-observability.md` — how a maintainer knows the plugin is healthy.
8. `0008-test-architecture.md` — what's tested at which layer, and why some layers have no tests yet.
9. `adr/` — the decision records that defined the shape (numeric order).

Governance rule: architecture changes land **before** the implementation
that depends on them (ADR → spec doc → code). ADRs are immutable once
accepted; superseding creates a new ADR and marks the old one
`superseded by ADR-N`.

---

## 5. The skills system — 14 skills, 3 layers (overview)

`SKILLS.md` is the **source of truth**. Any change under `skills/` MUST be
paired with a `SKILLS.md` change in the same PR.

| Skill | Layer | One-line role |
|---|---|---|
| `using-board-superpowers` | Entry | Manual page + first-touch router; routes by user signal or hook `INVOKE:` marker |
| `briefing-daily` | Molecular | Producer daily orientation: board read, WIP, stale claims, next action |
| `intaking-requirement` | Molecular | Producer intake: acknowledge → shape-judge → spec-first → route/create card |
| `reviewing-pr-queue` | Molecular | Producer PR review queue: validate via enforcing-pr-contract, comment, transition |
| `triaging-board` | Molecular | Producer triage: Blocked remediation + stale-claim release |
| `consuming-card` | Molecular | Consumer one-card-to-PR lifecycle (23 nodes: F1–F4 + B1–B5 + G1–G4 + C1–C4) |
| `decomposing-into-milestones` | Molecular | INVEST + vertical-slicing engine; turns a design artifact into Ready cards |
| `bootstrapping-repo` | Molecular | Sole executor for the 22 setup-stages (first-time + upgrade reconvergence) |
| `board-canon` | Atomic | Read-only contract: 6-state machine + Card body schema + branch naming + WIP formula |
| `enforcing-pr-contract` | Atomic | PR three-section contract (A) + AC terminal-state sync (B) + auto-close keyword (C) |
| `operating-kanban` | Atomic | 8-action Kanban Protocol dispatch over the active projection (Form A/B/C) |
| `classifying-actions` | Atomic | D-AUTONOMY-1 matrix + 5-step triage + override merge → A/R/N decision |
| `auditing-actions` | Atomic | Audit schema + two-entry rule + BYO-RDBMS write + jsonl degradation |
| `composing-siblings` | Atomic | Sibling-plugin (`gstack:*`/`superpowers:*`) invocation discipline + Mode-2 check |

**Layering rule (strict downward dependency):**

```
Entry ──routes to──> Molecular ──reads from──> Atomic
Atomic skills are reflexes — they MUST NOT call any same-plugin skill.
```

- **Entry** (1): router only, never does real work, loaded every session.
- **Molecular** (7): business workflows, state-machine-shaped.
- **Atomic** (6): single-purpose reflexes reused by many molecular skills.

The three-check layer assignment: (1) does it route or work? (2) does it
have domain/business semantics? (3) does it depend on no other same-plugin
skill? A skill spanning two layers MUST be split.

Per-skill `layer` / `type` / `mode` / `bounded-context` live in a sibling
`.skill-meta.yaml` file next to each `SKILL.md` (deliberately **not** in
frontmatter — frontmatter Tier 3 forbids these). CI gate
`scripts/verify-skill-metadata.sh` enforces that the yaml agrees with the
`SKILLS.md` catalog. These four fields are the skill's **taxonomic position**;
here's what each one means (schema per `SKILL_DEVELOPMENT.md` §
"board-superpowers metadata convention"):

| Field | Allowed values | Meaning |
|---|---|---|
| **`layer`** | `entry` / `molecular` / `atomic` | Position in the skill graph (see the layering rule above). Determines the **body-length budget** (entry ≤ 200, molecular 250–450, atomic 200–300 lines) **and what the skill is allowed to depend on** — atomic skills must not call any same-plugin skill; dependency direction is strictly Entry → Molecular → Atomic. |
| **`type`** | `technique` / `pattern` / `reference` / `discipline` | The skill's *shape*, which drives the **body skeleton + testing regime**. `pattern` → Skeleton A (e.g. `decomposing-into-milestones`); `reference` → Skeleton B (e.g. `board-canon`); `technique` (pipeline) → Skeleton C; `discipline` → pressure-test regime (refusal conditions, not procedure steps — e.g. INVEST checks). |
| **`mode`** | `claude-code-only` / `codex-only` / `both` | **Platform compatibility.** Determines which frontmatter fields are safe to use and whether the body may name CC-only tools directly (e.g. `Agent`, `SendMessage`, `EnterWorktree`). `both` means the body stays platform-portable. (All 14 v1 skills are `both` — dual-platform parity is load-bearing.) |
| **`bounded-context`** | `board` / `session` / `bootstrap` / `audit` / `spec` | The DDD bounded context the skill **primarily** acts on (per `0003-domain-model/02-bounded-contexts.md`): **board** = Card/PR aggregates + GitHub Project; **session** = Producer/Consumer aggregates + OS processes/worktrees; **bootstrap** = host/repo setup; **audit** = the audit trail; **spec** = the spec pointer. A skill may *touch* several contexts (see the "Bounded-context → skill mapping" in `SKILLS.md`), but the yaml holds its **primary** one. |

Concrete examples (from the actual `.skill-meta.yaml` files):

| Skill | `layer` | `type` | `mode` | `bounded-context` |
|---|---|---|---|---|
| `using-board-superpowers` | entry | pattern | both | spec |
| `consuming-card` | molecular | pattern | both | session |
| `board-canon` | atomic | reference | both | board |

So a phrase like "an atomic, reference-type, both-mode, board-context skill"
decodes to **`board-canon`**: a single-purpose reflex (atomic), shaped as a
read-only contract (reference), portable across CC + Codex (both), acting on
the Board context. The four fields together tell you the skill's graph
position, body shape, platform reach, and domain home in one line.

**Simplified call graph:**

```
using-board-superpowers (entry)
  ├─> briefing-daily ──────────────┐
  ├─> intaking-requirement ────────┤
  ├─> reviewing-pr-queue ──────────┼─> (atomics) board-canon, operating-kanban,
  ├─> triaging-board ──────────────┤     classifying-actions, auditing-actions,
  ├─> consuming-card ──────────────┤     enforcing-pr-contract, composing-siblings
  ├─> decomposing-into-milestones ─┤
  └─> bootstrapping-repo ──────────┘
        │
        └─> (cross-plugin, via composing-siblings) gstack:/* + superpowers:*
```

---

## 6. The 14 skills — what each one does

Each skill lives at `skills/<name>/SKILL.md` with a `references/` subfolder
for progressive-disclosure detail and a `.skill-meta.yaml` for machine
metadata. Below: what each skill is, when it fires, what it does, and what
it composes.

### Entry layer (1)

#### `using-board-superpowers` — manual page + first-touch router
- **What:** The only entry skill. Loaded every session. Provides full
  plugin orientation inline (14-skill catalog, 6-state Card lifecycle, 5
  bounded contexts, on-disk state, routing tree) AND routes ambiguous
  sessions or hook-injected `INVOKE:` markers to the right molecular skill.
- **When it fires:** On first message in any board-superpowers session, or
  when the user asks "what is this plugin / how does this work / what skills
  exist / explain the architecture", or on a `SessionStart`-injected
  `INVOKE:` marker.
- **What it does:** Runs a 3-step reliable gate (dep check → state probe →
  marker consumption) — because CC `SessionStart` delivery is unreliable,
  the entry skill re-do the state check itself. Then routes: `[board-card:#N]`
  → `consuming-card`; "morning briefing"/"what should I work on" →
  `briefing-daily`; "new requirement" → `intaking-requirement`; "review the
  PRs" → `reviewing-pr-queue`; "what's blocked" → `triaging-board`;
  "set up board-superpowers" / `INVOKE: bootstrapping-repo` →
  `bootstrapping-repo`.
- **Composes:** every molecular skill (downward only). Body ~225 lines
  (intentionally over the 200-line entry budget because it doubles as the
  manual page).

### Molecular layer (7)

#### `briefing-daily` — Producer daily-briefing routine
- **What:** Reads the board, groups cards by Status, flags WIP situations
  and stale claims, recommends ONE next action.
- **When:** "morning briefing" / "what should I work on" / "today's plan" /
  "board overview".
- **Does:** Calls `operating-kanban` `read_board`, applies the `board-canon`
  WIP formula (`In Progress + suspended + In Review`; Blocked excluded),
  detects stale claims, produces a hot-card dispatch recommendation.
  Read-only — records a read-only audit marker via `auditing-actions`.
- **Composes:** `board-canon`, `operating-kanban` (read_board),
  `composing-siblings`, `classifying-actions` + `auditing-actions`.
- **Covers journey nodes** A1–A5 (board overview, ordered PR queue, "what's
  blocking me", context-switch reload, today's dispatch).
- **Reference:** `references/daily-detail.md` (empty-board case, stale-claim
  age computation, hot-card formatting, tone).

#### `intaking-requirement` — Producer intake routine
- **What:** Acknowledges an incoming requirement and runs a 4-step pipeline:
  acknowledge → shape judgment → spec-first check → route/create card.
- **When:** "new requirement" / "intake this idea" / "I have a feature" /
  "add a card".
- **Does:** Shape judgment is a 4-row table (cross-release / milestone-
  grouped / multi-card / single-card). Spec-first check is a 6-row table
  touching bounded contexts / ADRs / schemas. Routes pre-card design to
  `gstack:/office-hours`, `gstack:/plan-ceo-review`, `superpowers:brainstorming`;
  plan synthesis to `superpowers:writing-plans`; multi-card decomposition to
  `decomposing-into-milestones`. Direct single-card creation uses
  `operating-kanban` `create_card`.
- **Composes:** `board-canon`, `operating-kanban` (create_card),
  `composing-siblings`, `classifying-actions` + `auditing-actions`.
- **Covers** B1 (design conversation routing) + B3 (single-card fast-path) +
  G4 (the intake → decompose bridge cannot be skipped).
- **References:** `intake-decision-tree.md`, `scope-shape-judgment.md`,
  `spec-first-checklist.md` (the intake-routing trio).

#### `reviewing-pr-queue` — Producer review-queue routine
- **What:** Lists open PRs linked to cards, validates each against the
  three-section PR contract, comments on violations, transitions
  non-compliant cards back to `In Progress`, summarizes the queue.
- **When:** "review the PRs" / "what's in In Review" / "merge ready".
- **Does:** For each open PR, runs `enforcing-pr-contract` (Contract A PR
  body shape + Contract B AC terminal-state + Contract C auto-close
  keyword); on violation, comments on the PR and uses `operating-kanban`
  `transition_card` to flip the card back to `In Progress`.
- **Composes:** `board-canon` (state machine), `operating-kanban`
  (transition_card), `enforcing-pr-contract`, `composing-siblings`,
  `classifying-actions` + `auditing-actions`.
- **Covers** C1 (review PR) + C2 (return to In Progress).
- **Reference:** `review-queue-detail.md` (merge-conflict handling,
  multi-card PRs, self-review, approve-vs-request-changes, non-claim branch
  edge cases).

#### `triaging-board` — Producer triage routine
- **What:** Scans `Blocked` cards with 3-class blocker remediation
  (external-dependency / decision-pending / stale-block) and releases stale
  claim branches (>72h flag; >7 days release recommendation).
- **When:** "what's blocked" / "triage the board" / "release stale claims".
- **Does:** `operating-kanban` `read_board` with status filter `Blocked`;
  classifies each blocker and recommends remediation; for stale claims uses
  `operating-kanban` `release_claim` (cancellation) and `transition_card`
  (Blocked → In Progress unblock).
- **Composes:** `board-canon` (Blocked semantics), `operating-kanban`
  (read_board / release_claim / transition_card), `composing-siblings`,
  `classifying-actions` + `auditing-actions`.
- **Covers** C4 (unblock blocked card) + C5 (cancel stale claim).
- **Reference:** `triage-detail.md` (blocker classification, stale-claim
  release procedure, suspended-card review schedule).

#### `consuming-card` — Consumer session main skill (Shape X, 23 nodes)
- **What:** The Consumer's one-card-to-PR mega-routine, hosting all 23
  lifecycle journey nodes:
  - **F1–F4 stage frame:** claim / implement / verify / submit-PR.
  - **B1–B5 bootstrap inline:** plan synthesis / TDD / refusal reflexes.
  - **G1–G4 governance:** audit / R-class propose-await / A-class gate /
    mode topology.
  - **C1–C4 composing-siblings handoffs:** planning / TDD implementation /
    verification chain / conditional QA + security.
- **When:** `[board-card:#N]` / "claim card N" / "work on card N" /
  "implement card N".
- **Does:** F1 claim via `scripts/claim-card.sh` (atomic git-push-lease
  lock); F2 implement via `superpowers:subagent-driven-development` /
  `superpowers:test-driven-development`; F3 verify via
  `superpowers:verification-before-completion` → `gstack:/review` →
  `superpowers:requesting-code-review`, conditional `gstack:/qa` (UI) +
  `gstack:/cso` (security); F4 submit via `scripts/submit-pr.sh` (3-section
  PR + `Closes #N` trailer); post-merge cleanup via
  `scripts/post-merge-cleanup.sh`. Consumer `action_id`s 100–113 (review
  cycle 100–111 + PR-submit pre-flight 112 + post-merge cleanup 113).
- **Modes:** Mode-1 (architect-spawned interactive terminal — works on CC
  **and** Codex) vs Mode-2 (Producer-spawned CC subagent — CC-only at v1,
  `max_depth=1` so it cannot spawn further subagents; every sibling
  invocation MUST be procedural).
- **Composes:** all 6 atomics + the cross-plugin set above.
- **References:** `stage-1-claim`, `stage-2-implement`, `stage-3-verify`,
  `stage-4-submit`, `post-merge-cleanup`, `migration-fc0-to-23-nodes.md`.

#### `decomposing-into-milestones` — INVEST + vertical-slicing engine
- **What:** Turns a design artifact (brainstorming output, eng-review
  notes, requirements doc) into INVEST-compliant, vertically-sliced Ready
  cards on the board. Skeleton A — *Discipline* — because INVEST and
  vertical-slicing are **refusal conditions** (Wake 2003), not procedure steps.
- **When:** "decompose this feature" / "split into cards" / "break this
  into milestones" / "拆成卡" / intake-handoff.
- **Does:** Step 1 dispatches by argument type (file / dir / freeform
  stdin). Then enforces INVEST + vertical slicing + the Card body schema +
  XS/S/M/L sizing; refuses cards that fail the checks. Creates cards via
  `operating-kanban` `create_card` + `transition_card`.
- **Composes:** `board-canon` (terminal Card body schema authority),
  `operating-kanban` (create_card + transition_card), `classifying-actions`,
  `auditing-actions`. Cross-plugin: `superpowers:writing-plans`,
  `gstack:/plan-eng-review`.
- **References:** `card-schema`, `decomposition-patterns`, `invest-checklist`,
  `size-calibration` (primary-source-grounded: Wake 2003 INVEST, Cohn SPIDR,
  Reinertsen Little's Law, Fowler StoryCounting).

#### `bootstrapping-repo` — sole executor for the 22 setup-stages
- **What:** Drives first-time setup **and** plugin-upgrade reconvergence
  (per ADR-0012; absorbs the former `migrating-repo-version` scope —
  version-transition migrations are `generation:` bumps within stages).
- **When:** `INVOKE: bootstrapping-repo` marker (from `SessionStart` when
  any stage is `never-run` or `stale`) or the architect saying "set up
  board-superpowers" / "bootstrap this repo".
- **Does:** Loads `scripts/stages-registry.yml` → calls
  `stages_lib._lifecycle.evaluate_all_stages()` (topological sort + per-
  stage lifecycle diff) → executes each stage by character: **automated**
  stages via `uv run python3 -c "from stages_lib import <module>;
  <module>.executor(...)"`; **agentic** stages by surfacing a prompt,
  waiting, validating, persisting. Bumping a stage's `generation` marks it
  `drifted` → re-run on upgrade. Bootstrap `action_id`s 200–208; outbox-
  shaped `--mode bootstrap-pending` audit rows.
- **Composes:** `board-canon` (read schema invariants), `classifying-actions`
  + `auditing-actions`. Board reads route through `operating-kanban`
  (ADR-0027).
- **References:** `intro`, `first-time-user-guide`, `stage-execution-flow`,
  `config-item-protocol`, `architect-ux-failure-surfaces`, `changelog/v0.2.0`.

### Atomic layer (6) — reflexes; `user-invocable: false`; call nothing in-plugin

#### `board-canon` — read-only contract (the "what is legal" SPOT)
- **What:** The canonical, backend-agnostic contract every other skill
  consults before touching the board. Contains: the **6-state machine**
  with an explicit legal/illegal transition table; the **Card body schema**
  (thin-pointer Spec/Owner/Estimate + 5 sections Goal/AC/Out-of-scope/
  Dependencies/Notes + bottom audit-trail marker + optional Execution
  Hints + auto-prepended creator-trace marker); the **claim protocol**
  (the branch push IS the claim signal — atomic, conflict-detectable,
  cheap to undo); the **WIP formula** (`In Progress + suspended + In
  Review`; Blocked excluded); **branch naming**
  (`claim/<kanban-id>-<key-slug>-<title-slug>`; v0.4.x legacy accepted).
- **Called by:** all 7 molecular skills.
- **References:** `state-machine`, `card-body-schema`, `claim-protocol`,
  `wip-counting`, `branch-naming`.

#### `enforcing-pr-contract` — PR contract (the "what a compliant PR looks like" SPOT)
- **What:** Two-contract enforcement. **Contract A** — PR body three-section
  shape: `## Automated Verification` (required, non-empty), `## Human
  Verification TODO` (optional but never filler), `## Retro Notes`
  (required when reusable lessons exist). **Contract B** — card body AC
  sync: every acceptance criterion must be `[x]` or `[!]` (with reason) at
  PR-submit time; bare `[ ]` is forbidden. **Contract C** — the
  `Closes #<card>` auto-close keyword. Provides injection templates for the
  Consumer (Step 10) + validation rules for the Producer (review-queue).
- **Called by:** `consuming-card` (Step 9.5 + Step 10) +
  `reviewing-pr-queue` (violation flagging). Also checked by
  `scripts/submit-pr.sh`.
- **References:** `section-templates`, `validation-rules`, `filler-detection`.

#### `operating-kanban` — backend-projection dispatch (the "how to act on this backend" SPOT)
- **What:** Owns the 8 Kanban Protocol actions (`read_board`, `read_card`,
  `create_card`, `transition_card`, `claim_card`, `release_claim`,
  `link_pr_to_card`, `comment_on_card` OPTIONAL). Reads
  `<repo>/.board-superpowers/settings.yml § modules.m10_kanban` to resolve
  the **active projection**, loads the per-projection reference file under
  its own `references/`, and dispatches per **Form A** (bash CLI — v1
  GitHubProjectAdapter), **Form B** (plugin-shipped MCP server — future
  Linear/Jira), or **Form C** (REST/GraphQL — reserved). Also owns the
  bootstrap-side **setup-capability registry** that M3 stage predicates
  consume (ADR-0027).
- **Called by:** all 7 molecular skills that touch the board.
- **Distinct from `board-canon`:** `board-canon` owns "what is legal"
  (backend-agnostic, stable); `operating-kanban` owns "how to act" on the
  active backend (mutates as new projections land).
- **References:** `action-dispatch`, `backend-selection`, `form-a-bash`,
  `form-b-mcp`, `form-c-rest`, `failure-mode-dispatch`, `github-project-v2`
  (+ future `linear.md` / `jira.md`).

#### `classifying-actions` — autonomy classifier (the "A/R/N decision" SPOT)
- **What:** The D-AUTONOMY-1 matrix + 5-step triage rule + `autonomy_overrides`
  parsing. The caller hands in an `action_id`; this skill returns **A**
  (auto-execute), **R** (propose-and-await-approval), or **N** (never).
- **Matrix:** 14 Producer rows + 14 Consumer rows (`action_id` 100–113) +
  9 Bootstrap rows (`action_id` 200–208).
- **5-step triage:** architect reserved power → R; source-of-truth edit →
  R; interrupts in-flight work → R; cross-card structural → R; else A.
- **Overrides:** `autonomy_overrides:` at user (`~/.board-superpowers/
  overrides.yml`) + project (`<repo>/.board-superpowers/config.local.yml`)
  layers, merged by `bsp_resolve_autonomy_class` (project wins) — promotes
  R → A as trust grows.
- **Called by:** all 7 mutating molecular skills, immediately before
  `auditing-actions`.
- **References:** `matrix`, `triage-rule`, `override-parsing`,
  `action-id-catalog`. Body ~81 lines.

#### `auditing-actions` — audit writer (the "record what you did" SPOT)
- **What:** The audit-log schema (8 columns + 4 enum sets) + the **R-class
  two-entry rule** (propose + resolve) + BYO-RDBMS write conventions +
  **degradation mode** (when the DB is unavailable, every A-class action
  degrades to R-class with a jsonl fallback; the `mode` field records the
  degradation cause).
- **Called by:** all 7 mutating molecular skills, immediately after
  `classifying-actions` returns A or R.
- **Calls (external):** `${CLAUDE_PLUGIN_ROOT}/scripts/audit-log-write.sh`.
- **References:** `schema`, `two-entry-rule`, `db-write-conventions`,
  `degradation-mode`. Body ~84 lines.

#### `composing-siblings` — sibling-plugin invocation discipline (the "how to invoke gstack/superpowers" SPOT)
- **What:** Consolidates the rules for invoking `gstack:*` / `superpowers:*`
  skills correctly: (a) **SKILL invocation = in-process content loading,
  NOT subagent spawn** (ADR-0008); (b) **Mode-2 `max_depth=1`
  compatibility** — a procedural-vs-subagent decision tree for every
  composed sibling; (c) **per-phase routing** (gstack = bookends:
  direction + delivery verification; superpowers = middle: the TDD loop);
  (d) the **`<plugin>:<skill>` namespace prefix** rule (cross-platform,
  prevents bare-reference ambiguity).
- **Called by:** all 4 Producer routines + `consuming-card` (all 5 Consumer
  handoff points) + `decomposing-into-milestones`.
- **References:** `handoff-points` (9-row caller × scenario table),
  `sibling-plugin-table`, `procedural-fallback-rules`, `boundary`.
- **Body ~101 lines.** *(For your adaptation: this is the skill that becomes
  mostly moot if you drop superpowers + gstack — see `00-goal.md` v0.6.)*

---

## 7. The hooks — what each one does

Hooks live in `hooks/` and are registered by `hooks/hooks.json`. CC
auto-discovers `hooks.json` at install time; Codex requires running
`scripts/register-codex-hooks.sh` once (and that script registers **only**
`SessionStart`, because Codex has no `Skill` tool for `PostToolUse` to
observe — see the Codex parity gap below).

### `hooks/hooks.json` — the registration
Registers three events:
- **`SessionStart`** (matcher `startup`, timeout 10s) → `session-start.sh`
- **`PreToolUse`** (matchers `Edit` / `Write` / `MultiEdit`, timeout 5s) → `pre-tool-use.sh`
- **`PostToolUse`** (matcher `Skill`, timeout 5s) → `post-tool-use.sh`

### `hooks/session-start.sh` (~463 lines) — the intent-injecting boot hook
- **What:** Runs on every session start. **Self-contained** (intentionally
  does NOT source `common.sh`; duplicates `normalize_repo_path`,
  `sanitize_dep_name`, `sanitize_reason_line`, `primary_repo_root` inline
  so a broken lib can't derail boot). Three layers:
  1. **Dep check** via `scripts/check-deps.sh --machine` → `MISSING=`,
     `ROUTING_INJECTED=`, `PROJECT=` lines.
  2. **Lifecycle diff / intent injection** — if the per-repo venv is
     absent, falls back to a v0.4.x file-presence heuristic (host-shared +
     repo-shared `settings.yml` both absent → emit `INVOKE: bootstrapping-repo`);
     if the venv is present, runs
     `PYTHONPATH=<plugin>/scripts python3 -m stages_lib lifecycle-probe …`
     which returns the two-line marker
     (`INVOKE: <skill>` / `REASON: <one-line>`) or empty.
  3. **Audit outbox observer** — if
     `~/.board-superpowers/audit-pending.sentinel` exists, surfaces
     "audit-pending: outbox has unflushed rows".
- **Output:** emits
  `{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":<joined>}}`
  via `json.dumps`.
- **Exit:** **always 0** — advisory, never blocks. This hook does not *do*
  things; it hands the session a routing hint (the `INVOKE:` marker) the
  entry skill fast-paths on.

### `hooks/pre-tool-use.sh` (~121 lines) — the skills/ edit gate (CC-only)
- **What:** Enforces the doctrine "don't edit `skills/` without going
  through the `skill-creator` entry skill" (AGENTS.md doctrine #4).
  Self-contained. Reads the JSON payload from stdin (`session_id`,
  `tool_name`, `tool_input.file_path`). Only gates `Edit`/`Write`/`MultiEdit`
  on paths matching `*/skills/*` or `skills/*`. Checks for a flag file at
  `${TMPDIR:-/tmp}/board-superpowers-sessions/<session_id>/skill-creator-invoked.flag`.
  If the flag is **absent** → emits
  `{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny",…}}`
  on stdout AND legacy `exit 2` + stderr reason. Fails **open** on internal
  error (so a buggy hook can't lock you out of `skills/`).

### `hooks/post-tool-use.sh` (~79 lines) — the gate's matching half (CC-only)
- **What:** On a `Skill` tool invocation, scans every string value in
  `tool_input` for one ending in `skill-creator`; on match, **writes** the
  `skill-creator-invoked.flag` file for that session. Always exits 0.
- **Why:** This is the matching half of the Process gate — it records that
  `skill-creator` was invoked so `pre-tool-use.sh` will allow subsequent
  `skills/` edits in the same session.

> **Codex parity gap:** Codex CLI has no `Skill` tool, so `PostToolUse`
> can't observe skill invocations and the flag-file lifecycle can't
> complete. Therefore `register-codex-hooks.sh` registers **only**
> `SessionStart` on Codex; the Process gate stays doctrine-only (the
> "⛔ STOP" block in `skills/AGENTS.md`) on Codex. CC users get tool-level
> enforcement via `hooks.json`.

---

## 8. How a session actually flows

### 8.1 The boot path (every session)

1. **`SessionStart` hook fires** → `hooks/session-start.sh` runs its three
   layers (dep check → lifecycle diff/`INVOKE:` marker → audit outbox
   observer) and emits `additionalContext`. Always exits 0.
2. **Entry skill `using-board-superpowers` auto-matches** on the user's
   first message (or the injected `INVOKE:` marker). Runs its 3-step
   reliable gate (dep check → state probe → marker consumption). Then routes.
3. A **molecular skill** runs the workflow, calling **atomic skills** for
   contracts and **sibling plugins** (`gstack:*`/`superpowers:*`) for real
   disciplines, via `composing-siblings`.
4. **Every mutating action** goes through `classifying-actions` (A/R/N
   decision) then `auditing-actions` (`scripts/audit-log-write.sh`).

CC auto-discovers `hooks/hooks.json`; Codex requires running
`scripts/register-codex-hooks.sh --install-user` once after install.

### 8.2 Trace A — "what should I work on?"

`using-board-superpowers` routes the phrase → **`briefing-daily`** → reads
the board via `operating-kanban` `read_board` → applies the `board-canon`
WIP formula → flags stale claims → recommends ONE next action → records a
read-only audit marker via `auditing-actions`.

### 8.3 Trace B — "[board-card:#42]"

`using-board-superpowers` routes on the literal token → **`consuming-card`**
(Shape X, 23 nodes):
- **F1 claim:** `scripts/claim-card.sh` — 4-step atomic transaction:
  (1) `gh project item-edit` flips Status → `In Progress`; (2) `git fetch`;
  (3) `git worktree add` a `claim/<N>-<slug>` branch; (4) `git push -u`.
  The push is the distributed lock (ADR-0002); first push wins.
- **F2 implement:** delegates TDD to `superpowers:subagent-driven-development`
  / `superpowers:test-driven-development` (via `composing-siblings`).
- **F3 verify:** `superpowers:verification-before-completion` →
  `gstack:/review` → `superpowers:requesting-code-review`; conditional
  `gstack:/qa` (UI cards) and `gstack:/cso` (security-flagged cards).
- **F4 submit:** `scripts/submit-pr.sh` builds the 3-section PR body +
  `Closes #42` trailer + `<!-- board-superpowers:pr -->` marker.
- Architect verifies the `## Human Verification TODO`, merges (humans merge;
  agents never self-merge — ADR-0006 row 12 = N).
- **Post-merge cleanup:** `scripts/post-merge-cleanup.sh` removes the
  worktree + branch; card → `Done`.

Every status flip / claim / PR link is A-or-R classified and audit-logged.

---

## 9. The scripts — what each one does

All scripts live under `scripts/`. **Cross-script conventions** (from
`docs/architecture/0005-contracts/01-script-contracts.md`): every script
begins `set -euo pipefail` and sources `lib/common.sh` (except `check-deps.sh`,
which is deliberately self-contained); the leading `# …` header comment is
the `--help` text; universal exit codes `0` success / `1` op-failure / `2`
bad args / `3` runtime cmd missing; `gh` JSON output is piped to `python3`
with identifiers passed via env vars (never string-interpolated); plugin
paths use `${CLAUDE_PLUGIN_ROOT}`.

### 9.1 The shared library

#### `scripts/lib/common.sh` (~2042 lines — the mega-library)
Not directly executable; callers `set -euo pipefail` then source it. All
helpers are prefixed `bsp_`. Key functions:

| Function | What it does |
|---|---|
| `bsp_plugin_root` | Resolves `${CLAUDE_PLUGIN_ROOT}` or derives from `BASH_SOURCE` (Codex fallback) |
| `bsp_normalize_repo_path` | `/Users/foo/bar` → `Users-foo-bar` (keys per-repo state) |
| `bsp_primary_repo_root` | Worktree-safe primary repo root via `git rev-parse --git-common-dir` |
| `bsp_ensure_venv` | Self-healing per-repo Python venv at `<repo>/.board-superpowers/.venv/` (uv-managed) |
| `bsp_inject_routing_block` | Marker-pair injection into `CLAUDE.md`/`AGENTS.md` with BOM/CRLF normalization + SHA256 |
| `bsp_resolve_active_projection` | Reads `settings.yml § modules.m10_kanban` to pick the active Kanban projection (awk-based, no PyYAML) |
| `bsp_resolve_autonomy_class` | ADR-0006 matrix defaults + user/project `autonomy_overrides` merge (project wins) |
| `bsp_resolve_audit_db_url` | Resolves the audit DB URL (env > `credentials.yml`) |
| `bsp_audit_local_write` | jsonl fallback audit writer with the `mode`-field enum |
| `bsp_stage_state_set/get` | Setup-stage lifecycle state persistence into `settings.yml` |
| `bsp_render_creator_trace_block` | Emits the creator-trace marker (platform + session-id) |
| `bsp_log` / `bsp_die` / `bsp_require_cmd` / `bsp_parse_owner_number` / `bsp_sanitize_slug` / `bsp_show_help` | Logging / fatal / command-presence / arg-parsing / slug / help helpers |

#### `scripts/lib/audit-schema.{sqlite,postgres,mysql}.sql`
The DDL for the audit log table per DB scheme (the 6-scheme allowlist per
ADR-0009). Applied by `audit-init.sh`.

### 9.2 Board-mutating scripts (the v1 GitHubProjectAdapter Form A projection)

Per ADR-0025, these four are the v1 **GitHubProjectAdapter projection's**
Form A (bash CLI) implementation — they call `gh` directly. Future backends
(Linear/Jira) ship their own Form A or skip to Form B/C.

#### `scripts/claim-card.sh` (~131 lines) — the atomic Consumer claim
- **What:** (a) Distributed lock via `git push --force-with-lease=<ref>:` on
  a `claim/<N>-<slug>` branch + (b) filesystem isolation via a dedicated
  worktree. Both succeed atomically or both clean up on failure.
- **4-step transaction:** (1) `gh project item-edit` Status → `In Progress`;
  (2) `git fetch origin`; (3) `git worktree add <path> -b claim/<N>-<slug>
  origin/<base>`; (4) `git push --force-with-lease … --set-upstream` (the
  atomic lock step). Also writes a `.board-superpowers/claims/<N>.claim`
  marker file.
- **Stdout (success):** exactly two lines — `branch=<name>` then
  `worktree=<path>` (structured contract `consuming-card` parses).
- **Exit codes (pinned by ADR-0002):** `0` claimed; `10` race-lost (MUST
  stop, never retry — surface who won); `20` git/network error; `30` bad
  args / missing `git`.
- **Worktree path resolution:** 3-priority — `$BOARD_SP_WORKTREE_DIR` →
  `<primary>/.worktrees/` (if gitignored) →
  `$HOME/.config/superpowers/worktrees/<project>/`.

#### `scripts/create-card.sh` — create a card on the board
- **What:** Create a GitHub Issue with the standard body and add it to the
  configured GitHub Project, in one shot.
- **Args:** `--title`, `--body-file`, `--project OWNER/NUMBER`, optional
  `--repo`, repeatable `--label`.
- **Stdout:** a bare issue number (the calling skill composes follow-ups
  like `transition-card.sh --issue $N`).
- **Exit:** `0` created+linked; `1` issue created but failed to add to
  project (prints a manual `gh project item-add` fix-forward command);
  `2` bad args; `3` `gh` unavailable.
- **Why two-step:** `gh issue create --project` expects a project *title*,
  not OWNER/NUMBER, so `gh issue create` then `gh project item-add` is
  canonical.

#### `scripts/transition-card.sh` — move a card to a new Status
- **What:** Resolve the project + issue + Status-field option to backend
  IDs, then `gh project item-edit --single-select-option-id` to mutate the
  column. Used by both Producer and Consumer.
- **Args:** `--issue`, `--project OWNER/NUMBER`, `--to <Status>` (one of
  the six canonical names, case-insensitive), optional `--repo`.
- **Stdout:** `moved issue #<N> to <Status>` (human-readable).
- **Security:** identifiers (`ISSUE_NUM`, `REPO_FULL`, `TO_STATUS`) are
  passed to the embedded `python3` filter via env vars, never
  string-interpolated — closes a CVE-grade injection vector (H1/L3).

#### `scripts/read-board.sh` — list cards as JSON
- **What:** List cards from a GitHub Project as a JSON array; optional
  `--status` filter. Used by `briefing-daily` (F-01), `intaking-requirement`
  (F-08), and `consuming-card` (F-C0 manual pull).
- **Args:** `--owner`, `--project <number>`, optional `--status`.
- **Stdout:** `[{"number":12,"title":"…","status":"Ready","url":"…"}, …]`.
  (gh has no server-side status filter as of gh 2.x, so it pulls all items
  then filters in python.)
- **Exit:** `0` success (even with empty array); `1` bad args / gh failure.

### 9.3 Bootstrap scripts

#### `scripts/bootstrap-host.sh` — F-B1 host bootstrap
- **What:** Cross-repo, per-machine initialization. When
  `~/.board-superpowers/manifest.yml` is absent → create
  `~/.board-superpowers/` (mode 0700) + write the initial manifest
  (`schema_version`, `host_bootstrapped_at`, `last_seen_version`). When
  present → refresh `last_seen_version` if behind the running plugin
  (preserves `host_bootstrapped_at`).
- **Atomicity:** render to a per-process scratch file, chmod, atomic `mv`.
- **Flags:** `--force` (overwrite); `--plugin-root` (testability);
  `--auto-install-uv` (non-interactive uv install for CI).

#### `scripts/bootstrap-project.sh` — F-B2 per-repo setup
- **What:** One-time per-repo setup: standard labels, Status-field
  validation, `config.yml`, `.gitignore`. Per ADR-0001 it does **NOT**
  create the GitHub Project — the architect creates it via UI.
- **Args:** `--project OWNER/NUMBER` (required), `--wip` (default 5).
- **Side effects:** creates 9 standard labels via `gh label create`
  (idempotent); reads (not writes) `gh project view` to validate the Status
  field's 6 options; writes `.board-superpowers/config.yml`; appends
  `.board-superpowers/claims/` to `.gitignore`.

#### `scripts/bootstrap-rollback.sh` — undo F-B2 in reverse order
- **What:** Symmetric reverse of F-B2 (the "boil-the-lake symmetry
  enforcer"). Reverse order: (1) `rm config.yml`; (2) remove the bootstrap
  entry from `.gitignore`; (3) remove the routing block (between markers)
  from `AGENTS.md` **and** `CLAUDE.md`; (4) `rm
  ~/.board-superpowers/repos/<normalized>/state.yml`; (5) **prompt** before
  `rm credentials.yml` (default NO).
- **Does NOT:** delete labels, touch `manifest.yml` (F-B1 is independent),
  or delete `audit-local.jsonl` (audit history is durable).
- **Flags:** `--yes`, `--keep-credentials`, `--rm-credentials`,
  `--plugin-root`, `--repo-root`.
- **Symmetry rule:** any future F-B2 step addition MUST add a matching
  rollback step here in reverse order.

#### `scripts/setup-labels.sh` — create the 13 standard labels
- **What:** One-shot create of the 13 standard labels (GitHub labels are a
  per-repo resource the plugin can't auto-create at install time).
  Idempotent (skips existing via `gh label list`).
- **The 13 labels:** Ops (4) — `wip-override`, `suspended`, `security`,
  `pr-contract-override`; Type (5) — `type:feature`, `type:bug`,
  `type:chore`, `type:refactor`, `type:epic`; Size (4) — `size:XS`,
  `size:S`, `size:M`, `size:L`.
- **Rate-limit defense:** a 100ms sleep follows each *created* label
  (skipped labels don't pause) to dodge GitHub's secondary rate limit on
  cold-start.

#### `scripts/register-codex-hooks.sh` — register the SessionStart hook on Codex
- **What:** Codex CLI does NOT auto-discover `hooks.json` (the plugin
  manifest spec has no `hooks` field). This script registers the
  `SessionStart` hook into `~/.codex/hooks.json` (user scope) or
  `<repo>/.codex/hooks.json` (per-repo, requires repo trust). Idempotent;
  backs up `hooks.json` before overwriting.
- **Modes:** (no arg) print snippet + instructions; `--install-user`;
  `--install-repo`; `--uninstall-user`.
- **Codex parity gap (intentional):** registers **only** `SessionStart` —
  not `PreToolUse`/`PostToolUse` — because Codex has no `Skill` tool, so
  the gate's flag-file lifecycle can't complete and would block forever.

### 9.4 Audit scripts

#### `scripts/audit-init.sh` — one-shot DDL apply
- **What:** Apply the audit-log DDL to the configured DB. Idempotent (DDL
  `IF NOT EXISTS` + sentinel UPSERT). Dispatches by URL scheme across the
  6-scheme allowlist (sqlite/sqlite3/postgresql/postgres/mysql/mysql+pymysql,
  per ADR-0009). Pre-init version detection decides whether to run the
  v1→v2 migration first.
- **Called by:** `bootstrap-project.sh` step 2g + manual architect re-run.
- **Exit:** `0` DDL applied (or already current); `1` DB unreachable / DDL
  failed; `2` bad args; `3` `psql`/`mysql` client unavailable (sqlite uses
  stdlib).

#### `scripts/audit-log-write.sh` (~354 lines) — per-mutating-action audit writer
- **What:** Writes one `AuditEntry` row per mutating action.
- **Args:** `--action-id` (1–14 producer / 100–113 consumer / 200–208
  bootstrap), `--decision A|R|N`, `--skill`, `--approval-stage`,
  `--outcome`, `--payload`, `--repo-root`, `--mode` (only `bootstrap-pending`
  allowed externally).
- **Flow:** validate `action_id` (reject → `contract-violation` jsonl row)
  → opportunistic flush guard (600s backoff, forks
  `audit-flush-pending.sh`) → `bsp_ensure_venv` → `bsp_resolve_audit_db_url`
  → INSERT via `sqlite3`/`psql`/`pymysql`; on any failure →
  `bsp_audit_local_write` (jsonl fallback with the right `mode`).
- **Exit:** **always 0** if at least one row was written somewhere (DB or
  jsonl) — so a mutating action never fails just because the audit DB is
  down.

#### `scripts/audit-flush-pending.sh` + `audit-flush-impl.py` — outbox flush worker
- **What:** Scans all per-repo `audit-local.jsonl` files, transitions
  `status:pending` rows → DB INSERT (idempotent via `event_uuid` UNIQUE) →
  `status:processed`. Preserves rows (no deletion) per the retroactive-
  record contract.
- **Failure modes:** `retry_count` per failed row; ≥5 →
  `mode=audit-dead-letter`; `pending_since` > 24h → `audit-dead-letter` (TTL).
- **Concurrency:** per-jsonl exclusive lock via stdlib `fcntl.flock` (in
  `audit-flush-impl.py`) — eliminates the prior dependency on the
  util-linux `flock` binary (absent on stock macOS).
- **Exit:** `0` flush complete; `1` corrupt jsonl rows; `2` partial INSERT
  failure; `3` `audit_db_url` not configured.

#### `scripts/migrations/audit-v1-to-v2.sh` + `audit-v1-to-v2-impl.py` — schema migration
- **What:** Migrate an existing v1 audit DB to v2 (adds the `event_uuid`
  column + unique index for idempotent outbox flush). Run automatically by
  `audit-init.sh` when it detects a v1-shape DB; can also be run manually.

#### `scripts/pre-submit-audit.sh` — pre-PR automation aggregator
- **What:** Runs all pre-PR checks in sequence and outputs Markdown to
  stdout suitable for pasting into a PR body's `## Automated Verification`
  section. Returns 0 if all passed; 1 otherwise.
- **Checks it runs:** `shellcheck -x scripts/*.sh scripts/lib/*.sh hooks/*.sh`;
  `verify-skill-metadata.sh`; `verify-skill-frontmatter.sh`;
  `verify-skill-anti-patterns.sh`. (Plus any test suite the repo declares.)
- **Why:** gives the Consumer's PR-submit step its `## Automated
  Verification` content in one shot.

### 9.5 PR + post-merge scripts

#### `scripts/submit-pr.sh` — open a PR with the three-section contract
- **What:** Open a PR with the three-section contract enforced, **OR**
  update an open PR's body while preserving the canonical `Closes #<card>`
  trailer (Contract C). Validated per `08-pr-contract.md` +
  `enforcing-pr-contract`.
- **Modes:** `create` (default — open a new PR) and `--update-body`
  (idempotently strip any tail-anchored `Closes`/`Fixes`/`Resolves` block
  and re-append the canonical trailer, so post-open body edits don't tear
  down the PR↔Issue link GitHub keys its merge→close webhook on).
- **Args:** `--title` (≤70 chars, action-style), `--body-file`, `--base`
  (default `main`), `--card <N>`; in update-body mode `--pr <N>`.
- **Refuses** `--update-body` if the PR's current body has no matching
  trailer at all (means it was opened via direct `gh pr create` — the chain
  is unrecoverable; manual recovery per `consuming-card` Step 12).

#### `scripts/post-merge-cleanup.sh` — post-merge worktree + branch cleanup
- **What:** After a PR merges, remove the claim worktree + delete the local
  claim branch (`action_id` 113, A-class). Called by `consuming-card`
  Step 12 and optionally by the cron installer. Idempotent; **never
  `rm -rf`** — uses only `git worktree remove` + `git branch -D`.
- **Steps when PR is MERGED:** (1) verify the worktree exists (else
  "already cleaned up" exit 0); (2) `gh pr list` for the claim branch;
  (3) branch on PR state — MERGED → cleanup, OPEN → exit 2 (retry later),
  CLOSED → exit 3 (closed-without-merge, `action_id` 103); (4) `git
  worktree remove` (refuse exit 4 if uncommitted changes); (5) `git branch
  -D`; (6) append A-class audit row.
- **Args:** `--card <N>`, `--owner`, optional `--repo-root`.

#### `scripts/install-post-merge-cron.sh` — recurring cleanup job installer
- **What:** Install a recurring `post-merge-cleanup.sh` job that polls
  until the PR reaches a terminal state (MERGED or CLOSED), then uninstalls
  itself. On macOS: writes a LaunchAgent plist + `launchctl`; on Linux:
  appends a crontab entry wrapped in marker comments.
- **Args:** `--card <N>`, `--owner`, `--poll-interval-minutes` (default 15),
  `--timeout-hours` (default 48).
- **Why:** the no-daemon-constraint (C-PLUGIN-2) way to get "after the PR
  merges, clean up the worktree" without a long-running process.

### 9.6 Dep-check + CI/skill-gate scripts

#### `scripts/check-deps.sh` — the self-contained readiness probe
- **What:** Detects that `superpowers` and `gstack` are reachable from the
  current session and that the project's `CLAUDE.md` carries the
  routing-block marker. **Self-contained** (does NOT source `common.sh`) so
  a broken lib can't derail dep detection.
- **Modes:** `human` (default — banner if anything missing, success line if
  OK) and `--machine` (stdout only when something wrong: `MISSING=<csv>`,
  `ROUTING_INJECTED=<yes|no>`, `PROJECT=<path>` — these key names are
  protocol; renaming them breaks `session-start.sh`'s parser).
- **Exit:** `human` mode `0`/`2`/`3`; `--machine` mode always `0` (the
  output channel signals state). Layer 1 of the three-layer dep-alert
  strategy; the no-daemon-friendly readiness probe (ADR-0007 C-PLUGIN-2).

#### `scripts/verify-skill-metadata.sh` — CI gate: yaml ↔ catalog consistency
- **What:** Checks every `skills/*/.skill-meta.yaml` agrees with
  `SKILLS.md` (the source-of-truth catalog) — layer/type/mode/bounded-
  context fields match. Run by `pre-submit-audit.sh` + CI.

#### `scripts/verify-skill-frontmatter.sh` — CI gate: frontmatter compliance
- **What:** Checks every `SKILL.md`'s frontmatter is **Tier 1 + Tier 2**
  compliant and contains **no Tier 3** (forbidden) fields, per
  `SKILL_DEVELOPMENT.md`.

#### `scripts/verify-skill-anti-patterns.sh` — CI gate: A9 + A10 clean
- **What:** Scans `skills/**/SKILL.md` **and** `skills/**/references/**.md`
  for `SKILL_DEVELOPMENT.md` anti-patterns **A9** (internal codes
  (`F-XX`/`ADR-XXXX`/`§X.`/`PXa`/`I-X`/`D-XXX-X`/`C-XXX-X`) + cross-boundary
  refs (`docs/architecture/` literals, `../../docs/` traversal, root
  maintainer-doc filenames inside shipped skill payload)) and **A10**
  (phase-narrative leakage). Exit 0 clean / 1 violations.

### 9.7 The setup-stages engine (Python)

#### `scripts/stages-registry.yml` + `stages-registry.schema.json`
22 stages across 10 modules (M1 plugin-runtime, M2 Python, M3 Board ops,
M4 Audit, M5 Repo config, M6 Gitignore, M7 Agent routing, M8 Autonomy
overrides, M9 Hook registration, M10 BoardAdapter selection). Per-stage
shape: `stage_id`, `module`, `character: automated|agentic`, `locality`
(host-shared/repo-shared/repo-git/repo-clone/external), `platforms`
(cc/codex/both), `executor`, `generation` (a monotonic int — bumping it
triggers re-run on upgrade), `depends_on`, `target_state_schema`,
optional `applicable_when` predicate. The schema file validates the YAML.

#### `scripts/stages_lib/` (54 Python files)
- **`__main__.py`** — CLI entry point (e.g. `python3 -m stages_lib
  lifecycle-probe …` used by `session-start.sh`).
- **`_lifecycle.py`** — `evaluate_all_stages()`: topological sort of stages
  + per-stage lifecycle diff (computes `pending`/`applied`/`drifted`/
  `not-applicable`/`failed`).
- **`_canonical.py`** — canonicalization helpers (the canonicalization
  invariant the spec relies on).
- **`_partitioned_settings.py`** — read/write across the 4 settings
  localities (host-shared / repo-shared / repo-git / repo-clone).
- **`_m7_inject_helpers.py`** — routing-block injection helpers for the M7
  stages.
- **22 stage executors** (`m1_host_create_state_dir.py`,
  `m1_host_write_manifest.py`, `m1_repo_write_state_yml.py`,
  `m2_host_install_uv.py`, `m2_repo_copy_uv_templates.py`,
  `m2_repo_sync_venv.py`, `m3_repo_ensure_labels.py`,
  `m3_repo_validate_status_field.py`, `m4_repo_acquire_dsn.py`,
  `m4_repo_apply_audit_ddl.py`, `m4_repo_audit_health_check.py`,
  `m4_repo_flush_pending_audit.py`, `m5_repo_set_wip_limit.py`,
  `m5_repo_write_config_local_yml.py`, `m5_repo_write_config_yml.py`,
  `m6_repo_append_gitignore.py`, `m7_repo_detect_agentsmd_form.py`,
  `m7_repo_inject_block_routing_rule.py`,
  `m7_repo_inject_block_skill_routing.py`,
  `m8_host_bootstrap_overrides_yml.py`, `m9_host_register_codex_hooks.py`,
  `m10_repo_choose_kanban_projection.py`) — one per stage; each exposes
  `executor()` + `idempotency_check` + `target_state_predicate` +
  `compute_target_state` (the 5-callable contract per ADR-0014). The names
  tell you exactly what each stage does (e.g. `m4_repo_apply_audit_ddl` =
  apply the audit DDL to the repo's DB; `m7_repo_inject_block_skill_routing`
  = inject the skill-routing block into the repo's `CLAUDE.md`/`AGENTS.md`).
- **`test_*.py`** — co-located pytest suites for every stage executor + the
  canonical/lifecycle/partitioned-settings helpers.

#### `scripts/templates/`
- **`pyproject.toml` + `uv.lock`** — copied per-repo by `m2_repo_copy_uv_templates`
  to seed the per-repo Python venv (`<repo>/.board-superpowers/.venv/`).
- **`settings.host-shared.yml` / `settings.repo-shared.yml` /
  `settings.repo-git.yml` / `settings.repo-clone.yml`** — the 4 partitioned
  settings templates (per ADR-0024) that the M5/M8 stages write from.

---

## 10. Key contracts (the load-bearing ones)

### Kanban Protocol (`0005-contracts/00-kanban-protocol.md`, ADR-0025)
The top contract — **not** an SDK, **not** a test gate. Agents reason in
this vocabulary regardless of backend.
- **6 states:** `Backlog → Ready → In Progress → Blocked → In Review → Done`.
- **8 actions:** `read_board`, `read_card`, `create_card`, `transition_card`,
  `claim_card`, `release_claim`, `link_pr_to_card`, `comment_on_card` (OPTIONAL).
- **3 projection forms:** Form A (bash CLI — v1 GitHubProjectAdapter),
  Form B (plugin-shipped MCP server — future Linear/Jira), Form C (REST/GraphQL — reserved).
- **Card hierarchy is flat** (ADR-0026) — no parent/child at protocol level.
- **Identity** is composite `(kanban_id, Card.key)`; `Card.key` is opaque.

### PR contract (`0002-…/08-pr-contract.md`, `enforcing-pr-contract`)
Every Consumer PR has three sections:
- `## Automated Verification` (required) — what ran and passed.
- `## Human Verification TODO` (optional but never filler) — the architect's job.
- `## Retro Notes` (required when reusable lessons exist) — knowledge harvesting, never KPIs.
Plus a `Closes #<card>` trailer and a `<!-- board-superpowers:pr -->` marker.

### Card body schema + branch naming + WIP (`board-canon`)
- **Body:** thin-pointer (Spec/Owner/Estimate) + 5 sections
  (Goal / Acceptance criteria / Out of scope / Dependencies / Notes) +
  bottom audit-trail marker.
- **Branch:** `claim/<kanban-id>-<key-slug>-<title-slug>` (v0.5.0 canonical;
  v0.4.x legacy accepted).
- **WIP:** `In Progress + suspended + In Review` (Blocked excluded); soft cap, default 5.

### D-AUTONOMY-1 (ADR-0006, `classifying-actions`)
- **A** = auto-execute + one audit entry.
- **R** = propose + await approval + resolve; **two** audit entries.
- **N** = permanently rejected (v1 has N=0).
- Matrix: 14 Producer + 14 Consumer + 9 Bootstrap rows. R-class includes
  merge, claim cancellation, card split, `CLAUDE.md`/`config.yml` edit,
  Blocked transition. `autonomy_overrides:` at user + project layers can
  promote R → A as trust grows.
- When the audit DB is unavailable, **every A-class action degrades to R-class**.

### Plugin-runtime constraints (ADR-0007)
- **C-PLUGIN-1:** no in-memory cross-session IPC — signals go via GitHub
  artifacts or on-disk transcripts.
- **C-PLUGIN-2:** no daemon — "monitor/detect" features are lazy via the
  **preflight-piggyback** idiom (run a situation check before every architect prompt).
- **C-PLUGIN-3:** controlled Consumer-dispatch concurrency (default = 1 serial;
  tunable upward).

### Modes (`consuming-card`)
- **Mode-1:** architect-spawned Consumer (paste a kick-off prompt into a fresh
  terminal). Works on CC **and** Codex.
- **Mode-2:** Producer-spawned Consumer as a CC subagent. **CC-only at v1.**
  `max_depth=1` → a Consumer **cannot** spawn further subagents. Every
  sibling-plugin invocation from Mode-2 MUST be procedural (ADR-0008).

---

## 11. Key ADRs (the "why")

Read in numeric order; these are the most load-bearing:

| ADR | Decision (one line) |
|---|---|
| 0001 | Pluggable board backend; GitHub Project v2 is the v1 reference; Linear/Jira are first-class future targets. |
| 0002 | Atomic claim = `git push --force-with-lease` on a `claim/…` branch (the distributed lock; first push wins). |
| 0003 | One worktree per Consumer session (card-deterministic path); no HEAD contention across N Consumers. |
| 0004 | Composition over reimplementation — `superpowers` + `gstack` are **hard** runtime deps; we never duplicate them. |
| 0005 | v1 BoardAdapter contract surface (5 methods, 6 statuses); rescoped by 0025 to "the v1 projection's shape." |
| 0006 | Producer autonomy boundary — the D-AUTONOMY-1 A/R/N matrix + 5-step triage rule + BYO-RDBMS audit. |
| 0007 | Plugin-runtime constraints C-PLUGIN-1/2/3 + the preflight-piggyback idiom. |
| 0008 | Plugin-to-plugin SKILL invocation = in-process **content loading, not subagent spawn**; `max_depth=1` for Mode-2. |
| 0009 | SQLite allowed as a 5th/6th BYO audit-DB scheme (default for solo architect). |
| 0010 | AI cadence ~100× convention; re-anchor deadlines to v1-GA-relative events, not calendar offsets. |
| 0011 | Defer 11 Producer routines to v1.x (overnight batch, retro, weekly report, etc.) — demand-pull, not calendar. |
| 0012 | Unified check-script trigger model — `SessionStart` emits `INVOKE: bootstrapping-repo`; sole executor for setup + upgrade. |
| 0025 | Kanban Protocol is the **top-level** contract (above the SDK); transport-agnostic; MCP is first-class. |
| 0026 | Multi-kanban lifecycle (5 kanban states) + **flat** Card hierarchy (sub-issues are display-only metadata). |
| 0027 | M3 setup-capability dispatch routes through `operating-kanban` projection reference files, not SDK methods. |
| 0028 | Cron is an explicit J2 trigger carrier (compute/present split) — the closest thing to an always-on agent primitive. |

---

## 12. Premises P1–P8 + non-goals (what you're fighting if you push off-course)

The eight load-bearing premises (`0001-positioning.md`), each with a
falsification test:

- **P1** — Role-shift: architect value is sequencing/judgment/architecture,
  not coding.
- **P2a** — Substrate: use the team's existing board as truth; never own state.
- **P2b** — Methodology embedded as code (INVEST, vertical slicing, …).
- **P3** — Solo / small-team scale at v1 (one architect or 2–3 sharing a board).
- **P4a** — Truth-source belongs to the user, never us.
- **P4b** — Composition is permanent (never reimplement upstream disciplines).
- **P5** — Distribution stays minimal (git clone + `/plugin add`; never hosted).
- **P6** — Human verification is a first-class output (the `## Human Verification TODO`).
- **P7** — Meta-methodology, not opinionated configuration (we ship mechanisms, not taste-presets).
- **P8** — Default + override + accountability across every governance dimension.

**Non-goals** (explicit refusals): no backend/DB/web UI; no reimplementation;
no CI replacement; no story points/velocity/KPIs; no cross-team/fleet at v1;
no agent self-merge; no hosted install; no methodology-extension marketplace.

> **For adaptation work:** every one of these is a guardrail you either keep
> or consciously supersede with a new ADR. Pushing the repo against a
> premise without an ADR is the primary way adaptations decay.

---

## 13. The core nouns — board, card, and every related term (plain English)

> The whole plugin operates on a small set of nouns. This section explains
> each one in plain English — what it is, what it isn't, and a concrete
> example — so the rest of the guide (and the spec) has words to hang on.
> The one-line versions are in §14 (Glossary); this is the elaborated version.

### Board
- **What it is:** A **kanban board** — the team's shared to-do list, organized
  into columns by status. In board-superpowers the board is **your GitHub
  Project v2**; the plugin never owns a board of its own (P2a/P4a). Future
  versions support Linear/Jira boards too, via the Kanban Protocol.
- **What it isn't:** NOT a git repo, NOT a directory, NOT a database table.
  It's the GitHub Project you create in the GitHub UI (the one non-scriptable
  bootstrap step).
- **Concrete example:** You create a GitHub Project v2 named "Acme Dashboard"
  with a `Status` field whose options are exactly
  `Backlog → Ready → In Progress → Blocked → In Review → Done`. That Project
  IS "the board." Every card lives as a column-positioned item on it.
- **The board is the single source of truth:** if you deleted the plugin
  tomorrow, your board + your git remote still tell the whole story. The
  plugin refuses to keep a parallel state store.

### Card
- **What it is:** A **single unit of work** on the board — one GitHub Issue,
  added to the Project, carrying a structured body. The atomic thing a
  Consumer agent claims and delivers. **Invariant I-1: one Card = one
  Consumer session = one PR** — no multi-card sessions, no PR that resolves
  multiple cards.
- **What it isn't:** NOT a sprint story, NOT a sub-task, NOT an epic. The
  Card hierarchy is **flat** (ADR-0026) — there are no parent/child cards at
  the protocol level. (GitHub/Linear/Jira "sub-issues" you create natively
  show up as **display-only** metadata, not as protocol children.)
- **The card body** has a fixed shape (see `board-canon`): a **thin-pointer**
  block (Spec / Owner / Estimate) at the top + 5 sections — **Goal**,
  **Acceptance criteria** (a `[ ]` / `[x]` / `[!]` checklist), **Out of
  scope**, **Dependencies**, **Notes** — + a bottom audit-trail marker.
- **Concrete example:** Card #42 "Add `revenue` chart + `sales_db` connector."
  Body: Goal = "users see a revenue lines chart fed from `sales_db`";
  Acceptance criteria = `[ ] chart renders last 30 days`,
  `[ ] connector retries on timeout`, …; Out of scope = "forecasting";
  Dependencies = "card #40 (db access)". A Consumer claims #42, implements
  it, opens a PR that `Closes #42`.

### Status (the 6 columns)
A card is always in exactly one of six states — these ARE the board's columns:
- **Backlog** — captured but not yet ready to be worked (the architect hasn't
  confirmed it's shippable-shaped).
- **Ready** — shaped (INVEST-compliant, vertically sliced) and OK for a
  Consumer to claim. `Backlog → Ready` is the architect's separate
  confirmation step.
- **In Progress** — a Consumer has claimed it and is actively implementing
  (a `claim/…` git branch + worktree exist).
- **Blocked** — work started but stopped on an external dependency / decision
  / stale state. **Excluded from WIP.** The Producer's triage routine works
  this column.
- **In Review** — the Consumer opened a PR; waiting on human review/merge.
- **Done** — PR merged; card closed.

Transitions follow a state machine (`board-canon` has the legal/illegal
table) — e.g. you can't go `Backlog → In Review` directly.

### WIP (Work In Progress)
- **What it is:** A **count of how many cards are currently being worked**,
  used as a soft capacity limit so the team doesn't spread too thin. The
  board-superpowers WIP formula is:

  > **WIP = `In Progress` + `suspended` + `In Review`**  (Blocked excluded)

  i.e. cards in the `In Progress` column + cards in the `In Review` column +
  cards with the `suspended` label. **`Blocked` is excluded** because a
  blocked card isn't consuming active attention.
- **It's a soft cap, not a hard gate** (P2b): default `wip_limit: 5`. When
  WIP exceeds the cap, the plugin **warns, doesn't block**. To claim past
  the cap intentionally, the Producer applies the `wip-override` label.
- **`suspended`** is a *label* (not a Status) marking a card paused mid-work
  — it still counts toward WIP (the worktree/branch stick around) so paused
  work doesn't vanish from your capacity view.
- **Concrete example:** 3 cards `In Progress` + 1 `suspended` + 2 `In
  Review` = **WIP 6**. With `wip_limit: 5`, the daily briefing flags
  "WIP 6 > cap 5" and recommends finishing/closing before claiming more.
- **Why no story points / velocity / burndown:** WIP + Done-count replace
  burndown; XS/S/M/L replaces story-point estimation. The repo deliberately
  dropped sprint-cadence artifacts (see §12 and `0001-positioning.md` §
  "AI-native concept hygiene").

### Claim (and ClaimBranch / ClaimMarker)
- **Claim** — the **atomic act of a Consumer taking exclusive ownership of a
  card**, so two agents can't both work it. In board-superpowers the claim is
  **a git operation, not a board operation**: `git push --force-with-lease` of
  a `claim/<card>-<slug>` branch. **First push wins; the loser's push is
  rejected** (ADR-0002). The board only *observes* the resulting Status flip
  to `In Progress`.
- **ClaimBranch** — the git branch the claim lives on, named
  `claim/<kanban-id>-<key-slug>-<title-slug>` (e.g. `claim/42-revenue-chart`).
  **The branch IS the lock** — as long as it exists on the remote, the card
  is claimed. Deleting the branch releases the claim.
- **ClaimMarker** — a small YAML file (`.board-superpowers/claims/<N>.claim`)
  recording claim metadata (session slug, timestamp). Local-only; gitignored.
- **Why git-push as the lock:** atomic, free, durable, observable on any git
  host, and it doubles as the feature branch — no separate lock service
  (P4a: no owned state).
- **Concrete example:** Consumers A and B both try to claim card #42. Both
  run `claim-card.sh`. A's `git push --force-with-lease` lands first; B's
  push is rejected with exit code `10` (race-lost — MUST stop, never retry).
  B sees who won and picks a different card.

### Worktree
- **What it is:** A **separate working directory** (a `git worktree`) for one
  Consumer's work on one card, so N parallel Consumers never share a HEAD or
  trip over each other's checkout. **Invariant I-7: one card = one
  worktree.** Default path:
  `$HOME/.config/superpowers/worktrees/<project>/<branch>`.
- **Lifecycle:** created by `claim-card.sh` on claim; persists across Mode-2
  suspend/resume (preserving partial work); self-deletes on PR merge
  (`post-merge-cleanup.sh`); preserved on Blocked termination.
- **Concrete example:** The Consumer on card #42 works in
  `~/.config/superpowers/worktrees/acme-dashboard/claim-42-revenue-chart/`.
  A second Consumer on card #43 works in a sibling directory with its own
  HEAD. Neither sees the other's uncommitted changes.

### PR (Pull Request) and the PR contract
- **What it is:** The deliverable a Consumer opens against the card's base
  branch. Every Consumer PR has a fixed **three-section shape** (the PR
  contract, enforced by `enforcing-pr-contract` + `submit-pr.sh`):
  - `## Automated Verification` (required) — what tests/lints/reviews ran
    and passed.
  - `## Human Verification TODO` (optional but never filler) — the steps the
    AI couldn't automate; **this is the architect's remaining job** (P6).
  - `## Retro Notes` (required when reusable lessons exist) — knowledge
    harvesting, never KPIs/velocity.
  Plus a `Closes #<card>` trailer (so merging the PR auto-closes the card's
  issue) and a `<!-- board-superpowers:pr -->` marker.
- **Humans merge; agents never self-merge** (ADR-0006 row 12 = N). The
  Consumer opens the PR; a human reviews the Human Verification TODO and
  merges.

### Thin-pointer
The card body's top block (Spec / Owner / Estimate). The card *points* to
where the real spec lives (e.g. "spec: `docs/architecture/0007-observability.md`
§2") instead of duplicating it. The Consumer self-fetches the spec at claim
time (invariant I-9) — so the spec can evolve without every card being
rewritten.

### Thread / Milestone (the grouping nouns)
Because there's no Sprint and no Epic, two lighter nouns group cards:
- **Thread** — a thematic grouping (a named work mainline, e.g. "audit-log
  hardening"). Replaces "Epic as theme."
- **Milestone** — a deliverable bucket (a thing you ship, e.g. "v0.5.0").
  Replaces "Epic as deliverable."

A card has `0..1` Milestone and `0..N` Threads. Neither is a parent card;
neither is claimable; both are display/grouping only.

### INVEST
The **refusal conditions** every card must satisfy before it's allowed onto
the board as `Ready` (Wake 2003). The `decomposing-into-milestones` skill
**refuses** cards that fail any:
- **I**ndependent — can ship without waiting on a sibling.
- **N**egotiable — not a fixed contract; can be discussed.
- **V**aluable — delivers user-visible value on its own.
- **E**stimable — you can size it XS/S/M/L.
- **S**mall — fits in one Consumer session / one PR.
- **T**estable — has clear acceptance criteria you can check.

A card that's "too big" or "not independently shippable" gets **sliced
further** (vertical slicing) rather than accepted as-is.

### Size (XS / S / M / L)
The replacement for story points. Four buckets: `size:XS` (<50 LOC / 1-2
files), `size:S` (50-200 / 2-5), `size:M` (200-400 / 5-10), `size:L`
(400-500 / up to 10 files — the ceiling). Coarse enough to be quick,
granular enough to flag "this is too big, slice further." There is
deliberately **no `size:XL`** — an XL is a signal to decompose, not a size
to accept.

### Labels (the `type:` / `size:` / ops labels)
GitHub labels on a card, in three namespaces (created by `setup-labels.sh`):
- **Type** — `type:feature` / `type:bug` / `type:chore` / `type:refactor` /
  `type:epic` — what kind of work.
- **Size** — `size:XS` / `size:S` / `size:M` / `size:L` — see above.
- **Ops** — `wip-override` (claim past WIP cap), `suspended` (paused, still
  counts toward WIP), `security` (triggers a `gstack:/cso` security pass on
  PR submit), `pr-contract-override` (bypass three-section validation).

### Kanban Protocol / Projection
- **Kanban Protocol** — the *backend-agnostic* mental model agents reason in
  (ontology + 6 states + 8 actions + compliance levels). It's a **contract,
  not an SDK** — agents read SKILL bodies + MCP tool descriptions, not a
  function table.
- **Projection** — a concrete realization of the Protocol on one backend. v1
  ships one: the **GitHubProjectAdapter** (Form A — bash CLI calling `gh`).
  Future: Linear/Jira (expected Form B — plugin-shipped MCP server). Form C
  (REST/GraphQL) is reserved.
- **The 8 protocol actions:** `read_board`, `read_card`, `create_card`,
  `transition_card`, `claim_card`, `release_claim`, `link_pr_to_card`,
  `comment_on_card` (OPTIONAL). Every board-touching skill dispatches these
  through `operating-kanban`.

### A quick end-to-end picture

```
Board (your GitHub Project v2)
  └─ Card #42 (GitHub Issue + structured body + thin-pointer)
       ├─ Status:  Ready → In Progress (claim) → In Review (PR) → Done (merge)
       ├─ ClaimBranch: claim/42-revenue-chart        ← the git-layer lock
       ├─ Worktree:   ~/.config/superpowers/worktrees/acme/claim-42-…/
       ├─ Labels:     type:feature, size:S
       └─ PR #57:     ## Automated Verification
                     ## Human Verification TODO
                     ## Retro Notes
                     + Closes #42
```

A Consumer **claims** #42 (Status → In Progress, branch pushed, worktree
created) → **implements** via TDD → **opens PR #57** (Status → In Review) →
a **human verifies + merges** (Status → Done, worktree removed, branch
deleted). Every status flip / claim / PR link is A-or-R classified and
audit-logged.

---

## 14. Glossary (the terms you'll see everywhere)

| Term | Meaning |
|---|---|
| **Architect** | The human who drives Producer/Consumer sessions; the scarce attention the plugin optimizes for. |
| **Producer / Manager** | The keep-the-board-healthy role; long-lived, aggregate view, never writes code. |
| **Consumer / Implementer** | The one-card-to-PR role; claims one Ready card, delivers one PR. |
| **Card** | A unit of work on the board; flat hierarchy; one Card = one Consumer session = one PR. |
| **Card.key** | Opaque card identifier; never parsed by the agent. |
| **Status (6)** | Backlog → Ready → In Progress → Blocked → In Review → Done. |
| **Claim / ClaimBranch / ClaimMarker** | The atomic ownership transfer; the `claim/…` git branch IS the claim signal. |
| **WIP** | In Progress + suspended + In Review (Blocked excluded); soft cap default 5. |
| **Kanban Protocol** | The top semantic contract (ontology + 6 states + 8 actions + 3 projection forms). |
| **Projection** | A concrete realization of the Protocol on one backend (Form A/B/C). |
| **Mode-1 / Mode-2** | Architect-spawned Consumer vs Producer-spawned CC subagent (max_depth=1). |
| **D-AUTONOMY-1** | The A/R/N autonomy matrix. |
| **AuditEntry** | Append-only governance row; R-class writes two (propose + resolve). |
| **Thin-pointer** | The card body's spec-pointer block; the Consumer self-fetches the spec rather than re-deriving it. |
| **Thread / Milestone** | Thematic grouping / deliverable bucket (replace Epic; no Sprint). |
| **INVEST** | Independent, Negotiable, Valuable, Estimable, Small, Testable — card refusal conditions. |
| **Setup-stages** | The 22-stage bootstrap/upgrade system (M1–M10) with a 5-state lifecycle. |
| **INVOKE: marker** | The two-line intent-injection payload (`INVOKE: <skill>` / `REASON: <line>`) from SessionStart. |
| **Sibling plugin** | `superpowers:*` or `gstack:*` — invoked with the `<plugin>:<skill>` namespace prefix. |
| **Preflight piggyback** | The no-daemon awareness idiom: run a situation check before every architect prompt. |

---

## 15. Conventions you MUST follow if you modify anything

From `AGENTS.md` (the maintainer guide). These are enforced by doctrine, CI,
and hooks — not optional.

- **`SKILLS.md` is the source of truth for `skills/`.** Any `skills/` change
  (add/rename/re-edge/re-layer) MUST land in the same PR as a `SKILLS.md`
  change. An edit to `skills/` without `SKILLS.md` is unmergeable.
- **Read the per-directory contract before touching that subtree.** Each of
  `skills/`, `hooks/`, `scripts/`, `docs/architecture/` has a nested
  `AGENTS.md`. Doctrine: no "I already know," no "this change is too small,"
  same-PR contract updates.
- **Spec stays English** (`SKILL_DEVELOPMENT.md` anti-pattern A5). Chinese
  discussion belongs in `docs/plans/<feature>/` (gitignored) or commit/PR messages.
- **Working-tree discipline:** the repo root stays on `main`; every PR is
  authored in a `git worktree` at
  `$HOME/.config/superpowers/worktrees/board-superpowers/<branch>`.
- **Don't `@`-prefix the six companion docs** — force-loading them into every
  session is the anti-pattern they warn against.
- **Don't skip pre-commit hooks** (`--no-verify`) or amend-on-hook-failure.
- **Dogfood:** any non-trivial plugin change goes through the plugin's own
  Producer → Consumer flow on its GitHub Project (the self-hosting section
  of `AGENTS.md`).
- **Skill-authoring gate:** editing `skills/` requires the
  `example-skills:skill-creator` invocation per `skills/AGENTS.md` — enforced
  by the `pre-tool-use.sh` hook (see §7).

---

## 16. Quick orientation checklist for a new session

1. Skim `README.md` § "Why this exists" + "A typical day" (5 min).
2. Read `docs/architecture/0001-positioning.md` (the premises + non-goals).
3. Skim `SKILLS.md` (the 14-skill catalog — already in your session context);
   then §5–§6 here for what each skill does.
4. Open `skills/using-board-superpowers/SKILL.md` to see the routing tree.
5. When you need to know what a hook/script does, jump to §7 / §9 here.
6. When you need *why*, jump to the relevant ADR in `docs/architecture/adr/`.

That's enough to navigate. Drill into `0005-contracts/` and the companion
docs only when the work touches their scope.