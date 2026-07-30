# agent-teams Implementation Plan

Status: active plan for evolving the Producer minimum viable product into the
proposed Phase 1 agent team
Applies to: `mvp/producer-from-scratch`
Last updated: 2026-07-30

## 1. Outcome

The desired outcome is a small but complete Claude Code agent team in which:

1. a System Analyst creates and shapes a requirement;
2. a System Architect produces the durable specification and makes
   implementation work Ready;
3. an Engineering Manager dispatches the next legal seat;
4. a Research and Development engineer claims one Card, works through
   test-driven development, and opens one Pull Request;
5. a separate Quality Assurance engineer session writes an evidence-backed
   verdict;
6. the Quality Assurance engineer either returns the Card to the Research and
   Development engineer or hands it to the human merge gate;
7. the human verifies and merges;
8. durable board state is sufficient for every next session to resume.

This plan starts from the current four-skill, one-script minimum viable
product. It does not assume the larger `board-superpowers` implementation is
present.

The plan follows the design relationship defined in
[`ARCHITECTURE.md` section 2.3](./ARCHITECTURE.md#23-what-is-inherited-and-what-is-adapted):
Producer and Consumer are per-session execution shapes, while the named team
seats carry capability and authority. Milestones M1 through M3 complete the
minimum viable Producer path from intake through readiness and dispatch.
Milestone M4 introduces the one-Card Research and Development engineer
Consumer. Milestone M5 introduces the independent Quality Assurance engineer
queue inspection and one-Card verification. Every milestone communicates
through durable GitHub Issues, GitHub Project Cards and fields, comments,
branches, worktrees, and Pull Requests rather than in-memory agent calls.

## 2. Completion levels

Two completion levels prevent "usable" and "full proposed governance" from
being conflated.

### 2.1 Functional Phase 1

Functional Phase 1 is complete when one disposable Card can traverse:

```text
(Backlog, architect)
  -> (Ready, rd)
  -> (In Progress, rd)
  -> (In Review, qa)
  -> (In Review, human)
  -> Done after human merge
```

It must also prove the Quality Assurance rejection path:

```text
(In Review, qa) -> (In Progress, rd)
```

and refuse an illegal direct handoff from the Research and Development
engineer to the human.

### 2.2 Governed target

The governed target additionally requires:

- a seat-aware action policy;
- hard human-only merge;
- handoff cap and work-in-progress policy;
- append-only actor-seat audit;
- recovery visibility for partial mutations;
- an end-to-end trace reconstructable from durable artifacts.

Field auto-provisioning, Codex parity, multi-backend support, cron, and
team-of-teams are not required for either completion level.

## 3. Status legend

| Label | Meaning |
|---|---|
| **Done** | Implemented in this checkout and locally verified |
| **Partial** | Some behavior exists, but a required path or verification is missing |
| **Pending** | In scope and not implemented |
| **Blocked externally** | Requires an external tool, credential, or disposable resource |
| **Deferred** | Intentionally outside the current completion level |
| **Decision** | Implementation must not proceed until the named contract is settled |

## 4. Delivered baseline

### 4.1 Repository and packaging

| Work item | Status | Evidence |
|---|---|---|
| Empty-tree minimum viable product on an orphan branch | Done | `d9b739a` |
| Claude plugin identity `agent-teams` | Done | `.claude-plugin/plugin.json` |
| Local marketplace `agent-teams-local` | Done | `.claude-plugin/marketplace.json` |
| Public rename from the earlier prototype identity | Done | `8dc82df` |
| Claude manifest validation | Done | Passed on 2026-07-30 |
| Codex manifest | Deferred | Not present by design |

### 4.2 Skills

| Work item | Status | Evidence |
|---|---|---|
| Entry routing skill | Done | `skills/using-agent-teams/SKILL.md` |
| Analyst intake skill | Done | `skills/intaking-requirement/SKILL.md` |
| Architect docs-only specification skill | Partial | Skill exists; live Git/Pull Request flow unverified |
| Engineering Manager dispatch skill | Done | `skills/dispatching-work/SKILL.md` |
| Research and Development engineer execution skill | Pending | No skill exists |
| Quality Assurance engineer verification skill | Pending | No skill exists |

### 4.3 Board adapter

| Work item | Status | Evidence |
|---|---|---|
| Config read/write | Done | Unit-tested round trip |
| `gh` wrapper with structured failure | Done | Injectable `Gh` class |
| Project/field/option lookup | Done | Unit-tested with fake `gh` |
| Project item normalization and repo filtering | Done | Unit-tested |
| `doctor` | Partial | Validates Roles plus Backlog/Ready, not all Statuses |
| `list` | Done | Implemented; live response unverified |
| deterministic `dispatch` | Done | Unit-tested filtering and order |
| `intake` | Partial | Unit-tested; live and recovery behavior unverified |
| `handoff` | Partial | Unit-tested; no cap, audit, or concurrency guard |
| Status transition | Pending | No command |
| Card claim/worktree | Pending | No command |
| Pull Request link/verdict/post-merge operations | Pending | No commands |

### 4.4 Verification

| Check | Status | Latest evidence |
|---|---|---|
| Python syntax | Done | Passed 2026-07-30 |
| Focused unit suite | Done | 9/9 passed on 2026-07-30 |
| Claude plugin validation | Done | Passed 2026-07-30 |
| Non-mutating Claude namespace load | Done | Recorded in minimum viable product handoff/testing guide |
| Test from unrelated repository | Pending | Not proven in current evidence |
| Persistent marketplace install | Pending | Procedure documented only |
| Live GitHub Project read | Blocked externally | `gh` not installed |
| Live mutation | Blocked externally | `gh` and disposable Project required |

## 5. Priority gap map

### P0: prove and close the current slice

- validate actual `gh project` response shapes;
- close the Backlog-to-Ready hole;
- validate all six Status options;
- report partial mutation state and recovery instructions;
- test on a disposable Project.

### P1: complete the five-seat workflow

- add Status transition policy;
- add Research and Development engineer claim/test-driven development/Pull Request workflow;
- add independent Quality Assurance engineer verdict workflow;
- enforce human merge gate;
- add work-in-progress and handoff-loop safety.

### P2: complete proposed governance

- seat-aware action classification;
- audit with `actor_seat`;
- structured handoff/verdict schemas;
- end-to-end reconstructable trace.

### P3: optional platform growth

- automatic field provisioning;
- persistent/scheduled carriers;
- Codex parity;
- additional board backends;
- OPS/security seats and team-of-teams.

## 6. Milestone map

```text
M0  Architecture/status docs                         Done in this change
 |
M1  Live GitHub contract proof + adapter hardening
 |
M2  Domain policy + Status operations
 |
M3  Architect -> Ready vertical slice
 |
M4  Research and Development engineer execution and exclusive claim
 |
M5  Quality Assurance engineer verification and human merge lane
 |
M6  Engineering Manager operations, work-in-progress, and recovery
 |
M7  Seat-aware governance and audit
 |
M8  Golden-path proof and release
 |
`-> Optional: setup automation, carriers, Codex, backends, Phase 2/3
```

M1 through M6 produce Functional Phase 1. M7 and M8 produce the governed
target.

## 7. M0 - Architecture and implementation status

Status: **Done when this documentation change lands**

### Delivered

- [x] Reconciled both handoffs with current Git state.
- [x] Distinguished the earlier full implementation from the current minimum
      viable product.
- [x] Referenced the original board-superpowers architecture and the complete
      agent-team-adaptation dossier directly.
- [x] Separated named team seats from Producer and Consumer execution shapes.
- [x] Mapped every session handoff through GitHub Issues, GitHub Project Cards
      and fields, comments, worktrees, Pull Requests, verification, and human
      merge.
- [x] Defined the complete Producer-and-Consumer architecture, including
      shared GitHub data contracts, session protocols, component boundaries,
      concurrency, recovery, governance, and human acceptance.
- [x] Kept delivered-state inventory and remaining work in this implementation
      plan instead of mixing Producer-only status into the architecture.
- [x] Mapped every proposed capability to Implemented, Partial, Pending, or
      Deferred.
- [x] Adapted the target skill catalog to this orphan branch instead of
      treating "17 skills" as a goal.
- [x] Recorded current verification evidence and the missing `gh` blocker.

### Exit criteria

- `docs/ARCHITECTURE.md` defines the normative overall design, while this plan
  is the sole status ledger for implemented and remaining work.
- Every claim about shipped behavior points to current code or current test
  evidence.
- No Research and Development engineer, Quality Assurance engineer, audit, setup-stage, Codex, or live GitHub behavior is called
  implemented.

## 8. M1 - Live GitHub contract proof and adapter hardening

Status: **Pending / externally blocked in part**

Purpose: prove that the current adapter matches a real `gh` version before
building more behavior on its assumed JSON shapes.

### Work items

#### M1.1 Development-load proof from an unrelated repository

- [ ] Start Claude in an unrelated repository with `--plugin-dir`.
- [ ] Confirm exactly four namespaced skills appear.
- [ ] Run the three non-mutating route prompts.
- [ ] Record Claude version, source commit, command, and output summary.

No GitHub installation is required for this item.

#### M1.2 Disposable GitHub environment

- [ ] Install GitHub CLI.
- [ ] Authenticate with repository and Project scopes.
- [ ] Create or select a disposable repository and Project.
- [ ] Create the documented six-option `Status` field.
- [ ] Create the documented six-option `Role` field.
- [ ] Run `init` and preserve the generated config as a test fixture with
      repository identifiers sanitized.

This is the current external blocker.

#### M1.3 Capture actual `gh` contracts

- [ ] Capture sanitized output from `project view`.
- [ ] Capture sanitized output from `project field-list`.
- [ ] Capture sanitized output from `project item-list`.
- [ ] Capture sanitized output from `project item-add`.
- [ ] Confirm repository representation and single-select field shapes.
- [ ] Convert the captures into hermetic fixtures.

Do not make production code more permissive until the real shapes are known.

#### M1.4 Harden `doctor`

- [ ] Validate all six Status options, not only Backlog and Ready.
- [ ] Report every missing field/option in one diagnostic response.
- [ ] Validate `repo` as `OWNER/REPO`.
- [ ] Reject empty custom field/status names.
- [ ] Reject duplicate dispatch Roles.
- [ ] Add one focused test per failure.

#### M1.5 Handle Project size and pagination

- [ ] Determine whether `gh project item-list --limit` can safely exceed
      100 on the supported CLI.
- [ ] Either implement pagination/adequate limit or document and detect the
      ceiling.
- [ ] Add a test proving Cards past the first response page are not silently
      lost.

#### M1.6 Make partial failure actionable

- [ ] Define a structured partial-result shape:

```json
{
  "ok": false,
  "partial": true,
  "completed": ["issue_created", "project_item_added"],
  "failed": "status_set",
  "recovery": ["..."]
}
```

- [ ] Preserve created Issue URL/number and Project item ID as soon as known.
- [ ] Add tests for failure after every remote mutation in intake.
- [ ] Add tests for comment failure after Role mutation in handoff.
- [ ] Do not claim rollback unless a real compensation succeeded.

### Exit criteria

- `doctor` passes against a disposable Project.
- read-only `list` and `dispatch` return the expected live Cards.
- one disposable intake completes and its exact durable result is verified.
- failures identify the last completed mutation and a safe fix-forward.
- fixtures reflect observed GitHub CLI output.

## 9. M2 - Domain policy and Status operations

Status: **Pending**

Purpose: create the deterministic contract required by the System Architect,
Research and Development engineer, and Quality Assurance engineer instead of
scattering lifecycle rules through skill prose.

### Decision gates

Before implementation:

- [ ] Decide whether architect -> analyst is legal.
- [ ] Decide whether spec completion means Pull Request opened or Pull Request merged.
- [ ] Decide whether the intake Card becomes the implementation Card or
      creates flat implementation Cards.
- [ ] Record the decisions in `docs/ARCHITECTURE.md`.

Recommended defaults:

- allow architect -> analyst for under-specified work;
- make implementation work Ready only after the specification is durable on
  the target branch;
- create flat implementation Cards when a spec has multiple independently
  shippable slices; reuse the intake Card only for a genuine single-Card
  change.

### Work items

#### M2.1 Domain types

- [ ] Represent Role and Status as validated domain values.
- [ ] Define a normalized `Card`.
- [ ] Define structured `Handoff` and `Verdict` payloads.
- [ ] Move policy constants out of CLI parsing.

#### M2.2 Six-state lifecycle

- [ ] Define the legal Status transition table.
- [ ] Refuse illegal transitions before mutation.
- [ ] Add a semantic `transition` command.
- [ ] Require the acting seat for mutating transitions.
- [ ] Preserve Role unless a separate handoff command runs.
- [ ] Test every legal and illegal edge.

#### M2.3 Canonical handoff policy

- [ ] Reconcile the current and proposed authority matrices.
- [ ] Add a default handoff cap of six.
- [ ] Count structured handoff comments for the Card.
- [ ] On cap breach, refuse normal handoff and route recovery to Engineering Manager.
- [ ] Keep Role mutation independent from Status transition.

#### M2.4 Structured handoff comments

Adopt a parseable contract:

```markdown
<!-- agent-teams:handoff -->
**Handoff**: `rd` -> `qa`
**Reason**: Pull Request #57 is ready
**Needs from you**: Verify UI behavior and data correctness
**Artifacts**: Pull Request #57; branch `claim/42-revenue-chart`
```

- [ ] Escape or constrain values so generated Markdown is unambiguous.
- [ ] Retain a human-readable note.
- [ ] Add parsing/counting tests.

#### M2.5 Split the monolith at a behavioral seam

- [ ] Keep `scripts/producer_board.py` as the public entry point.
- [ ] Extract config/model/policy/GitHub/board modules only as needed by the
      new transition behavior.
- [ ] Preserve existing command syntax and JSON envelopes.
- [ ] Keep the Python standard-library-only runtime.

### Exit criteria

- all six Statuses are validated and governed;
- legal Status moves succeed, illegal moves refuse before mutation;
- the canonical handoff matrix and comment schema are test-backed;
- handoff cap behavior is deterministic;
- all existing nine tests still pass or are intentionally superseded.

## 10. M3 - Architect-to-Ready vertical slice

Status: **Pending**

Purpose: close the current golden-path break between specification completion
and Engineering Manager dispatch.

### Work items

#### M3.1 Specification completion contract

- [ ] Require the Card to be owned by architect.
- [ ] Require a durable specification artifact.
- [ ] Verify the Pull Request is docs-only.
- [ ] Link the spec/Pull Request from the Issue in a stable format.
- [ ] Apply the M2 decision about "Pull Request opened" versus "Pull Request merged."

#### M3.2 Single-Card promotion

For a genuinely single-Card implementation:

- [ ] transition `Backlog -> Ready`;
- [ ] handoff `architect -> rd`;
- [ ] include the specification artifact in the handoff;
- [ ] ensure `dispatch --role rd` returns the Card.

Role and Status remain separate mutations. If the second mutation fails, the
result must identify the partial state and fix-forward.

#### M3.3 Multi-Card decomposition

For a larger specification:

- [ ] expose a generic semantic `create-card` operation, distinct from
      analyst intake;
- [ ] require outcome, acceptance criteria, dependencies, and spec pointer;
- [ ] create flat implementation Cards in `(Ready, rd)`;
- [ ] avoid fake parent/child protocol semantics;
- [ ] leave a summary on the original intake Card.

Automatic decomposition quality remains a skill concern; deterministic code
owns creation and field assignment.

#### M3.4 Update the architect skill

- [ ] remove the current ambiguous "handoff after Pull Request exists" wording;
- [ ] describe single-Card promotion versus multi-Card decomposition;
- [ ] refuse production code;
- [ ] refuse Ready when the specification completion contract is unmet;
- [ ] add no-tool route/refusal tests where practical.

### Exit criteria

- one live analyst intake becomes at least one live `(Ready, rd)` Card;
- Engineering Manager dispatch returns its Research and Development engineer kickoff prompt;
- no manual Project field edit is needed between architect and Engineering Manager;
- a too-thin requirement can return to analyst if that authority is adopted.

## 11. M4 - Research and Development engineer execution and exclusive claim

Status: **Pending**

Purpose: turn `rd` from a dispatch value into a real Consumer-shaped seat.

### Decision gate

- [ ] Choose the claim primitive after the disposable Project is working.

Recommended: retain the proposed architecture's remote claim-branch
compare-and-swap semantics and one worktree per Card, implemented in
cross-platform Python/Git rather than importing the earlier shell framework.

### Work items

#### M4.1 Claim operation

- [ ] require `(Ready, rd)`;
- [ ] create a deterministic claim branch;
- [ ] create an isolated worktree;
- [ ] make remote branch acquisition the exclusivity signal;
- [ ] return a distinct race-lost result that must not retry;
- [ ] transition to `In Progress` only with a documented compensation order;
- [ ] persist enough claim metadata for safe resume and cleanup;
- [ ] add concurrency-focused tests using temporary Git remotes.

#### M4.2 Sibling-plugin preflight

- [ ] decide exact supported `superpowers` and `gstack` versions/surfaces;
- [ ] add a non-mutating dependency check;
- [ ] document missing-dependency behavior;
- [ ] ensure sibling skills are invoked by namespace and procedurally when
      runtime nesting would be unsafe.

#### M4.3 Add Research and Development engineer skill

Create `skills/consuming-card/SKILL.md` with:

- [ ] `[role:rd] [board-card:#N]` routing;
- [ ] one Card, one worktree, one Pull Request;
- [ ] test-driven development through `superpowers`;
- [ ] verification before completion;
- [ ] Pull Request body with automated evidence and a non-filler human TODO;
- [ ] no self-merge;
- [ ] blocked escalation to architect;
- [ ] Pull Request-ready handoff to Quality Assurance engineer.

#### M4.4 Pull Request submission boundary

- [ ] validate acceptance criteria are terminal or explicitly waived;
- [ ] create/link one Pull Request;
- [ ] transition `In Progress -> In Review`;
- [ ] handoff `rd -> qa`;
- [ ] preserve Pull Request URL, branch, test evidence, and known limitations in the
      handoff comment.

#### M4.5 Cleanup and resume

- [ ] define behavior for interrupted Research and Development engineer sessions;
- [ ] define Blocked state without deleting work;
- [ ] remove worktree/branch only after verified merge or explicit
      cancellation;
- [ ] never recursively delete an unresolved path.

### Exit criteria

- two simultaneous attempts to claim one Card produce one winner;
- the winner can resume from durable state;
- one Research and Development engineer Card is implemented with tests and a Pull Request;
- resulting board state is `(In Review, qa)`;
- Research and Development engineer -> human is deterministically refused.

## 12. M5 - Quality Assurance engineer verification and the human lane

Status: **Pending**

Purpose: make the Quality Assurance engineer an independent seat rather than
a self-review step inside the Research and Development engineer session.

### Work items

#### M5.1 Verdict contract

Define:

```text
verdict: pass | fail | blocked
evidence: commands, URLs, screenshots, findings
scope: functional, UI, data correctness, security applicability
artifacts: Pull Request and Card references
```

- [ ] reject a bare pass/fail without evidence;
- [ ] preserve reproducible findings;
- [ ] keep verdict comments parseable.

#### M5.2 Add Quality Assurance engineer skill

Create `skills/verifying-delivery/SKILL.md` with:

- [ ] `[role:qa] [board-card:#N]` routing;
- [ ] ownership precondition `(In Review, qa)`;
- [ ] Pull Request-contract validation;
- [ ] `gstack:/review`;
- [ ] browser-based verification for user-interface Cards;
- [ ] data-correctness checks for connector/metric Cards;
- [ ] `gstack:/cso` when security-relevant;
- [ ] refusal to modify production code;
- [ ] evidence-backed verdict.

#### M5.3 Pass path

- [ ] write PASS verdict;
- [ ] preserve Status `In Review`;
- [ ] handoff `qa -> human`;
- [ ] surface the exact `Human Verification TODO`;
- [ ] prevent any agent merge operation.

#### M5.4 Fail path

- [ ] write FAIL verdict with reproducible findings;
- [ ] transition `In Review -> In Progress`;
- [ ] handoff `qa -> rd`;
- [ ] ensure Engineering Manager dispatch can return the same Card to Research and Development engineer;
- [ ] retain the same Pull Request/branch when appropriate.

#### M5.5 Post-merge reconciliation

- [ ] define whether GitHub auto-close is sufficient or an explicit
      reconciliation command is required;
- [ ] represent Done Role consistently (`human` or empty);
- [ ] clean the claim worktree only after merge is confirmed.

### Exit criteria

- Quality Assurance engineer pass creates `(In Review, human)` without merging;
- Quality Assurance engineer fail creates `(In Progress, rd)` with actionable findings;
- the entry router recognizes Quality Assurance engineer and Research and Development engineer;
- one live failure/fix/pass cycle completes.

## 13. M6 - Engineering Manager operations, work-in-progress, and recovery

Status: **Pending**

Purpose: evolve prompt rendering into safe team operations without coupling
correctness to autonomous spawning.

### Work items

#### M6.1 Role-lane briefing

- [ ] group Cards by Role and Status;
- [ ] show human-lane merge queue;
- [ ] show Blocked Cards and aging;
- [ ] show handoff counts approaching the cap;
- [ ] identify missing Role/Status as data-quality errors.

#### M6.2 Work-in-progress policy

- [ ] define work-in-progress as active `In Progress` plus `In Review`;
- [ ] choose whether Blocked is excluded;
- [ ] start with a soft global cap;
- [ ] defer per-seat caps until live starvation or overload is observed;
- [ ] make over-cap dispatch explicit rather than silently suppressing work.

#### M6.3 Dispatch safety

- [ ] refuse dispatch when the target seat has no legal next action;
- [ ] distinguish "prompt rendered" from "session started";
- [ ] include reason and required artifact in every queue entry;
- [ ] keep deterministic ordering;
- [ ] support one Role filter and a machine-readable JSON format.

#### M6.4 Recovery routines

- [ ] surface partial intake/handoff operations;
- [ ] surface stale claims;
- [ ] route Research and Development engineer blockers to architect and unresolved architect blockers to
      Engineering Manager;
- [ ] route handoff-cap breaches to Engineering Manager;
- [ ] document safe fix-forward commands.

### Exit criteria

- Engineering Manager sees an accurate team view;
- work-in-progress and handoff loops are visible;
- dispatch never claims it started an agent;
- recovery does not require inspecting raw Project node IDs.

Functional Phase 1 is complete at the end of M6.

## 14. M7 - Seat-aware governance and audit

Status: **Pending**

Purpose: reach the governed target proposed by the adaptation architecture.

### Work items

#### M7.1 Action catalog

- [ ] enumerate semantic mutations once, without duplicating IDs per Role;
- [ ] include create, transition, handoff, claim, release, Pull Request submit,
      verdict, and cleanup;
- [ ] distinguish read-only events from mutations.

#### M7.2 Seat-aware policy

- [ ] classify `(action, seat)` as automatic, review-required, or forbidden;
- [ ] apply hard forbidden floors before overrides;
- [ ] make agent merge forbidden and non-overridable;
- [ ] make out-of-seat mutations refuse before calling GitHub;
- [ ] add project-local overrides only after a live approval proves to be
      pure friction.

Do not copy the earlier full matrix blindly. Re-derive it from the six
implemented workflows and their actual mutation set.

#### M7.3 Audit schema

Use a new schema for this branch, with `actor_seat` present from the start:

- [ ] SQLite default using Python standard library;
- [ ] event UUID for idempotency;
- [ ] append-only rows;
- [ ] actor seat and session ID;
- [ ] semantic action, decision, outcome, and payload;
- [ ] JSONL fallback when SQLite is unavailable;
- [ ] no invented v2-to-v3 migration.

#### M7.4 Mutation integration

- [ ] write audit records for all semantic mutations;
- [ ] record partial failures honestly;
- [ ] record illegal-handoff refusals;
- [ ] ensure audit failure does not falsely report board failure;
- [ ] provide one command/query for a Card's seat-by-seat path.

### Exit criteria

- an out-of-seat action is refused before mutation;
- merge remains impossible for agent seats;
- one query reconstructs the golden-path Card history;
- audit degradation is visible and recoverable.

## 15. M8 - Golden-path proof and release

Status: **Pending**

Purpose: verify the system as a team, not as disconnected commands.

### Work items

#### M8.1 Fresh disposable repository

- [ ] load the plugin from source;
- [ ] configure a new disposable repository;
- [ ] run `doctor`;
- [ ] verify there is no hidden dependency on the plugin repository.

#### M8.2 Positive golden path

Use a small data-dashboard requirement:

```text
Show revenue by region for the last 30 days.
```

- [ ] analyst intake -> `(Backlog, architect)`;
- [ ] architect spec/decomposition -> `(Ready, rd)`;
- [ ] Engineering Manager dispatch -> Research and Development engineer prompt;
- [ ] Research and Development engineer test-driven development/Pull Request -> `(In Review, qa)`;
- [ ] Quality Assurance engineer evidence/pass -> `(In Review, human)`;
- [ ] human verifies and merges -> Done;
- [ ] each step starts from only its Role/Card prompt and durable artifacts.

#### M8.3 Negative paths

- [ ] Quality Assurance engineer rejects at least once and Research and Development engineer fixes the same Card;
- [ ] illegal Research and Development engineer -> human handoff refuses;
- [ ] one claim race produces a clean loser;
- [ ] one partial comment failure produces a fix-forward;
- [ ] one handoff-cap breach routes to Engineering Manager.

#### M8.4 Release verification

- [ ] full unit suite;
- [ ] GitHub contract tests;
- [ ] temporary-Git claim tests;
- [ ] live disposable-board e2e;
- [ ] Claude plugin validation;
- [ ] runtime skill discovery;
- [ ] documentation matches observed commands and outputs;
- [ ] version bump and release notes.

### Exit criteria

- Functional Phase 1 and governed target criteria both pass;
- no checklist item relies on an unrecorded manual board edit;
- the live trace is linked from the release notes;
- known limitations are explicit.

## 16. Optional milestones

These are deliberately outside the critical path.

### O1 - Automatic field setup

Revisit only after M1 confirms the installed `gh` command shape.

- idempotently create or validate Role/Status fields;
- retain a UI fallback;
- prefer one `setup` command over importing a 22-stage lifecycle engine;
- add a staged engine only if upgrades develop multiple independent,
  versioned setup concerns.

### O2 - Additional carriers

- one-deep Engineering Manager subagent for short Quality Assurance engineer/triage work;
- scheduled `claude -p` runs;
- carrier output consumes the same dispatch artifact;
- board state remains the correctness channel.

### O3 - Codex parity

- add `.codex-plugin/plugin.json`;
- verify skill discovery and command environment;
- replace any Claude-only assumptions;
- do not claim parity based only on manifest presence.

### O4 - Additional board backends

- extract a board port only when a second backend is selected;
- preserve semantic operations rather than exposing a generic field setter;
- add backend contract tests.

### O5 - Phase 2 and Phase 3 organization

- OPS and dedicated security seats;
- persistent agent identity/capability registry;
- multiple teams and a coordinating layer;
- cross-machine wake-up.

## 17. Forecast file map

This is a forecast, not a claim that the files exist.

| Area | Expected change |
|---|---|
| `docs/ARCHITECTURE.md` | normative Producer-and-Consumer design and decision updates |
| `docs/IMPLEMENTATION_PLAN.md` | milestone status and evidence |
| `scripts/producer_board.py` | preserved CLI entry point |
| `scripts/agent_teams/config.py` | extracted config validation |
| `scripts/agent_teams/model.py` | Role, Status, Card, Handoff, Verdict |
| `scripts/agent_teams/policy.py` | state machine, authority, cap, governance |
| `scripts/agent_teams/github.py` | `gh` invocation and normalization |
| `scripts/agent_teams/board.py` | semantic board operations |
| `scripts/agent_teams/workflows.py` | intake/promote/claim/verdict composition |
| `skills/using-agent-teams/SKILL.md` | Research and Development engineer/Quality Assurance engineer routing |
| `skills/authoring-spec/SKILL.md` | promotion/decomposition contract |
| `skills/dispatching-work/SKILL.md` | Role lanes/work-in-progress/recovery |
| `skills/consuming-card/SKILL.md` | new Research and Development engineer workflow |
| `skills/verifying-delivery/SKILL.md` | new Quality Assurance engineer workflow |
| `tests/test_producer_board.py` | retained CLI regression tests |
| `tests/fixtures/gh/` | sanitized live `gh` response fixtures |
| `tests/test_policy.py` | state and handoff matrix |
| `tests/test_partial_failures.py` | mutation prefix/fix-forward behavior |
| `tests/test_claim.py` | temporary-Git race/worktree behavior |
| `tests/e2e/` | opt-in disposable-board tests |

The module split should be introduced incrementally. Empty placeholder
modules are not a milestone deliverable.

## 18. Test architecture

| Layer | Purpose | Network |
|---|---|---|
| Unit | policy, parsing, ordering, recovery shapes | none |
| Adapter contract | replay sanitized real `gh` fixtures | none |
| Git integration | claim races and worktrees with temp remotes | local only |
| Plugin validation | manifest and skill discovery | none |
| Claude smoke | router and refusal behavior | Claude runtime |
| Live board e2e | actual GitHub reads/mutations | opt-in, disposable only |

Required principles:

- fake `gh` remains injectable;
- live tests never use a production Project;
- expected failures are asserted as structured results;
- no test depends on an installed audit DB client;
- tests distinguish "prompt rendered" from "session started";
- success claims always cite the latest observed run.

## 19. Dependency and sequencing rules

1. M1 precedes new GitHub mutation code; real response shapes first.
2. M2 policy precedes Research and Development engineer/Quality Assurance engineer mutations; legality before workflows.
3. M3 closes architect -> Ready before Research and Development engineer is implemented.
4. M4 claim precedes parallel Research and Development engineer execution.
5. M5 Quality Assurance engineer remains a separate session from Research and Development engineer.
6. M6 keeps human launch as the default carrier.
7. M7 governance is derived from implemented actions, not speculative rows.
8. M8 is the only point at which the whole Phase 1 team may be called
   complete.
9. Every milestone updates both status tables in these docs.
10. A live external side effect requires the disposable resource to be
    named and confirmed in the test record.

## 20. Immediate next actions

The next session should:

1. run the unrelated-repository Claude load and record the result;
2. install `gh` and authenticate with Project scope;
3. create a disposable Project with the required fields;
4. capture the real `gh` JSON contracts;
5. run `doctor`, read-only dispatch, and one disposable intake;
6. update M1 evidence before changing architecture;
7. settle the three M2 architect/handoff decisions;
8. implement the smallest Status transition that closes
   `(Backlog, architect) -> (Ready, rd)`.

No Research and Development engineer or Quality Assurance engineer workflow,
audit system, setup automation, or autonomous carrier work should begin
before those steps establish a working live-board foundation.
