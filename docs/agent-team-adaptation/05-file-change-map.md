# 05 — File change map (every file you touch)

> The *which files* document. Design is in
> [`03-target-architecture.md`](./03-target-architecture.md); ordering is in
> [`04-implementation-plan.md`](./04-implementation-plan.md). Card numbers
> below refer to that plan.
>
> Every path was confirmed to exist in the v0.7.0 tree at the time of
> writing. **Re-verify before editing** — this file will age.

**Totals: 24 files created · 33 edited · the rest untouched.**

Legend — **NEW** create · **EDIT** modify · **⚠** contract-coupled, check
the same-PR rule before you commit.

---

## 1. `docs/architecture/` — spec (M0)

### Create

| File | Card | Contents |
|---|---|---|
| `adr/0029-agent-seats-at-plugin-layer.md` | 1 | The narrow I-3 supersession. Human identity stays flat; agent seats are orthogonal. |
| `adr/0030-seat-dimension-autonomy.md` | 2 | Supersedes ADR-0006. 2-D matrix, `seat_overrides`, handoff authority, row 12 stays `N`. |
| `adr/0031-handoff-card-protocol-action.md` | 3 | Extends ADR-0025. The ninth action. |

### Edit

| File | Card | What changes | |
|---|---|---|---|
| `adr/0006-producer-autonomy-boundary.md` | 2 | Header only → `superseded by ADR-0030`. **Body is immutable — do not rewrite it.** | ⚠ |
| `adr/0025-kanban-protocol-as-top-contract.md` | 3 | Header note: extended by ADR-0031. Not superseded. | ⚠ |
| `adr/README.md` | 1–3 | Index rows for 0029–0031. | |
| `0002-…/07-cross-cutting-invariants.md` | 1 | I-3 amendment + pointer to ADR-0029. Leave I-1, I-2, I-7 alone. | ⚠ |
| `0002-…/02-roles.md` | 1 | Producer/Consumer reframed as *session shapes*; the six seats introduced as an orthogonal axis. | ⚠ |
| `0003-domain-model/01-ubiquitous-language.md` | 4 | **Seat**, **Handoff**, **Lane**. | ⚠ |
| `0003-domain-model/02-bounded-contexts.md` | 4 | Seats live in the **Session** context, not Board. | |
| `0005-contracts/00-kanban-protocol.md` | 4 | 8 actions → 9. Compliance levels for `handoff_card`. | ⚠ |
| `0005-contracts/06-audit-log-schema.md` | 4 | `actor_seat` column; 300-block catalog; payload sub-schemas 300–305. | ⚠ |
| `0005-contracts/03-config-schemas.md` | 4 | `seat_overrides:` block + precedence. | ⚠ |
| `0005-contracts/09-session-agent-protocol.md` | 14 | Seat as a J1 trigger-actor value. **Declare a new value; do not redefine the axes.** | ⚠ |
| `0005-contracts/04-skill-contracts.md` | 16–18 | Contract rows for the three new skills. | |
| `docs/architecture/AGENTS.md` | 4 | Change-impact matrix rows for the new couplings. | ⚠ |

**Do not touch:** `0001-positioning.md`. Every premise P1–P8 survives this
design intact — including P4b, since you kept the sibling plugins. If you
find yourself editing it, something has gone wrong upstream.

---

## 2. `skills/` — 3 new, 13 edited (M1–M4)

> **Every file in this section trips the Process gate.** Invoke
> `example-skills:skill-creator`, read `SKILL_DEVELOPMENT.md` in session,
> edit `SKILLS.md` first. See `skills/AGENTS.md`.

### Create — `skills/dispatching-work/` (Card 16)

| File | Contents |
|---|---|
| `SKILL.md` | EM dispatch routine. 250–450 lines. |
| `.skill-meta.yaml` | `molecular` / `technique` / `claude-code-only` / `session` |
| `references/dispatch-algorithm.md` | Lane scan → WIP → handoff cap → ordering |
| `references/queue-format.md` | The dispatch-queue artifact shape |
| `evals/evals.json` | Regime 2 matrix |

### Create — `skills/authoring-spec/` (Card 17)

| File | Contents |
|---|---|
| `SKILL.md` | Architect spec-to-PR routine. 250–450 lines. |
| `.skill-meta.yaml` | `molecular` / `pattern` / `claude-code-only` / `spec` |
| `references/spec-vs-plans.md` | `docs/architecture/` vs `docs/plans/` vs card body |
| `references/adr-authoring.md` | When a decision earns an ADR |
| `evals/evals.json` | Regime 2 matrix |

### Create — `skills/verifying-delivery/` (Card 18)

| File | Contents |
|---|---|
| `SKILL.md` | QA owned-verification routine. 250–450 lines. |
| `.skill-meta.yaml` | `molecular` / `discipline` / `claude-code-only` / `board` |
| `references/verdict-schema.md` | Verdict shape + evidence requirements |
| `references/qa-refusals.md` | What QA refuses to pass, and why |
| `references/pressure-scenarios.md` | Regime 1 log — `discipline` type needs pressure tests, not an eval matrix |

### Edit

| File | Card | What changes | |
|---|---|---|---|
| `SKILLS.md` *(repo root)* | 9,10,11,13,14,16–22 | Catalog 14 → 17; call graph; SPOT derivation for the handoff SPOT; bounded-context map; cross-plugin edges. **Edit before the `skills/` change, same PR.** | ⚠ |
| `using-board-superpowers/SKILL.md` | 14 | Parse `[role:<seat>]`; bind the seat. Body is already ~225 lines over a 200 budget — **push prose out, do not add to it**. | ⚠ |
| `using-board-superpowers/references/routing.md` | 14 | The seat routing table. | |
| `board-canon/SKILL.md` | 9 | `Role` as an orthogonal field; pointer to the new reference. | ⚠ |
| `board-canon/references/handoff-authority.md` | 9 | **NEW file** — authority matrix, refusal rule, handoff cap. | |
| `board-canon/references/card-body-schema.md` | 9 | `Role` field; explicitly not a Status, not `Assignees`. | ⚠ |
| `operating-kanban/SKILL.md` | 10 | Ninth action in the dispatch list. | |
| `operating-kanban/references/action-dispatch.md` | 10 | `handoff_card` dispatch rules. | |
| `operating-kanban/references/github-project-v2.md` | 10 | Map to `handoff-card.sh`; declare the `seat_field` setup capability. | ⚠ |
| `classifying-actions/SKILL.md` | 11 | Two-argument call. Body ≤ 200 lines. | ⚠ |
| `classifying-actions/references/matrix.md` | 11 | Seat columns on every row. | ⚠ |
| `classifying-actions/references/action-id-catalog.md` | 11 | Rows 300–305. | ⚠ |
| `classifying-actions/references/override-parsing.md` | 12 | `seat_overrides` + precedence. | |
| `auditing-actions/SKILL.md` | 13 | `actor_seat` in payload templates. | |
| `auditing-actions/references/schema.md` | 13 | Column added. | ⚠ |
| `composing-siblings/references/handoff-points.md` | 22 | Rows for the three new skills. | ⚠ |
| `composing-siblings/references/procedural-fallback-rules.md` | 22 | Re-check Mode-2 for the new call sites. | |
| `briefing-daily/SKILL.md` | 19 | Group by `Role` lane; surface handoff counts. | |
| `triaging-board/SKILL.md` | 19 | Escalate along the authority lines. | |
| `intaking-requirement/SKILL.md` | 20 | Terminate in a handoff to `architect`; refuse to set `Ready`. | |
| `intaking-requirement/references/intake-decision-tree.md` | 20 | Analyst-seat routing. **Mirrored in root `AGENTS.md` — both or neither.** | ⚠ |
| `decomposing-into-milestones/SKILL.md` | 21 | Set `Role=rd` on created cards. | |
| `consuming-card/SKILL.md` | 21 | F4 hands to `qa`; blocked path escalates to `architect`. Keep the diff small. | ⚠ |
| `consuming-card/references/stage-4-submit.md` | 21 | Handoff step after PR open. | |
| `reviewing-pr-queue/SKILL.md` | 22 | QA-seat routine; pass → `human`, fail → `rd`. | |
| `bootstrapping-repo/SKILL.md` | 6 | The new role-field stage in the flow. | ⚠ |
| `bootstrapping-repo/references/stage-execution-flow.md` | 6 | Stage row + UI fallback. | |

**Do not touch:** `enforcing-pr-contract/**`. The PR contract is
seat-independent and is exactly what the human reviews. Leaving it alone is
a feature.

---

## 3. `scripts/` — 5 new, 8 edited (M1–M3)

### Create

| File | Card | Contents |
|---|---|---|
| `handoff-card.sh` | 8 | The Form A `handoff_card` implementation. |
| `dispatch-agent.sh` | 15 | Kick-off prompt renderer (`--format paste\|subagent\|cron`). |
| `migrations/audit-v2-to-v3.sh` | 13 | Adds `actor_seat`. Mirror v1→v2 exactly. |
| `migrations/audit-v2-to-v3-impl.py` | 13 | Per-scheme DDL + meta bump to 3. |
| `stages_lib/m11_repo_ensure_role_field.py` | 6 | 5-callable stage executor. |
| `stages_lib/test_m11_repo_ensure_role_field.py` | 6 | Co-located pytest. |

### Edit

| File | Card | What changes | |
|---|---|---|---|
| `lib/common.sh` | 12,13 | `bsp_resolve_autonomy_class` takes a seat; `bsp_audit_local_write` carries `actor_seat`. Two focused changes in ~2000 lines. | ⚠ |
| `lib/audit-schema.sqlite.sql` | 13 | Column + meta version 3. | ⚠ |
| `lib/audit-schema.postgres.sql` | 13 | Same, literally aligned. | ⚠ |
| `lib/audit-schema.mysql.sql` | 13 | Same, literally aligned. | ⚠ |
| `read-board.sh` | 7 | Emit `role`; add `--role` filter; absent field → `null`. | |
| `audit-log-write.sh` | 13 | `--actor-seat`; validate 300–305. | ⚠ |
| `audit-init.sh` | 13 | Auto-run v2→v3, as it already does v1→v2. | |
| `audit-flush-impl.py` | 13 | Pass `actor_seat` through the outbox. | |
| `stages-registry.yml` | 6 | `m11_repo_ensure_role_field` — module, character, locality, generation, `depends_on`, `applicable_when`. | ⚠ |

**Do not touch:** `claim-card.sh`, `submit-pr.sh`, `post-merge-cleanup.sh`,
`create-card.sh`, `transition-card.sh`, `check-deps.sh`, `bootstrap-*.sh`,
the `verify-skill-*.sh` gates, `pre-submit-audit.sh`. The claim primitive and
the PR path are the parts of this repo you most want unchanged.

---

## 4. `hooks/` — nothing

No hook changes. `session-start.sh` keeps injecting `INVOKE: bootstrapping-repo`;
the new role-field stage rides the existing lifecycle diff for free — which
is the whole point of the setup-stages engine.

The seat is carried by the `[role:]` token in the first message, not by a
hook. Resist the temptation to add a `SessionStart` seat probe: the hook
cannot know which seat *you* intended, and CC `SessionStart` delivery is
documented as unreliable anyway.

---

## 5. Root maintainer docs — 5 edited

| File | Card | What changes | |
|---|---|---|---|
| `SKILLS.md` | many | See § 2. The single most edit-frequent file in the plan. | ⚠ |
| `AGENTS.md` | 5,20 | Routing block gains seat routing. The compose section is mirrored in `intake-decision-tree.md` — **both or neither**. | ⚠ |
| `BOARD_DEVELOPMENT.md` | 5 | Ninth action; `Role` field; handoff authority. | ⚠ |
| `SETUP_STAGES_DEVELOPMENT.md` | 6 | The `m11` stage in the registry walk-through. | ⚠ |
| `MULTI_AGENT_DEVELOPMENT.md` | 14 | A section on horizontal agents: why nesting is not used, why the board is the channel. | |

**Do not touch:** `SKILL_DEVELOPMENT.md`, `FEATURE_DESIGN_METHODOLOGY.md`,
`PLUGIN_DEVELOPMENT.md`. They describe *how to build*, and none of that
changes. `README.md` / `README.zh-CN.md` are user-facing — update them at
M5, once the behavior is real, not while it is half-built.

---

## 6. `tests/` — 6 new, 2 edited

| File | Card | Contents |
|---|---|---|
| `tests/unit/test-handoff-card.sh` | 8 | **NEW** — legal, illegal, past-cap, exit codes |
| `tests/unit/test-read-board-role.sh` | 7 | **NEW** — `--role` filter; absent field → `null` |
| `tests/unit/test-seat-overrides.sh` | 12 | **NEW** — one case per precedence pair |
| `tests/unit/test-dispatch-agent.sh` | 15 | **NEW** — all three output formats |
| `tests/e2e/test-audit-v3-migration.sh` | 13 | **NEW** — v2 DB → v3, rows preserved |
| `tests/e2e/test-seat-handoff-e2e.sh` | 24 | **NEW** — RD → QA → human on a scratch board |
| `scripts/stages_lib/test_m11_*.py` | 6 | **NEW** — co-located, per convention |
| existing suites | various | **EDIT** — audit-row assertions gain the seat column |

---

## 7. Per-card file checklist

Print this. Tick it before each PR.

| Card | Files | Gate |
|---|---|---|
| 1 ADR-0029 | 4 | — |
| 2 ADR-0030 | 3 | — |
| 3 ADR-0031 | 3 | — |
| 4 Contracts | 7 | — |
| 5 Doc sync | 3 | — |
| 6 Role field | 6 | stages guide |
| 7 read-board | 2 | — |
| 8 handoff-card.sh | 2 | — |
| 9 board-canon | 4 | **skills + board guide** |
| 10 operating-kanban | 4 | **skills + board guide** |
| 11 classifying-actions | 4 | **skills** |
| 12 seat_overrides | 3 | — |
| 13 audit seat | 10 | **skills** |
| 14 seat token | 4 | **skills** |
| 15 dispatch-agent.sh | 2 | — |
| 16 dispatching-work | 6 | **skills** |
| 17 authoring-spec | 6 | **skills** |
| 18 verifying-delivery | 6 | **skills** |
| 19 EM edits | 3 | **skills** |
| 20 analyst edits | 4 | **skills** |
| 21 RD edits | 4 | **skills** |
| 22 QA edits | 4 | **skills** |
| 23 dashboard repo | — | separate repo |
| 24 golden path | 2 | — |
| 25 retro | varies | — |

"Gate" means an extra mandatory read before the first edit: **skills** =
`skill-creator` + `SKILL_DEVELOPMENT.md`; **board guide** =
`BOARD_DEVELOPMENT.md`; **stages guide** = `SETUP_STAGES_DEVELOPMENT.md`.
`board-canon` and `operating-kanban` trip two gates each.

---

## 8. The coupled-file pairs

These break silently — one half edited, the other not — and CI will not
always catch them.

| If you edit… | You must also edit… | Enforced by |
|---|---|---|
| any `skills/<name>/` structure | `SKILLS.md` catalog row | `verify-skill-metadata.sh` |
| `.skill-meta.yaml` | `SKILLS.md` row | `verify-skill-metadata.sh` |
| root `AGENTS.md` compose section | `intake-decision-tree.md` | change-impact matrix only — **human discipline** |
| `00-kanban-protocol.md` | `board-canon` + `operating-kanban` + `BOARD_DEVELOPMENT.md` | change-impact matrix only |
| `06-audit-log-schema.md` | all 3 `audit-schema.*.sql` + `auditing-actions` | nothing — **human discipline** |
| `stages-registry.yml` | `SETUP_STAGES_DEVELOPMENT.md` + the schema file | `stages-registry.schema.json` (partial) |
| any ADR supersession | the superseded ADR's header + `adr/README.md` | nothing — **human discipline** |

The rows marked *human discipline* are where this plan is most likely to
decay. The repo names doc lag as its primary failure mode, and it is right.

---

*Map only — no code modified. Paths verified against v0.7.0 on 2026-07-28.*
