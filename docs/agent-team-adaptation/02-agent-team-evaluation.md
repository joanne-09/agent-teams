# 02 — Agent-team adaptation evaluation

> Answers your three questions: (1) Is this repo suitable as the base for
> building a multi-agent software-engineering team (PM / system architect /
> QA / security / developers)? (2) What flaws/gaps do I see? (3) How do we
> achieve the goal?
>
> Grounded in first-hand reading of the spec, ADRs, skills, scripts, and
> hooks at **v0.7.0** (2026-07-21). No code was modified to produce this.
> Start with [`01-codebase-guide.md`](./01-codebase-guide.md) if you need
> orientation first.

> ## ⚠ Partially superseded — read this first
>
> This evaluation was written against the **v0.6** goal (drop
> `superpowers` + `gstack`; possibly supersede ADR-0008). The goal is now
> **v0.7** and two of those premises reversed, so parts of Q3 and the
> ADR-supersession list overstate the work:
>
> | This doc says | v0.7 reality |
> |---|---|
> | ~8 ADRs to supersede | **3 new ADRs** (0029/0030/0031). ADR-0003, 0004, 0007, 0008, 0009, 0026 are all untouched. |
> | "replace the 14-skill catalog" | **3 new skills, 13 small edits.** Keeping the sibling plugins removed the rest. |
> | Supersede ADR-0008 for deep hierarchies (Step 5c) | **Not possible.** `max_depth=1` is a host constraint on both platforms, not a plugin policy — see `00-goal.md` § "The ADR-0008 correction". |
> | ~60% of the repo is "replace" | Closer to **~10%**, under the v0.7 decisions. |
>
> **Still fully valid and worth reading:** Q1 (what you get for free / what
> you don't), the *case against* section, and Q2's severity-ranked gap list
> — those are observations about the repo, not about the plan.
>
> The current design is [`03-target-architecture.md`](./03-target-architecture.md).

---

## TL;DR verdict

**Yes, suitable as a base — with clear qualifications.** This is one of the
more thought-through "make parallel AI behave like a real team" substrates
you'll find: a backend-agnostic coordination contract (Kanban Protocol), a
clean parallelism primitive (git-push-lease claim + one-card-one-worktree),
a real governance lattice (D-AUTONOMY-1 A/R/N + audit log), and a
self-healing bootstrap engine. **But it is built around a specific thesis** —
*one human architect + N parallel implementer agents, where human attention
is the bottleneck* — and a **strict 2-role model** (Producer/Consumer).

So: **"a PM/architect/QA/security/dev agent team" is not a configuration of
board-superpowers — it is an extension.** You reuse the scheduling/governance
substrate essentially as-is, and you **replace the role layer** (2 roles → N
roles), **re-derive the skill catalog per role**, **extend the action_id +
autonomy catalogs**, and **revisit several load-bearing ADRs**.

- **Reusable as-is:** Kanban Protocol, audit log, D-AUTONOMY-1 pattern,
  one-card-one-worktree parallelism, setup-stages engine, hook intent
  injection, `composing-siblings` discipline, `common.sh` helpers.
- **Must replace/extend:** the 2-role model, the 14-skill catalog, the
  action_id catalog, possibly the 6-state machine, the entry router.
- **Must revisit (ADR supersessions):** ADR-0006 (team/role-layer overrides),
  and conditionally ADR-0008 (deep hierarchies), ADR-0007 (daemon/concurrency),
  ADR-0026 (multi-kanban), ADR-0009 (multi-writer audit), ADR-0003
  (cross-machine), ADR-0004 (only if you drop superpowers/gstack).

---

## The decision that changes everything — answer this first

Two forks determine the entire workplan. I've picked sensible defaults
(marked **⭐**) and the rest of the doc assumes them, flagging where the
other choices diverge.

### Fork 1 — Runtime model

- **⭐ A) Stay on Claude Code (+ Codex CLI) as the host; extend the plugin.**
  Matches how it's built. You inherit the `Agent` tool, agent teams
  (experimental), `SendMessage`, hooks, skill auto-matching, dual-platform
  parity. **Lowest friction; reuses the most.**
- **B) Port the design into a standalone programmatic orchestrator**
  (your own daemon/framework, LangGraph/AutoGen-shaped). Reuse the contracts
  and patterns; rewrite the runtime. Heaviest; loses CC/Codex affordances.
- **C) Use it largely as-is** for the single-architect + N-Consumers topology
  it ships today, and grow organically toward more roles.

### Fork 2 — Autonomy posture

- **⭐ Human-in-the-loop.** Human is the R-class approver; agents propose,
  humans merge. Matches ADR-0006/0007. Lowest risk; what the repo is built for.
- **Fully autonomous team.** Agents approve/merge. Fights ADR-0006 (human
  approval load-bearing) and ADR-0007 (no daemon, no IPC). Requires
  superseding ADRs + an agent-arbitration layer. Higher risk; only if you've
  thought hard about agent self-merge.

---

## Q1 — Is this repo suitable?

### What you get for free (strong, directly reusable)

- **Coordination backbone — Kanban Protocol.** 6 states, 8 actions, 3
  projection forms (A bash / B MCP / C REST). Backend-agnostic: agents
  reason uniformly whether the board is GitHub/Linear/Jira. The "projection
  IS the anti-corruption layer" framing means a second backend drops in
  without re-deriving the ontology (ADR-0025/0027).
- **Clean parallelism primitives.** Atomic `git push --force-with-lease` claim
  (ADR-0002) + one-card-one-worktree (ADR-0003) give N concurrent agents
  **zero HEAD contention with no server-side state**. The claim is essentially
  a distributed lock with an audit trail — exactly what a multi-agent team
  needs. **This is the single strongest part of the repo for your goal.**
- **Governance lattice.** D-AUTONOMY-1 A/R/N matrix + 5-step triage +
  per-`action_id` classification (37 rows today: 14 Producer + 14 Consumer +
  9 Bootstrap) + "default + override + accountability" (P8). A ready-made
  autonomy-escalation protocol. The **two-entry R-class audit rule**
  (propose + resolve) is a clean propose-then-approve primitive.
- **Audit trail as shared memory.** 8-column append-only `AuditEntry` with
  per-action JSONB payload + orthogonal `outcome`/`approval_stage` enums.
  Per-Project scope means cross-agent timeline reconstruction is one SQL
  query. BYO RDBMS (PG/MySQL/SQLite) + jsonl fallback.
- **Skill-graph architecture.** The 3-layer entry/molecular/atomic pattern
  with SPOT-driven atomic derivation is a clean way to encode role behaviors
  without duplication. The v0.7.0 refactor (splitting `managing-board` into
  4 per-routine SKILLs) is exactly the pattern you'd follow per *role*.
- **Always-on primitive — ADR-0028 cron-as-trigger-carrier.** The
  compute/present split lets scheduled agents run between human sessions,
  persist to durable state, and have the next session pick it up — **no
  daemon needed**. This is the closest thing to a self-running agent.
- **Self-healing bootstrap — setup-stages engine.** 22 stages, 5-state
  lifecycle, `generation` bumps trigger upgrade reconvergence (ADR-0012/0014).
  The engine generalizes to onboarding any agent-team infrastructure.
- **Cross-plugin composition discipline — `composing-siblings`.** Encodes
  Mode-2 `max_depth=1` compatibility, procedural-vs-subagent decisions,
  `<plugin>:<skill>` namespace prefix rules. **The most portable atomic** —
  repoint its handoff table and it serves any sibling set.
- **Dual-platform.** CC + Codex parity (with documented CC-only gaps).

### What you do NOT get (the gaps)

- **No first-class multi-role model.** Only Producer/Consumer (2 session
  types). PM/architect/QA/security/dev are not modeled. The human is the
  Architect; specialist viewpoints live in `gstack`/`superpowers`, invoked
  as opaque sibling skills. The repo's I-3 *deliberately flattens* role
  distinctions ("any maintainer = an architect").
- **No deep agent hierarchies under Mode-2.** `max_depth=1` (ADR-0008) means
  a Producer-spawned Consumer **cannot** spawn further subagents. A
  PM→architect→dev→QA→security chain is forbidden as nested subagents.
- **No agent-to-agent messaging (by design).** C-PLUGIN-1 forbids in-memory
  IPC; the contract channel is the **card-thread comment**. Tight synchronous
  choreography is high-latency.
- **No long-running orchestrator (by design).** C-PLUGIN-2 forbids daemons;
  "monitoring" is the preflight-piggyback idiom (run a situation check before
  the next architect prompt).
- **No agent identity / capability registry / dynamic role assignment.** The
  audit log records `actor_role: producer|consumer` but **not which agent**.
  No auction/bid/load-balancing router; work is assigned by card Status, not
  agent capability.
- **Single-architect assumption.** Multi-architect arbitration isn't modeled
  in the flows or the autonomy matrix (I-3 acknowledges multi-architect but
  doesn't model coordination).
- **Conservative concurrency default.** C-PLUGIN-3 default = 1 serial
  (tunable, but the default blocks parallelism out of the box).
- **SQLite single-writer.** Fine for solo architect; won't survive a
  multi-agent team — migrate to PG/MySQL when the 2nd concurrent writer
  appears (ADR-0009).
- **Cross-machine wake-up unsupported (TBD-1).** v1 Mode-2 is single-machine.
- **Permanent superpowers+gstack dependency.** ADR-0004 makes them hard
  runtime deps. If you don't want those disciplines, you fight a core premise.
- **Plugin-shaped, not a standalone runtime.** Loaded into a CC/Codex session;
  not a programmatic agent framework (no in-process graph runtime).

### Verdict

**Suitable as a base — yes, especially for the substrate.** If you wanted a
ready-made multi-role agent team out of the box, this isn't it. If you wanted
a rigorous governance + scheduling foundation to build one on — with a
battle-tested coordination contract, parallelism primitive, audit trail, and
autonomy model — this is a strong choice and saves you from re-deriving the
hard parts.

---

## The case against — reasons this repo may NOT be suitable for your goal

> The verdict above is "yes, as a base." To keep this honest, here is the
> case *against*. If any of the **fundamental mismatches** below match your
> goal, this is likely the wrong starting point and a purpose-built
> multi-agent framework will be less total work. The **conditional
> mismatches** make it unsuitable for a *specific shape* of goal unless you
> accept the named trade-off. This section is deliberately distinct from
> Q2 (which lists flaws *to fix if you proceed*); this one lists reasons
> *not to proceed at all*.

### Fundamental mismatches — if these are true for you, walk away

1. **You want a multi-agent *runtime*, not a single-session plugin.**
   board-superpowers is a plugin loaded into one Claude Code / Codex session
   that routes *that session* into one of two roles. There is no "team of
   agents" at runtime — there is one session at a time, plus optionally
   one-deep subagents (Mode-2). If your mental model is a system where N
   agents coexist, message each other, and coordinate as peers (AutoGen /
   CrewAI / LangGraph / Swarm shape), this is the wrong starting point. You
   would be *extracting patterns*, not using the system.

2. **The repo is philosophically committed to *not* modeling roles.** I-3
   states "board-superpowers does not model role / team / permission
   concepts at the plugin layer — those live in GitHub." Role flattening is
   a deliberate premise, not an oversight. Your goal — PM / architect / QA
   / security / dev as *distinct agents* — runs directly *against* the
   repo's stated philosophy. You'd be building the one thing the maintainer
   explicitly chose not to build.

3. **It is locked to a human-in-the-loop thesis.** Every load-bearing
   mechanism — preflight-piggyback, R-class approval gates, "humans merge,
   agents propose" (P6, ADR-0006 row 12 = N) — optimizes for "human
   attention is the bottleneck" (P1). If your goal is a more *autonomous*
   team where agents coordinate among themselves with less human
   gatekeeping, these mechanisms are friction to be disabled, not features
   to be reused. You'd be superseding the very premises that justify the
   repo's existence.

4. **Composition is permanently locked to `superpowers` + `gstack`
   (ADR-0004).** The plugin refuses to run without them, and the repo
   explicitly refuses a methodology-extension marketplace (non-goals). If
   your team doesn't want those specific disciplines, or wants its own,
   there is no plug-in point short of forking — and forking a hard
   dependency is a maintenance trap.

5. **~60% of the repo is "replace," not "reuse."** The implementation
   survey's own estimate: the 14-skill catalog, the 2-role model, the
   6-state machine, the GitHub-Project-specific scripts, and the 22
   bootstrap stages are all board-superpowers-specific and would be
   rewritten. The honest question is whether the ~40% you keep
   (`common.sh` helpers, the audit write path, the hook architecture, the
   setup-stages *engine*, the classifying/auditing *pattern*) is worth the
   constraints you inherit. For a purpose-built multi-agent team, a
   purpose-built framework is plausibly *less* total work than replacing
   60% of this one — and you'd carry none of the constraints below.

### Conditional mismatches — unsuitable for a specific goal shape

6. **No agent-to-agent communication.** C-PLUGIN-1 forbids in-memory IPC;
   the only contract channel is a GitHub card-thread comment read on the
   next session. A team where PM, architect, dev, QA, and security cannot
   talk to each other in real time — only by writing card comments and
   waiting — is not how most people picture an "agent team." If your work
   needs live collaborative design or debugging, the latency is likely
   unacceptable. (The experimental `SendMessage` / agent-teams surface is
   CC-only, explicitly non-load-bearing, and flagged unstable — not a
   foundation to build on.)

7. **No persistent agent identity or shared working memory.** Agents are
   ephemeral sessions, not long-lived teammates. Beyond the append-only
   audit log and the board, there is no blackboard / shared in-flight state
   for partial findings, drafts, or intermediate artifacts. If your team
   needs shared transient memory, this substrate has no surface for it.

8. **`max_depth=1` caps topology at depth-2.** Hierarchical delegation
   (PM → tech-lead → dev → QA → security) is forbidden as nested
   subagents. The queue-based-handoff workaround (Q3 Step 5) works, but it
   is a *workaround for a constraint*, not native support — and it pushes
   all coordination back through high-latency board state.

9. **GitHub-centric at v1.** Truth lives on a GitHub Project (Form A is
   the only shipped projection; Linear/Jira are "expected in v1.x"). If
   you don't want to run coordination through GitHub Issues/Projects —
   e.g., you want an in-process task graph — GitHub is effectively
   mandatory today.

10. **The lifecycle is PR-delivery-shaped.** The entire model (card →
    claim → worktree → PR → merge) assumes the team's output is mergeable
    PRs against a git repo (invariant I-1: one card = one session = one
    PR). If your "software-engineering team" also produces exploration,
    research, ops, or non-PR deliverables, this lifecycle is a poor fit
    and will fight you.

11. **Single-machine at v1.** Cross-machine wake-up is unsupported
    (ADR-0003 TBD-1). If "team" means agents on multiple machines or
    containers, v1 doesn't support it without superseding ADR-0003.

12. **Multi-agent concurrency hits immediate walls.** SQLite single-writer
    (ADR-0009) and C-PLUGIN-3's default concurrency = 1 serial both bite
    on day one of having >1 concurrent agent. Fixable, but it means the
    "out of the box" experience is effectively single-agent.

### When you should probably choose something else instead

Walk away from board-superpowers as a base and pick a purpose-built
multi-agent framework (or build directly on the Claude Code `Agent` /
agent-teams primitives) if **any** of these is true:

- You want peers that message each other in real time (not via card comments).
- You want a true multi-agent *runtime* with N coexisting agents, not a
  routing plugin for one session at a time.
- You want full autonomy without human merge/approval gates.
- You don't want the `superpowers` + `gstack` hard dependency.
- You don't want GitHub as the coordination substrate.
- Your team's deliverables are not predominantly mergeable PRs.
- You want to run agents across multiple machines now.
- You want to avoid carrying 28 ADRs / 8 contract files / a change-impact
  matrix / a skills-edit gate to get the parts you actually need.

Conversely, **stay** with board-superpowers as a base if you specifically
want its **governance posture** (audit-every-mutation, A/R/N autonomy,
human-merge-gate), its **Kanban-over-GitHub coordination model**, and you're
willing to extend the role layer and supersede a few ADRs to get there. The
substrate is genuinely good — it's just built for a more specific shape than
"a multi-role agent team," and the case against is that the shape it *is*
built for may not be yours.

---

## Q2 — Flaws / gaps (severity-ranked)

Ranked by how much they actually block the goal.

### Blocking — must solve to get a multi-role agent team

1. **2-role ceiling.** The entry router, the 4 Producer routines, and
   `consuming-card` all assume Producer-or-Consumer. No PM/architect/QA/
   security/dev as distinct agents. → *Replace the role layer (Q3 Step 1–2).*
2. **`max_depth=1` (Mode-2).** Deep delegation chains can't run as nested
   subagents. → *Use queue-based handoffs (state on the board between one-deep
   spawns), or supersede ADR-0008 (Q3 Step 5).*
3. **No agent identity / role-assignment layer.** You can't today say
   "agent-3 is the QA agent; route security-flagged cards to agent-5," and
   the audit log can't reconstruct which agent did what beyond
   producer/consumer. → *Add `actor_id` + a capability-aware router
   (Q3 Step 4).*

### Constraining — workable but costs design

4. **C-PLUGIN-1 (no IPC).** All inter-agent coordination via durable state
   (GitHub/state.yml/audit). High-latency; no shared object graph. Fine for
   loose choreography; painful for tight negotiation.
5. **C-PLUGIN-2 (no daemon).** No always-on orchestrator agent. Workaround:
   lean on ADR-0028 cron-J2, or explicitly supersede with a daemon-permitted
   mode.
6. **Human approval is load-bearing (ADR-0006).** Merge, source-of-truth
   edits, Blocked transitions, card splits are R-class. `autonomy_overrides`
   exist at user+project layers but **not at team/role layer** — so you can't
   scoped-promote R→A for "the QA agent can auto-approve test-only changes."
   → *Add a team/role layer to overrides (Q3 Step 3).*
7. **6-state machine is kanban-shaped.** A multi-role team often wants
   role-specific review states ("in PM review", "in architect review", "in
   QA", "in security"). The flat 6-state machine + flat Card hierarchy
   (ADR-0026) doesn't model that. → *Extend with role-specific labels/states
   or move to a richer task-graph.*
8. **Single-architect assumption.** Multi-architect / multi-LLM-architect
   teams need an ownership/arbitration layer the protocol doesn't specify.
9. **Conservative concurrency default (C-PLUGIN-3 = 1).** Must tune upward
   for parallel team execution.

### Operational — house that grows with the team

10. **SQLite single-writer** → migrate to PG/MySQL for multi-agent.
11. **Cross-machine wake-up unsupported (TBD-1)** → distributed-agent teams
    across machines need ADR-0003 supersession.
12. **Permanent superpowers+gstack dependency (ADR-0004)** → if your team
    doesn't want those, you fight a core premise. (Recommend keeping them —
    they're high quality and composition is the repo's strength.)
13. **Plugin-shaped runtime** → if you want a standalone daemon-style system,
    this isn't that; choose Path B (port).
14. **Governance/contract ceremony is heavy.** 28 ADRs, 8 contract files, 14
    skills, a change-impact matrix, same-PR doc rules. Great for a serious
    product; possibly more than a lightweight internal team wants to carry.
    (You can slim this for an internal fork — but it's load-bearing for the
    repo's quality, so trim deliberately.)
15. **Multi-kanban runtime carve-out.** ADR-0026 hard-fails on >1 kanban at
    v1.0 — so per-team specialized kanbans (one for security, one for QA)
    wait for v1.x runtime support. Labels can approximate in the meantime.

### Not actually flaws — deliberate refusals (don't "fix" these)

- **No sprint / standup / story points** — deliberate AI-native concept
  hygiene (P2b, ADR-0010). The repo argues each becomes ceremony when
  throughput scales 100× while attention doesn't. Don't re-add them without
  an ADR.
- **Agents can't self-merge** — deliberate (P6, ADR-0006 row 12 = N). Keep
  this unless you've thought hard about agent self-merge safety.
- **No hosted control plane / no owned state** — the core differentiator
  (P2a/P4a). Don't add one; it collapses the repo's reason to exist.

---

## Q3 — How to achieve the goal

### Recommended path — A: stay on Claude Code as host, extend the role layer

Reuses the most, fights the fewest premises. The pattern to mirror
throughout is the **v0.7.0 refactor**: the old `managing-board` mega-SKILL
was split into 4 per-routine SKILLs (`briefing-daily`, `intaking-requirement`,
`reviewing-pr-queue`, `triaging-board`). Do the same **per role**.

**Step 0 — Decide the two forks above.** The rest assumes Path A + human-in-the-loop.

**Step 1 — Map roles onto the existing surface, then extend.** Don't port the
14-skill catalog blindly; re-derive per role using
`FEATURE_DESIGN_METHODOLOGY.md`'s 3-stage pipeline (user-journey enumeration
→ J1–J5 requirement dimensions → ROI function). Initial mapping:

| Role | Reuses today | New / extended work |
|---|---|---|
| **PM** | `intaking-requirement` (intake), `briefing-daily` (orientation) | PM-specific intake criteria; stakeholder routing |
| **System architect** | `decomposing-into-milestones`, `gstack:/plan-eng-review` | Architecture-decision routing; ADR-authoring routine |
| **Developer** | `consuming-card` (the whole 23-node lifecycle) | Mostly as-is; possibly per-language variants |
| **QA** | `reviewing-pr-queue`, `gstack:/qa`, `gstack:/review` | A **"QA Consumer" variant** that owns a card end-to-end (today QA is a verification *step* inside a dev Consumer, not a role) |
| **Security** | `gstack:/cso`, `enforcing-pr-contract` | A **"Security Consumer" variant** + security-flagged routing |
| **Reviewer / merge-gate** | `reviewing-pr-queue`, the human Architect's job today | If you want an agent reviewer, that's a new R-class approver role — revisit ADR-0006 |

**Step 2 — Generalize the entry router from 2-role to N-role.**
`using-board-superpowers` currently routes Producer-vs-Consumer. Extend the
routing tree to role-tagged routes, and add a **role-assignment layer**
(which agent plays which role — see Step 4). Keep the 3-step reliable gate
(dep check → state probe → marker consumption).

**Step 3 — Extend the action_id catalog + autonomy matrix.** Today: Producer
1–14, Consumer 100–113, Bootstrap 200–208. Add role-specific ranges (e.g.,
PM 300–309, architect 310–319, QA 320–329, security 330–339) and re-populate
`classifying-actions`. **Crucially, add a team/role layer to
`autonomy_overrides`** so e.g. "the QA agent can auto-approve test-only
changes" — this is the key governance extension and requires an **ADR-0006
supersession**.

**Step 4 — Add agent identity + a capability-aware router.** Extend
`AuditEntry` with an `actor_id` column (which agent). Add a capability
registry (which agent can play which role / handle which card type) so the
router assigns work by **capability, not just card Status**. The J1–J5
session-agent protocol already reserves space for new roles — *declare value
distributions, don't redefine the axes.*

**Step 5 — Solve deep hierarchies without fighting `max_depth=1`.** Three options:
- **(a) Stay depth-2.** Producer (PM/architect) → Consumer (dev); route
  QA/security as *verification steps inside the dev Consumer* (this is how it
  works today). Simplest; keeps ADR-0008 intact.
- **(b) Queue-based handoff (recommended).** Persist state to the card body /
  audit log between one-deep spawns: Producer spawns a dev Consumer → it
  finishes → Producer spawns a QA Consumer for the same card → etc. State
  lives on the board, not in a nested call stack. **This is the
  board-superpowers-idiomatic answer** and sidesteps `max_depth=1`.
- ~~**(c) Supersede ADR-0008** with a deeper-topology mode.~~ **Struck at
  v0.7 — not achievable.** `MULTI_AGENT_DEVELOPMENT.md:42` records
  "subagents cannot spawn subagents; agent-teams cannot nest teams" as a
  **host** property of both Claude Code and Codex. An ADR cannot grant what
  the runtime refuses. Option (b) is not a workaround for (c); it is the
  only mechanism there ever was.

**Step 6 — Always-on / scheduled agents via ADR-0028 cron-J2.** For agents
that should run between human sessions (overnight batch, periodic triage,
security scans), use the cron-as-trigger-carrier pattern with the
compute/present split — no daemon needed, stays within C-PLUGIN-2. This
re-opens ADR-0011's deferred routines (overnight batch F-07, stale-session
detection F-11, triage ladder F-10) on demand-pull.

**Step 7 — Tight agent-to-agent choreography (if needed).** C-PLUGIN-1
forbids in-memory IPC as a *correctness* channel, but on the CC fast path
the experimental `SendMessage` + agent teams
(`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`) can be a *latency optimization* —
**never the only signal.** Per `MULTI_AGENT_DEVELOPMENT.md`, the portable
fallback is board-state + transcript reachback. Use agent teams for
peer-to-peer messaging if you accept the experimental-stability caveat
(re-check on stable release before shipping user-facing behavior on it).

**Step 8 — Backend.** If the team doesn't use GitHub Projects, add an
`operating-kanban/references/<backend>.md` projection (Form B/C is already
designed for this). Or keep GitHub Projects — path of least resistance.

**Step 9 — Multi-agent audit concurrency.** Migrate the audit DB from SQLite
to Postgres/MySQL **before the second concurrent writer appears** (ADR-0009).
The audit write path (`audit-log-write.sh`) is reusable as-is; only the
default scheme changes.

**Step 10 — Bootstrap the team.** Repopulate `stages-registry.yml` with
agent-team stages (LLM provider config, agent persona loading, tool
permission grants, team roster registration, capability manifest). The
setup-stages engine is reusable; the 22 board-superpowers stages are what
you replace.

### Reuse map — keep vs replace vs revisit

| Keep essentially as-is | Replace / repopulate | Revisit (ADR supersession) |
|---|---|---|
| `scripts/lib/common.sh` path/venv/audit/routing helpers | 14-skill catalog → per-role SKILLs | ADR-0006 (team/role override layer) |
| `audit-log-write.sh` + audit schema (add `actor_id`) | action_id catalog (add role ranges) | ADR-0008 (only if deep nesting needed) |
| Hook architecture (`session-start.sh` intent injection) | entry router (2-role → N-role) | ADR-0007 C-PLUGIN-2 (only if daemon needed) |
| setup-stages engine (`stages_lib/`) | `stages-registry.yml` contents | ADR-0007 C-PLUGIN-3 (tune concurrency) |
| `composing-siblings` pattern (repoint handoff table) | 6-state machine (maybe role-specific review states) | ADR-0026 (multi-kanban runtime, if per-team kanbans) |
| D-AUTONOMY-1 A/R/N pattern | D-AUTONOMY-1 rows (add role rows) | ADR-0009 (SQLite→PG/MySQL for concurrency) |
| Kanban Protocol (6 states, 8 actions, 3 forms) | PR contract *content* (keep 3-section shape) | ADR-0003 (cross-machine, if distributed) |
| one-card-one-worktree parallelism | role-assignment / capability router (new) | ADR-0004 (only if dropping superpowers/gstack) |

### ADRs you'd likely supersede

| ADR | Why | Action |
|---|---|---|
| 0006 | Need team/role-layer `autonomy_overrides`; possibly R→A for agent approvers | New ADR extending the override schema |
| ~~0008~~ | **Struck at v0.7.** `max_depth=1` is a host constraint, not a plugin policy — no ADR can lift it | None. Use horizontal agents + board handoffs |
| 0007 (C-PLUGIN-2) | Only if you need an always-on orchestrator daemon | New ADR permitting a daemon mode (prefer cron-J2 first) |
| 0007 (C-PLUGIN-3) | Parallel team execution needs >1 default concurrency | Tune the concurrency parameter (may not need an ADR) |
| 0026 | Per-team specialized kanbans | Wait for v1.x runtime, or approximate with labels |
| 0009 | Multi-agent concurrent audit writers | Migrate to PG/MySQL (operational; may need an ADR for default change) |
| 0003 | Distributed agents across machines | New ADR for cross-machine wake-up |
| 0004 | Only if you drop superpowers/gstack | New ADR; strongly consider keeping them instead |

### Alternative path — B: port the design into a standalone orchestrator

If you want a programmatic, daemon-style, in-process graph runtime, reuse the
**contracts and patterns** — Kanban Protocol, D-AUTONOMY-1, audit schema +
two-entry rule, 3-layer skill graph, setup-stages lifecycle, hook intent
injection, `composing-siblings` discipline — and rewrite the runtime. You
lose CC/Codex affordances (Agent tool, hooks, skill auto-match, dual-platform
parity) and the experimental agent-teams surface; you gain full control of
execution, IPC, and topology. **Heaviest path; only choose it if the plugin
shape is genuinely wrong for your target.**

### Alternative path — C: use as-is, grow organically

Run the single-architect + N-Consumers topology it ships today (it works —
it's dogfooded on its own repo). Treat specialist "roles" as verification
*steps* inside the dev Consumer (already how QA/security work via gstack).
Add roles only when real demand appears (mirroring ADR-0011's demand-pull
re-opening triggers). **Lowest effort; slowest to a true multi-role team.**
A good way to learn the substrate before committing to Path A.

---

## Decisions you need to make (so the plan can be refined)

These forks materially change the workplan. Defaults are marked ⭐ above; tell
me where you differ.

1. **Runtime** — Path A (extend on Claude Code), B (port to standalone), or C
   (as-is + grow)?
2. **Autonomy posture** — human-in-the-loop (keep merge/approval human) or
   fully autonomous (agents approve/merge)?
3. **Roles** — which roles, exactly? (PM, system architect, dev, QA, security,
   reviewer, …?) And is the "architect" a **human or an agent**?
4. **Backend** — GitHub Projects (easy) or Linear/Jira/other?
5. **Hierarchy depth** — depth-2 (Producer→Consumer) is free; deeper needs
   queue-based handoffs or an ADR-0008 supersession. How deep?
6. **Always-on?** — if yes, lean on ADR-0028 cron-J2 (no daemon) vs. supersede
   C-PLUGIN-2 (daemon allowed)?
7. **Keep superpowers + gstack?** — recommended yes; if no, you supersede
   ADR-0004.
8. **Scale** — one machine (v1 supports) or distributed across machines
   (needs ADR-0003 work)?
9. **How much ceremony?** — keep the ADR/contract discipline (good for a
   serious product) or slim it for an internal tool?

---

## Cross-reference

- Repo layout, reading order, session flow, where code lives, contracts, ADR
  map, glossary: [`01-codebase-guide.md`](./01-codebase-guide.md).
- Multi-agent surface (Agent tool, agent teams, `SendMessage`, Mode-2,
  `max_depth`): [`../../MULTI_AGENT_DEVELOPMENT.md`](../../MULTI_AGENT_DEVELOPMENT.md).
- Positioning / premises / non-goals: [`../../docs/architecture/0001-positioning.md`](../../docs/architecture/0001-positioning.md).
- Skill-authoring methodology: [`../../SKILL_DEVELOPMENT.md`](../../SKILL_DEVELOPMENT.md)
  and [`../../FEATURE_DESIGN_METHODOLOGY.md`](../../FEATURE_DESIGN_METHODOLOGY.md).

---
*Analysis only — no code modified. Reflects v0.7.0 as of 2026-07-21. Verify
ADR numbers, skill names, and file paths against the repo before relying on
them in implementation.*