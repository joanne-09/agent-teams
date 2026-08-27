# HANDOFF: agent-teams

> A Claude Code plugin whose current session automatically coordinates bounded engineering subagents through GitHub state, retaining only readiness and exceptional QA human gates.

**Stack**: Claude Code plugin / Python 3.12 standard library / GitHub CLI / GitHub Projects v2 / Git / Slidev

**Last updated**: 2026-08-28 — session 14: the QA split ran live twice; the first run went inline, the spawn-first prose fix landed, and the second run fanned out fully (structure/behaviour/risk + spec-blind browser worker, one PASS verdict on Card #28)

---

## Project Goal & Scope

This orphan branch builds agent-teams from an empty tree, deliberately not inheriting the earlier full framework. **Both the Producer and Consumer halves are now built.** A Producer session shapes work — creates, refines, routes, prioritises, unblocks. A Consumer session resolves exactly one Card: the Developer and Architect routines claim, implement, and open one Pull Request; the Quality Assurance routine reviews it, publishes evidence, and runs deterministic acceptance.

The durable coordination surface is one GitHub Project. Cards are GitHub Issues carrying two orthogonal single-select fields: `Status` (where the work is) and `Role` (whose turn it is).

The system no longer spends human attention on specification merges, prompt transport, routine implementation merges, defect routing, or reconciliation. Product specifications publish directly on the current Git branch. The current session plans work and spawns bounded subagents. Readiness remains the mandatory human gate. QA independently reviews the exact Pull Request head; deterministic policy routes `eligible` through monitored auto-merge, `defect` back to `dev`, and `protected_change` to the exceptional human gate.

Normative design lives in [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md); delivery status and the milestone ledger live in [`docs/IMPLEMENTATION_PLAN.md`](./docs/IMPLEMENTATION_PLAN.md). **Do not restate milestone detail here — that plan is the single status ledger.**

Still intentionally excluded: audit database, schema migrations, lifecycle hooks, automatic field provisioning, Codex packaging, multiple board backends, persistent daemons, and recursive agent trees. Flat current-session bounded subagent spawning is now the default carrier.

The earlier full implementation is a **separate sibling repository**, `../agent-teams-main` (the board-superpowers fork). Its `docs/agent-team-adaptation/` dossier is the source of this adaptation's intent and is worth reading before changing the authority model.

---

## Architecture

- **This repository is the plugin.** Consuming repositories only hold `.agent-teams/config.json`.
- **Claude-only surface.** `.claude-plugin/plugin.json` names `agent-teams` v0.2.0; local marketplace is `agent-teams-local`. No Codex manifest on this branch.
- **Ten focused skills — eight Producer, two Consumer.** `using-agent-teams` is the small entry router. Producer routines are `intaking-requirement` and focused `clarifying-card` (analyst), `authoring-spec` (architect), `briefing-board` / `triaging-board` / `dispatching-work` (lead), and `inspecting-queue` (qa). Consumer routines are `consuming-card` (dev and architect-documentation) and `verifying-delivery` (qa). The worker preloads none of them; each planned stage invokes exactly one on demand.
- **One plugin worker agent plus deterministic planning.** `Producer.next_actions` emits typed `spawn`, `controller`, `monitor`, and `reconcile` actions. `dispatching-work` executes them in the user's current session; no person opens a second session or copies a kickoff prompt. Workers cannot spawn grandchildren.
- **Product specs go directly to Git.** `publish-spec` stages only one `docs/*.md` path, commits and pushes it on the current branch, then records its exact last-changing commit on the Card. No spec PR, branch, worktree, or merge gate exists. Decomposed children inherit the structured spec record in their Issue bodies.
- **A Consumer request must name a Card.** `[board-card:#N]`, "work on 12", "verify #21". Without one it is not a Consumer request — orient first. The router never picks a Card on the user's behalf.
- **Orientation is the default and is directly callable.** A session that opens with no specific request runs `briefing-board` unprompted. Read-only, so it is always safe to repeat.
- **The router may never infer `human`** (ARCHITECTURE §10.2). Every other seat is safe to infer because choosing one grants nothing — policy re-checks regardless. **This boundary is instruction-level, not code-enforced, and cannot be**: the adapter cannot distinguish a seat token a person supplied from one a session supplied.
- **Seven functional modules** keep a strict downward dependency direction: model, policy, config, github, git, board, and workflows. errors.py supplies the shared expected-failure base, and scripts/producer_board.py remains the stable public entry point every skill invokes.
- **`policy.py` touches no network**, and now also owns acceptance. It reads a `Config` duck-typed rather than importing it, preserving the dependency direction. That purity is why every acceptance route is asserted individually.
- **The remote claim branch is the mutual-exclusion primitive**, and the claim pushes a *unique empty commit* rather than the base SHA — see Hard-won Discoveries, this is the single most important implementation detail on the branch.
- **Semantic operations only.** No `set_card_field`, and no CLI flag through which a caller could steer an acceptance route.
- **Authority is checked before the first GitHub call**, so a refusal costs nothing and leaves no partial state.
- **Status and Role are orthogonal.** A handoff changes Role and writes context; it never silently changes Status. When both must move, that is two operations.
- **Honest partial failure.** Multi-step mutations return `{ok:false, partial:true, completed:[...], failed:..., recovery:[...]}`. Creation steps are never replayed; nothing ever claims a rollback that did not run.
- **The gates are enumerable, and openable from a surface that is not a terminal.** `human_gates` (CLI `gates`) is `next_actions` narrowed to the gate list, so the two cannot disagree. Every entry carries `argv` when a plugin command opens the gate (`readiness`, `qa_exception`) and `pull_request` when GitHub does (`spec_merge`, `manual_merge`) — a gate with no `argv` has no plugin command *by design*, and a surface that drew a button for one would be inventing authority the plugin refuses. `AGENT_TEAMS_HUMAN_ORIGIN` is a provenance label on the resulting comment, never a grant: `resolve_acting_role` still keys on the agent markers alone.
- **One human gate plus one exception lane, now implemented.** `promote_to_ready` refuses every agent seat including `lead`. `merge_pull_request` — free-form merge of a caller-chosen Pull Request — **remains in `policy.HARD_FLOORS`**; decision 8 did not remove it. A companion action `request_automated_merge` is refused to *all six* seats including `human`, so "no seat may request a merge" is an assertion rather than an absence.
- **Verdict and acceptance are separate types**, neither convertible into the other. QA writes `Verdict` (`pass`/`fail`/`blocked`, bound to the exact head SHA); policy writes `Acceptance` (`eligible`/`defect`/`protected_change`); QA cannot select its own route. That separation is structural, not prose.
- **Protected changes name files, not just categories.** Seven default categories, configurable; policy may add but emptying a default category is a configuration error.
- **agent-teams calls no other plugin.** Skill content is derived locally with attribution; nothing is called at runtime and correctness never depends on a sibling being installed.
- **All eight Producer skills use focused, attributed procedures.** The new clarifying-card skill separates existing-Card recovery from new intake. Source disciplines are adapted locally from board-superpowers, superpowers, and gstack; ATTRIBUTION.md records what was reused and what agent-teams invented. No sibling plugin is a runtime dependency.
- **release-claim is deprecated emergency cleanup, not a routine gate.** Normal interrupted work resumes the existing remote claim branch automatically. Destructive deletion remains human-only for evidence-backed cases where preserving the branch is unsafe.

---

## Established Conventions

- Work in `C:\Users\User\Documents\intern\ITRI\agent-teams-project\agent-teams`. Feature work has used a worktree under `../.worktrees/<name>`; session 6 did this and then, at the user's request, moved the result onto the main branch and deleted the worktree. **Note the collision risk**: `../.worktrees` is also the default `workspace` for Consumer claim worktrees (`claim-<n>-<slug>`), so development worktrees should not reuse that naming.
- Keep the branch small. Do not reintroduce audit, setup-stage, hook, or dual-platform frameworks without a demonstrated failure.
- Skill directories use lowercase verb-led names; `SKILL.md` plus an optional `references/` directory. Frontmatter carries `name` and a trigger-rich `description` including do-NOT-use disambiguation.
- The bounded worker must have the Skill tool and no skills preload list. Every spawn action names exactly one qualified workflow skill; that skill and its conditional references load on demand.
- **Derived skills carry a four-line attribution comment** naming what was derived, the source with MIT + copyright holder + URL, and a pointer to `ATTRIBUTION.md`. Keep it short — a `SKILL.md` body is loaded into context every time the skill fires, and provenance detail is not operational content. Per-element `DERIVED` / `INVENTED` labels live in `ATTRIBUTION.md`.
- **Never cite a source you have not read.** Session 6 found four such citations, and the over-claim concealed a real defect. See Hard-won Discoveries.
- All deterministic GitHub behaviour lives in `scripts/agent_teams/`; skills describe orchestration, judgment, and refusal boundaries. Skills contain no raw Project field identifiers and no ad hoc `gh` commands.
- **Never report a mutation as successful without `"ok": true` in the CLI JSON.** Expected failures return structured error JSON on stderr and exit 1. A lost claim race exits 1.
- Python standard library only. No dependency install, no virtualenv, no SQLite.
- Tests use an injected fake `gh` (`tests/fake_gh.py`) and a fake Git (`tests/fake_gh.FakeGit`). The claim-race tests are the exception: they drive **real git** against a local bare repository, because a fake would have agreed with the wrong implementation.
- **Evidence must be structured to be checkable.** `test_strength` entries are objects with a `dimension` from a closed vocabulary, `evidence`, and optionally `falsified_by`. Free prose is refused — a substring search for "branch" accepts "no branch coverage".
- Intake leaves Status `Backlog` and Role `architect`. No agent seat may make a Card Ready. `decompose` creates children at `(Backlog, human)`.
- `dispatch` remains a read-only compatibility view. Automation uses WIP-aware `next-actions`: current-session workers are actually started, direct-spec authoring is serialized, and durable GitHub state—not child prose—decides completion.
- When superseding a test, leave a comment saying what changed and why. Sessions 4 and 6 both did this; the reasons are inline in `tests/test_policy.py` and `tests/test_consumer.py`.

---

## Environment Setup

- Windows PowerShell and Git; Python 3.9+ (observed 3.12.3); Claude Code 2.1+.
- Tests: `python -m unittest discover -s tests -p "test_*.py"` — no dependencies required. Expect ~40s; the real-git claim tests dominate.
- Manifest validation: `claude plugin validate .`
- Sibling-invariant check: `grep -rE "superpowers:|gstack:/" skills/` must return nothing.
- Development load: `claude --plugin-dir C:\Users\User\Documents\intern\ITRI\agent-teams-project\agent-teams` from an unrelated repository. Confirm the checkout is on `mvp/producer-from-scratch` first.
- Slides: `cd slides && npx slidev build` (verify) or `npm run dev` (present). `npx slidev export --format png --range N` renders individual slides.

**`gh` is installed at `C:\Program Files\GitHub CLI\gh.exe` but is not authenticated.** Run `gh auth login`, then `gh auth refresh -s project`. Configure a consuming repository with `producer_board.py init`, then `producer_board.py doctor`. Credentials stay in the GitHub CLI store.

Live board tests need a disposable repository and Project with all six `Status` options and all six `Role` options. **For the acceptance path they additionally need**: repository auto-merge enabled, branch protection with required checks, and `required_checks` set in config. `doctor` reports both as non-fatal `acceptance_problems`.

---

## External References

- [Claude Code plugin docs](https://code.claude.com/docs/en/plugins) — manifests, `--plugin-dir`, namespaces.
- [Claude Code subagent docs](https://code.claude.com/docs/en/sub-agents) — confirms that skills listed in subagent frontmatter are fully preloaded, while unlisted skills remain invocable through the Skill tool.
- [GitHub CLI Project manual](https://cli.github.com/manual/gh_project) — the commands the adapter wraps.
- [board-superpowers](https://github.com/PanQiWei/board-superpowers) — MIT. Source for `consuming-card` and `enforcing-pr-contract` derivations; also present locally at `../agent-teams-main`.
- [superpowers](https://github.com/obra/superpowers) — MIT. Source for TDD and evidence-before-claims discipline. Local copy in the plugin cache under `claude-plugins-official/superpowers/6.2.0/`.
- [gstack](https://github.com/garrytan/gstack) — MIT. Source for the pre-emit verification gate, confidence calibration, and browser-QA discipline. **Not installed locally**; fetch source text with `curl` on `raw.githubusercontent.com`, not WebFetch (see Hard-won Discoveries).
- [OpenCodeReview](https://github.com/alibaba/open-code-review), [PR-AF](https://github.com/Agent-Field/pr-af), [GitHub Agentic Workflows](https://github.com/github/gh-aw), [Prow Tide](https://docs.prow.k8s.io/docs/components/core/tide/), [Code Review Benchmark](https://github.com/withmartian/code-review-benchmark) — researched patterns, never dependencies.
- [2026 automated-code-review evaluation](https://arxiv.org/abs/2606.15689) — evidence against making one language-model verdict the merge authority.
- `../agent-teams-main/docs/agent-team-adaptation/` — the design dossier this adaptation implements.
- [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) — normative design. Appendix A records decisions 1-8; decision 8 is now implemented.
- [`docs/IMPLEMENTATION_PLAN.md`](./docs/IMPLEMENTATION_PLAN.md) — the sole status ledger.
- [`docs/specs/2026-08-06-consumer-flow-design.md`](./docs/specs/2026-08-06-consumer-flow-design.md) — the approved Consumer design.
- [`docs/plans/2026-08-06-consumer-flow.md`](./docs/plans/2026-08-06-consumer-flow.md) — the 17-task implementation plan that was executed.
- [`ATTRIBUTION.md`](./ATTRIBUTION.md) — per-element `DERIVED` / `INVENTED` labels and the record of what was verified how.
- [`slides/2026-08-06-weekly.md`](./slides/2026-08-06-weekly.md) — **the QA flow contract.** Session 6 treated this as authoritative and fixed the implementation to match it.

---

## Progress

The automation extension and lazy-loading skill architecture are implemented on
mvp/producer-from-scratch. The user committed the automation as cf4f681,
committed the skill split as 6f6851a, and merged the updated remote branch as
bbf1335. Before this handoff update, the worktree was clean.

| Milestone | Status | Notes |
|---|---|---|
| Direct specification publication | Done | Exact path and commit recorded on the Card; no spec PR |
| Same-session automation | Done | next-actions drives bounded workers, controllers, monitors, and reconciliation |
| Minimal human surface | Done | One mandatory Status-to-Ready gate; protected or ambiguous QA is conditional |
| Automatic delivery tail | Done | Defect loop, delayed-check monitoring, exact-head auto-merge, and Done reconciliation |
| Lazy workflow loading | Done | Worker preloads no workflow bodies and invokes exactly one selected skill |
| Focused clarification | Done | clarifying-card handles returned existing Cards; intake creates only new Cards |
| Runtime source reuse decision | Done | Source procedures are adapted locally and attributed; no sibling plugin installation required |
| Live Consumer and merge proof | **Done** (Lee's side, 08-12) | Full live run on the real board: eligible auto-merge, defect/exception lane, exact-head re-verification, automatic reconciliation — see session 9 |
| Demo annotation package | Pending | Team-lead feedback requests annotated slides, node screenshots, and a Word record of intake questions |

---

## Key Files

| File | Status | Description |
|---|---|---|
| agents/agent-teams-worker.md | Load-bearing | Generic bounded carrier with the Skill tool and no workflow preload list |
| scripts/agent_teams/workflows.py | Load-bearing | next-actions selects one routine and qualified skill; also owns readiness, resume, acceptance, and reconciliation workflows |
| skills/clarifying-card/SKILL.md | New / stable | Resolves one question on an existing Backlog analyst Card without creating a duplicate |
| skills/intaking-requirement/SKILL.md | Active | New-requirement intake only; returned-Card behavior was extracted |
| skills/dispatching-work/SKILL.md | Load-bearing | Current-session orchestration loop and exact-skill worker launch |
| skills/using-agent-teams/SKILL.md | Load-bearing | Small intent router; never selects human |
| scripts/agent_teams/policy.py | Load-bearing | Network-free authority, verdict validation, and deterministic acceptance |
| scripts/agent_teams/git.py | Load-bearing | Unique remote claim commit, resume lookup, and guarded worktrees |
| scripts/agent_teams/board.py | Active | Semantic Project, Issue, Pull Request, verdict, and acceptance operations |
| README.md | Active | Simple workflow explanation and source-reuse versus agent-teams overlay |
| docs/ARCHITECTURE.md | Normative | On-demand skill composition and the governance design |
| CLAUDE_TESTING.md | Active | Ten-skill and lazy-worker verification checklist |
| tests/test_workflows.py | Active | Planner skill markers, clarifying route, and no-preload worker contract |
| tests/fake_gh.py | Assumption risk | Fake GitHub shapes; still requires live comparison |

---

## Test Status

Session 8 ran only focused checks, as requested:

- 16 planner and worker-loading tests passed in 0.012 seconds.
- clarifying-card, intaking-requirement, using-agent-teams, and dispatching-work all passed quick_validate.py.
- claude plugin validate . passed.
- git diff --check passed before this handoff update.

The automation implementation previously passed a 241-test focused regression
set and the full 385-test hermetic suite in 93.795 seconds before it was
committed as cf4f681. The full suite was not rerun after the lazy-loading split;
the 16 focused tests cover the changed planner and worker contract.

Hermetic tests prove the policy decision table, claim exclusivity against real
Git, exact-head protection, partial-failure handling, direct specification
records, decomposition replay, WIP admission, delayed merge monitoring, and
merge-evidence-only Done.

They do not prove that a real Claude child invokes exactly one Skill at runtime,
that the Consumer GitHub CLI JSON assumptions match a live repository, or that
auto-merge and protected QA work end to end.

---

## Known Issues & Deferred Debt

- **Lazy loading lacks a live child trace** (agents/agent-teams-worker.md) — tests prove the frontmatter and planner markers, but no headless Claude run has yet shown that one worker invokes exactly one skill and no unrelated body.
- **Readiness can be displayed from a stale spec record** (scripts/agent_teams/workflows.py, next_actions) — finalization safely refuses a changed or missing exact commit, but the planner can still ask the human to move Status to Ready before detecting that staleness.
- **Live GitHub JSON shapes: one corrected, rest behaved but unaudited** (tests/fake_gh.py) — the 08-12 live run surfaced and fixed the first real mismatch (`gh repo view` has no `autoMergeAllowed` JSON field on gh 2.97.0; `auto_merge_enabled()` now reads REST `allow_auto_merge`, fake updated — commit 6dd0289). PR view/checks/merge shapes worked live end to end but have not been compared field-for-field.
- **Consumer acceptance live proof: eligible and defect routes proven live (08-12); `protected_change` route still fake-only** — no live delivery has yet touched a protected path.
- **The demo package is behind the code** (slides/) — team-lead feedback asks for clear GitHub-versus-agent-teams annotations, generated-versus-handwritten Card labels, skill provenance per prompt, a dedicated merge-logic slide, screenshots of every end-to-end node, and a Word document containing the analyst questions.
- **falsified_by remains attested evidence** (scripts/agent_teams/policy.py) — the schema requires a specific mutation and named failing test but cannot prove the mutation was executed.
- **Handoff remains partially non-atomic** (scripts/agent_teams/board.py) — Role changes before the comment posts; PartialHandoff preserves fix-forward material.
- ~~Pagination remains heuristic~~ — replaced 08-21: `Board.ITEMS_QUERY` pages by GraphQL cursor (1 rate-limit point per page vs ~1 point per item for `gh project item-list`); `fetch_all_items` is left in github.py unused and can be deleted.
- **Seat binding is a process-level floor, not a cryptographic one** (scripts/agent_teams/policy.py, resolve_acting_role) — an agent that deliberately scrubs `CLAUDECODE` from its environment can still claim `human`. The merge floor remains GitHub branch protection. See CONFIGURATION.md "Process environment".
- **Plugin snapshot layout** — `claude plugin install` from the local marketplace copies the whole working tree (546 MB with slides/node_modules; .gitignore not honoured). Move the deck out of the plugin repo or point `source` at a `plugin/` subdirectory.
- **Installed snapshot drifts from source** — `claude plugin update` is a no-op while the version string is unchanged; uninstall + install after pulls.
- ~~**The CCAM dashboard's config form is behind this branch**~~ — resolved
  2026-08-27 in `../agent-teams-dashboard` (uncommitted, branch
  `feat/plugin-scope-listing`). The descriptor now carries the current key
  names, a per-role section, and `ui_paths`; the form resolves inherited
  defaults. Verified against the real plugin: `# pass 9`, `# fail 0`.
- **The two repositories can drift** (`agent-teams-dashboard`
  `server/lib/agent-teams/config-schema.js`) — the descriptor is
  documentation-derived and is not imported from the plugin, so a future
  config key silently fails to appear in the form. The dashboard test now
  pins the three renamed keys and rejects the old ones, which catches a
  *rename*; it cannot catch an *addition*. Adding a config key means editing
  that file too.
- **The QA decomposition has never run live** (agents/qa-browser-worker.md,
  skills/verifying-delivery) — 517 hermetic tests prove the browser-evidence
  refusal, the seat contracts, and the per-role schedules. Nothing proves that
  a real `qa-worker` actually spawns three passes and a browser worker, that
  the browser worker stays blind to the diff in practice, or that Playwright
  drives the delivered app from a detached worktree. First real test is the new
  dataset run.
- ~~**Nested QA helpers may re-break dashboard attribution**~~ (todo item 8) —
  checked 2026-08-27. The 08-21 `SubagentStop` fix **holds at depth 3**
  (coordinator → `qa-worker` → typed helper); a new regression test in the
  dashboard's `server/__tests__/api.test.js` pins it, and the full server suite
  is 115/115. Residual, deliberately not fixed: attribution among several
  *untyped* helpers running concurrently still uses the oldest-working
  fallback, so review passes can complete in the wrong order in the Workflows
  tab. Cosmetic — a typed seat worker can no longer be completed by a helper,
  which was the damaging form.
- **The dashboard gate button widens who can open a gate, by exactly as much as the dashboard is reachable** (`agent-teams-dashboard`
  `server/lib/agent-teams/gates.js`) — it strips `CLAUDECODE` /
  `CLAUDE_CODE_SESSION_ID` from the child, which is the same environment
  scrub the plugin's own docstring names as the way to lie about being a
  person. That is correct for a browser click and indistinguishable from a
  `curl` of the localhost API. Mitigations shipped: the readiness gate only
  moves a Card to Ready; the **merge** gate needs
  `AGENT_TEAMS_HUMAN_GATES=merge` on the server; the client sends a Card and
  a gate kind, never a command. Unmitigated: set `DASHBOARD_TOKEN` if the
  host is shared. The floor under a merge is still branch protection.
- **The gate button has never run against a live board** (`server/lib/agent-teams/gates.js`) — 12 hermetic tests prove the opt-in, the refusal to take a command from the client, and the environment scrub; nothing yet proves `gates` parses on a real board or that `promote` succeeds through the subprocess. First real test is the next dataset run.
- **`browser_evidence` is attested, like `falsified_by`** (policy.py) — the
  schema can require a flow, an invalid-input case, and a console reading; it
  cannot prove a browser was ever opened.
- **No automatic field provisioning or audit database** — intentionally deferred; doctor validates and GitHub artifacts remain the trail.

---

## Open Decisions

- **Live-rollout exit criteria** — decide the Pull Request sample, seeded-defect set, precision/recall target, false-negative budget, and rollback trigger before trusting automated acceptance outside shadow mode.
- **Mutation-testing infrastructure** — decide whether to add a tool that can verify QA falsification claims instead of only validating their structure.
- **Parent Card closure** — decide whether and when a decomposed parent becomes Done after all children ship; live Card #18 is now the concrete case (#19/#20 Done, #21 held, parent still `(Backlog, architect)`).
- **Demo scope and audience** — decide whether the next deck update targets the requested internal colleague-sharing package only or also prepares for the broader meeting.

Settled this session: workflow skills remain locally adapted and attributed
rather than runtime dependencies; the worker preserves dynamic loading by
invoking one selected skill through the Skill tool. The human changes only Card
Status to Ready after architect completion; the controller performs the
deterministic validation and Role handoff.

---

## Hard-won Discoveries

- **Subagent skills frontmatter is eager, not lazy.** Listing six skills in agent-teams-worker injected all six complete bodies at startup. Removing that list and retaining the Skill tool preserves on-demand loading; next-actions must name the one qualified skill explicitly.
- **A mixed intake skill creates routing risk.** New-requirement intake and returned-Card clarification have different mutation boundaries. Extracting clarifying-card prevents a returned Card from accidentally running intake and creating a duplicate Issue.
- **Reuse and architecture are different layers.** board-superpowers, superpowers, and gstack provide strong engineering procedures. Agent-teams should reuse those ideas in focused, attributed skills while owning only the Card routing, Ready gate, durable claim, exact-head acceptance, and automation overlay.
- **A recorded specification is not automatically current.** The final readiness controller rechecks the exact Git commit; the planner must do the same before showing the human gate if it wants the instruction timing to be exact.
- **The obvious Git claim gives two winners.** Pushing the shared base SHA is a no-op success that skips force-with-lease evaluation. A unique empty claim commit is required, and real-Git race tests are essential.
- **Free-prose evidence is not checkable.** Test strength and findings need structured dimensions, quoted code, challenge results, and named falsification evidence.
- **A rule applied on one route is not a rule.** Every alternate path to Ready, Done, or merge must be searched and tested; generic create and transition previously bypassed governance.
- **Source claims must be verified.** Earlier unread citations concealed a Pull Request closing-keyword defect. Read the exact source before recording derivation.
- **The Windows sandbox helper is missing.** codex-windows-sandbox-setup.exe cannot launch, so apply_patch and default shell calls fail. This session used validated Git patches outside the broken helper; no destructive fallback was used.
- **Line endings can produce false differences.** Normalize CRLF/LF before trusting checksums or destructive cleanup decisions.

---

## Blockers / Waiting On

No local implementation blocker.

- ~~**Live Consumer proof**~~ — resolved 08-12: `agent-teams-test` now has branch protection (strict, required check `test` via `.github/workflows/ci.yml`), repository auto-merge, and `required_checks` in config; `doctor` reports empty `acceptance_problems`; the live run exercised the whole tail.
- ~~**Lazy-loading runtime proof**~~ — resolved 08-12: each live worker's kickoff named exactly one `[skill:...]` and per-worker transcripts (session `subagents/` directory in Lee's `~/.claude-team` config) show one Skill invocation per worker.
- **Demo assets and annotations** — waiting on execution of the requested slide, screenshot, and Word-document work; the feedback itself is already captured in this handoff.
- **Push or further commits** — require explicit user instruction. Do not commit, push, create another branch, or create a worktree automatically.

---

## Current State

mvp/producer-from-scratch, **uncommitted session-12 and session-13 work** on
top of the 08-21 commit (Lee's side), itself on 980a93c (Joanne's config
externalization + recovery) and 3f82792 (08-21 slides). Full suite 535/535;
`claude plugin validate .` passes; `git diff --check` clean. The dashboard
side is uncommitted on `feat/plugin-scope-listing`: server 1047/1047,
client 334/334, `tsc -b` clean. Nothing committed or pushed in either
repository — that still requires explicit user instruction.

**Session 12 touches Joanne's config work directly.** The externalized config
grew a `roles` block and lost three key names to clearer ones (old names still
load). See the session log below for the shape and the reasoning; the
dashboard's config form needs the same keys added on Lee's side.

**For Joanne — things that changed under you since 980a93c (please review, all
touch your files):**

1. **Five seat workers replace `agents/agent-teams-worker.md`** (`analyst-/architect-/dev-/qa-/lead-worker.md`, identical contract; `_spawn_action` emits `"agent": "agent-teams:<seat>-worker"` and `"env": {"AGENT_TEAMS_ACTING_ROLE": "<seat>"}`). Reason: external monitors learn the role from the agent type, not the prompt.
2. **`.claude-plugin/marketplace.json` rewritten** — marketplace name `agent-teams` (was your `agent-teams-local`), installed into the demo config as `agent-teams@agent-teams`. Lee decided to keep this one; say if you object.
3. **`--acting-role` is no longer trusted** (`policy.resolve_acting_role`, `producer_board.py`): `AGENT_TEAMS_ACTING_ROLE` binds a process to a seat, and inside any Claude Code shell a command that claims or defaults to `human` is refused. Live cause: the lead ran `promote 27` with no flag and inherited the human default. `main()` takes `env=` for tests; tests pass `env={}`.
4. **PR body contract changed** (`validate_pr_body`, ARCHITECTURE 9.5, pr-contract.md): `Card: #<issue>` is required and `Closes/Fixes/Resolves #N` is **refused**; `_reconcile_to_done` closes the Issue itself (`Board.close_issue`). Reason: GitHub closing the Issue on merge races `reconcile` on any Project with the default "item closed → Done" workflow.
5. **accept-after-merge fixed**: a merged PR reports `mergeable: UNKNOWN` forever; policy no longer waits on it (`pr_facts["merged"]`), and `accept` skips `arm_auto_merge` on a merged PR.
6. **Board reads**: lean GraphQL query + per-process memo keyed on `Gh.mutations`; `_is_safe_read` treats `api graphql` query documents as reads. Measured: `item-list --limit 100` = 101 points on a 4-card board; the new query = 1.
7. **`verifying-delivery`** forbids checking out the PR branch in the repo root (detached review worktree instead) — a QA worker left the main checkout on `pr-29` live.
8. **The CCAM dashboard** (`reference/ccam` in Lee's tree, fork of hoangsonww/Claude-Code-Agent-Monitor) edits `.agent-teams/config.json` through a Python bridge that imports your `Config` and depends on exactly `Config.from_dict / to_dict / revision / write`; its form descriptor mirrors the CONFIGURATION.md tables — keep them in sync if you add keys.
9. **Host setting for Ollama-served models**: `skillListingBudgetFraction: 0.05` (documented in CONFIGURATION.md) — without it 8 of 10 skill descriptions are dropped and intent routing fails silently.

## Next Steps

0. **Run the new dataset end to end with the QA split on** (todo 6). It is the
   first live test of the browser worker, the three review passes, and the
   nested-spawn dashboard attribution all at once. Verify both JSON and CSV
   inputs; the new use case is store/venue info, not transit routing.
0b. **Have the team lead execute `docs/RUNBOOK.md` cold** (todo 7 — the
   document is written; the point of it is the dry run). Ask them to note
   the last Checkpoint that passed wherever they get stuck; that note is
   the defect report. Part 7 (dashboard) especially needs correcting from
   a real setup.
0c. **Commit the dashboard changes** — `../agent-teams-dashboard` has
   uncommitted work on `feat/plugin-scope-listing` (config descriptor, the
   inheritance-aware form, the depth-3 regression test, and now the human-gate
   route, panel, and its 12 tests). Left uncommitted at the user's
   instruction, same as this repository.
0d. **Press the gate button once against the live board** (session 13). The
   readiness route is the one to try: start the dashboard, open the Agent
   Teams page against `agent-teams-test`, and approve the Card held at the
   gate. Card #21 is still deliberately parked there from session 9, which
   makes it the obvious subject — decide first whether to spend it.

1. ~~Lazy-loading runtime evidence~~ — done live 08-12 (see session 9); optionally archive the worker transcripts as durable evidence.
2. Tighten Producer.next_actions so a Backlog human Card is shown as a readiness gate only when check_spec_gate confirms the recorded exact commit is still current; add the focused stale-record test.
3. ~~Live eligible and defect routes~~ — done 08-12. Remaining: exercise the `protected_change` route live (a delivery touching e.g. `scripts/agent_teams/policy.py` or `.github/`), and optionally compare PR JSON field-for-field against tests/fake_gh.py.
4. Update the demo materials from the team-lead feedback: annotate GitHub versus agent-teams behavior, identify generated versus handwritten Cards, label prompt-to-skill provenance, isolate merge logic, capture each end-to-end node, and produce the requested Word question record.
5. Review this HANDOFF.md diff and commit or push only when the user explicitly asks.

---

## Suggested Skills

Use dispatching-work only in the coordinating session. A bounded worker should
invoke exactly the qualified skill returned by next-actions; do not restore a
skills preload list. Keep source-derived disciplines in focused local skills
and conditional references, with attribution, unless a future explicit
decision accepts sibling plugins as runtime dependencies.

---

## Session Log

<!-- newest entry at top -->

### 2026-08-28 — Session 14 (Lee: the QA split ran live, went inline once, and the prose got fixed)

Two live re-verification runs (glm-5.2 over Ollama, tmux demo session, Lee's tree).

**Run 1, Card #26**: PASS at the merged head; the stuck 08-21 card is finally Done. The browser-evidence gate fired twice — first refusing the worker's attempt to publish without a browser pass, then refusing a malformed `browser_evidence.console` shape. **The fan-out did not happen**: no helper spawns, no deliberation, one agent inline.

**Why (checked, not assumed)**: not the platform — a live probe showed a background-spawned qa-worker spawns `agent-teams:qa-browser-worker` fine, and current docs allow 3-layer nesting. The cause was our own text: `qa-worker.md`'s shared contract said "do not spawn another agent" two sections before the helpers section allowed it, and `verifying-delivery` called a single inline pass "a complete and valid review — dispatch what the session supports". glm resolved the contradiction conservatively.

**The fix (this session, tests 462→535 still green, `plugin validate` OK)**: spawn-first wording in three places — `agents/qa-worker.md` (contract line now grants exactly the helpers; fallback requires an *attempted* spawn and records the failure mode in `limitations`), `skills/verifying-delivery/SKILL.md` (Reviewer-passes intro: "dispatching is not a judgment call"; 7b exception now triggers only on a failed attempt — the test-pinned "if no browser worker was dispatched" phrase kept), and the decision record's fallback paragraph.

**Run 2, Card #28** (board manually reverted with raw `gh` + verdict/acceptance comments deleted — Done is terminal in policy, deliberate bypass, user-approved): **full fan-out** — structure/behaviour/risk + spec-blind browser worker under one qa seat, one PASS verdict. 43/43 tests, 11 flows + 8 garbage-input cases (XSS rendered as literal text, 0 script tags, clean console), security 10/10, mutation-confirmed test strength, and one genuine finding: the DOM wiring layer has no test that fails when it breaks (the risk pass deleted it; 43/43 stayed green) — spec-accepted, follow-up Card candidate.

Deck: QA pages of `slides/2026-08-28-weekly.md` updated with the real evidence (new "The Split, Live" + "What Each Reviewer Did" pages — the latter replaced a short-lived "First Run Ignored the Split" page at the user's request — real XSS case replacing the placeholder JSON, stale "nothing ran live" notes corrected); PNG-export checked. Dashboard again duplicated helper rows with shifting parents and left one stale "Working" — root-caused and fixed the same night in the dashboard fork (`a37ae9d`): a named teammate's meta.json records its instance name as agentType, which minted fake per-card subagent types in the Workflows views and broke the transcript-to-live-row match.

**Late addition — the gate button was pressed for real.** Joanne's dashboard half landed on Windmill10/claude-code-agent-monitor (`d5b225e`, with `8e09e4c` fixing the config-rename drift; server suite green after both). To press it against a genuine gate: intake → spec ran for the QA-recommended follow-up (**Card #32**, failing-on-breakage tests for the search DOM-wiring layer; spec `docs/specs/2026-08-28-card-32-search-wiring-tests.md`, commit 734d2a7 — note: it commits to a `_dom`-seam refactor of oil-map.js, so acceptance must re-confirm the browser pass). The Human-gates panel listed the readiness gate; the **Approve button** promoted it — the board flipped to `(Ready, dev)` with no terminal involved — and the run stopped there deliberately: #32 sits at `(Ready, dev)` as the natural live-demo starter. Deck gained two pages ("The Human Gate Is a Button" in Part 1, "The Same Gate, One Week Later" after Part 2's readiness-gate page) with before/after panel screenshots in `slides/images/2026-08-28/`.

### 2026-08-27 — Session 13 (the human gate stopped needing a terminal)

The readiness gate was the last routine step that made a person leave whatever
they were doing and type `producer_board.py promote 19`. It is now a button on
the dashboard's Agent Teams page. Both repositories changed; both are
uncommitted.

**Plugin.** `human_gates` (CLI `gates`) is `next_actions` narrowed to the gate
list — the same computation, so the two cannot disagree about whether a gate is
open, and a person-facing surface never has to read a plan that names subagent
spawns. Every gate entry now goes through one `_gate` helper and has one shape.

The shape is the part worth remembering. Before this, `readiness` carried
`cli_convenience: "promote 19"`, `qa_exception` carried
`command: "approve-exception 21"`, and `spec_merge` / `manual_merge` carried
neither — three spellings of the same idea and one silent gap. Now every entry
has `argv`: a list when a plugin command opens the gate, `null` when GitHub
does, in which case it carries `pull_request` instead. That `null` is
normative, not a placeholder — no seat, the human included, may merge a Pull
Request of its own choosing (`HARD_FLOORS`), so a surface drawing a button for
those gates would be inventing authority the plugin refuses.

`AGENT_TEAMS_HUMAN_ORIGIN` (`terminal` | `dashboard`) came out of the same
work. It is deliberately **not** an authority mechanism: `resolve_acting_role`
still keys on the agent markers alone, so an agent session stamping itself
`dashboard` is refused exactly as before — there is a test that asserts
precisely that, because it is the property most likely to be "simplified" away
later. What it earns is the trail: `promote` appends the surface to the handoff
comment, and `approve_exception` writes it to the Card *before* it merges,
since that is the one route by which a protected change reaches the base branch
and the record has to survive a failed merge. The vocabulary is closed because
the value lands in a GitHub comment.

**Dashboard** (`../agent-teams-dashboard`, `feat/plugin-scope-listing`).
`server/lib/agent-teams/gates.js` + two routes + `AgentTeamsGates.tsx`, which
now sits above the config form because it is the part that waits on you.

**The honest part, and the reason this took design rather than plumbing.** The
plugin refuses the `human` seat to any process carrying `CLAUDECODE`, and the
dashboard server has almost certainly inherited it from the terminal that
started it. So the child's environment is scrubbed of those markers — which is
*exactly* the manoeuvre `resolve_acting_role`'s own docstring names as the way
an agent lies about being a person. It is right here (a person clicked) and
indistinguishable from a `curl` of the localhost API. Three things keep it
proportionate rather than pretending it is airtight:

1. The client sends a Card number and a gate kind, never a command. The server
   re-reads `gates` and runs the `argv` the plugin published for that exact
   gate, so a stale tab cannot open a closed gate and the endpoint is a button
   rather than a remote shell.
2. The **merge** gate is opt-in: `AGENT_TEAMS_HUMAN_GATES=merge` on the server,
   or the button stays disabled and the row shows the terminal command and says
   why. The readiness gate, which only moves a Card to Ready, is on by default.
3. It is written down — in `gates.js`, in USAGE, in ARCHITECTURE 4.5.2, in the
   dashboard README, and in Known Issues above — in the same terms the plugin
   already uses about its own seat binding. The floor under a merge remains
   GitHub branch protection.

Also fixed in passing: `dispatching-work` still named `spec_merge_mode` and
`merge_mode`, which session 12's rename sweep covered in the four docs but not
in the skills.

Tests 519 → 535 (plugin); dashboard server 1047/1047 with 12 new, client
334/334 with the Agent Teams screen snapshot reviewed and regenerated,
`tsc -b` clean. `claude plugin validate .` and `git diff --check` pass. Not
done: no live press yet — see Next Step 0d.

---

### 2026-08-27 — Session 12 (per-role config, merge renames, QA decomposition)

Implemented todo items 1-5 from the 2026-08-21 review, uncommitted on
`mvp/producer-from-scratch`. Tests 462 → 517, `claude plugin validate .`
passes, `git diff --check` clean.

**1+2 — per-role config and the merge renames.** `spec_merge_mode` →
`spec_pr_merge_mode`, `merge_mode` → `code_pr_merge_mode`, `merge_method` →
`code_pr_merge_method`; old names still parse and are dropped on save, the
current name wins when both appear. New optional `roles` block keyed by
`analyst / architect / dev / qa / lead / merge_master` overriding `recovery`
field by field (overrides stored, never a resolved copy, so a later edit to a
top-level default still reaches the fields a role did not restate). A key under
a role that does not consume it is a validation error naming the owner.
`recovery_policy` became `{default, roles}` and every planned action now
carries its own resolved `recovery`. `Board` takes a `seat` so transport
retries spend the bound seat's budget. CONFIGURATION.md gained a "consumed by"
column, a per-role section, and a renamed-settings table.

**Caught by a test, worth remembering**: the parser's local `roles` shadowed
the one holding `dispatch_roles`, so a `roles` block silently overwrote the
dispatch allow-list with its own seat keys. A block naming only valid seats
produced *no error at all* — the board just stopped dispatching two of three
roles. Only the round-trip test with `merge_master` in it failed.
`test_roles_block_does_not_disturb_dispatch_roles` now pins it.

**3+4+5 — QA.** Decision record: `docs/decisions/2026-08-27-qa-decomposition.md`.
Two axes, one verdict authority. New `agents/qa-browser-worker.md` gets the
Card, spec, and running app but **not the diff** — the blindness is the point,
and it is what makes QA's evidence independent rather than a second read of
Dev's work. `qa-worker` gained `Agent`/`SendMessage`/`ListAgents` and spawns up
to three review passes (`structure`/`behaviour`/`risk` — three bundles, not
eight, so the diff is copied three times for non-overlapping findings) plus the
browser worker. `next_actions` is unchanged: still one spawn per Card stage.

`Verdict.browser_evidence` is a new validated field: `policy.validate_verdict`
(now taking an optional duck-typed `config`) refuses a **pass** whose changed
files match the new `ui_paths` config and which carries no flows, invalid-input
cases, and console reading. Backend and docs Cards are unaffected; a `fail`
never carries the burden. The browser procedure lives in exactly one file
(`references/browser-pass.md`); `verifying-delivery` holds only the exclusivity
rule and a fallback for when no browser worker was dispatched.

**Checked, not assumed**: Claude Code subagents *can* spawn subagents (three
layers, needs `Agent` in `tools`) and `SendMessage` works between siblings with
a roster (v2.1.206+). This repository's "workers cannot spawn grandchildren" was
our policy, not a platform limit. Also established: same-Card stages are
sequential, so dev and qa workers are never co-alive — direct dev↔qa messaging
is impossible under the current contract, which is why item 5 landed as
QA-internal messaging instead.

**7 — the runbook.** `docs/RUNBOOK.md`: cold-start, English, written for
someone who has used neither this plugin nor Claude Code. Accounts and tool
install → a Claude Code primer → plugin install → GitHub repo/Project/fields/CI/
branch-protection → `init`/`doctor` → one Card shipped end to end → optional
dashboard → a troubleshooting chapter built from the failures this project
actually hit. **Every part ends with a Checkpoint** (a command plus its expected
output) because the team lead's stated plan is to run it cold and find the gaps.

Two tests pin it: `test_runbook_names_only_commands_that_exist` (its command
appendix is the part most likely to rot silently) and
`test_runbook_keeps_its_checkpoints`. Every cited command and flag was verified
against `_build_parser` rather than written from memory.

Part 7 (the dashboard) is **explicitly marked unverified** — CCAM is not in this
tree, so it is reconstructed from this handoff rather than from its source. It
says so in a callout at the top of the section, and the runbook closes with a
"what this does not cover" list.

**Doc rename sweep.** README, USAGE, ARCHITECTURE, and IMPLEMENTATION_PLAN were
still on `spec_merge_mode` / `merge_mode` / `merge_method`; all four now use the
current names. Only CONFIGURATION.md's rename table still mentions the old ones,
deliberately. README also gained `roles`/`ui_paths` rows and a pointer to the
runbook.

Not done: items 6 (dataset — not delivered here), 8 (dashboard Workflows tab,
and now with a concrete reason to re-check it), 9 (parked).

---

### 2026-08-27 — Session 12b (dashboard, `../agent-teams-dashboard`)

The dashboard turned out to be available after all, so Part 7 of the runbook is
now written from its source rather than reconstructed, and two flagged
follow-ups are closed. All uncommitted, on `feat/plugin-scope-listing`.

**A real bug, not just a gap.** The config form still wrote `merge_mode`. The
plugin accepts it (legacy) but rewrites it to `code_pr_merge_mode` on save — so
the key the form looks for disappears from the file it just wrote, and the
user's merge-mode choice appeared to revert to "default" on the next read.
Renaming the three keys in `config-schema.js` fixes it.

Also added there: a `roles` section (per-seat `max_retries` plus the
merge-master merge keys), `ui_paths`, and a `defaultFrom` mechanism —
per-role fields inherit from the top level, so a static default would have
greyed in the plugin's built-in value and contradicted the configured one.
Inheriting enums get an explicit `inherit` option, because a `<select>` always
holds a value and without it one touch would write an override the form could
never clear.

**Todo 8 discharged with evidence.** The 08-21 `SubagentStop` fix holds at
depth 3 (coordinator → `qa-worker` → typed helper), pinned by a new test in
`server/__tests__/api.test.js`. Residual: untyped concurrent helpers still fall
back to oldest-working attribution — cosmetic ordering, and the damaging form
(a helper completing a seat worker) stays fixed.

Verified: `agent-teams-config.test.js` 9/9 **against the real plugin**
(`AGENT_TEAMS_SCRIPTS=.../agent-teams/scripts AGENT_TEAMS_PYTHON=python` — the
default `python3` does not exist on Windows, which is why that suite had been
silently skipping), `api.test.js` 115/115, client 334/334, `tsc -b` clean.

---

### 2026-08-20 → 08-21 — Sessions 10–11 (Lee's side — dashboard, full unattended run, fixes)

Per-seat worker split and installable marketplace (08-20). Adopted CCAM as the management dashboard, fixed its plugin-scope listing, added an Agent Teams page whose Config tab writes `.agent-teams/config.json` through `config_bridge.py` (imports `Config`; same `config_revision` as `doctor`). Full 毒油地圖 rerun on glm-5.2 via Ollama, unattended, watched from the dashboard: intake → architect (found the 桃園市/桃園縣 join defect) → #26 dev/QA with a real QA-found defect and a fix-forward → #27/#28 routine. Four plugin findings came out of it and were fixed 08-21 (see Current State items 3–7), plus two dashboard fixes (nested-helper `SubagentStop` completing the wrong worker; graph labels truncating to `agent-teams:…`). Deck `slides/2026-08-21-weekly.md` (30 pages, your Part 1 kept). Tests 434 → 462.

### 2026-08-12 → 08-13 — Session 9 (Lee's side — first live automation run)

**The automation extension ran live, end to end, on the real board** (repo `Windmill10/agent-teams-test`, project 4). Human surface for the whole run: **two `promote` commands plus one exception sign-off** — the 08-07 "five human command points" finding is resolved in practice, not just in code.

Setup first: retired the first oil-map run recoverably (removal commit `7b22d9b`; issues #12/#15/#16 closed and archived — closed-issue history stayed visible, see below), then configured acceptance: CI workflow with required check `test` (`c8d0f09`), branch protection (strict), repository auto-merge, `required_checks: ["test"]` in config. `doctor` then surfaced the branch's **first live-shape bug** — real gh 2.97.0 has no `autoMergeAllowed` JSON field on `repo view`; `auto_merge_enabled()` now reads REST `allow_auto_merge` and the fake matches the verified shape (`6dd0289`). `acceptance_problems` empty afterwards; 397/397 tests green.

The run (one `cc_team` session, tmux "demo"): intake **found the retired run in git history** and asked rerun-vs-fresh before assuming; fresh clarification re-scoped the data source mid-loop (a parallel research pass re-confirmed no national machine-readable violation dataset exists; the seed became the ongoing 2026 中聯油脂 苯駢芘 case) → #18. The coordinator spawned the architect as an in-session worker: spec committed **directly to main** (`298f36a`, no PR), decompose → #19/#20/#21 with dependency order; the architect declined to assert a penalty amount it could not source (left `未公開`). Human `promote 19` (no `--spec` flag — the Card carries the spec record). Dev worker: claim → worktree → PR #22, **honestly flagging a CI risk in its retro**. The required check failed — a real bug in our own `ci.yml` (`node --test test/` treats the path as a module; bare `node --test` is correct). The coordinator root-caused it with a four-variant evidence table, predicted it would block #20/#21, and **stopped for human sign-off before touching shared CI config** — the exception lane's first live firing, on exactly the right class of change. One-line fix `c0daf1a`; dev resumed and updated the branch (strict re-test), QA **re-verified the exact new head** (stale-evidence rule exercised live), acceptance `eligible` → auto-merge `5722496` → #19 Done, reconciled automatically. `promote 20` then ran the whole loop hands-off to Done (PR #23). **#21 is deliberately held at the gate as the live-demo card.**

Also proven live: lazy loading (each worker kickoff named exactly one `[skill:...]`; full per-worker transcripts under the session's `subagents/` directory), WIP-aware `next-actions`, resume-after-fix, `[expected:(Status, Role)]` stamps surviving into worker prompts. Weekly deck: Part 2 of `slides/2026-08-13-weekly.md` replaced with the new run (11 slides; `images/2026-08-13/` holds grey placeholders awaiting the user's screenshots — same filenames, drop-in); Part 1 untouched (Joanne's). Root-level `HANDOFF.md` updated separately.

---

### 2026-08-12 — Session 8

Changed the child-context architecture after team-lead feedback. The generic
worker no longer preloads six full skills; next-actions names one qualified
skill and the worker invokes only that skill through the Skill tool. Extracted
clarifying-card from intaking-requirement so existing returned Cards cannot
accidentally create duplicate intake Issues. Updated README, architecture,
usage, attribution, testing guidance, and focused planner coverage to explain
source reuse versus the agent-teams governance overlay. Sixteen focused tests,
four skill validators, plugin validation, and diff checking passed; no broad
suite or live child trace was run. The user committed this work as 6f6851a and
merged the branch as bbf1335 before this handoff update.

---

### 2026-08-12 — Session 7

Implemented the automation extension directly on
`mvp/producer-from-scratch`, uncommitted: direct current-branch product specs,
typed WIP-aware next actions, one bounded plugin worker, same-session
coordination, returned-Card clarification, one Ready gate plus conditional QA, monitored auto-merge,
and automatic reconciliation. Audit-driven fixes made decomposed children
promotable and retries idempotent, closed generic Done bypasses, and added
GitHub exact-head merge protection. Focused 241-test and full 385-test suites
are green; plugin validation passes; `git diff --check` is clean.

---

### 2026-08-07 — Session 6 (Joanne's side)

Implemented the entire Consumer half — the milestone every prior session had deferred — from an approved spec and a 17-task plan, executed inline with a red-green-commit cycle per task. Added `scripts/agent_teams/git.py` (claim compare-and-swap, guarded worktrees), the `Verdict`/`Acceptance` contracts, protected-path classification, `validate_verdict` and `evaluate_acceptance` in the still-network-free policy layer, Pull Request operations and auto-merge arming on the board, a `Consumer` class with `claim`/`submit`/`verdict`/`accept`/`reconcile`/`worktree_status`, six CLI commands, and two new skills. Tests 145 → 344.

The session's key discovery came from testing the claim primitive rather than reasoning about it: the obvious compare-and-swap produces **two winners** in the common case, because pushing an identical base SHA to an existing ref is a no-op success that never evaluates the lease. The claim now pushes a unique empty commit with a session nonce, and the race tests drive real git for exactly this reason.

Three rounds of correction followed, each prompted by the user. First, checking the implementation against `slides/2026-08-06-weekly.md` — treated as the authoritative contract — found the eligible route stopping at "armed" instead of completing to `Done`, and protected changes naming categories instead of files; both fixed. Second, an audit of my own attribution found four sources cited without being read, and that over-claim had concealed a real defect: `validate_pr_body` accepted only `Closes #N` where Contract C and GitHub accept `Fixes` and `Resolves` too. Third, the test-strength rule turned out to be a substring search that accepted "NO branch coverage was measured"; `test_strength` is now structured with a required `falsified_by` naming what was broken and which test caught it.

The user committed the work as `6d77238` and `6024d9a` and pushed; the development worktree and its branch were deleted at their request. `gh` is still unauthenticated, so **nothing below the fake `gh` has ever run** — that remains the whole of the risk. One substantive contradiction is left open and untouched: the deck says the plugin will *reuse* sibling skills, while what shipped is derivation and invariant 10 forbids runtime calls.

---

### 2026-08-06 — Session 6 (Lee's side)

- **Skill-content migration, all seven Producer skills.** Cloned obra/superpowers into `reference/`, inventoried it plus gstack (local checkout) and board-superpowers with three parallel research passes; verdict: derive locally with attribution, never depend at runtime (all three MIT). Migrated `intaking-requirement` (shape judgment, spec awareness, decline policy), `briefing-board` (fixed template, recommendation ladder, stale-claim check, read-failure rules, card-scoped re-entry), `triaging-board` (stale-claim sweep, external-dependency class, evidence rules), `using-agent-teams` (state table, non-signals, router anti-pattern), `inspecting-queue` (report-never-act observation guards), `authoring-spec` (INVEST + vertical-slicing refusal gates, SPIDR, XS/S/M/L ceiling), and hardened `dispatching-work` from live-test findings. A coverage pass restored over-compressed load-bearing text into per-skill `references/` files; `docs/skill_migration_audit.md` proves per-item disposition of every source section, including conscious rejections (their Ready-at-intake, lead-executed release, very-large-cohesive-PR allowance).
- **`release-claim`** added end to end: policy action (human-only, teaching refusal), CLI command with branch-first mutation order and partial-failure envelope, guards (must be In Progress; mainlines refused), 14 new tests. Kickoff prompts now stamp `[expected:(Status, Role)]`. Tests 130 → 145.
- **Live verification**: doctor green post-rename; live reads; release-claim refusals live; two headless `claude -p` skill probes passed — the briefing probe rendered the new template and overrode the code's wrong recommendation, the roadmap-intake probe refused to file with no board mutation. Found the `_recommend` readiness-rung defect. Probe harness requires `sandbox.enabled: false` in `agent-teams-test/.claude/settings.json` (gh misreports sandbox blocks as invalid tokens).
- **Slides**: weekly deck restructured as sibling files in one Slidev project (`2026-08-06-weekly.md`, run via `npm run dev:weekly`); two sections written (updated workflow honoring the not-yet-shipped caveat; demo with image placeholders); the user committed and pushed slides (`1b403c8`), Joanne refined the QA-workflow slides on top (`787a720`).
- PM reply for last week's meeting sent (items 1–9); flagged to clarify that 「引入 skills」 means deriving definitions, not installing plugins.

---

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
