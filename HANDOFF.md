# HANDOFF: agent-teams

> A Claude Code plugin that runs the **Producer** side of an artificial intelligence engineering board over a GitHub Project: session bootstrap, requirement intake, architect specification and readiness, EM briefing/triage/dispatch, and QA queue inspection.

**Stack**: Claude Code plugin / Python 3.12 standard library / GitHub CLI / GitHub Projects v2 / Git / Slidev

**Last updated**: 2026-07-31 by session 3

---

## Project Goal & Scope

This orphan branch builds agent-teams from an empty tree, deliberately not inheriting the earlier full framework. **The Producer half is now complete.** A Producer session shapes work — creates, refines, routes, prioritises, unblocks — and a Consumer session resolves exactly one Card. Consumer execution (RD implementation, QA verdicts) is the next milestone and is not built.

The durable coordination surface is one GitHub Project. Cards are GitHub Issues carrying two orthogonal single-select fields: `Status` (where the work is) and `Role` (whose turn it is).

Normative design lives in [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md); delivery status and the milestone ledger live in [`docs/IMPLEMENTATION_PLAN.md`](./docs/IMPLEMENTATION_PLAN.md). **Do not restate milestone detail here — that plan is the single status ledger.**

Still intentionally excluded: audit database, schema migrations, lifecycle hooks, automatic field provisioning, Codex packaging, multiple board backends, autonomous agent spawning. Additions need evidence from an observed failure, not inheritance from the earlier implementation.

The earlier full implementation is a **separate sibling repository**, `../agent-teams-main` (the board-superpowers fork). Its `docs/agent-team-adaptation/` dossier is the source of this adaptation's intent and is worth reading before changing the authority model.

---

## Architecture

- **This repository is the plugin.** Consuming repositories only hold `.agent-teams/config.json`.
- **Claude-only surface.** `.claude-plugin/plugin.json` names `agent-teams` v0.2.0; local marketplace is `agent-teams-local`. No Codex manifest on this branch.
- **Seven Producer skills.** `using-agent-teams` runs the mandatory read-only bootstrap then routes by leading `[role:<seat>]`. `intaking-requirement` (analyst), `authoring-spec` (architect), `briefing-board` / `triaging-board` / `dispatching-work` (em), `inspecting-queue` (qa).
- **Six functional modules** under `scripts/agent_teams/`, with a strictly downward dependency direction (plus `__init__.py` and `errors.py`, so `ls` shows eight files):

  ```
  model      validated Role, Status, Card, Handoff, Verdict
  policy     pure legality — transitions, authority, caps, seat actions
  config     configuration and its validation
  github     gh invocation, pagination, error classification
  board      semantic board operations
  workflows  transactions with partial-failure recovery

  errors     AgentTeamsError — the one base every expected failure shares,
             so the CLI can catch refusals without swallowing real bugs
  ```

  `scripts/producer_board.py` remains the **stable public entry point** every skill invokes.
- **`policy.py` touches no network.** That is the load-bearing design choice: it is why every transition edge and every seat pair is asserted individually rather than sampled, and it is what caught two authority holes (see Hard-won Discoveries).
- **Semantic operations only.** `transition_card` and `handoff_card` exist; there is deliberately **no** `set_card_field`.
- **Authority is checked before the first GitHub call**, so a refusal costs nothing and leaves no partial state.
- **Status and Role are orthogonal.** A handoff changes Role and writes context; it never silently changes Status. When both must move, that is two operations.
- **Honest partial failure.** Multi-step mutations return `{ok:false, partial:true, completed:[...], failed:..., recovery:[...]}`. Nothing ever claims a rollback that did not run.
- **Human merge is a hard floor.** `merge_pull_request` is `refuse` for every agent seat and is listed in `policy.HARD_FLOORS` as non-overridable.

---

## Established Conventions

- Work in `C:\Users\User\Documents\intern\ITRI\agent-teams-project\agent-teams`. Feature work uses a worktree under `../.worktrees/<name>`, merged back and removed when done (sessions 3 used this twice successfully).
- Keep the branch small. Do not reintroduce audit, setup-stage, hook, or dual-platform frameworks without a demonstrated failure.
- Skill directories use lowercase verb-led names and contain only `SKILL.md`. Frontmatter carries `name` and a trigger-rich `description`.
- All deterministic GitHub behaviour lives in `scripts/agent_teams/`; skills describe orchestration, judgment, and refusal boundaries.
- **Never report a mutation as successful without `"ok": true` in the CLI JSON.** Expected failures return structured error JSON on stderr and exit 1.
- Python standard library only. No dependency install, no virtualenv, no SQLite.
- Tests use an injected fake `gh` (`tests/fake_gh.py`). The suite must never need network or a real Project.
- Intake leaves Status `Backlog` and Role `architect`. It must not make the Card Ready — that is the architect's decision and the action policy refuses it.
- Dispatch is read-only and deterministic: configured seat order, then Card number. Say "prompt rendered", never "session started".
- When superseding a test, leave a comment saying what changed and why. Four original tests were superseded this way; the reasons are in `tests/test_producer_board.py`.

---

## Environment Setup

- Windows PowerShell and Git; Python 3.9+ (observed 3.12.3); Claude Code 2.1+.
- Tests: `python -m unittest discover -s tests -p "test_*.py"` — no dependencies required.
- Manifest validation: `claude plugin validate .`
- Development load: `claude --plugin-dir C:\Users\User\Documents\intern\ITRI\agent-teams-project\agent-teams` from an unrelated repository. Confirm the checkout is on `mvp/producer-from-scratch` first.
- Slides: `cd slides && npx slidev build` (verify) or `npm run dev` (present). `npx slidev export --format png --range N` renders individual slides for visual inspection.

**`gh` is still not installed on this machine.** After installing: `gh auth login`, then `gh auth refresh -s project`. Configure a consuming repository with `producer_board.py init`, then run `producer_board.py doctor` before any mutation. Credentials stay in the GitHub CLI store, never in repository files.

Live board tests need a disposable repository and Project with all six `Status` options (Backlog, Ready, In Progress, Blocked, In Review, Done) and all six `Role` options (analyst, architect, rd, qa, em, human). `doctor` validates all twelve and reports every missing one in a single response.

---

## External References

- [Claude Code plugin docs](https://code.claude.com/docs/en/plugins) — manifests, `--plugin-dir`, namespaces.
- [GitHub CLI Project manual](https://cli.github.com/manual/gh_project) — the commands the adapter wraps.
- `../agent-teams-main/docs/agent-team-adaptation/` — the design dossier this adaptation implements. `03-target-architecture.md` §5.2 is the authority matrix; `00-goal.md` records why nesting is impossible.
- [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) — normative design. §16.1 records the settled implementation decisions.
- [`docs/IMPLEMENTATION_PLAN.md`](./docs/IMPLEMENTATION_PLAN.md) — the sole status ledger.
- [`README.md`](./README.md) — setup, tuning knobs, full CLI reference.
- [`CLAUDE_TESTING.md`](./CLAUDE_TESTING.md) — safe, persistent-install, and live test procedure. **Stale: written for the four-skill layout.**

---

## Progress

Producer surface complete and hermetically tested. Live GitHub behaviour still unproven.

| Milestone | Status | Notes |
|---|---|---|
| Producer MVP (4 skills, 1 script) | Done | Sessions 1–2 |
| Domain model + pure policy layer | Done | `model.py`, `policy.py`; every Status/Role pair asserted |
| Adapter hardening | Done | Pagination with truncation detection, six-Status `doctor`, partial-failure recovery |
| Six-state transitions + handoff cap | Done | Authority keyed to transition destination |
| Architect → Ready vertical slice | Done | `promote` and `decompose`, gated on a durable specification |
| EM operations | Done | `brief`, `triage`, WIP, data-quality detection |
| QA queue inspection | Done | Producer-shaped; issues no verdicts |
| Session context bootstrap | Done | Read-only, per-seat, owned by the entry skill |
| Slide deck | Done | Parts 3–5 clarity pass; **uncommitted** |
| Plugin manifest re-validation | Pending | Not re-run since the seven-skill layout landed |
| Test from unrelated repository | Pending | Never performed |
| Live disposable Project test | Pending | Blocked on `gh` |
| RD / QA Consumer execution | Pending | Next milestone; see plan M4/M5 |

---

## Key Files

| File | Status | Description |
|---|---|---|
| `scripts/producer_board.py` | Active | Stable public CLI entry point; delegates to the package |
| `scripts/agent_teams/policy.py` | **Load-bearing** | Pure legality. Change nothing here without adding an edge test |
| `scripts/agent_teams/model.py` | Active | Validated domain values; `_one_line` neutralises comment-forging input |
| `scripts/agent_teams/workflows.py` | Active | Producer transactions and their recovery recipes |
| `scripts/agent_teams/board.py` | Active | Semantic operations; no generic field setter |
| `scripts/agent_teams/github.py` | Active | `gh` wrapper, error classification, pagination escalation |
| `scripts/agent_teams/config.py` | Active | Validation that reports every defect at once |
| `skills/*/SKILL.md` | Active | Seven Producer skills |
| `tests/fake_gh.py` | Active | Shared fake `gh`; supports arming any subcommand to fail on the *n*th call |
| `tests/test_policy.py` | Active | 41 tests; exhaustive pair coverage |
| `tests/test_partial_failures.py` | Active | 12 tests; every mutation boundary |
| `tests/test_workflows.py` | Active | 35 tests; the four Producer flows |
| `tests/test_producer_board.py` | Active | 35 tests; adapter + CLI contract |
| `slides/slides.md` | **Modified** | 18 content slides + 5 dividers |
| `slides/styles/index.css` | **Modified** | Type scale and layout for the deck |
| `CLAUDE_TESTING.md` | **Stale** | Still describes four skills |

---

## Test Status

`python -m unittest discover -s tests -p "test_*.py"` → **123 passed**, 0.22s, no network. Re-verified on the merged result before cleanup.

Notable coverage:

- every Status pair (36) and every Role pair (36) asserted individually, not sampled;
- pagination: a 250-Card board reads completely; a 10,000-Card board raises rather than returning a partial board;
- every partial-mutation boundary in intake, handoff, promote, decompose — including an assertion that no result ever contains the words "rolled back", "rollback", "reverted", or "undone";
- the merge floor: refused for all five agent seats, permitted only for `human`.

Slides verified by build (`npx slidev build`, 5.8s) plus a pixel scan of exported PNGs confirming no slide clips its bottom edge.

**Not tested**: any live `gh` call; disposable-repository intake; architect docs PR; live handoff; persistent marketplace install; plugin manifest validation since the seven-skill layout; end-to-end from an unrelated consuming repository.

> Every green test is hermetic. It proves the adapter behaves correctly **given response shapes that have never met a real `gh`**. That gap is the project's largest open risk.

---

## Known Issues & Deferred Debt

- **Live `gh` JSON shapes are assumed** (`tests/fake_gh.py`) — fixtures encode expected shapes; a live Project must confirm `project view`, `field-list`, `item-list`, `item-add`, and `pr view`.
- **Pagination strategy is an assumption** (`github.fetch_all_items`) — it escalates `--limit` until a response returns short. **If the installed `gh` caps `--limit`, this must become a documented ceiling instead.** Verify before trusting dispatch on a large board.
- **Handoff remains partially non-atomic** (`board.handoff_card`) — Role changes before the comment posts. Now surfaced as `PartialHandoff` carrying the exact comment body for replay, rather than hidden.
- **`handoff_count` fails open** (`board.handoff_count`) — if comments cannot be read it returns 0, so the cap under-counts rather than stalling the team. Deliberate; revisit if ping-pong goes undetected.
- **No automatic field provisioning** — `doctor` validates and explains, never creates.
- **No claim or WIP enforcement** — `brief` reports WIP but nothing blocks dispatch past the limit.
- **No audit trail beyond GitHub artifacts** — the partial-failure envelope is not a substitute; plan M7.
- **`CLAUDE_TESTING.md` is stale** — describes four skills and the old command set.

---

## Open Decisions

- **First Consumer capability** — options: RD claim/worktree/PR, or QA verdict first; need: evidence from the first live Producer run.
- **Pagination ceiling** — options: keep escalation, or switch to a documented hard ceiling; need: observed `gh project item-list --limit` behaviour on a real board.
- **`handoff_count` fail-open** — options: keep, or fail closed and stall; need: a live case where an unreadable comment thread mattered.
- **Persistent installation** — options: continue `--plugin-dir`, or install the local marketplace; need: user preference after unrelated-repository testing.

**Settled this session** (rationale in `docs/ARCHITECTURE.md` §16.1, do not relitigate without new evidence): `architect → analyst` is legal; `spec_completion` defaults to `merged`; decomposition is by shape; transition authority keys off the destination.

---

## Hard-won Discoveries

- **Writing the rules down as executable policy found five real bugs.** Three contradicted documents already written (`architect → analyst` missing from the authority matrix; `doctor` checking 2 of 6 Statuses; board read capped at 100 with no truncation check). Two only became visible once the rules ran: a generic `transition` could reach `Ready`, bypassing the `promote_to_ready` refusal, and handoff free text could forge a second `**Handoff**` line a parser would read. **Both authority holes were caught by tests written expecting them to pass.** Prose can hold a contradiction indefinitely; a table of 36 asserted pairs cannot.
- **Silent truncation was the worst bug in the codebase.** A Card past page one was invisible to dispatch while dispatch reported success. Failing loudly beats returning a short list.
- **A pure policy module is worth the extra file.** Because `policy.py` imports nothing that touches the network, its edges are cheap to assert exhaustively — which is exactly why the holes surfaced.
- **Slide density is a layout problem, not a wording problem.** Type in Parts 3–5 ran down to 0.54rem (~9px). Judging from source was useless; exporting PNGs and looking at them revealed two slides overflowing and two with headings misaligned because each card centred its content independently. Fixed structurally (`grid-template-rows: auto auto 1fr`), not by trimming words until nothing wrapped.
- **Verify a verification.** A pixel scan for clipped slides reported all nine clipped — because it assumed the theme's warm background while the export renders on white. Calibrate the check against a sampled pixel before trusting its verdict.
- **`--plugin-dir` remains the reliable development proof**; it overrides stale installed copies.
- **Worktrees under `../.worktrees/` work well here** — created, merged with `--no-ff`, verified on the merged result, then removed. Used twice this session without incident.

---

## Blockers / Waiting On

- **Live GitHub verification** — waiting on: `gh` plus a disposable Project. This blocks plan M1.1–M1.3 and gates everything downstream.
- **Remote synchronisation** — waiting on: user decision. `mvp/producer-from-scratch` is **4 commits ahead** of `origin/mvp/producer-from-scratch`; nothing has been pushed.

---

## Current State

On `mvp/producer-from-scratch`, HEAD `b7f7b60`, **4 ahead of origin**, one worktree (the repo root). Merge commit `995af48` brought in `feat/producer-complete`; that branch and its worktree were removed after the merged result tested green.

**Uncommitted**: `slides/slides.md` and `slides/styles/index.css` — the Parts 3–5 clarity pass. The user explicitly asked that these not be committed. Everything else is clean.

The plugin is v0.2.0: seven skills, six deterministic modules, 123 passing tests. No process is running, no live board has been touched, and `gh` is not installed.

Cross-repo note: the sibling `../agent-teams-main` had its `docs/producer-context-bootstrap` worktree merged into `main` (fast-forward to `1077530`) and removed. That repo is clean and unrelated to this branch's history.

---

## Next Steps

The Producer surface is code-complete. **Every remaining Producer risk is the same risk: none of it has met a real GitHub CLI.** Close that before building more.

1. Install `gh`; authenticate with Project scope.
2. Create a disposable repository and Project with both six-option fields.
3. Run `producer_board.py doctor` and confirm it reports what is actually missing.
4. Capture real `gh project view / field-list / item-list / item-add` JSON; replace the assumed shapes in `tests/fake_gh.py` with the captures.
5. **Confirm `gh project item-list --limit` behaviour** against `github.fetch_all_items`. If `gh` caps the limit, convert the escalation into a documented ceiling.
6. Run one disposable intake, one promote, one handoff; check the durable board against what each JSON envelope claimed.
7. Re-run `claude plugin validate .` and load from an unrelated repository; confirm all seven skills appear.
8. Refresh `CLAUDE_TESTING.md` for the seven-skill layout, and update the §4.4 verification table in the plan with observed evidence.

Only then start Consumer work (M4/M5) or audit (M7). Building a second seat on unverified response shapes doubles what must be re-checked when the first real `gh` call disagrees with a fixture.

---

## Suggested Skills

- **`superpowers:verification-before-completion`** — the single most relevant skill here. This project's recurring failure mode is a confident claim ahead of its evidence; the handoff above distinguishes hermetic from live proof precisely because of it.
- **`superpowers:test-driven-development`** — before touching `policy.py`. Both authority holes were found by writing the test first and being surprised.
- **`superpowers:systematic-debugging`** — when the first live `gh` call disagrees with a fixture. Expect that, and diagnose rather than loosening the adapter.
- **`superpowers:using-git-worktrees`** then **`superpowers:finishing-a-development-branch`** — the established flow for feature work on this branch.
- **`superpowers:executing-plans`** — `docs/IMPLEMENTATION_PLAN.md` is a real written plan; execute it rather than improvising a milestone.
- **`superpowers:brainstorming`** — before designing the RD/QA Consumer seats, which are genuinely new design work rather than plan execution.

---

## Session Log

<!-- newest entry at top -->

### 2026-07-31 — Session 3

Completed the Producer surface. Extracted the 592-line CLI into six modules with a strictly downward dependency direction, keeping `producer_board.py` as the stable entry point. Added `promote`, `decompose`, `transition`, `brief`, `triage`, `queue`, `create-card`, and `bootstrap`; added `briefing-board`, `triaging-board`, and `inspecting-queue` skills (four skills → seven). Fixed three defects the architecture already forbade — missing `architect → analyst` authority, silent board truncation past 100 Cards, and a `doctor` that checked two of six Statuses — plus two authority holes found while building. Settled the three M2 decision gates and recorded them with rationale in `ARCHITECTURE.md` §16.1. Tests 9 → 123, all hermetic. Merged via worktree (`995af48`) after verifying the merged result, then removed the worktree and branch.

Updated the slide deck for v0.2.0 and added a slide on the five bugs the policy layer caught. A second pass on Parts 3–5 fixed two slides that overflowed off the bottom edge, two whose headings misaligned when titles wrapped, and type that ran as small as 0.54rem. Those slide changes are **uncommitted at the user's request**.

Also merged the sibling `agent-teams-main` repo's `docs/producer-context-bootstrap` worktree into its `main` and removed it.

Nothing pushed. `gh` still not installed, so no live GitHub operation was performed.

---

### 2026-07-30 — Session 2

Renamed the plugin identity from `board-superpowers-producer` to `agent-teams`, the marketplace to `agent-teams-local`, the entry skill to `using-agent-teams`, and the consuming config path to `.agent-teams/config.json`. Verification passed after the rename: 9 unit tests, warning-free manifest validation, and a real non-mutating namespace load.

---

### 2026-07-30 — Session 1

Built the Producer MVP from an empty orphan branch (`d9b739a`), added a handoff (`8c8546f`) and Claude testing guide (`fa23e0b`). Validation passed: 9 unit tests, Python syntax, warning-free plugin validation, Git whitespace checks, and a real non-mutating Claude namespace load. No live GitHub mutation attempted.

---
<!-- previous sessions below this line — do not edit -->
