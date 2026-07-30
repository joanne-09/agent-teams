# agent-team-adaptation — analysis & implementation docs

This directory holds the analysis and the implementation plan for building a
**multi-agent software-engineering team** (EM, system analyst, system
architect, RD, QA) on top of `board-superpowers`, to develop a **data
dashboard**.

> **These docs are NOT part of the board-superpowers spec.** The spec source
> of truth is [`docs/architecture/`](../architecture/) (read
> `0001-positioning.md` first). The docs here are *adaptation notes* written
> from the point of view of someone using this repo as a base and modifying
> it. Nothing here is authoritative about board-superpowers itself.
>
> Once implementation starts, the decisions in `03` graduate into real ADRs
> under `docs/architecture/adr/` (0029–0031). At that point those ADRs — not
> these notes — become authoritative.

## Why this directory exists

- One place to find every doc produced for this effort.
- **Git-tracked** by choice. It deliberately sits *outside* the gitignored
  scaffolding locations (`docs/plans/` and `docs/board-superpowers/plans/`),
  so the analysis persists in version control rather than living as scratch.

## Docs

| # | Doc | Purpose |
|---|-----|---------|
| 0 | [`00-goal.md`](./00-goal.md) | **The anchor. v0.7, finalized.** What is being built and the four decisions that shape it. Everything else serves this. |
| 1 | [`01-codebase-guide.md`](./01-codebase-guide.md) | Understand and **trace** the board-superpowers codebase: repo layout, spec reading order, the 14-skill system, session flow, every hook and script, the load-bearing contracts + ADRs, glossary. **Read first if the repo is unfamiliar.** |
| 2 | [`02-agent-team-evaluation.md`](./02-agent-team-evaluation.md) | Is this repo suitable as a base? What are the gaps? Written against the **v0.6** goal — parts are superseded by `03`; see the banner at its top. Still the best source for the *case against*. |
| 3 | [`03-target-architecture.md`](./03-target-architecture.md) | **The design.** Role-as-board-field, the handoff protocol and authority matrix, horizontal-agent topology, seat-dimension autonomy, the skill catalog delta, and the three ADRs to write. |
| 4 | [`04-implementation-plan.md`](./04-implementation-plan.md) | **The plan.** 25 cards across 6 milestones, in dependency order, with sizes and acceptance criteria. Includes a 10-card walking-skeleton subset. |
| 5 | [`05-file-change-map.md`](./05-file-change-map.md) | **The checklist.** Every file to create or edit, what changes in it, which card owns it, and which coupled file must change with it. |
| 6 | [`06-operating-runbook.md`](./06-operating-runbook.md) | **The manual.** Setup, launching each seat, a day in the life, the human's job, health checks, failure modes, tuning, and how to grow to Phase 2/3. |

## Reading order

**If you are deciding whether to do this:** `00` → `02` → `03`.

**If you are building it:** `00` → `03` → `04` → `05`, with `01` open beside
you for orientation and `06` as the target-state picture.

**If you are running it:** `06`.

## Status

- Analysis and design: **complete**. Goal finalized at v0.7.
- Implementation: **not started.** No plugin code has been modified to
  produce any of these docs.

Last updated: 2026-07-28.
