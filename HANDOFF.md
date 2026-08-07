# HANDOFF: agent-teams

> A Claude Code plugin for a GitHub-Project-coordinated artificial intelligence engineering team. Both halves are now implemented — a Producer shapes work, a Consumer resolves one Card through claim, delivery, evidence-grounded review, and deterministic acceptance. What remains is live-GitHub proof.

**Stack**: Claude Code plugin / Python 3.12 standard library / GitHub CLI / GitHub Projects v2 / Git / Slidev

**Last updated**: 2026-08-07 — session 6, both tracks (Joanne's side: Consumer implementation; Lee's side: skill-content migration, `release-claim`, live verification)

---

## Project Goal & Scope

This orphan branch builds agent-teams from an empty tree, deliberately not inheriting the earlier full framework. **Both the Producer and Consumer halves are now built.** A Producer session shapes work — creates, refines, routes, prioritises, unblocks. A Consumer session resolves exactly one Card: the Developer and Architect routines claim, implement, and open one Pull Request; the Quality Assurance routine reviews it, publishes evidence, and runs deterministic acceptance.

The durable coordination surface is one GitHub Project. Cards are GitHub Issues carrying two orthogonal single-select fields: `Status` (where the work is) and `Role` (whose turn it is).

The system no longer spends human attention on every passing delivery. Readiness remains the mandatory human gate. QA independently reviews the implementation, publishes evidence for the exact Pull Request head, and a separate deterministic evaluator routes `eligible` to auto-merge, `defect` back to `dev`, and `protected_change` to `human`. No agent seat directly merges or selects its own merge route.

Normative design lives in [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md); delivery status and the milestone ledger live in [`docs/IMPLEMENTATION_PLAN.md`](./docs/IMPLEMENTATION_PLAN.md). **Do not restate milestone detail here — that plan is the single status ledger.**

Still intentionally excluded: audit database, schema migrations, lifecycle hooks, automatic field provisioning, Codex packaging, multiple board backends, autonomous agent spawning. Additions need evidence from an observed failure, not inheritance from the earlier implementation.

The earlier full implementation is a **separate sibling repository**, `../agent-teams-main` (the board-superpowers fork). Its `docs/agent-team-adaptation/` dossier is the source of this adaptation's intent and is worth reading before changing the authority model.

---

## Architecture

- **This repository is the plugin.** Consuming repositories only hold `.agent-teams/config.json`.
- **Claude-only surface.** `.claude-plugin/plugin.json` names `agent-teams` v0.2.0; local marketplace is `agent-teams-local`. No Codex manifest on this branch.
- **Nine skills — seven Producer, two Consumer.** `using-agent-teams` runs the mandatory read-only bootstrap, then **infers the seat and routine from the user's plain-language intent** — a person never names a seat. Producer: `intaking-requirement` (analyst), `authoring-spec` (architect), `briefing-board` / `triaging-board` / `dispatching-work` (lead), `inspecting-queue` (qa). Consumer: `consuming-card` (dev and architect-documentation routines), `verifying-delivery` (qa).
- **A Consumer request must name a Card.** `[board-card:#N]`, "work on 12", "verify #21". Without one it is not a Consumer request — orient first. The router never picks a Card on the user's behalf.
- **Orientation is the default and is directly callable.** A session that opens with no specific request runs `briefing-board` unprompted. Read-only, so it is always safe to repeat.
- **The router may never infer `human`** (ARCHITECTURE §10.2). Every other seat is safe to infer because choosing one grants nothing — policy re-checks regardless. **This boundary is instruction-level, not code-enforced, and cannot be**: the adapter cannot distinguish a seat token a person supplied from one a session supplied.
- **Seven functional modules** under `scripts/agent_teams/`, strictly downward dependency direction (plus `__init__.py` and `errors.py`, so `ls` shows nine files):

  ```
  model      validated Role, Status, Card, Handoff, Verdict, Acceptance
  policy     pure legality — transitions, authority, caps, seat actions,
             protected classification, verdict validation, acceptance
  config     configuration and its validation
  github     gh invocation, pagination, error classification
  git        local Git and remote ref arbitration (claim, worktrees)
  board      semantic board operations
  workflows  Producer and Consumer transactions with partial-failure recovery

  errors     AgentTeamsError — the one base every expected failure shares
  ```

  `scripts/producer_board.py` remains the **stable public entry point** every skill invokes.
- **`policy.py` touches no network**, and now also owns acceptance. It reads a `Config` duck-typed rather than importing it, preserving the dependency direction. That purity is why every acceptance route is asserted individually.
- **The remote claim branch is the mutual-exclusion primitive**, and the claim pushes a *unique empty commit* rather than the base SHA — see Hard-won Discoveries, this is the single most important implementation detail on the branch.
- **Semantic operations only.** No `set_card_field`, and no CLI flag through which a caller could steer an acceptance route.
- **Authority is checked before the first GitHub call**, so a refusal costs nothing and leaves no partial state.
- **Status and Role are orthogonal.** A handoff changes Role and writes context; it never silently changes Status. When both must move, that is two operations.
- **Honest partial failure.** Multi-step mutations return `{ok:false, partial:true, completed:[...], failed:..., recovery:[...]}`. Creation steps are never replayed; nothing ever claims a rollback that did not run.
- **One human gate plus one exception lane, now implemented.** `promote_to_ready` refuses every agent seat including `lead`. `merge_pull_request` — free-form merge of a caller-chosen Pull Request — **remains in `policy.HARD_FLOORS`**; decision 8 did not remove it. A companion action `request_automated_merge` is refused to *all six* seats including `human`, so "no seat may request a merge" is an assertion rather than an absence.
- **Verdict and acceptance are separate types**, neither convertible into the other. QA writes `Verdict` (`pass`/`fail`/`blocked`, bound to the exact head SHA); policy writes `Acceptance` (`eligible`/`defect`/`protected_change`); QA cannot select its own route. That separation is structural, not prose.
- **Protected changes name files, not just categories.** Seven default categories, configurable; policy may add but emptying a default category is a configuration error.
- **agent-teams calls no other plugin.** Skill content is derived locally with attribution; nothing is called at runtime and correctness never depends on a sibling being installed.
- **All seven Producer skills carry derived open-source content** (session 6, Lee's side): procedures adapted from board-superpowers (MIT); the analyst clarification loop derived from superpowers `brainstorming` after PM feedback. Skills gained per-skill `references/` files; `ATTRIBUTION.md` holds the notices; `docs/skill_migration.md` records adopted/rewired/rejected per skill; `docs/skill_migration_audit.md` proves per-item coverage. `grep -rn "superpowers:|gstack:/" skills/` must stay empty.
- **`release-claim` is a human-only recovery gate** (session 6, Lee's side): deletes an abandoned claim branch and returns the Card `In Progress -> Ready` with a release comment, in that order (asymmetric failure modes). `policy.py` refuses every agent seat; the Card must actually be In Progress so the command is not a side door past `promote`. Kickoff prompts stamp `[expected:(Status, Role)]` so a receiving session can detect a stale kickoff.

---

## Established Conventions

- Work in `C:\Users\User\Documents\intern\ITRI\agent-teams-project\agent-teams`. Feature work has used a worktree under `../.worktrees/<name>`; session 6 did this and then, at the user's request, moved the result onto the main branch and deleted the worktree. **Note the collision risk**: `../.worktrees` is also the default `workspace` for Consumer claim worktrees (`claim-<n>-<slug>`), so development worktrees should not reuse that naming.
- Keep the branch small. Do not reintroduce audit, setup-stage, hook, or dual-platform frameworks without a demonstrated failure.
- Skill directories use lowercase verb-led names; `SKILL.md` plus an optional `references/` directory. Frontmatter carries `name` and a trigger-rich `description` including do-NOT-use disambiguation.
- **Derived skills carry a four-line attribution comment** naming what was derived, the source with MIT + copyright holder + URL, and a pointer to `ATTRIBUTION.md`. Keep it short — a `SKILL.md` body is loaded into context every time the skill fires, and provenance detail is not operational content. Per-element `DERIVED` / `INVENTED` labels live in `ATTRIBUTION.md`.
- **Never cite a source you have not read.** Session 6 found four such citations, and the over-claim concealed a real defect. See Hard-won Discoveries.
- All deterministic GitHub behaviour lives in `scripts/agent_teams/`; skills describe orchestration, judgment, and refusal boundaries. Skills contain no raw Project field identifiers and no ad hoc `gh` commands.
- **Never report a mutation as successful without `"ok": true` in the CLI JSON.** Expected failures return structured error JSON on stderr and exit 1. A lost claim race exits 1.
- Python standard library only. No dependency install, no virtualenv, no SQLite.
- Tests use an injected fake `gh` (`tests/fake_gh.py`) and a fake Git (`tests/fake_gh.FakeGit`). The claim-race tests are the exception: they drive **real git** against a local bare repository, because a fake would have agreed with the wrong implementation.
- **Evidence must be structured to be checkable.** `test_strength` entries are objects with a `dimension` from a closed vocabulary, `evidence`, and optionally `falsified_by`. Free prose is refused — a substring search for "branch" accepts "no branch coverage".
- Intake leaves Status `Backlog` and Role `architect`. No agent seat may make a Card Ready. `decompose` creates children at `(Backlog, human)`.
- Dispatch is read-only and deterministic: configured seat order, then Card number. Say "prompt rendered", never "session started".
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

Both surfaces implemented and hermetically tested. **Consumer code has never touched a live board** — that is the main remaining risk. The Producer surface has been live-verified on Lee's side (live board reads, refusals, headless probes, and the full 毒油地圖 Producer run of 2026-08-06/07).

| Milestone | Status | Notes |
|---|---|---|
| Producer surface | Done | Seven skills, hermetically tested; live-verified on Lee's side |
| Skill-content migration (all 7 Producer skills) | Done | Lee's side: derived from board-superpowers (MIT) with attribution; clarification loop from superpowers `brainstorming`; per-item coverage audit in `docs/skill_migration_audit.md` |
| `release-claim` human recovery gate | Done | Lee's side: policy row + CLI + 14 tests; refusal paths exercised live |
| Developer Consumer (M4) | Done except live proof | Claim/worktree/one-PR delivery; exclusivity proven against real git |
| QA Consumer (M5.1–M5.3) | Done except live proof | `verifying-delivery`, verdict contract, eight review dimensions, evidence gate, challenge and blind-spot loops |
| Deterministic acceptance and merge (M5.4–M5.5) | Done except live proof | Acceptance decision table, exact-SHA invalidation, protected classification, auto-merge arming, reconciliation |
| Slide conformance | Done | All 16 mechanical slide claims verified by running the real code |
| Attribution accuracy | Done | Four unread citations removed; per-element labels added |
| Plugin manifest re-validation | Done | Warning-free on the nine-skill layout |
| Test-strength enforcement | Partial | Structured `falsified_by` contract enforced; no mutation-testing infrastructure of our own |
| Live Producer cycle (intake → spec → decompose → promote) | Done | Lee's side, 2026-08-06/07: 毒油地圖 run — #12 intake with clarification loop, spec PR #13 merged, children #14–#16, #14 promoted |
| Live Consumer cycle (claim → PR → verdict → accept) | **Pending** | Nothing below the fake `gh` has run for the Consumer half |
| Shadow-mode calibration | Pending | No precision/recall evidence before removing routine human review |

---

## Key Files

| File | Status | Description |
|---|---|---|
| `scripts/agent_teams/git.py` | **New / load-bearing** | Claim compare-and-swap and guarded worktrees. The unique-claim-commit rule is here; read its module docstring before touching it |
| `scripts/agent_teams/policy.py` | **Load-bearing** | Now also owns protected classification, `validate_verdict`, and `evaluate_acceptance`. Still touches no network |
| `scripts/agent_teams/model.py` | Active | `Verdict` (evidence) and `Acceptance` (decision) as deliberately non-convertible types |
| `scripts/agent_teams/workflows.py` | Active | `Producer` and `Consumer`. `Consumer.accept` is the deterministic tail; `_reconcile_to_done` is shared with `reconcile` |
| `scripts/agent_teams/board.py` | Active | Semantic operations plus Pull Request reads, verdict/acceptance records, auto-merge arming |
| `scripts/agent_teams/config.py` | Active | Five Consumer keys; `protected_paths` may only grow |
| `scripts/producer_board.py` | Stable | Public CLI. `accept` takes only an Issue number — do not add flags to it |
| `skills/consuming-card/` | **New** | Developer and Architect-documentation routines, plus three references |
| `skills/verifying-delivery/` | **New** | QA routine, plus three references. `references/verdict-schema.md` documents the evidence contract |
| `skills/using-agent-teams/SKILL.md` | **Load-bearing** | Router. May infer agent seats but never `human` |
| `tests/test_git.py` | **New / slowest** | Real-git claim race and worktree guards. ~40s of the suite |
| `tests/test_acceptance.py` | **New** | Acceptance decision table asserted row by row |
| `tests/test_consumer.py` | **New** | Consumer transactions against the fakes |
| `tests/fake_gh.py` | Active / **assumption risk** | Fake `gh` and `FakeGit`. Every Pull Request JSON shape here is assumed, never verified |
| `ATTRIBUTION.md` | **Active** | Provenance labels and the correction record |
| `CLAUDE_TESTING.md` | Active | Updated for nine skills; the live Consumer procedure is written but unperformed |

---

## Test Status

`python -m unittest discover -s tests -p "test_*.py"` — **344 passed**, ~40s, no network. Run on HEAD `6024d9a` at the end of session 6 (Joanne's side).

Split: `test_consumer` 77, `test_acceptance` 68, `test_producer_board` 56, `test_workflows` 48, `test_policy` 43, `test_git` 23, `test_partial_failures` 16.

`claude plugin validate .` passes warning-free. `grep -rE "superpowers:|gstack:/" skills/` returns nothing.

What the suite genuinely proves:

- **Claim exclusivity, against real git.** Two clones racing one Card produce exactly one winner, including the same-base and fast-forwardable cases.
- Every acceptance decision-table row, every protected category, every invalid-pass condition, individually.
- Both worked examples in `references/verdict-schema.md` were executed against the real validator; the "refused" example produces exactly the six documented refusals.

What it does not prove:

- **Any live `gh` behaviour for the Consumer half.** Pull Request view/checks/merge shapes are assumptions encoded in `tests/fake_gh.py`.
- That auto-merge, reconciliation, or the protected-change lane work against GitHub.
- That a `falsified_by` claim is *true* — only that it is present and specific enough to check.

Live verification (Lee's environment — macOS, `gh` authenticated as Windmill10):

- **Live board (github.com/users/Windmill10/projects/4)**: `doctor` green (all 12 options post-rename); `brief`/`list`/`dispatch` live reads correct; `release-claim` refused live for an agent seat and for a not-In-Progress card, both before any GitHub call.
- **Headless skill probes** (`claude -p` from `agent-teams-test` with `--plugin-dir`): (1) "brief me" — fixed report template rendered exactly, human queue led, never-act-as-human held, and the skill's recommendation ladder **overrode the code's wrong "board is clear" string**; (2) roadmap-level intake — the shape gate refused to file with no board mutation. Bonus: three accidental auth-failure runs each obeyed the read-failure rule (verbatim error, no synthesized state, clean stop).
- **Full live Producer run (2026-08-06/07, 毒油地圖)**: intake with the new clarification loop produced #12; architect session (with its own background research agent) produced spec PR #13; human gate caught a `Closes #12` auto-close keyword in the PR body (skill hardened in response); decompose produced #14–#16 at `(Backlog, human)` honoring the walking-skeleton hint and a human-supplied-dataset prerequisite; human promoted #14 to `(Ready, dev)`.
- Probe harness note: nested headless sessions need the test repo's `.claude/settings.json` (`sandbox.enabled: false`) or `gh` misreports sandbox keychain/network blocks as "token invalid".
---

## Known Issues & Deferred Debt

- **Live `gh` JSON shapes are assumed** (`tests/fake_gh.py`) — the largest risk on the branch. `pr view`, `pr checks`, `pr list`, changed-file listing, and `repo view --json autoMergeAllowed` have never been seen from a real GitHub CLI.
- **`falsified_by` is checkable, not verifiable** (`scripts/agent_teams/policy.py`) — the rule proves QA made a specific, attributable claim. It cannot prove the mutation was actually run. Closing this needs mutation-testing infrastructure we do not have.
- **The skill-direction slide contradicts invariant 10** — see Open Decisions. Unresolved and deliberately untouched.
- **Pagination strategy is an assumption** (`github.fetch_all_items`) — escalates `--limit` until a response returns short.
- **Handoff remains partially non-atomic** (`board.handoff_card`) — Role changes before the comment posts; `PartialHandoff` preserves replay material.
- **`handoff_count` and `latest_verdict` fail open** — an unreadable comment counts as zero / not-a-verdict. Avoids stalling; can under-count.
- **No automatic field provisioning, WIP enforcement, or audit store** — `doctor` validates, `brief` reports, GitHub artifacts are the trail.
- **Specification-gate gaps remain** — an unverified non-PR spec pointer is accepted.
- **`../.worktrees` is shared** between development worktrees and Consumer claim worktrees.
- **`workflows._recommend` lacks a readiness-queue rung** (found by live testing, Lee's side) — with Cards at `(Backlog, human)` it says "the board is clear"; the merge queue is checked but the promote queue is not, and the brief payload has no `awaiting_readiness` field. The briefing skill's prose ladder masks it in practice, but the JSON field actively misleads. Small fix: add the rung ranked first, expose the queue, one test.
- **Three notation/contract items need Joanne's blessing** (Lee's side): the `depends-on (soft): #N` body convention referenced in intake/authoring-spec references; the `[expected:(Status, Role)]` kickoff stamp as the Consumer preflight input; and the `release_claim` policy action (her Consumer work landed after these — confirm she accepts them rather than assuming).
- **Board hygiene observed live**: #4 is Done with no Role (harmless). Whether a parent Card closes when its children ship remains an open reconcile-design question (#12 is the live case now).

---

## Open Decisions

- **Human-intervention count is too high (Lee's live-run finding, 2026-08-07)** — the first full loop (#14: intake → spec → decompose → promote → dispatch → dev → QA fail → defect → fix → QA pass → merge → Done) required five human command points: merge the spec PR, `promote`, merge the implementation PR, `reconcile-done`, plus carrier duties (launching every seat's session and pasting kickoffs). Operating it, this feels like too many steps and too much command surface; the target is **at most 2–3 interventions, each a simple command**. Consolidation candidates, none decided: (a) fold spec-PR merge + `promote` into one approval command (promote is already refused until the spec is merged, so the two are sequenced anyway — one command could merge then promote); (b) fold implementation merge + `reconcile-done` into one command, or auto-reconcile once the merge is detected — reconcile is bookkeeping with no judgment content, the strongest automation candidate; (c) on a repo with CI + branch protection the routine implementation merge already disappears (auto-merge armed by acceptance), which alone brings a clean run down to spec-approval + promote; (d) the carrier cost (session launches + kickoff pasting) is the other felt burden — a launcher wrapper around `dispatch` output would cut it without touching the no-autonomous-spawning decision. Target end shape: answer intake questions, one readiness approval, one merge decision only when policy escalates.
- **The skill-direction slide versus invariant 10** — `slides/2026-08-06-weekly.md` says agent-teams will *reuse* skills from board-superpowers, superpowers, and gstack, and its presenter note says "we did not finish the integration". What shipped is *derivation with attribution*; invariant 10 forbids runtime calls. Options: soften the slide to "adopt/derive", or amend invariant 10 and Appendix A.1 to permit runtime composition. **Needs**: a decision on whether correctness may depend on a sibling plugin being installed. This is the one substantive gap between the deck and the code.
- **Shadow-rollout exit criteria** — the PR sample, seeded-defect suite, precision/recall targets, false-negative budget, and rollback trigger before routine human review is trusted to be gone. Nothing here is calibrated.
- **Mutation-testing infrastructure** — whether to adopt a tool so `falsified_by` can be machine-checked rather than attested.
- **Pagination ceiling and persistent installation** — retain as live-verification decisions.

**Settled** (rationale in `docs/ARCHITECTURE.md` Appendix A.2–A.3; do not relitigate without new evidence): `architect → analyst` is legal (1); `spec_completion` defaults to `merged` (2, readiness half superseded by 6); decomposition is by shape (3); transition authority keys off the destination (4); creation obeys the same rule on both axes (5); only `human` opens `Backlog → Ready` (6); the plugin infers agent seats but never `human` (7); the routine second human gate is replaced by QA evidence plus deterministic acceptance (8, now implemented). Settled in session 6: merge backend is GitHub auto-merge armed by the controller; `Done` is owned by `lead`; protected categories are the seven in `config.DEFAULT_PROTECTED_PATHS`.

---

## Hard-won Discoveries

- **The obvious claim implementation gives two winners.** Pushing the base SHA to the claim ref with an empty-expect lease reports `Everything up-to-date` and exits `0` — git never evaluates the lease. Since two Consumers normally branch from the *same* base, that is the common case, not an edge case: both sessions conclude they own the Card. The fix is to push a unique empty commit carrying a session nonce. **A coverage-only test suite would have reported this path fully covered while asserting the wrong outcome.** This is why the race tests drive real git.
- **A substring search for evidence is the same error it is meant to catch.** The first `test_strength` rule searched free prose for one of six dimension words, so `"line coverage 98%; NO branch coverage was measured"` passed — the token was present. A check that a word appears proves nothing, exactly as a line that executed proves nothing. Evidence must be structured to be checkable.
- **Citing a source you have not read is fabrication, and it hides defects.** Session 6 cited four sources it never opened, including per-item audit rows for `reviewing-pr-queue`. The over-claim concealed a real bug: `validate_pr_body` accepted only `Closes #N`, while board-superpowers' Contract C — and GitHub — accept `Closes`/`Fixes`/`Resolves` case-insensitively. Reading the source found it.
- **WebFetch summarises even when asked for verbatim content.** Both gstack skills came back as model-written summaries, not source text. Use `curl` on `raw.githubusercontent.com` when the exact wording matters. The summaries happened to be faithful — that was luck, and it was checked afterwards.
- **`git diff` and file checksums can disagree, and neither alone is trustworthy before a destructive operation.** Comparing the worktree to the branch showed "identical" by `git diff` and "13 files differ" by checksum. The cause was CRLF versus LF; normalising line endings showed zero real differences. Trusting either signal alone would have meant deleting on a false pass or refusing on a false alarm.
- **`--force-with-lease=<ref>:` is only evaluated when a push is actually attempted.** A no-op push skips the lease entirely. It *does* correctly reject a fast-forwardable descendant, which is stronger than plain fast-forward rules.
- **Decision 8 does not remove the no-agent-merge invariant.** It removes mandatory human review of every passing delivery. `merge_pull_request` stays a hard floor; the controller reaches merge as a *consequence* of an eligible acceptance, and `accept` takes only an Issue number so there is no argument through which a session could steer its route.
- **Empty `required_checks` must fail closed.** Without required checks, `gh pr merge --auto` merges immediately and the retest-against-current-base guarantee is vacuous. Nothing is ever `eligible` until they are configured.
- **A rule applied in one path is not a rule.** Earlier authority bugs survived because alternate paths reached the same state. Search and test every route to a protected outcome.
- **Documents must label target versus shipped behaviour** — and now that they match, keep them matching. The slide is the contract; when it and the code disagree, fix the code or change the slide deliberately.

---

## Blockers / Waiting On

- **Authenticated live GitHub verification for the Consumer half** — on Joanne's Windows environment `gh` is installed but not logged in; on Lee's macOS side `gh` is authenticated (Windmill10) and the live 毒油地圖 board is available. The Consumer live test can run on Lee's side against `agent-teams-test`.
- **A repository configured for acceptance** — the merge path needs auto-merge enabled, branch protection with required checks, and matching `required_checks` in config. `agent-teams-test` does not have these yet; without them nothing is ever `eligible` (fails closed).
- **The skill-direction decision** — see Open Decisions. Blocks nothing technically, but the deck and the architecture currently say different things.
- **Remote synchronization** — Joanne's tip `9c75666` pulled and merged with Lee's local session work (conflict resolution recorded in this file). Nothing should be pushed without the user's instruction.

---

## Current State

Branch `mvp/producer-from-scratch` is at `9c75666` upstream (Joanne's slides update on top of `6024d9a` `feat: finish consumer (qa, dev) implementation`), with Lee's session work merged locally on top — clarification loop in `intaking-requirement`, the authoring-spec closing-keyword rule, and this conflict resolution — **uncommitted as of this update**. Joanne's session-6 commits are `6d77238` (docs) and `6024d9a` (implementation, skills, tests); the assistant commit `35c1d6e` added the design spec and plan.

The Consumer half is implemented end to end and hermetically green: **344 tests pass**, manifest validation warning-free, sibling invariant holds. Nine skills, seven functional modules, six new CLI commands (`claim`, `submit-pr`, `verdict`, `accept`, `reconcile-done`, `worktree-status`). Her development worktree and the `feat/consumer-flow` branch were deleted at the user's request; the 17-task reasoning survives in `docs/specs/`, `docs/plans/`, `ATTRIBUTION.md`, and code comments.

The live demo board (Lee's side) holds the 毒油地圖 run: #12 `(Backlog, architect)` — spec'd via merged PR #13, decomposed; #14 walking skeleton at `(Ready, dev)` — promoted by the human with a reviewed 3-record dataset attached as an issue comment; #15/#16 at `(Backlog, human)`; #4 Done (Snake). Retired: #1, #7, #9–#11. **The Consumer half has never touched a live board — #14 is the intended first live Consumer test.**

---

## Next Steps

0. Near-term leftovers (Lee's side): fix `workflows._recommend`'s missing readiness rung (+ `awaiting_readiness` in the brief payload, + test); settle the three Joanne-blessing items (soft-depends notation, expected-pair preflight contract, `release_claim` policy row); update the weekly deck's run table and screenshots to the 毒油地圖 numbers (#12–#16) after the run completes.
1. Decide the skill-direction question in Open Decisions — either edit the deck to say *derive/adopt* rather than *reuse*, or amend `docs/ARCHITECTURE.md` invariant 10 and Appendix A.1. Do not leave the deck and the architecture contradicting each other.
2. ~~Run one live Producer cycle~~ — done on Lee's side (毒油地圖: intake #12 → spec PR #13 merged → decompose #14–#16 → promote #14). Dispatch is the remaining Producer step.
3. Verify the assumed `gh` shapes against reality: run `gh pr view --json number,url,headRefOid,state,mergeable,isDraft,files,statusCheckRollup` on a real Pull Request and compare field-for-field with `tests/fake_gh.py`. Correct `board.pull_request` and the fixtures for any mismatch **before** trusting anything downstream.
4. For the acceptance path: enable auto-merge on `agent-teams-test`, add branch protection with at least one required check, and set `required_checks` in `.agent-teams/config.json`. Confirm with `producer_board.py doctor` that `acceptance_problems` is empty.
5. Run one live Consumer cycle on #14: `claim`, implement, `submit-pr`, then `verdict` and `accept`. Exercise all three routes deliberately — an eligible pass, a `fail` verdict returning the Card to `dev`, and a change touching `scripts/agent_teams/policy.py` to force `protected_change`.
6. Prove the two race behaviours live: two sessions claiming one Card, and a push landing after a verdict so `accept` refuses as stale.
7. Only then consider shadow-mode calibration against historical and seeded-defect Pull Requests, and publish precision/recall before treating automated acceptance as trustworthy.

---

## Suggested Skills

No additional plugin or skill runtime is required or desired. Compatible open `SKILL.md` instructions may continue to be adapted locally as documented process with source and license attribution — read the source first, and record what was verified and how. If multiple reviewer agents or passes are supported by the host carrier, keep them bounded by review dimension and let the QA Consumer own completeness, challenge, and synthesis.

---

## Session Log

<!-- newest entry at top -->

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
