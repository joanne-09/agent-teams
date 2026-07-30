# HANDOFF: agent-teams Producer MVP

> A minimal Claude Code plugin that proves analyst intake, architect specification delivery, durable Role handoff, and EM dispatch over a GitHub Project.

**Stack**: Claude Code plugin / Python 3.12 standard library / GitHub CLI / GitHub Projects v2 / Git

**Last updated**: 2026-07-30 by session 2

---

## Project Goal & Scope

This orphan branch builds the smallest useful Producer version of agent-teams from an empty tree. Done means Claude can load four namespaced skills, route analyst/architect/EM prompts, use one deterministic CLI to read and mutate a configured GitHub Project, and pass focused automated and runtime-loading checks.

The durable coordination surface is one GitHub Project. Cards are GitHub Issues with single-select `Status` and `Role` fields. Analyst intake creates a Backlog Card and hands it to architect; architect work produces a docs-only specification PR and hands the Card to RD; EM dispatch reads Ready Cards and renders kickoff prompts without spawning agents.

This MVP intentionally excludes audit databases, migrations, lifecycle hooks, automatic field provisioning, Codex packaging, multiple board backends, autonomous agent spawning, WIP/claim enforcement, automatic decomposition, Consumer/RD execution, and QA verification. Additions must be justified by observed MVP failures rather than copied wholesale from the earlier full implementation.

The earlier full implementation and its documentation remain on `main` at `e2e1dec`. This MVP lives on the unrelated orphan branch `mvp/producer-from-scratch`.

---

## Architecture

- **This repository is the plugin.** The repository root is the loadable `agent-teams` Claude Code plugin; consuming repositories only hold `.agent-teams/config.json`.
- **Claude-only plugin surface.** `.claude-plugin/plugin.json` names `agent-teams` version `0.1.0`; the local marketplace uses `agent-teams-local`. There is no Codex manifest on this branch.
- **Four-skill catalog.** `using-agent-teams` routes by leading `[role:<seat>]`; `intaking-requirement`, `authoring-spec`, and `dispatching-work` own the analyst, architect, and EM workflows.
- **One deterministic adapter.** `scripts/producer_board.py` is the entire runtime integration. It uses only Python's standard library and invokes `gh`; there is no service, package install, virtual environment, or shell library.
- **Repository-local coordinates.** A consuming repository stores non-secret Project coordinates in `.agent-teams/config.json`. Authentication is delegated to `gh`.
- **GitHub Project as truth.** The Project must already contain `Status` and `Role` single-select fields. `doctor` validates them but never provisions them.
- **Explicit handoff authority.** Source-to-target seat transitions are validated in the CLI. The current durable Role must match `--from-role`.
- **Carrier-neutral dispatch.** Dispatch returns deterministic prompts containing `[role:<role>] [board-card:#<number>]`; it neither starts a session nor mutates the Project.
- **Intentionally non-transactional external mutation.** Role changes before the Issue comment is posted. If the comment fails, the CLI reports failure and the Project remains the source of truth; no false rollback is attempted.

---

## Established Conventions

- Work directly in `C:\Users\User\Documents\intern\ITRI\agent-teams`; the user explicitly rejected maintainer worktrees for this experiment.
- Keep the MVP branch small. Do not reintroduce audit, setup-stage, hook, or dual-platform frameworks without a demonstrated failure.
- Skill directories use lowercase verb-led names and contain only `SKILL.md`.
- Skill frontmatter contains `name` and a trigger-rich `description`.
- All deterministic GitHub behavior belongs in `scripts/producer_board.py`; skills describe orchestration and safety boundaries.
- Mutating CLI commands return success JSON only after the durable operation completes; expected failures return structured error JSON on stderr.
- Unit tests use an injected fake `gh` adapter. Do not require network or a real Project for the focused suite.
- Intake must leave Status at `Backlog` and final Role at `architect`; it must not silently make the Card Ready.
- Dispatch is read-only and sorts by configured Role order, then Issue number.
- Use `--plugin-dir` while developing so Claude loads the current checkout instead of a cached marketplace copy.

---

## Environment Setup

Required development environment:

- Windows PowerShell and Git
- Python 3.9+; observed version is Python 3.12.3
- Claude Code 2.1+; observed version is 2.1.220

No Python dependency installation is required. The focused test command is `python -m unittest discover -s tests -v`; manifest validation is `claude plugin validate .`.

For safe Claude testing in another repository, start Claude with `--plugin-dir C:\Users\User\Documents\intern\ITRI\agent-teams`. Verify the source checkout is on `mvp/producer-from-scratch` first.

Live board tests additionally require GitHub CLI, repository authentication, Project scope, a disposable repository, and an existing Project containing Status options Backlog, Ready, In Progress, In Review, Done, and Blocked plus Role options analyst, architect, rd, qa, em, and human.

The current machine does not have `gh` installed. After installation, use `gh auth login` and `gh auth refresh -s project`. Configure a consuming repository with `producer_board.py init`, then run `producer_board.py doctor` before any mutation.

No environment variables are required. Credentials must remain in the GitHub CLI credential store, not repository files.

---

## External References

- [Claude Code plugin documentation](https://code.claude.com/docs/en/plugins) ? manifests, `--plugin-dir`, namespaces, and local development.
- [Claude Code marketplace documentation](https://code.claude.com/docs/en/plugin-marketplaces) ? local installation and cache behavior.
- [GitHub CLI Project manual](https://cli.github.com/manual/gh_project) ? commands used by the board adapter.
- `README.md` ? concise MVP setup and CLI reference.
- `CLAUDE_TESTING.md` ? complete safe, persistent-install, and optional live test procedure.

---

## Progress

The from-scratch MVP implementation is complete and locally validated. Safe plugin loading has been proven. Live GitHub Project behavior remains untested because `gh` is not installed.

| Milestone | Status | Notes |
|---|---|---|
| Empty orphan branch | Done | Root commit `d9b739a`; no inherited implementation files |
| Claude plugin scaffold | Done | Warning-free manifests at v0.1.0 |
| Four Producer skills | Done | Router, intake, architect spec, and EM dispatch |
| Deterministic board CLI | Done | Config, doctor, list, dispatch, intake, and handoff |
| Focused unit coverage | Done | 9 tests passed with fake `gh` |
| Claude runtime loading | Done | Namespace and three downstream routines confirmed |
| Testing documentation | Done | `README.md`, `CLAUDE_TESTING.md`, and this handoff |
| Test from unrelated repository | Pending | Documented but not performed in this session |
| Live disposable Project test | Pending | Blocked by missing `gh` and disposable Project |
| Rename and remote synchronization | In Progress | Rename is validated but uncommitted; local HEAD is also one commit ahead of the remote MVP branch |

---

## Key Files

| File | Status | Description |
|---|---|---|
| `.claude-plugin/plugin.json` | Stable | Claude plugin identity and v0.1.0 metadata |
| `.claude-plugin/marketplace.json` | Stable | Warning-free local marketplace definition |
| `scripts/producer_board.py` | Active | Entire deterministic GitHub Project adapter |
| `skills/using-agent-teams/SKILL.md` | Stable | Entry router and safety preconditions |
| `skills/intaking-requirement/SKILL.md` | Stable | Analyst intake and architect handoff |
| `skills/authoring-spec/SKILL.md` | Stable | Docs-only architect flow and RD handoff |
| `skills/dispatching-work/SKILL.md` | Stable | Read-only Ready queue and prompt rendering |
| `tests/test_producer_board.py` | Active | Nine standard-library tests using fake `gh` |
| `README.md` | Stable | Concise user setup and CLI reference |
| `CLAUDE_TESTING.md` | Stable | Detailed testing guide added at `fa23e0b` |
| `HANDOFF.md` | Active | Living cross-session state; modified by this session |

---

## Test Status

Observed passing checks:

- `python -m py_compile scripts\producer_board.py tests\test_producer_board.py` passed.
- `python -m unittest discover -s tests -v` passed 9 of 9 tests initially in 0.195 seconds and again after the rename in 0.063 seconds. Coverage includes configuration validation, Project item normalization, repository filtering, dispatch filtering/order, handoff authority and mutation calls, intake invariants, and `doctor` field checks.
- `claude plugin validate .` passed without warnings.
- `git diff --cached --check` passed before the implementation and documentation commits.
- A non-mutating Claude invocation using `/agent-teams:using-agent-teams` loaded successfully and named `intaking-requirement`, `authoring-spec`, and `dispatching-work`.

Not tested:

- no live `gh project` read or mutation;
- no disposable-repository intake;
- no architect-created docs PR;
- no live Role handoff/comment;
- no persistent marketplace installation of this MVP;
- no end-to-end test from an unrelated consuming repository.

No broad suite exists or is needed at this stage.

---

## Known Issues & Deferred Debt

- **Live `gh` JSON shapes are assumed** (`scripts/producer_board.py`) ? fixtures cover the expected shape, but a live Project must confirm item, field, option, and item-add responses.
- **Handoff is partially non-atomic** (`Board.handoff`) ? Role may change even if the subsequent Issue comment fails. This is surfaced instead of hidden behind a fake rollback.
- **No automatic field provisioning** (`Board.doctor`) ? consuming Projects must already have the required single-select fields and options.
- **No claim or WIP mechanism** (`Board.dispatch`) ? two humans can launch the same rendered Card because dispatch is deliberately read-only.
- **No automatic decomposition** (`skills/authoring-spec/SKILL.md`) ? the existing Card is handed to RD; large specifications are not split into implementation Cards.
- **No RD or QA execution workflows** (`skills/`) ? RD and QA are Role values and dispatch targets only.
- **No audit trail beyond GitHub artifacts** ? Project field changes and Issue comments are the only durable trace.

---

## Open Decisions

- **First post-MVP capability** ? options: claim/WIP protection, field setup, decomposition, RD/QA skills, or append-only audit; need: evidence from the first disposable Project run showing the highest-cost failure.
- **Handoff partial-failure policy** ? options: keep surfaced partial failure or add compensation; need: observe whether comment failure is common and whether automatic reversal would cause more confusion.
- **Persistent installation workflow** ? options: continue development-only `--plugin-dir` usage or install the local marketplace; need: user preference after safe unrelated-repository testing.

---

## Hard-won Discoveries

+- **The clean MVP needed an orphan branch, not another incremental refactor.** Starting from an empty tree prevented the 16-skill catalog, audit migration, setup-stage framework, hooks, and dual-platform contracts from returning by inertia. `main` remains available for comparison.
+- **`--plugin-dir` is the reliable development proof.** Session-only plugins may not appear in `/plugin`; `/help`, namespaced commands, and a direct non-interactive invocation prove discovery and override stale installed copies.
+- **The earlier persistent plugin problem was a stale path/cache issue, not a manifest failure.** Direct source loading avoided the old v0.7.0 cache miss.
+- **Windows and POSIX path assumptions must not be mixed casually.** The full implementation exposed MSYS/native-Python SQLite path failures. The MVP avoids virtual environments and SQLite entirely.
+- **The generic skill initializer is unnecessary for Claude-only plugin skills.** Minimal `SKILL.md` files with correct frontmatter validated and loaded without Codex UI metadata.
+- **Narrow validation was sufficient and faster.** Nine fake-`gh` tests, manifest validation, whitespace checking, and one real Claude load covered the current risk surface without legacy suites.

---

## Blockers / Waiting On

- **Live GitHub verification** ? waiting on: GitHub CLI and a disposable Project; action needed: install `gh`, authenticate with Project scope, create or select a disposable Project with required Status/Role options, then follow `CLAUDE_TESTING.md`.
- **Remote synchronization** ? waiting on: user decision to push; action needed: push local commit `fa23e0b` and the eventual handoff commit if the remote MVP branch should be current.

---

## Current State

The checkout is on `mvp/producer-from-scratch`. HEAD remains `fa23e0b`; `origin/mvp/producer-from-scratch` is `8c8546f`, so the local branch is one committed change ahead before considering the current working tree. `main` and `origin/main` both point to `e2e1dec`.

This repository root is the loadable Claude Code plugin. Its public identity is now `agent-teams`, its marketplace is `agent-teams-local`, its entry command is `/agent-teams:using-agent-teams`, and consuming repositories use `.agent-teams/config.json`.

The rename and handoff update are uncommitted. Modified paths are the two Claude manifests, `.gitignore`, `README.md`, `CLAUDE_TESTING.md`, `HANDOFF.md`, and `scripts/producer_board.py`; the entry skill is renamed from `skills/using-board-superpowers/` to `skills/using-agent-teams/`. No process is running, no live board has been touched, and `gh` is not installed.

Latest observed verification is green: 9 unit tests passed, `claude plugin validate .` passed without warnings, and Claude loaded the new `agent-teams` namespace. The handoff skill does not authorize committing or pushing, so the next session must inspect and review this dirty working tree first.

---

## Next Steps

1. Review the complete rename diff and confirm no public `board-superpowers-producer`, `using-board-superpowers`, or `.board-superpowers/producer.json` identifiers remain outside historical Session Log text.
2. From an unrelated repository, run Claude with `--plugin-dir C:\Users\User\Documents\intern\ITRI\agent-teams` and execute `/agent-teams:using-agent-teams` plus the three no-tool routing prompts in `CLAUDE_TESTING.md`.
3. Commit the plugin rename, testing-guide changes, entry-skill move, and this handoff together on `mvp/producer-from-scratch` if the review passes.
4. Install GitHub CLI, authenticate with Project scope, and run `producer_board.py doctor` against a disposable Project with the documented Status and Role options.
5. Run one read-only dispatch, one disposable analyst intake, and one architect-to-RD handoff; extend the MVP only from observed failure evidence.

---

## Session Log

<!-- newest entry at top -->

### 2026-07-30 ? Session 2

Renamed the repository's Claude plugin identity from `board-superpowers-producer` to `agent-teams`. Renamed the local marketplace to `agent-teams-local`, moved the entry skill to `using-agent-teams`, changed the consuming config path to `.agent-teams/config.json`, and updated README/testing commands. Focused verification passed after the rename: 9 unit tests, warning-free manifest validation, and a real non-mutating `/agent-teams:using-agent-teams` load. The rename and this handoff update remain uncommitted; no live GitHub operation was performed.

---

### 2026-07-30 ? Session 1

Built the Producer MVP from an empty orphan branch and committed the core at `d9b739a`. Added and committed a detailed handoff at `8c8546f` and Claude testing guide at `fa23e0b`. Focused validation passed: 9 unit tests, Python syntax, warning-free Claude plugin validation, Git whitespace checks, and a real non-mutating Claude namespace load. No live GitHub mutation was attempted; `gh` is still missing, so disposable Project verification is the next substantive step.

---
<!-- previous sessions below this line ? do not edit -->
