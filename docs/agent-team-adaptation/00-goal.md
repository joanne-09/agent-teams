# 00 — Goal

> **Status: v0.7 — FINALIZED.** Both v0.6 blockers are resolved, and one
> v0.6 claim turned out to be factually wrong (see "The ADR-0008 correction"
> below). The adaptation is back to a **role-layer extension**, not a heavy
> fork.
>
> This doc is the **anchor** for the whole `agent-team-adaptation/`
> directory. The design that implements it is
> [`03-target-architecture.md`](./03-target-architecture.md).

---

## One-sentence statement

Build an **all-agent software-engineering team** structured like a **company
eng org** (leads above ICs), developing a **data dashboard** (UI + data
sources) on the **board-superpowers** base — running **as a Claude Code
plugin**, **one team first → team-of-teams later** — where agents
autonomously handle analysis / spec / architecture / docs, a **human reviews
code changes and merges**, and **TDD / QA / security continue to come from
the `superpowers` and `gstack` sibling plugins**.

---

## The four decisions (v0.6 → v0.7)

| # | Question | Answer | Consequence |
|---|---|---|---|
| a | Where do TDD / QA / security come from? | **Keep `superpowers` + `gstack`** | ADR-0004 stands. No discipline skills to write. `composing-siblings` stays load-bearing. **Removes the largest risk item and ~6 skills of work.** |
| b-i/ii | Org chart | **EM → {analyst, architect}; architect → {RD, QA}** | Becomes an authority + routing model on the board, not a call stack. |
| b-iii | Hierarchy mechanism | **Horizontal agents, coordinated on the GitHub board** | ADR-0008 untouched — see the correction below. |
| — | Fork posture | **Pragmatic internal fork** | Keep substrate + governance. ADRs only for supersessions. New surfaces CC-only. |

### The ADR-0008 correction

v0.6 offered "supersede ADR-0008 to allow real nested subagents" as a live
option. **It is not one.**
[`MULTI_AGENT_DEVELOPMENT.md`](../../MULTI_AGENT_DEVELOPMENT.md) line 42
records the constraint as a property of the **host**, on both platforms:

> Child can spawn further children — **No** — subagents cannot spawn
> subagents; agent-teams cannot nest teams. *Portable (negative).*

An ADR cannot change what Claude Code permits. A nested EM → architect → RD
call stack was never available at any price. Your question —
*"but it is work in github board, can we use horizontal agents for now?"* —
is therefore not a compromise; it is the only correct answer, and the
company hierarchy survives intact as **authority over board state** rather
than as a call stack. See [`03-target-architecture.md`](./03-target-architecture.md)
§ 5–6.

---

## Phasing

| Phase | Shape | Roles | Why |
|---|---|---|---|
| **Phase 1 (day-one)** | One team, all-agent | Team Lead (EM), system analyst, system architect, RD (TDD), QA engineer (**security folded in**) | Get one team working end-to-end first. |
| **Phase 2** | One team, expanded | **+ system OPS engineer**, **+ dedicated security role** | Add ops and split security out of QA once Phase 1 is stable. |
| **Phase 3** | Team-of-teams | multiple sub-teams + a coordinating layer | Scale beyond a single team once the single-team pattern is proven. |

Mirrors board-superpowers' demand-pull deferral pattern (ADR-0011). Both
later phases are **additive** under the v0.7 design — adding a seat is four
mechanical steps, not a redesign (`06-operating-runbook.md` § 9).

---

## Runtime

- **Phase 1–3: run inside Claude Code as a plugin (Path A).** Extend
  `board-superpowers` on its native host — inherit the `Agent` tool, hooks,
  skill auto-matching.
- Accept the plugin runtime constraints (ADR-0007): no in-memory IPC, no
  daemon. Coordination is board state; scheduling, when wanted, is cron
  (ADR-0028).
- **Standalone orchestrator (Path B) — deferred.** Revisit only if a real
  reason to leave the Claude Code host emerges.

---

## Sibling plugins — KEPT (v0.7)

`superpowers` and `gstack` are two external plugins that board-superpowers
hard-depends on (ADR-0004), and they supply the actual engineering
disciplines:

- `superpowers` → the coding-discipline loop: TDD, brainstorming,
  writing-plans, systematic-debugging, subagent-driven-development,
  verification-before-completion, requesting-code-review.
- `gstack` → the bookends: direction-setting (`office-hours`,
  `plan-ceo-review`, `plan-eng-review`) + delivery verification (`/qa`,
  `/review`, `/cso`, `/codex`).

**v0.7 decision: keep both.** The seats consume them exactly as the current
Producer/Consumer roles do — RD via `superpowers:test-driven-development`,
QA via `gstack:/qa` + `gstack:/cso` + `gstack:/review`, architect via
`gstack:/plan-eng-review` + `superpowers:writing-plans`. Every invocation
goes through `composing-siblings`.

This is what turned the adaptation from a heavy fork back into an extension.

---

## All roles are agents; human is outside the team

- **Every team seat is an AI agent** — Team Lead, analyst, architect, RD,
  QA, and later OPS + dedicated security.
- **The human is outside the team** — a stakeholder / operator who reviews
  code changes and merges. Not a team seat, but a routable destination: the
  `human` value of the `Role` field is the merge gate.

---

## Hierarchy — company-like, carried by the board

```
Engineering Manager / Team Lead (agent)
├── System Analyst (agent)
├── System Architect (agent)              ← tech lead
│   ├── RD engineer(s) (agent)            ← IC
│   └── QA engineer(s) (agent)            ← IC (security folded in, Phase 1)
└── (Phase 2) System OPS engineer, dedicated Security engineer
```

At **runtime** every agent is a peer session. The tree above is expressed as
a **legal-handoff matrix** — who may hand work to whom — plus a
seat-dimension autonomy matrix that decides which actions each seat may take
at all. Two examples of the tree becoming enforcement rather than decoration:

- RD may hand off to `architect` (escalate) and `qa` (PR ready), but **not**
  to `human` — only QA opens the merge gate.
- `Backlog → Ready` is `A` for the architect and `N` for RD — RD cannot
  declare its own work ready.

Full matrices: [`03-target-architecture.md`](./03-target-architecture.md)
§ 5.2 and § 8.

---

## The team

| Role | Scope | Phase | Reports to | Discipline source |
|---|---|---|---|---|
| **Team Lead / EM** | Coordination, dispatch, board health | 1 | — (top) | `briefing-daily`, `triaging-board`, new `dispatching-work` |
| **System analyst** | Requirements & system analysis; intake | 1 | Team Lead | `intaking-requirement` |
| **System architect** | Architecture & decomposition; data-flow design | 1 | Team Lead | `decomposing-into-milestones`, new `authoring-spec`, `gstack:/plan-eng-review` |
| **RD (TDD flow)** | Red → Green → Refactor; claims cards, delivers PRs | 1 | Architect | `consuming-card` + `superpowers:test-driven-development` |
| **QA engineer** | Functional, UI, data-correctness; **+ security pass** | 1 | Architect | new `verifying-delivery` + `gstack:/qa` + `gstack:/cso` + `gstack:/review` |
| **System OPS engineer** | Deployment, pipeline ops, monitoring, release | 2 | Team Lead | TBD |
| **Security engineer** | Dedicated security role split out of QA | 2 | Team Lead | `gstack:/cso` moves here |

**Three new skills total** — `dispatching-work`, `authoring-spec`,
`verifying-delivery`. Everything else is reuse or small edits.

---

## Human's role & autonomy posture

- **The human is a review gate for code changes + merge.** Agents propose;
  humans merge (P6, ADR-0006 row 12 = `N`, preserved verbatim for **every**
  agent seat).
- **Everything upstream of code is autonomous**: agents write specs, design
  docs, architecture, analysis, and decomposition freely, then implement
  under review. Flow: **spec / docs → implement (human-gated) → merge
  (human-gated)**.
- Maps onto D-AUTONOMY-1 with a seat dimension added: **A** =
  analysis/spec/docs/board reads/card creation/handoffs; **R** = source-of-
  truth edits, Blocked transitions, card splits (per seat); **N** = merge,
  and any action outside a seat's authority.
- **Per-PR gate** (human reviews the PR before merge), not per-edit.

---

## Adaptation profile (v0.7)

Keeping the sibling plugins and using horizontal agents removes both v0.6
supersessions. What remains:

- **3 new ADRs** — 0029 (agent seats at the plugin layer; narrow I-3
  supersession), 0030 (seat-dimension autonomy; supersedes ADR-0006), 0031
  (`handoff_card` as a ninth protocol action; extends ADR-0025).
- **3 new skills**, 13 small skill edits, 1 skill untouched.
- **1 additive audit column**, 1 new board field, 2 new scripts.
- **No supersession of** ADR-0003, ADR-0004, ADR-0007, ADR-0008, ADR-0009,
  ADR-0026. Compare `02-agent-team-evaluation.md`'s eight-ADR list — that
  was written under the v0.6 assumptions.

**Reused untouched:** Kanban Protocol, claim primitive, one-card-one-worktree,
PR contract, 6-state machine, WIP formula, audit write path, setup-stages
engine, hook intent injection, `common.sh`, and both sibling plugins.

---

## Your exact words (running log)

- (v0.1) "use this codebase to build agents team of software engineer teams (that some are pm some are system architecturer, etc)"
- (v0.1) "use this repo as the basic basement, i could do any modifications"
- (v0.1) "check if this repo is available to this, what is the flaw you see, how can we do to achieve our goal"
- (v0.1) "write a doc to help me understand and trace the codebase easily"
- (v0.1) "write a section [of] reasons or flaws that make this repo not suitable for my goal"
- (v0.1) "write a doc … describ[ing] my goal, i will check and then ask you to check and modify my goal"
- (v0.2) "the use case is on dada dashboard (with UI and data source), the team must have system analyst, system architecturer, RD (TDD flow), QA engineer, system OPS engineer (can do later)"
- (v0.3) "all the roles are agents, i think we can do one team first, then try team of teams, and for security role i think we can do with QA first, and a different security role can do later."
- (v0.4) "for human i think just like claude code, when need to modify code it needs human review, and it can still write spec and other relative doc first then implement"
- (v0.5) "i think run in claude code is better (act as a plugin) but as a whole different orchestrator sounds cool, list as do it later"
- (v0.6) "what does it mean to keep superpower and gstack ????? does it mean it using these two skills in the repo ? but i don't want this / we have have deeper hierarchy, i want it to work like a engineer team in a company"
- (v0.7) "for now keep superpowers + gstack for my goal"
- (v0.7) "but it is work in github board, can we use horizontal agents for now ?"
- (v0.7) "write documents to tell me how to implement"

> Note: "dada dashboard" is read as **data dashboard**.

---

## Open questions

**All blockers resolved.** Remaining items are build details with working
defaults recorded in `03`–`06`; change them if you disagree.

| # | Question | Working default | Where |
|---|---|---|---|
| 1 | Coordination backend | GitHub Projects v2 | `03` § 3 |
| 2 | Always-on / scheduled? | Human-launched in Phase 1; cron (ADR-0028) in Phase 2 | `03` § 6 |
| 3 | Scale & deployment | One machine, 5 seats, concurrency 2 | `06` § 8 |
| 4 | Deliverable shape | PRs primarily; specs/docs/configs also via `authoring-spec` | `03` § 4 |
| 5 | Governance ceremony | Keep it — pragmatic fork keeps ADRs for supersessions | `04` § 9 |
| 6 | Success criteria | The Card 24 golden path | `04` § 7 |
| 7 | Where the dashboard lives | A **separate** product repo; the fork is installed into it | `04` § 0.2 |

---

## What success looks like

A working **Phase 1 team** running as a Claude Code plugin: an **analyst**
agent intakes *"show revenue by region, last 30 days"* and hands it up; the
**architect** agent writes the spec and decomposes it into INVEST cards and
hands them down; the **EM** agent dispatches; **RD** agents claim cards and
deliver UI + data-connector code via TDD, then hand off to **QA**; the **QA**
agent runs functional, UI, data-correctness and security passes, writes a
verdict, and either bounces the card back to RD or opens the merge gate; a
**human** verifies the `## Human Verification TODO` and merges.

Every handoff is a legal move on a matrix, every mutating action is
classified and audited with its seat, and one SQL query reconstructs any
card's path through the org. Phase 2 adds OPS and a dedicated security seat
by editing three matrices; Phase 3 adds teams the same way.

---

## Change log

- **v0.1 (2026-07-21)** — initial draft from the conversation.
- **v0.2 (2026-07-21)** — confirmed use case (data dashboard) + roles.
- **v0.3 (2026-07-21)** — all roles are agents; one team → team-of-teams;
  security folded into QA now, dedicated later. Added Phasing.
- **v0.4 (2026-07-21)** — human reviews code + merges; spec-first autonomous
  upstream. Per-PR gate default.
- **v0.5 (2026-07-21)** — runtime = Claude Code plugin (Path A); standalone
  orchestrator (Path B) deferred.
- **v0.6 (2026-07-21)** — proposed dropping `superpowers` + `gstack` and a
  deeper hierarchy; flagged two blockers; framed the work as a heavy fork.
- **v0.7 (2026-07-28)** — **FINALIZED.** Sibling plugins **kept** (ADR-0004
  stands). Org chart confirmed (EM → analyst + architect → RD + QA).
  Topology = **horizontal agents on the board**. Fork posture = pragmatic
  internal fork. **Corrected the v0.6 claim that ADR-0008 could be
  superseded** — `max_depth=1` is a host constraint, not a plugin policy.
  Net effect: back to a role-layer extension. Design in `03`, plan in `04`,
  file map in `05`, runbook in `06`.
