# HANDOFF: agent-teams

> A Claude Code plugin for a GitHub-Project-coordinated artificial intelligence engineering team: the Producer surface is complete, and the next target is one-Card Developer execution plus evidence-grounded QA and deterministic acceptance.

**Stack**: Claude Code plugin / Python 3.12 standard library / GitHub CLI / GitHub Projects v2 / Git / Slidev

**Last updated**: 2026-08-05 by session 5

---

## Project Goal & Scope

This orphan branch builds agent-teams from an empty tree, deliberately not inheriting the earlier full framework. **The Producer half is complete.** A Producer session shapes work — creates, refines, routes, prioritises, unblocks — and a Consumer session resolves exactly one Card. Consumer execution remains the next milestone: M4 adds Developer claim/worktree/Pull Request delivery; M5 adds the new QA review, verdict, deterministic acceptance, and controlled merge path. None of that Consumer execution is built yet.

The durable coordination surface is one GitHub Project. Cards are GitHub Issues carrying two orthogonal single-select fields: `Status` (where the work is) and `Role` (whose turn it is).

The target no longer spends human attention on every passing delivery. Readiness remains the mandatory human gate. QA independently reviews the implementation, publishes evidence for the exact Pull Request head, and a separate deterministic evaluator routes `eligible` to a non-agent merge controller, `defect` back to `dev`, and `protected_change` to `human`. No agent seat directly merges or selects its own merge route.

Normative design lives in [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md); delivery status and the milestone ledger live in [`docs/IMPLEMENTATION_PLAN.md`](./docs/IMPLEMENTATION_PLAN.md). **Do not restate milestone detail here — that plan is the single status ledger.**

Still intentionally excluded: audit database, schema migrations, lifecycle hooks, automatic field provisioning, Codex packaging, multiple board backends, autonomous agent spawning. Additions need evidence from an observed failure, not inheritance from the earlier implementation.

The earlier full implementation is a **separate sibling repository**, `../agent-teams-main` (the board-superpowers fork). Its `docs/agent-team-adaptation/` dossier is the source of this adaptation's intent and is worth reading before changing the authority model.

---

## Architecture

- **This repository is the plugin.** Consuming repositories only hold `.agent-teams/config.json`.
- **Claude-only surface.** `.claude-plugin/plugin.json` names `agent-teams` v0.2.0; local marketplace is `agent-teams-local`. No Codex manifest on this branch.
- **Seven Producer skills.** `using-agent-teams` runs the mandatory read-only bootstrap, then **infers the seat and routine from the user's plain-language intent** — a person never names a seat. `intaking-requirement` (analyst), `authoring-spec` (architect), `briefing-board` / `triaging-board` / `dispatching-work` (lead), `inspecting-queue` (qa).
- **Orientation is the default and is directly callable.** A session that opens with no specific request runs `briefing-board` unprompted; "brief me" / "where are we" is also a first-class request at any point. Read-only, so it is always safe to repeat.
- **The router may never infer `human`** (ARCHITECTURE §10.2). Every other seat is safe to infer because choosing one grants nothing — policy re-checks regardless. `human` holds readiness and protected-change exception authority, so a router able to adopt it could approve its own exception. **This boundary is instruction-level, not code-enforced, and cannot be**: the adapter cannot distinguish a seat token a person supplied from one a session supplied.
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
- **One mandatory human gate plus one exception lane is the new target.** `promote_to_ready` remains refused for every agent seat including `lead`; only the human opens `Backlog -> Ready`. The delivered code still has `merge_pull_request` in `policy.HARD_FLOORS` and therefore remains human-only. M5 must atomically replace that old merge floor with deterministic acceptance and a controlled non-agent merge operation; protected or ambiguous changes still go to `human`.
- **QA owns review evidence, not merge authority.** The QA Consumer claims one `(In Review, qa)` Card/Pull Request, checks design and architecture conformance, correctness and edge cases, every changed/new file, security and compatibility, cross-file risks, and test strength. It detects blind spots, repeats affected dimensions, challenges material findings, and publishes a structured verdict bound to the exact head SHA.
- **Verdict and acceptance are separate contracts.** QA writes `pass`, `fail`, or `blocked`. Deterministic policy separately writes `eligible`, `defect`, or `protected_change`; QA cannot select its own route. A pass is invalid if stale, incomplete, missing a required dimension, or treating line execution as sufficient test evidence.
- **Protected changes are explicit.** The initial protected set covers authority/policy, QA acceptance and merge logic, GitHub workflow or credential handling, dependencies and plugin manifests, agent instruction files, security boundaries, and changes to approved architecture/design.
- **agent-teams calls no other plugin.** M5 may adapt compatible open review instructions into its own `skills/verifying-delivery/SKILL.md` with attribution, but nothing is called at runtime and correctness never depends on a sibling being installed.

---

## Established Conventions

- Work in `C:\Users\User\Documents\intern\ITRI\agent-teams-project\agent-teams`. Feature work uses a worktree under `../.worktrees/<name>`, merged back and removed when done (sessions 3 used this twice successfully).
- Keep the branch small. Do not reintroduce audit, setup-stage, hook, or dual-platform frameworks without a demonstrated failure.
- Skill directories use lowercase verb-led names and contain only `SKILL.md`. Frontmatter carries `name` and a trigger-rich `description`.
- All deterministic GitHub behaviour lives in `scripts/agent_teams/`; skills describe orchestration, judgment, and refusal boundaries.
- **Never report a mutation as successful without `"ok": true` in the CLI JSON.** Expected failures return structured error JSON on stderr and exit 1.
- Python standard library only. No dependency install, no virtualenv, no SQLite.
- Tests use an injected fake `gh` (`tests/fake_gh.py`). The suite must never need network or a real Project.
- QA evidence must distinguish execution coverage from behavioral strength. Changed-line coverage alone never establishes a pass; require branch outcomes, positive/negative scenarios, mutation resistance where applicable, and live integration evidence for GitHub behavior.
- QA may use multiple bounded reviewer agents or independent passes by dimension when the carrier supports them, but the bound QA Consumer owns completeness and synthesis. Reviewer outputs are evidence, never authority.
- Intake leaves Status `Backlog` and Role `architect`. It must not make the Card Ready — **no agent seat may**. The architect shapes and hands to `human`; the human runs `promote`, which transitions to `Ready` and hands to `dev`. `decompose` therefore creates children at `(Backlog, human)`.
- Dispatch is read-only and deterministic: configured seat order, then Card number. Say "prompt rendered", never "session started".
- When superseding a test, leave a comment saying what changed and why. Four original tests were superseded this way; the reasons are in `tests/test_producer_board.py`.

---

## Environment Setup

- Windows PowerShell and Git; Python 3.9+ (observed 3.12.3); Claude Code 2.1+.
- Tests: `python -m unittest discover -s tests -p "test_*.py"` — no dependencies required.
- Manifest validation: `claude plugin validate .`
- Development load: `claude --plugin-dir C:\Users\User\Documents\intern\ITRI\agent-teams-project\agent-teams` from an unrelated repository. Confirm the checkout is on `mvp/producer-from-scratch` first.
- Slides: `cd slides && npx slidev build` (verify) or `npm run dev` (present). `npx slidev export --format png --range N` renders individual slides for visual inspection.

**`gh` is installed at `C:\Program Files\GitHub CLI\gh.exe` but is not authenticated.** Run `gh auth login`, then `gh auth refresh -s project`. Configure a consuming repository with `producer_board.py init`, then run `producer_board.py doctor` before any mutation. Credentials stay in the GitHub CLI store, never in repository files.

Live board tests need a disposable repository and Project with all six `Status` options (Backlog, Ready, In Progress, Blocked, In Review, Done) and all six `Role` options (analyst, architect, dev, qa, lead, human). `doctor` validates all twelve and reports every missing one in a single response.

---

## External References

- [Claude Code plugin docs](https://code.claude.com/docs/en/plugins) — manifests, `--plugin-dir`, namespaces.
- [GitHub CLI Project manual](https://cli.github.com/manual/gh_project) — the commands the adapter wraps.
- [OpenCodeReview](https://github.com/alibaba/open-code-review) — strongest reviewed pattern for deterministic changed-file enumeration, bundling, high-precision line findings, and locally adaptable review instructions; do not add it as a runtime dependency.
- [PR-AF](https://github.com/Agent-Field/pr-af) — inspiration for dynamic review dimensions, evidence grounding, falsification, cross-file compound risk, and blind-spot loops; repository licensing was unclear during this research, so do not copy code or treat its benchmark claims as independent proof.
- [GitHub Agentic Workflows](https://github.com/github/gh-aw) and [safe-output policy](https://github.github.com/gh-aw/reference/safe-outputs-pull-requests/) — inspiration for read-only agents, typed validated outputs, protected files, fail-closed policy, and separation of reasoning from mutation; not a runtime dependency.
- [Prow Tide](https://docs.prow.k8s.io/docs/components/core/tide/) — the clearest open merge-controller pattern: continuously evaluate eligibility, retest against the current base, then merge; many deployments still rely on human `lgtm`/approval labels.
- [Code Review Benchmark](https://github.com/withmartian/code-review-benchmark) — open offline and online evaluator for reviewer precision/recall; useful for shadow-mode calibration before automated acceptance.
- [OpenWorker](https://github.com/andrewyng/openworker) — researched and rejected for this gate: it is a general local desktop coworker whose consequential actions are approval-gated, not a Pull Request assurance or merge-policy engine.
- [2026 automated-code-review evaluation](https://arxiv.org/abs/2606.15689) — one preprint found a severe synthetic-to-real PR performance drop; evidence against making one language-model verdict the merge authority.
- `../agent-teams-main/docs/agent-team-adaptation/` — the design dossier this adaptation implements. `03-target-architecture.md` §5.2 is the authority matrix; `00-goal.md` records why nesting is impossible.
- [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) — normative design. Appendix A records decisions 1-8; decision 8 supersedes the mandatory human merge gate for eligible changes.
- [`docs/IMPLEMENTATION_PLAN.md`](./docs/IMPLEMENTATION_PLAN.md) — the sole status ledger.
- [`docs/USAGE.md`](./docs/USAGE.md) — operating guide: setup, the daily loop, readiness, automated acceptance, protected-change exceptions, result envelopes, and troubleshooting.
- [`README.md`](./README.md) — setup, tuning knobs, full CLI reference.
- [`CLAUDE_TESTING.md`](./CLAUDE_TESTING.md) — safe, persistent-install, and live test procedure. **Stale: written for the four-skill layout.**

---

## Progress

Producer surface complete. The replacement for the mandatory second human gate
is now researched and documented as architecture, but no Consumer, QA verdict,
acceptance evaluator, or controlled merge implementation exists. Live GitHub
behavior remains unproven.

| Milestone | Status | Notes |
|---|---|---|
| Producer surface | Done | Seven skills and six deterministic modules; latest recorded suite is 130 hermetic tests from 2026-07-31 |
| QA-gate replacement research | Done | Open reviewers, agentic workflow safety, merge controllers, testing strength, and benchmark evidence assessed in session 5 |
| Normative QA workflow and decision 8 | Done | Commit `f4378ee`; QA evidence, separate acceptance result, protected-change exception, and controlled merge target documented |
| Developer Consumer (M4) | Pending | Claim/worktree/one-Pull-Request delivery is not built |
| QA Consumer (M5.1–M5.3) | Pending | `skills/verifying-delivery/SKILL.md`, verdict schema, multidimensional review, evidence challenge, and report publication are not built |
| Deterministic acceptance and merge (M5.4–M5.5) | Pending | Eligibility policy, exact-SHA invalidation, protected classification, status/check publication, controlled merge, and reconciliation are not built |
| Test-strength infrastructure | Pending | No changed-branch, mutation, state-property, or live-GitHub acceptance proof exists yet |
| Plugin manifest re-validation | Pending | Not re-run since the seven-skill layout landed |
| Test from unrelated repository | Pending | Never performed |
| Live disposable Project test | Pending | `gh` is installed but unauthenticated; disposable repository/Project still needed |

---

## Key Files

| File | Status | Description |
|---|---|---|
| `docs/ARCHITECTURE.md` | **Active / normative** | Session 5 added the New QA workflow, decision 8, protected-change policy, verdict/acceptance separation, and end-to-end target |
| `docs/IMPLEMENTATION_PLAN.md` | **Active / status ledger** | M5 now specifies locally owned QA review, evidence challenge, deterministic eligibility, controlled merge, and stronger testing |
| `docs/USAGE.md` | Active | Explains the pending target versus the still-manual delivered merge path |
| `README.md` | Active | Overview updated for one readiness gate plus protected-change exceptions |
| `HANDOFF.md` | **Modified** | This session-5 continuation record; do not commit unless the user asks |
| `scripts/agent_teams/policy.py` | **Load-bearing / target mismatch** | Pure current legality still makes merge human-only; M5 must add non-agent eligibility/merge without granting an agent seat direct merge |
| `scripts/agent_teams/model.py` | Active | Existing `Verdict` model will need exact head, conformance, review coverage, test-strength, challenges, blind spots, and limitations |
| `scripts/agent_teams/workflows.py` | Active | Producer transactions; planned home or composition seam for verdict, acceptance, merge, and reconciliation |
| `scripts/agent_teams/board.py` | Active | Semantic operations only; future acceptance/merge operations must not introduce a generic mutation escape hatch |
| `scripts/agent_teams/github.py` | Active | `gh` wrapper and likely adapter boundary for checks, Pull Request head validation, mergeability, and controlled merge |
| `scripts/producer_board.py` | Stable | Public CLI entry point; future commands must preserve existing syntax and structured envelopes |
| `skills/using-agent-teams/SKILL.md` | **Load-bearing** | Router may infer agent seats but never `human` |
| `skills/verifying-delivery/SKILL.md` | **Missing / planned** | M5 QA Consumer workflow; may adapt compatible open instructions locally but must call no sibling plugin |
| `tests/fake_gh.py` | Active / assumption risk | Shared fake `gh`; live shapes remain unverified |
| `tests/test_policy.py` | Active | Current exhaustive seat/status policy coverage; must grow for acceptance and protected-change decisions |
| `tests/test_workflows.py` | Active | Current Producer flows; no Consumer/QA/merge-controller coverage |
| `tests/test_partial_failures.py` | Active | Must eventually cover verdict/status/check/merge/reconciliation boundaries |
| `CLAUDE_TESTING.md` | **Stale** | Still describes four skills and predates the QA target |

---

## Test Status

No unit, integration, mutation, coverage, or live GitHub suite was run in session 5 because this session changed research and documentation only. The result below is the last recorded hermetic run from 2026-07-31, not fresh evidence for current HEAD.

- `python -m unittest discover -s tests -p "test_*.py"` — **130 passed**, 0.24s, no network (last recorded 2026-07-31).
- That suite exhaustively checked Status and Role pairs, partial-mutation behavior, and the current human-only merge floor. The merge-floor assertion describes the code as it exists today; the new QA acceptance/controller design is not implemented.
- Split at that run: `test_policy` 41, `test_workflows` 41, `test_producer_board` 36, `test_partial_failures` 12.
- The slide deck was previously verified by build plus a calibrated exported-PNG clipping scan.
- `git diff --check` passed for the final handoff edit; Git emitted only its normal LF-to-CRLF working-copy advisory.
- No line, branch, mutation, requirements-traceability, integration, or failure-injection metrics were produced. The new QA standard explicitly treats line execution as insufficient evidence of behavioral test strength.

Still untested: every live `gh` path; disposable-repository intake; architect docs PR; live handoff; persistent marketplace installation; manifest validation since the seven-skill layout; unrelated-repository end to end; the proposed QA verdict, acceptance evaluator, protected-change routing, and merge controller.

> The 130 green tests are hermetic and predate this session. They prove adapter behavior only against assumed response shapes. Live GitHub behavior and the new QA workflow remain the largest assurance gaps.
---

## Known Issues & Deferred Debt

- **Target/code mismatch is intentional but high-risk** — the docs now specify automated QA plus deterministic acceptance, while the implementation and the last recorded tests still enforce the old human-only merge floor. Do not describe the target as shipped.
- **The QA path does not exist yet** — no claim workflow, complete-change inventory, architecture baseline check, structured evidence schema, verdict publisher, blind-spot loop, or exact-head-SHA invalidation has been implemented.
- **Acceptance and merge enforcement do not exist yet** — there is no independent `eligible | defect | protected_change` evaluator, protected-path matcher, expected-source status check, stale-base retest, or non-agent merge controller.
- **Test-strength enforcement does not exist yet** — there are no current line/branch figures, mutation results, requirement-to-test traceability, property/state checks, or integration/failure-injection evidence. A covered line must never be treated as proof that its behavior was asserted.
- **Live `gh` JSON shapes are assumed** (`tests/fake_gh.py`) — fixtures encode expected shapes; a disposable live Project must confirm `project view`, `field-list`, `item-list`, `item-add`, and `pr view`.
- **Pagination strategy is an assumption** (`github.fetch_all_items`) — it escalates `--limit` until a response returns short. If `gh` caps the limit, this must become an explicit documented ceiling.
- **Handoff remains partially non-atomic** (`board.handoff_card`) — Role changes before the comment posts. `PartialHandoff` preserves the exact replay material but does not undo the first mutation.
- **`handoff_count` fails open** (`board.handoff_count`) — unreadable comments count as zero. This avoids stalling but can under-count ping-pong.
- **No automatic field provisioning, WIP enforcement, or independent audit store** — `doctor` only validates, `brief` only reports, and GitHub artifacts remain the audit trail.
- **`CLAUDE_TESTING.md` is stale** — it describes four skills and the old command set.
- **Specification-gate gaps remain** — an unverified non-PR pointer is accepted, and `create-card` / `transition` do not consult the gate directly.
- **Research projects are patterns, not dependencies** — OpenCodeReview, PR-AF, GitHub Agentic Workflows, Prow Tide, OpenReview, PR-Agent, Code Review Benchmark, and OpenWorker have not been installed or invoked. Recheck licensing before copying; PR-AF had no clearly identified license during this research.

---

## Open Decisions

- **Merge backend and identity** — choose GitHub auto-merge/merge queue, a GitHub App, or a narrow CLI controller; define the one non-agent identity allowed to request merge and the exact expected source of its acceptance status.
- **Protected-change matcher** — settle the versioned path/rule configuration for policy and authority code, QA acceptance/merge logic, GitHub workflows and credentials, dependency manifests, agent instructions, security boundaries, and architecture/design changes.
- **Evidence schema and thresholds** — define required fields, requirement/invariant identifiers, changed-file accounting, severity model, coverage dimensions, mutation policy including equivalent mutants, and which missing evidence fails closed.
- **Shadow-rollout exit criteria** — define the PR sample, seeded-defect suite, precision/recall targets, false-negative budget, flake budget, and rollback trigger before routine human review can be removed.
- **Review topology** — decide which bounded dimensions run as separate agents/passes when the carrier supports them, their context boundaries, and how the QA Consumer detects and repeats blind spots while retaining sole responsibility for synthesis.
- **Board routing after acceptance** — settle durable artifacts and transitions for `eligible`, `defect`, and `protected_change`, plus who reconciles a successfully merged Card to `Done`.
- **Pagination ceiling, `handoff_count` fail-open behavior, and persistent installation** — retain as live-verification decisions after authenticated GitHub testing.

**Settled** (rationale in `docs/ARCHITECTURE.md` Appendix A.2–A.3; do not relitigate without new evidence): `architect → analyst` is legal (1); `spec_completion` defaults to `merged` (2, readiness half superseded by 6); decomposition is by shape (3); transition authority keys off the destination (4); creation obeys the same destination rule on both axes (5); only `human` opens `Backlog → Ready` (6); the plugin infers agent seats but never `human` (7); and the second routine human gate is replaced in the target design by QA evidence, an independently computed acceptance result, deterministic policy enforcement, and a human exception only for protected changes (8). The current code still implements the old merge floor until M5.

---

## Hard-won Discoveries

- **An AI reviewer is not a merge controller.** Most open reviewers reduce review effort but still assume a human or platform policy makes the final decision. Removing the routine second human gate requires a separate deterministic acceptance and merge-control layer.
- **Separate reasoning, evidence, decision, and mutation.** QA may investigate and publish a structured verdict, but an independent deterministic evaluator must select `eligible`, `defect`, or `protected_change`; only a tightly scoped non-agent controller may mutate merge state.
- **Bind every verdict to the exact PR head SHA.** A new push invalidates the evidence. Current-base eligibility also requires the platform to retest or merge-queue the candidate rather than trusting a stale review.
- **Line coverage is execution evidence, not behavioral proof.** Strong assurance combines branch and scenario coverage, explicit negative paths, mutation resistance, requirement/invariant traceability, property or state testing where suitable, and integration/failure injection at risky boundaries.
- **Complete change accounting prevents quiet blind spots.** Enumerate every changed/new/deleted file, split large changes into reviewable units, and require each requirement and architectural invariant to map to implementation and test evidence.
- **OpenWorker is the wrong layer for this gate.** It is a general local coworker with approval-gated consequential actions, not a PR assurance or merge-policy system.
- **GitHub Agentic Workflows contributed the strongest safety pattern.** Read-only/default-deny capabilities, typed safe outputs, protected files, and deterministic enforcement are more important here than adopting that project as a runtime dependency.
- **Empirical reviewer quality drops on real PRs.** The reviewed 2026 study reported very low real-only F1 in its setup; do not let one LLM verdict become sole merge authority. Use multiple evidence dimensions, deterministic checks, protected exceptions, and shadow calibration.
- **A rule applied in one path is not a rule.** Earlier authority bugs survived because alternate paths reached the same state. Search and test every route to a protected outcome.
- **Hermetic fixtures can hide the largest integration risk.** The 130 tests have never exercised a real `gh`; validate response shapes and pagination before building more workflow logic on them.
- **Documents must label target versus shipped behavior.** Decision 8 deliberately changes the future architecture while the current code still has the human-only merge floor.
- **The Windows sandbox helper is unavailable in this environment.** `codex-windows-sandbox-setup.exe` could not launch, so this session needed approved out-of-sandbox reads and direct invocation of Codex's patch engine. Recheck before assuming normal sandboxed tools work.

---

## Blockers / Waiting On

- **Authenticated live GitHub verification** — `gh` is installed at `C:\Program Files\GitHub CLI\gh.exe` but is not logged in. A disposable repository and Project are still required to verify the Producer adapter, pagination, mutations, and durable artifacts before M4/M5 can be trusted end to end.
- **QA policy choices** — the merge backend/identity, expected status-check source, protected matcher, evidence schema, quantitative thresholds, and shadow-rollout exit criteria must be settled before implementing an auto-merge path.
- **Implementation authorization/scope** — this session was research and documentation only. No QA, evaluator, merge-controller, CI, or test-infrastructure implementation was requested or started.
- **Remote synchronization** — `mvp/producer-from-scratch` is one commit ahead of origin. Nothing should be pushed without the user's instruction.
- **Local tooling** — the Codex Windows sandbox setup helper is missing. Safe reads/patches were possible with approval, but future command execution may need the same workaround or a repaired installation.

---

## Current State

Repository: `C:\Users\User\Documents\intern\ITRI\agent-teams-project\agent-teams`.

Branch `mvp/producer-from-scratch` is at `f4378ee0ee467ab4c027c9eae1bb5c2c7c983844` (`feat: research second human gate replacement and write docs`), one commit ahead of `origin/mvp/producer-from-scratch`, with one worktree. The commit appeared during this session under Joanne's identity and changed `README.md`, `docs/ARCHITECTURE.md`, `docs/IMPLEMENTATION_PLAN.md`, and `docs/USAGE.md`; the assistant did not create it.

The only working-tree change after this handoff is `HANDOFF.md`. Do not commit, push, or otherwise publish it unless the user asks. No implementation, policy, workflow, or test file was changed in this session.

Producer remains v0.2.0 with seven skills and six deterministic modules. The last known test result is 130 hermetic passing tests from 2026-07-31. The documentation now contains the target QA/acceptance architecture, but runtime behavior remains the old human-only merge floor until M5 and the acceptance/controller work are implemented.

`gh`  is installed but unauthenticated. No live Project, repository mutation, PR review, external reviewer runtime, or merge attempt occurred, and no relevant process is running.

---

## Next Steps

1. Review this handoff and the committed documentation target; keep the target/current-code distinction explicit.
2. Authenticate `gh` with the needed repository and Projects scopes, create a disposable repository/Project, and close the Producer live-verification gaps including JSON shapes, pagination, intake, promotion, and handoff.
3. Settle the open QA policy choices: evidence schema, exact-head invalidation, protected matcher, thresholds, merge backend/identity, expected check source, and shadow-rollout criteria.
4. Follow the implementation-plan order unless deliberately reprioritized: build and verify the M4 Developer Consumer, then build the M5 QA Consumer around complete change inventory and bounded review dimensions.
5. Implement the structured QA verdict as evidence only, then a separate deterministic acceptance evaluator returning exactly `eligible`, `defect`, or `protected_change`.
6. Add the narrow non-agent merge controller and durable board routing: eligible may merge, defects return to Dev, protected changes route to Human, and Lead reconciles successful merge to Done.
7. Build the assurance suite before removing routine human review: branch/scenario assertions, mutation testing, requirements/invariant traceability, property/state checks where useful, integration/failure injection, stale-SHA tests, protected-path tests, and current-base/merge-queue tests.
8. Run in shadow mode against historical and seeded-defect PRs, publish precision/recall/false-negative/flake evidence, and remove the routine second human gate only after the agreed exit criteria pass.

---

## Suggested Skills

No additional plugin or skill runtime is required or desired for the planned QA workflow. Compatible open `SKILL.md` instructions may be adapted locally as documented process, with source and license attribution, but the workflow must not depend on invoking those external plugins. If multiple reviewer agents/passes are supported by the host carrier, keep them bounded by review dimension and let the QA Consumer own completeness, challenge, and synthesis.

---

## Session Log

<!-- newest entry at top -->

### 2026-08-05 — Session 5

- Researched current open approaches to replacing the second routine human code-review gate: OpenCodeReview, PR-AF, GitHub Agentic Workflows, Prow Tide, OpenReview, PR-Agent, Code Review Benchmark, OpenWorker, GitHub native merge controls, and recent empirical reviewer evaluation.
- Settled the target split: QA claims and reviews the PR, grounds and challenges findings, publishes an exact-head-SHA verdict, and never chooses its own route; an independent deterministic evaluator returns `eligible`, `defect`, or `protected_change`.
- Defined QA review dimensions: architecture/design conformance, correctness and edge cases, complete change accounting and splitting, security/compatibility, cross-file risk, behavioral test strength, and blind-spot detection/review repetition. Multiple bounded agents/passes are optional; QA owns completeness and synthesis.
- Clarified that line coverage is not test adequacy. Required evidence should include branch/scenario assertions, negative paths, mutation resistance, requirements/invariant traceability, property/state testing where suitable, and integration/failure injection.
- Updated `README.md`, `docs/ARCHITECTURE.md`, `docs/IMPLEMENTATION_PLAN.md`, and `docs/USAGE.md`; those documentation changes were committed during the session as `f4378ee` under Joanne's identity. The target is explicitly not implemented, and no external reviewer plugin becomes a runtime dependency.
- No code or tests were changed or run. `gh` is installed but unauthenticated; no live GitHub operation occurred. This `HANDOFF.md` update remains uncommitted at the user's request.

---

### 2026-07-31 — Session 4

Closed two authority holes and added the second human gate.

`create_card` wrote a whole `(Status, Role)` routing state while asking only whether the seat could create a Card. An analyst could therefore create a Card already `Ready` — bypassing the `promote_to_ready` refusal — or already owned by `dev`, forging the `analyst -> dev` edge §6.4 explicitly forbids. At the CLI it exited `0` and printed `"ok": true`. It had no test coverage at all, which is why 123 green tests never saw it. `create_card` now asks all three questions; recorded as ARCHITECTURE §16.1 decision 5.

Then, checking whether the board really had the two human gates the deck claimed: it did not. Only merge was a floor, and `promote`, `transition`, `create-card`, and `decompose` were all open to the architect. `promote_to_ready` is now `refuse` for every agent seat including `lead` — a `review`-class entry would have been decorative, since `Decision.permitted` is true for `REVIEW`. The architect hands to `human`; `promote` is the human's routine and defaults to `--acting-role human`; `decompose` creates children at `(Backlog, human)`. Because authority keys off the destination, that one change closed `transition --to Ready` and `create-card --status Ready` too. Recorded as decision 6, which supersedes the readiness half of decision 2.

Corrected a standing overclaim: agent-teams composes **no** sibling skills. `grep` finds zero references to `superpowers` or `gstack` in `skills/` or `scripts/`. §4.10, §11.12, §2.3, and the §16 decision table now say the disciplines are referenced by name, not invoked.

Then settled the **interaction model**, which was the session's other substantive change. The entry skill required a leading `[role:<seat>]` token and, on ambiguity, told the model to *"ask which seat is acting. Never guess a seat."* The user corrected this: a person should never name a role — they state intent and the plugin decides. Rewrote `using-agent-teams` around intent inference; `[role:...]` is now documented as a machine channel (the dispatch kickoff format) and an explicit override, not the human interface. Orientation became both the default opening move and a directly callable request at any point, and `briefing-board`'s description was widened to advertise it. Recorded as ARCHITECTURE §16.1 decision 7, with §3.3 and §11.1 rewritten.

Added the **`human` exemption** as a consequence: the router may infer any agent seat but never `human`, because that seat holds both gates and a router able to adopt it could approve its own readiness decision. Documented honestly that this is instruction-level and *cannot* be code-enforced — the adapter cannot tell a seat token a person supplied from one a session supplied.

Checked board-superpowers directly for two questions the user raised, rather than answering from memory:

- **Does the original use handoffs for cross-session context?** No. `docs/agent-team-adaptation/03-target-architecture.md` §5.1 says *"Add `handoff_card` to the eight actions"*; ADR-0031 is titled *"`handoff_card` as the ninth protocol action"*; the protocol's own ontology line reads *"Board / Card / Status / Claim / PR Link / Label / Comment"* — no Role. The original had no seats, so it had no "whose turn is it" question: context crossed sessions via the Card body, Status, the claim branch, and the PR contract, with `comment_on_card` marked OPTIONAL. `Role` + `handoff_card` are this adaptation's addition.
- **Does the original route by intent?** Yes, and our new model matches it. `skills/using-board-superpowers/SKILL.md` is an entry skill whose second job is *"Router"*, mapping "what should I work on" → `briefing-daily`, "new requirement" → `intaking-requirement`, "what's blocked" → `triaging-board`. Two differences: they route to *routines* (they have no seats), and on ambiguity they *ask* whereas ours orients first and proposes. They also auto-invoke via a `CLAUDE.md`/`AGENTS.md` routing block and a SessionStart hook — we deliberately have no hooks.

Also wrote **`docs/USAGE.md`** (new, ~380 lines): setup, the daily loop in plain language, the two gates, reading result envelopes and partial failures, troubleshooting, command reference. And added **ARCHITECTURE §10.0**, elaborating what each durable artifact is *for* — Project as routing index, Issue as record plus the inter-session message bus, Git as the only atomic mutual-exclusion primitive available, Pull Request as the sole home of evidence — with a design test for any proposed feature.

Tests 123 → 130. Slide deck reworked: Part 4 expanded 3 → 5 slides (added the handoff contract and partial-failure recovery), Part 5 gained a "What's Next" roadmap and lost the local-checks slide, the bug slide was removed at the user's request, "Our Seats" swapped its Token column for "The user says…", and two real clipping bugs were fixed. All 23 slides verified clear by a PNG scan calibrated against a sampled background pixel.

The user committed the code and doc changes as `2cd10b6`; `README.md` and the slides remain uncommitted. `gh` still not installed.

---

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
