# 03 — Target architecture (the design you are implementing)

> **Status: design, v0.7 decisions locked.** This is the *what you are
> building* document. [`04-implementation-plan.md`](./04-implementation-plan.md)
> is the *in what order*; [`05-file-change-map.md`](./05-file-change-map.md)
> is the *which files*; [`06-operating-runbook.md`](./06-operating-runbook.md)
> is the *how to run it once built*.
>
> Grounded in a first-hand read of the spec, ADRs, skills, scripts and hooks
> at **v0.7.0**. Where a claim needs verification against a live `gh` /
> Claude Code install, it is marked **[verify]**.

---

## 1. What your v0.7 answers changed

Four decisions landed. Two of them reverse the v0.6 framing in
[`00-goal.md`](./00-goal.md), and the effect is large: the adaptation goes
back from a **heavy fork** to a **role-layer extension**.

| Decision | v0.6 assumption | v0.7 answer | Effect |
|---|---|---|---|
| Sibling plugins | Drop `superpowers` + `gstack`; supersede ADR-0004 | **Keep them** | ADR-0004 stands. No discipline skills to write. TDD/QA/security/review keep coming from the siblings. `composing-siblings` stays load-bearing. **Removes ~6 new skills and the largest risk item.** |
| Org chart | proposed | **EM → {analyst, architect}; architect → {RD, QA}** | Becomes an *authority + routing* model on the board (§5), not a call stack. |
| Topology | queue-based handoffs vs supersede ADR-0008 | **Horizontal agents, coordinated on the GitHub board** | ADR-0008 untouched. Nothing to supersede. §6. |
| Fork posture | — | **Pragmatic internal fork** | Keep substrate + governance. ADRs only for supersessions. New surfaces are CC-only; existing dual-platform code is left alone, not extended. |

### The correction that made the topology question easy

`00-goal.md` v0.6 framed `max_depth=1` as a board-superpowers constraint you
could supersede with an ADR. It is not.
[`MULTI_AGENT_DEVELOPMENT.md`](../../MULTI_AGENT_DEVELOPMENT.md) line 42
records it as a **host** property of both platforms:

> Child can spawn further children — **No** — subagents cannot spawn
> subagents; agent-teams cannot nest teams. *Portable (negative)*.

Writing an ADR does not change what Claude Code permits. So an
EM → architect → RD nested call stack was never available at any price.
Your instinct — *"it is work in a GitHub board, can we use horizontal
agents"* — is the correct and in fact the **only** answer. §6 shows how the
company hierarchy survives intact anyway.

---

## 2. The design in one sentence

**A role is a seat on the board, not a new kind of session:** add one
orthogonal `Role` field to the GitHub Project, define a legal-handoff matrix
between seats, make the autonomy matrix role-aware — and every one of the 14
existing skills keeps working, with three new molecular skills covering the
work no current role does.

---

## 3. The core move — `Role` is an orthogonal board field

The temptation is to model roles as new Statuses (`In Architect Review`,
`In QA`, `In Security`). **Do not.** New statuses break the 6-state machine,
every projection, `board-canon`, `claim-card.sh`, `transition-card.sh`, the
WIP formula, and ADR-0026 — for no gain.

Instead add **one single-select field** to the GitHub Project, orthogonal to
Status:

```
Status  answers  "where in the lifecycle is this card?"   (6 values, unchanged)
Role    answers  "whose turn is it right now?"            (6 values, new)
```

| Field | Values |
|---|---|
| `Status` (existing) | `Backlog` · `Ready` · `In Progress` · `Blocked` · `In Review` · `Done` |
| `Role` (new) | `analyst` · `architect` · `rd` · `qa` · `em` · `human` |

A card is the pair **(Status, Role)**. A **handoff** is a `Role` flip. A
lifecycle move is a `Status` flip. They are independent, and most real
transitions move exactly one of them.

### A card's life through the team

| # | Actor | Status | Role | What happened |
|---|---|---|---|---|
| 1 | analyst | `Backlog` | `architect` | Requirement intaken and shaped; handed up for decomposition |
| 2 | architect | `Ready` | `rd` | Decomposed, INVEST-checked, spec pointer written; queued for build |
| 3 | rd | `In Progress` | `rd` | Claimed (branch push + worktree) |
| 4 | rd | `In Review` | `qa` | PR opened with the three-section contract; handed to QA |
| 5 | qa | `In Review` | `human` | QA + security passes green; handed to the merge gate |
| 6 | human | `Done` | — | Human verified the `## Human Verification TODO` and merged |

Failure paths use the same two dials and nothing else:

| Situation | Status | Role |
|---|---|---|
| QA rejects the PR | `In Progress` | `rd` |
| RD hits an external blocker | `Blocked` | `architect` (its lead) |
| Architect cannot resolve it | `Blocked` | `em` |
| Requirement is under-specified | `Backlog` | `analyst` |

**Zero new statuses. Zero changes to the state machine.** This is the single
highest-leverage decision in the design — it is why the other 90% of the
repo survives untouched.

### Why not GitHub's native `Assignees` field?

Because I-3 (`07-cross-cutting-invariants.md`) reserves GitHub user identity
for *humans*, and F-C13 stakeholder routing depends on `Card.assignees`
staying comment-source-agnostic. Overloading `Assignees` with agent seats
would break that invariant for real. A separate field keeps human identity
and agent seats orthogonal — which is also what makes the I-3 supersession
in §12 narrow enough to be safe.

---

## 4. Role → session shape → skills

The repo's Producer/Consumer split is a **session shape**, not a role:

- **Producer-shaped** — long-lived, aggregate view over the board, never
  authors commits, mutates board state.
- **Consumer-shaped** — short-lived, one card, one worktree, one PR.

Your five roles map cleanly onto those two shapes. Note how much is reuse:

| Role | Shape | Reuses today (unchanged) | New work |
|---|---|---|---|
| **EM / Team Lead** | Producer | `briefing-daily`, `triaging-board` | **`dispatching-work`** (new molecular) — read the role lanes, pick what runs next, emit the dispatch queue |
| **System analyst** | Producer | `intaking-requirement` | references only — analyst intake criteria + the handoff to architect |
| **System architect** | Producer **and** Consumer | `decomposing-into-milestones`, `gstack:/plan-eng-review`, `superpowers:brainstorming`, `superpowers:writing-plans` | **`authoring-spec`** (new molecular, Consumer-shaped) — a spec/ADR card that ends in a docs PR |
| **RD** | Consumer | **`consuming-card` entirely, all 23 nodes** — RD *is* today's Consumer | none |
| **QA** | Producer **and** Consumer | `reviewing-pr-queue`, `enforcing-pr-contract`, `gstack:/qa`, `gstack:/cso`, `gstack:/review` | **`verifying-delivery`** (new molecular, Consumer-shaped) — own a QA pass end-to-end, emit a verdict, optionally a test-only PR |

**Three new molecular skills. That is the whole skill delta.** Catalog goes
14 → 17. This is what keeping `superpowers` + `gstack` bought you.

Two roles are dual-shaped, and that is not a defect — it is why `actor_seat`
and `actor_role` stay separate columns in §9. The architect is
Producer-shaped when decomposing a batch and Consumer-shaped when its own
spec card produces a PR.

### Why these three and no others

Applying [`FEATURE_DESIGN_METHODOLOGY.md`](../../FEATURE_DESIGN_METHODOLOGY.md)'s
ROI test — *(capability gap × frequency × failure cost) / (maintenance cost +
routing complexity)*:

- **`dispatching-work`** — capability gap is total. Nothing in the repo picks
  *who* works next; today a human does it. Runs many times a day. Without it
  there is no team, just five disconnected agents.
- **`authoring-spec`** — gap is real. `decomposing-into-milestones` turns a
  design artifact *into cards*; nothing *produces* the design artifact as a
  reviewable deliverable. Your autonomy posture ("agents write specs and
  docs freely, then implement under review") depends on this existing.
- **`verifying-delivery`** — gap is a role/step mismatch. QA today is a
  *step inside* an RD Consumer (`consuming-card` C3/C4). For QA to be a seat
  that can *reject*, the pass must be owned by a separate session that
  cannot be rationalized away by the agent that wrote the code.

Everything else scored below the bar: analyst intake is `intaking-requirement`
with different reference material; RD is `consuming-card` verbatim.

---

## 5. The handoff protocol — how the org chart lives on a board

### 5.1 A ninth Kanban Protocol action

Add `handoff_card` to the eight actions in
`0005-contracts/00-kanban-protocol.md`. This is a protocol **extension**,
not a supersession — ADR-0025 establishes the protocol as the top-level
semantic contract and expects it to grow.

```
handoff_card(card, from_seat, to_seat, reason)
```

Implemented on the v1 GitHubProjectAdapter (Form A) as three steps:

1. set the `Role` single-select field to `to_seat`;
2. `comment_on_card` with a structured handoff note — this is the
   C-PLUGIN-1-compliant contract channel, the thing the receiving agent
   reads on its next session;
3. one audit row (§9).

Status is **not** touched by `handoff_card`. If the lifecycle also moved,
that is a separate `transition_card`. Keeping them separate is what makes
both idempotent and independently auditable.

Rejected alternative: a generic `set_card_field`. The Kanban Protocol is
deliberately semantic rather than an SDK (ADR-0025); a generic field-setter
is an abstraction leak that every future backend would have to emulate.

### 5.2 The authority matrix — this *is* your org chart

Legality of a handoff is *"what is legal"*, so by the atomic-layer boundary
discipline in [`SKILLS.md`](../../SKILLS.md) it belongs in **`board-canon`**,
not `operating-kanban`. Encode exactly this table:

| From ↓ / To → | `analyst` | `architect` | `rd` | `qa` | `em` | `human` |
|---|---|---|---|---|---|---|
| **analyst** | — | ✅ shaped | ❌ | ❌ | ✅ escalate | ✅ question |
| **architect** | ✅ send back | — | ✅ dispatch | ✅ dispatch | ✅ escalate | ✅ question |
| **rd** | ❌ | ✅ escalate | — | ✅ PR ready | ✅ escalate | ❌ |
| **qa** | ❌ | ✅ escalate | ✅ reject | — | ✅ escalate | ✅ merge gate |
| **em** | ✅ | ✅ | ✅ | ✅ | — | ✅ |
| **human** | ✅ | ✅ | ✅ | ✅ | ✅ | — |

Read the ✅s and the reporting lines fall out of them:

- **RD cannot hand to `human`.** Only QA opens the merge gate. That is the
  quality bar, expressed as a refusal.
- **RD escalates to `architect`, never to `em`.** That is "the architect is
  RD's tech lead," expressed as a routing rule.
- **`em` and `human` reach every seat.** That is the top of the org.
- **analyst never reaches `rd`.** Nothing goes to build without passing
  through the architect. That is the design-discipline gate.

An illegal handoff is a **refusal**, not a warning — the same treatment
`decomposing-into-milestones` gives an INVEST violation. This is the
mechanism that makes the hierarchy real rather than decorative.

### 5.3 What the receiving agent actually reads

The card comment written in step 2 is the interface. Fixed shape, so it can
be parsed as well as read:

```markdown
<!-- board-superpowers:handoff -->
**Handoff**: `rd` → `qa`
**Reason**: PR #57 open, three-section contract satisfied, all AC `[x]`
**Needs from you**: UI QA on the revenue chart; card carries `security` label
**Artifacts**: PR #57 · branch `claim/42-revenue-chart`
```

---

## 6. Runtime topology — horizontal agents

**Every agent is a peer at runtime. The hierarchy is authority over board
state, not a call stack.** Nothing nests, so `max_depth=1` never binds.

```
        ┌──────────────── the GitHub Project board ────────────────┐
        │  Card #42 = (Status, Role)  +  handoff comments  +  PRs   │
        └───▲────────▲────────▲────────▲────────▲──────────────────┘
            │        │        │        │        │
        ┌───┴──┐ ┌───┴───┐ ┌──┴──┐ ┌───┴──┐ ┌──┴───┐
        │  EM  │ │analyst│ │arch │ │  RD  │ │  QA  │   ← peer CC sessions,
        └──────┘ └───────┘ └─────┘ └──────┘ └──────┘     own context each
                                       │
                                  (may spawn 1-deep
                                   subagents — the
                                   existing Mode-2)
```

Three consequences worth internalizing:

1. **Org depth is unbounded** because it is board state. You could add
   directors above the EM in Phase 3 with no runtime change at all.
2. **Latency is session-granular.** A handoff is visible to the receiving
   agent when that agent next runs — not instantly. This is C-PLUGIN-1 by
   design and the price of the topology. Live negotiation between roles is
   not on the table; considered handoffs with a durable trail are.
3. **Nothing is experimental.** No `SendMessage`, no agent teams, no
   `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`. The repo's own doctrine
   (`MULTI_AGENT_DEVELOPMENT.md` § 1) forbids depending on those for
   correctness, and this design never needs to.

### Who starts the sessions

Honest answer, because C-PLUGIN-2 forbids a daemon. Three carriers, in
increasing autonomy:

| Carrier | How | When to use |
|---|---|---|
| **Human launch** | `dispatching-work` prints ready-to-paste kick-off prompts; you open terminals | Phase 1. Simplest, and you want to watch the first runs anyway |
| **One-deep subagent** | EM session spawns a role as a subagent via the `Agent` tool and waits | Short passes (a QA verdict, a triage sweep) inside one EM session |
| **cron (ADR-0028)** | Scheduled `claude -p` runs per seat, compute/present split | Phase 2, once you trust the loop unattended |

`dispatching-work` produces the same **dispatch queue** artifact regardless
of carrier — so changing carrier later is a config change, not a redesign.

---

## 7. Role-aware routing — the `[role:<seat>]` token

A session must know which seat it occupies before it can do anything. Reuse
the convention that already works — `consuming-card` triggers on the literal
token `[board-card:#N]`. Add a sibling:

```
[role:rd] [board-card:#42]
[role:qa] review the queue
[role:em] morning briefing
```

The entry skill `using-board-superpowers` parses `[role:<seat>]` first, binds
the seat for the session, and routes within that seat's routine set. Same
carrier works for a pasted root session, an `Agent`-tool prompt, and a cron
`claude -p` invocation — one mechanism, three carriers.

Routing after the seat is bound:

| Seat | Default routine | Also available |
|---|---|---|
| `em` | `briefing-daily` | `triaging-board`, `dispatching-work` |
| `analyst` | `intaking-requirement` | `briefing-daily` (read-only) |
| `architect` | `decomposing-into-milestones` | `authoring-spec`, `intaking-requirement` |
| `rd` | `consuming-card` | — |
| `qa` | `verifying-delivery` | `reviewing-pr-queue` |

**No seat token → today's behavior exactly.** Every existing phrase still
routes as it does now. This keeps the fork usable while half-built, and it
keeps the repo dogfoodable on itself.

---

## 8. Governance — the autonomy matrix gains a role dimension

Today `classifying-actions` is a function of one variable:

```
action_id → A | R | N
```

It becomes a function of two:

```
(action_id, seat) → A | R | N
```

This is the change that turns the org chart from documentation into
enforcement. Representative rows:

| `action_id` | Action | analyst | architect | rd | qa | em | human |
|---|---|---|---|---|---|---|---|
| 1 | Create cards | A | A | ❌ N | ❌ N | A | A |
| 3 | Split card | N | **A** | N | N | R | A |
| 5 | `Backlog → Ready` | N | **A** | ❌ N | N | A | A |
| 6 | `→ Blocked` | R | R | R | R | R | A |
| 8 | Cancel claim | N | R | R (own only) | N | R | A |
| 12 | **Merge PR** | **N** | **N** | **N** | **N** | **N** | ✅ |
| 100 | Claim card | N | A | **A** | A | N | A |

Three properties to preserve:

- **Row 12 is `N` for every agent seat.** P6 and I-2 hold unchanged. Humans
  merge; agents propose. Your v0.4 posture survives verbatim.
- **Row 5 `A` only for architect** is what stops RD marking its own work
  Ready — the hierarchy, enforced.
- **Row 3 promotes R→A for the architect.** Splitting a card is that seat's
  job; leaving it R would make the architect useless without a human.

Implementation is additive: `matrix.md` gains seat columns; a
`seat_overrides:` layer joins the existing user/project layers in
`autonomy_overrides`. Precedence: **project > user > seat > default**. This
is the **ADR-0006 supersession** and the single largest governance change.

### New `action_id` block — 300s

The repo's own precedent (`06-audit-log-schema.md` line 148) is that an
action with identical semantics from a different vantage **reuses its
existing id** with a different actor. Follow it: no per-role duplicate
ranges. Only genuinely new actions get numbers.

| `action_id` | Action | Default class |
|---|---|---|
| 300 | Handoff card to another seat | A |
| 301 | Escalate to lead seat (handoff + `Blocked`) | A |
| 302 | Reject / bounce back to a lower seat | A |
| 303 | Dispatch an agent session (emit kick-off) | A |
| 304 | QA verdict write (pass / fail + evidence) | A |
| 305 | Refuse an illegal handoff | A |

Six rows, not sixty. Everything else — create card, transition, claim,
PR submit — reuses 1–14 / 100–113 with the seat recorded in `actor_seat`.

---

## 9. Audit — one additive column

`actor_role` today carries a **CHECK constraint**
(`audit-schema.sqlite.sql:11`):

```sql
actor_role TEXT NOT NULL CHECK (actor_role IN ('producer','consumer'))
```

Two ways to record seats. Take the second:

| Option | Cost |
|---|---|
| Widen the `actor_role` CHECK to the six seats | Rewrites a constraint, invalidates every existing row's meaning, and destroys the shape/seat distinction that dual-shaped roles (§4) need |
| **Add `actor_seat` as a new nullable column** | Purely additive migration, backward compatible, and keeps *shape* (`producer`/`consumer`) and *seat* (`architect`/`qa`/…) as the two independent facts they actually are |

```sql
ALTER TABLE audit_log ADD COLUMN actor_seat TEXT;   -- NULL = pre-fork rows
```

- Migration `scripts/migrations/audit-v2-to-v3.sh`, mirroring the existing
  v1→v2 pair exactly (`.sh` + `-impl.py`).
- `audit-log-write.sh` gains `--actor-seat`.
- `auditing-actions` payload templates carry the seat.
- The jsonl fallback shape gains the field; `audit-flush-impl.py` passes it
  through.

**`actor_id` (which agent instance) is deliberately deferred.** `session_id`
already uniquely identifies a run, and with one session per seat
`session_id + actor_seat` answers every Phase 1 question. Add `actor_id`
only when a persistent roster appears in Phase 3.

### Stay on SQLite until it complains

`02-agent-team-evaluation.md` § 12 says migrate to Postgres before the
second concurrent writer. That is more conservative than the evidence
requires: audit writes are small and infrequent, and `audit-log-write.sh`
**always exits 0** because failures degrade to a jsonl outbox that flushes
later. A five-agent team writing a handful of rows per card will not
meaningfully contend.

**Signal to watch:** `mode=audit-dead-letter` rows, or a persistent
`audit-pending.sentinel`. When you see either, migrate. Not before — it is
a day of setup you can spend on the team instead.

---

## 10. Skill catalog delta — 14 → 17

| Skill | Layer | Change |
|---|---|---|
| `using-board-superpowers` | entry | **edit** — parse `[role:<seat>]`, route per §7. Body is already at ~225/200 lines; push the seat routing table into `references/routing.md` |
| `dispatching-work` | molecular | **new** — EM's dispatch routine |
| `authoring-spec` | molecular | **new** — architect's spec/ADR-to-PR routine |
| `verifying-delivery` | molecular | **new** — QA's owned verification pass |
| `board-canon` | atomic | **edit** — add the handoff authority matrix + `Role` field to the schema reference |
| `operating-kanban` | atomic | **edit** — add `handoff_card` dispatch + the Form A implementation |
| `classifying-actions` | atomic | **edit** — seat dimension + 300-block rows |
| `auditing-actions` | atomic | **edit** — `actor_seat` in payload templates |
| `composing-siblings` | atomic | **edit** — add the three new skills' sibling handoff points to `handoff-points.md` |
| `briefing-daily` | molecular | **edit** — group by Role lane as well as Status |
| `intaking-requirement` | molecular | **edit** — hand off to `architect` instead of terminating |
| `reviewing-pr-queue` | molecular | **edit** — becomes a QA-seat routine; hand to `human` on pass |
| `triaging-board` | molecular | **edit** — escalate along the §5.2 lines instead of to "the architect" generically |
| `consuming-card` | molecular | **edit, small** — hand off to `qa` at F4 instead of terminating |
| `decomposing-into-milestones` | molecular | **edit, small** — set `Role=rd` on created cards |
| `enforcing-pr-contract` | atomic | **untouched** |
| `bootstrapping-repo` | molecular | **edit** — one new stage for the `Role` field |

**3 new · 13 edits · 1 untouched.** Most edits are 5–30 lines. Compare that
to the v0.6 plan's "replace the 14-skill catalog."

---

## 11. What you do not touch (why this is now affordable)

Everything here works as shipped and needs no change for the agent team:

- **The claim primitive** — `claim-card.sh`, `git push --force-with-lease`,
  exit code 10 race-lost semantics. Five agents claiming concurrently is
  exactly what it was built for.
- **One-card-one-worktree** (ADR-0003) and the worktree path resolution.
- **The PR contract** — three sections, `Closes #N` trailer, `submit-pr.sh`,
  `enforcing-pr-contract`. Unchanged, and it is what the human reviews.
- **The 6-state machine and the WIP formula.**
- **`consuming-card`'s 23-node lifecycle** — RD is the Consumer.
- **The audit write path** — `audit-log-write.sh`, outbox, flush worker,
  dead-letter handling. One flag added, no logic changed.
- **The setup-stages engine** — `stages_lib/`, lifecycle diff, 5-callable
  contract. You add one stage; the engine is untouched.
- **Hook intent injection** — `session-start.sh` and its marker grammar.
- **`superpowers` + `gstack`** and the whole `composing-siblings` discipline.
- **`common.sh`** — all ~2000 lines of it.

---

## 12. Spec changes — three ADRs, in this order

Per the repo's governance rule (ADR → spec doc → code), these land **before**
the code that depends on them.

### ADR-0029 — Model agent seats at the plugin layer

The philosophical center of the fork. I-3
(`07-cross-cutting-invariants.md:43`) currently states:

> board-superpowers does not model role / team / permission concepts at the
> plugin layer — those live in GitHub.

Supersede it **narrowly**, and the narrowness is the whole trick:

- **I-3 continues to hold for human identity.** Any GitHub maintainer is
  still "an architect." F-C13 stakeholder routing, Producer F-03, and
  `Card.assignees` semantics are all unaffected.
- **Agent seats are a new orthogonal concept** carried by the `Role` field
  and `actor_seat`, never by GitHub user identity.

Because the supersession is narrow, nothing downstream of I-3 breaks. A
broad "we now model roles" supersession would have cascaded into four
features; this one cascades into zero.

### ADR-0030 — Seat-dimension autonomy + handoff authority

Supersedes ADR-0006's one-dimensional matrix. Contains: the 2-D matrix, the
`seat_overrides` layer and its precedence, the 300-block, the §5.2 authority
matrix, and an explicit restatement that **row 12 remains `N` for all agent
seats** so P6 is visibly preserved.

### ADR-0031 — `handoff_card` as the ninth protocol action

Extends ADR-0025. Contains: the signature, the Status-independence rule, the
Form A implementation, the handoff comment shape, and why a generic
`set_card_field` was rejected.

**No other ADR is superseded.** Not 0004 (siblings kept), not 0008
(horizontal agents never nest), not 0003, not 0026. Compare with
`02-agent-team-evaluation.md`'s eight-ADR list — that was written under the
v0.6 assumptions.

### Contract file edits

| File | Change |
|---|---|
| `0005-contracts/00-kanban-protocol.md` | 8 actions → 9 |
| `0005-contracts/06-audit-log-schema.md` | `actor_seat` column; 300-block catalog |
| `0002-…/07-cross-cutting-invariants.md` | I-3 amendment pointing at ADR-0029 |
| `0003-domain-model/01-ubiquitous-language.md` | Seat, Handoff, Lane |
| `0005-contracts/03-config-schemas.md` | `seat_overrides:` |

---

## 13. Deliberately deferred

Named so they do not creep in:

| Deferred | Why | Revisit when |
|---|---|---|
| OPS + dedicated security seats | Your Phase 2 | Phase 1 runs a week unattended |
| Team-of-teams | Your Phase 3 | One team is boring |
| `actor_id` / persistent roster | `session_id + actor_seat` suffices | A seat runs as >1 concurrent session |
| Postgres migration | SQLite + outbox is fine at this scale | Dead-letter rows appear |
| Agent teams / `SendMessage` | Experimental; correctness must not depend on it | It ships stable |
| Per-seat WIP caps | Global cap + Role lanes is enough signal | A seat is visibly starved |
| Multi-kanban (ADR-0026) | One board with Role lanes covers it | Seats need genuinely separate boards |
| Codex parity for new surfaces | Pragmatic-fork decision | You actually want Codex sessions |
| Cross-machine agents (ADR-0003 TBD-1) | One machine, Phase 1 | You outgrow one machine |

---

## 14. Risks, honestly

| Risk | Severity | Mitigation |
|---|---|---|
| **Handoff ping-pong** — QA bounces to RD, RD escalates to architect, architect returns to RD, forever | High | Cap handoffs per card (default 6). On breach: `Blocked` + `Role=em`. Implement in `board-canon` as a refusal, and surface the count in `briefing-daily` |
| **Seat drift** — an agent reasons outside its seat (RD redesigning the architecture) | High | The autonomy matrix refuses the *actions*, not the reasoning. Also give each role skill an explicit "not your job — hand off" refusal section, the way `decomposing-into-milestones` refuses non-INVEST cards |
| **Latency compounding** — 5 handoffs × session granularity | Medium | Batch: EM dispatches several seats per cycle. Accept it; it is the cost of C-PLUGIN-1 |
| **Human becomes the bottleneck at the merge gate** | Medium | Exactly P1's thesis, so it is working as intended. Keep `## Human Verification TODO` sharp; promote low-risk cards via `seat_overrides` once trust builds |
| **`gh project field-create` unavailable / different flags** | Low but blocking | **[verify]** before writing the bootstrap stage. Fallback: create the field in the GitHub UI, exactly as ADR-0001 already does for the Project itself |
| **Doc drift** — 17 skills × 5 contracts | Medium | Keep the same-PR contract rule from `AGENTS.md`. It is the reason this repo is legible enough to fork at all |

---

## 15. Reading on

1. [`04-implementation-plan.md`](./04-implementation-plan.md) — milestones and
   cards, in dependency order.
2. [`05-file-change-map.md`](./05-file-change-map.md) — every file, what
   changes in it, which card owns it.
3. [`06-operating-runbook.md`](./06-operating-runbook.md) — running the team
   day to day.

*Design only — no code modified. Reflects v0.7.0 as of 2026-07-28.*
