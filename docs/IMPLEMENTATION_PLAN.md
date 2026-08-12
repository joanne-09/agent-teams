# agent-teams Implementation Plan

Status: active plan for evolving the Producer minimum viable product into the
proposed Phase 1 agent team
Applies to: `mvp/producer-from-scratch`
Last updated: 2026-08-12

## 1. Outcome

The desired outcome is a small but complete Claude Code agent team in which:

1. a System Analyst creates and shapes a requirement;
2. a System Architect publishes the durable specification directly on the
   current Git branch and hands shaped Cards to the human readiness gate;
3. the current Tech Lead session plans and starts the next legal bounded
   subagent without human prompt transport;
4. a Developer claims one Card, works through
   test-driven development, and opens one Pull Request;
5. a separate Quality Assurance engineer session performs multidimensional,
   evidence-grounded review and writes a structured verdict;
6. deterministic policy routes an eligible delivery to automated merge, a
   defect back to the Developer, or a protected change to the human exception
   lane;
7. standing repository context plus live board state is sufficient for every
   bounded worker to reconstruct its role-appropriate project view and resume.

This plan started from a four-skill, one-script minimum viable product. The
Producer and Consumer surfaces are now connected by a deterministic
`next-actions` planner, one plugin worker agent, and a flat current-session
coordinator. It does not assume the larger `board-superpowers` implementation
is present.

### 1.1 Automation extension (2026-08-12)

This extension supersedes older milestone text that leaves human launch,
specification Pull Requests, or routine reconciliation as defaults.

| Work item | Status | Enforcement |
|---|---|---|
| Direct product spec on current branch; no spec PR | Implemented, uncommitted | `Git.publish_specification`, `publish-spec`, exact Card record |
| Same-session bounded worker launch; no prompt copy | Implemented, uncommitted | `next-actions`, `dispatching-work`, `agents/agent-teams-worker.md` |
| Two human gates only | Implemented, uncommitted | readiness policy and protected-change `approve-exception` |
| WIP-aware ordering and serialized direct-spec authors | Implemented, uncommitted | `Producer.next_actions` |
| Delayed merge monitoring and automatic reconciliation | Implemented, uncommitted | typed `monitor` / `reconcile` controller actions |
| Exact-head safety and no generic Done bypass | Implemented, uncommitted | `--match-head-commit`, merge-evidence-only reconciliation |
| Returned analyst Card clarification without duplicate intake | Implemented, uncommitted | `clarify` command and analyst worker route |

The plan follows the design relationship defined in
[`ARCHITECTURE.md` Appendix B](./ARCHITECTURE.md#appendix-b--lineage):
Producer and Consumer are per-session execution shapes, while the named team
seats carry capability and authority. Milestones M1 through M3 complete the
minimum viable Producer path from intake through readiness and dispatch.
Milestone M4 introduces the one-Card Developer
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
  -> (Ready, dev)
  -> (In Progress, dev)
  -> (In Review, qa)
  -> deterministic acceptance
  -> Done after automated merge
```

It must also prove the Quality Assurance rejection path:

```text
(In Review, qa) -> (In Progress, dev)
```

It must also prove the protected-change path:

```text
(In Review, qa) -> (In Review, human) -> Done after human decision
```

and refuse an illegal direct handoff from the Developer to the human or any
direct agent merge.

### 2.2 Governed target

The governed target additionally requires:

- a seat-aware action policy;
- deterministic acceptance and merge for eligible changes;
- a human exception lane for protected changes;
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
| Producer context bootstrap | Done | `bootstrap --role <seat>` in `workflows.Producer.bootstrap`; owned by the entry skill; `BootstrapTests` proves per-seat views and read-only behaviour |
| Analyst intake skill | Done | `skills/intaking-requirement/SKILL.md` |
| Architect specification skill | Done | `skills/authoring-spec/SKILL.md`; covers the three architect jobs and the readiness gate. Live Git/Pull Request flow still unverified |
| Tech Lead dispatch skill | Done | `skills/dispatching-work/SKILL.md` |
| Tech Lead briefing skill | Done | `skills/briefing-board/SKILL.md` |
| Tech Lead triage skill | Done | `skills/triaging-board/SKILL.md` |
| Quality Assurance queue inspection skill | Done | `skills/inspecting-queue/SKILL.md`; Producer-shaped, issues no verdicts |
| Developer execution skill | Done | `skills/consuming-card/SKILL.md` + 3 references; carries the Architect documentation routine too |
| Quality Assurance engineer verification and acceptance skill | Done | `skills/verifying-delivery/SKILL.md` + 3 references; eight review dimensions, pre-emit evidence gate, challenge loop, blind-spot loop |

### 4.3 Board adapter

| Work item | Status | Evidence |
|---|---|---|
| Config read/write and validation | Done | `config.py`; reports every defect at once; `ConfigTests` (8 tests) |
| `gh` wrapper with structured failure | Done | `github.py`; injectable `Gh` plus stderr classification into `auth`/`scope`/`not_found`/`permission`/`rate_limit` |
| Project/field/option lookup | Done | `board.py`; unit-tested with fake `gh` |
| Project item normalization and repo filtering | Done | `BoardReadTests`; unrecognised Role reads as unset rather than crashing |
| Pagination and truncation detection | Done | `github.fetch_all_items` escalates until a response returns short; `PaginationTests` proves a 250-Card board reads completely and a 10,000-Card board raises rather than truncating |
| `doctor` | Done | Validates all six Statuses and all six Roles, reporting every missing option in one response; `DoctorTests` |
| `list` | Done | Implemented; live response unverified |
| deterministic `dispatch` | Done | Unit-tested filtering and order |
| `bootstrap` | Done | Read-only per-seat startup context; `BootstrapTests` |
| `brief` | Done | Role lanes, work-in-progress, merge queue, data-quality defects, one recommendation; `BriefTests` |
| `triage` | Done | Blocked Cards grouped by responsible seat; `TriageTests` |
| `queue` | Done | Quality Assurance queue inspection with kickoff prompts; `VerificationQueueTests` |
| `intake` | Done | Single Role write; five-step recovery covered by `IntakeFailureTests` |
| `handoff` | Done | Authority matrix, cap counted from structured comments, partial-comment recovery; `HandoffTests`, `HandoffFailureTests` |
| Status transition | Done | `transition` command; authority keyed to the destination; `TransitionTests` |
| `promote` (Backlog to Ready) | Done | Readiness gate plus two independent operations; `PromoteTests`, `PromoteFailureTests` |
| `create-card` / `decompose` | Done | Flat implementation Cards with spec pointer and provenance; `DecomposeTests`, `DecomposeFailureTests` |
| Card claim/worktree | Done | `git.py`; exclusivity proven against real git (`ClaimRaceTests`), guarded worktree removal (`WorktreeTests`) |
| Pull Request link/verdict/acceptance/merge/reconciliation operations | Done | `board.pull_request`/`record_verdict`/`record_acceptance`/`arm_auto_merge`/`merge_state`; `Consumer.{claim,submit,verdict,accept,reconcile}`. Live `gh` shapes still assumed |
| Append-only audit log | Pending | M7; the partial-failure envelope is not a substitute |

### 4.4 Verification

| Check | Status | Latest evidence |
|---|---|---|
| Python syntax | Done | Passed 2026-07-31 |
| Unit suite | Done | 130/130 passed on 2026-07-31, after the seat rename (`python -m unittest discover -s tests -p "test_*.py"`) |
| Policy edge coverage | Done | All 36 Status pairs and all 36 Role pairs asserted individually, not sampled (`test_policy.py`) |
| Partial-failure coverage | Done | Every mutation boundary in intake, handoff, promote, and decompose (`test_partial_failures.py`) |
| Claude plugin validation | Pending | Manifests bumped to 0.2.0; not re-validated since the seven-skill layout landed |
| Non-mutating Claude namespace load | Pending | Superseded by the seven-skill layout; the recorded run covered four skills |
| Test from unrelated repository | Pending | Not proven in current evidence |
| Persistent marketplace install | Pending | Procedure documented only |
| Live GitHub Project read | Blocked externally | `gh` not installed on this machine |
| Live mutation | Blocked externally | `gh` and a disposable Project required |

Every "Done" row above is hermetic: it runs against an injected fake `gh` and
proves the adapter behaves correctly *given the response shapes it assumes*.
None of it proves those shapes match a real `gh`. That distinction is the
whole of M1.3 and it remains open.

## 5. Priority gap map

### P0: prove the slice against real GitHub

Everything in this band that could be closed without a live board has been.
What is left needs `gh`:

- validate actual `gh project` response shapes against the hermetic fixtures;
- test on a disposable Project;
- confirm `gh project item-list --limit` behaves as the pagination escalation
  assumes.

Closed in this change: the read-only context bootstrap, standing-context
loading, the Backlog-to-Ready hole, all six Status options, and structured
partial-mutation reporting with recovery instructions.

### P1: complete the five-seat workflow

Producer-side items are done: Status transition policy, the currently enforced
human-only merge floor, and work-in-progress plus handoff-loop safety. M5 must
replace that floor atomically with deterministic acceptance plus the protected-
change exception; until then, automated merge is designed but not implemented.
Remaining items are Consumer-shaped:

- add Developer claim/test-driven development/Pull Request workflow;
- add independent Quality Assurance engineer verdict workflow.

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
M0  Architecture/status docs                         Done
 |
M1  Live GitHub contract proof + adapter hardening   Done except live proof
 |                                                   (M1.1-M1.3 need gh)
M2  Domain policy + Status operations                Done
 |
M3  Architect -> Ready vertical slice                Done except live proof
 |
M4  Developer execution      Done except live proof
 |
M5  QA verification + deterministic acceptance       Done except live proof
M6  Tech Lead operations, WIP, recovery    Done (stale-claim input
 |                                                   shipped: worktree-status)
M6.5 Blocker resolution (`resolving-issues`)         Pending (claims now exist)
 |
M7  Seat-aware governance and audit                  Policy done; audit pending
 |
M8  Golden-path proof and release                    Pending (needs gh)
 |
`-> Optional: setup automation, carriers, Codex, backends, Phase 2/3
```

M1 through M6 produce Functional Phase 1. M7 and M8 produce the governed
target.

**Both surfaces are now implemented.** Every Producer-shaped routine in
`ARCHITECTURE.md` section 6 and every Consumer-shaped routine in section 7 —
Developer implementation, Architect documentation delivery, and Quality
Assurance verification through deterministic acceptance and controlled merge —
is built and hermetically tested.

**What remains is the live-GitHub proof that no amount of local testing can
substitute for.** Every `gh` response shape this code reads is still an
assumption encoded in `tests/fake_gh.py`, and no verdict, acceptance decision,
auto-merge arming, or reconciliation has ever run against a real repository.
Treat M8 and the M1.1-M1.3 items as the remaining risk, not as paperwork.

One exception is genuinely proven rather than assumed: claim exclusivity is
tested against **real git** using a local bare repository as origin, because a
fake would have agreed with the wrong implementation. See the note under M4.1.

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
- No Developer, Quality Assurance engineer, audit, setup-stage, Codex, or live GitHub behavior is called
  implemented.

## 8. M1 - Live GitHub contract proof and adapter hardening

Status: **Adapter hardening done; live contract proof externally blocked**

M1.4 through M1.7 are delivered and test-backed. M1.1 through M1.3 need an
installed `gh` and a disposable Project and remain the single largest risk in
the plan: every hermetic test below assumes response shapes that have not yet
been checked against a real GitHub CLI.

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

- [x] Validate all six Status options, not only Backlog and Ready.
- [x] Report every missing field/option in one diagnostic response.
- [x] Validate `repo` as `OWNER/REPO`.
- [x] Reject empty custom field/status names.
- [x] Reject duplicate dispatch Roles.
- [x] Add one focused test per failure.

#### M1.5 Handle Project size and pagination

- [ ] Determine whether `gh project item-list --limit` can safely exceed
      100 on the supported CLI.
- [x] Either implement pagination/adequate limit or document and detect the
      ceiling.
- [x] Add a test proving Cards past the first response page are not silently
      lost.

#### M1.6 Make partial failure actionable

- [x] Define a structured partial-result shape:

```json
{
  "ok": false,
  "partial": true,
  "completed": ["issue_created", "project_item_added"],
  "failed": "status_set",
  "recovery": ["..."]
}
```

- [x] Preserve created Issue URL/number and Project item ID as soon as known.
- [x] Add tests for failure after every remote mutation in intake.
- [x] Add tests for comment failure after Role mutation in handoff.
- [x] Do not claim rollback unless a real compensation succeeded.

#### M1.7 Producer context bootstrap

- [x] Make `using-agent-teams` own one common startup contract in addition to
      intent routing.
- [x] Load repository instructions plus compact product, architecture,
      decision, and team-configuration pointers before selecting work.
- [x] Query the complete live board through the deterministic `list` path
      before every Producer routine; never treat the kickoff snapshot as
      authoritative.
- [x] Build seat-specific views for System Analyst, System Architect,
      Tech Lead, and Quality Assurance queue work.
- [x] Ensure a direct downstream-skill match runs the bootstrap exactly once
      rather than skipping it or running it twice.
- [x] Keep bootstrap read-only and refuse mutation when configuration,
      pagination, identity, or live board state is uncertain.
- [x] Add repository-context fixtures and fake-`gh` tests proving that a fresh
      Producer session can reconstruct its view without prior conversation.
- [x] Treat bounded subagent, human terminal, and scheduled execution as
      equivalent carriers of the same startup contract.

### Exit criteria

- `doctor` passes against a disposable Project.
- read-only `list` and `dispatch` return the expected live Cards.
- one disposable intake completes and its exact durable result is verified.
- failures identify the last completed mutation and a safe fix-forward.
- fixtures reflect observed GitHub CLI output.
- fresh `analyst`, `architect`, and `lead` Producer launches report which
  standing sources and live board projection formed their startup context.

## 9. M2 - Domain policy and Status operations

Status: **Done**

All three decision gates are settled and recorded in `ARCHITECTURE.md`
Appendix A.2. Policy is pure and exhaustively tested: every Status pair and
every Role pair is asserted individually.

Purpose: create the deterministic contract required by the System Architect,
Developer, and Quality Assurance engineer instead of
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
- [ ] On cap breach, refuse normal handoff and route recovery to Tech Lead.
- [ ] Keep Role mutation independent from Status transition.

#### M2.4 Structured handoff comments

Adopt a parseable contract:

```markdown
<!-- agent-teams:handoff -->
**Handoff**: `dev` -> `qa`
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

Status: **Done except live proof**

`promote` and `decompose` close the gap between specification completion and
dispatch. The exit criteria requiring a *live* intake-to-Ready run stay open
until `gh` is available.

Purpose: close the current golden-path break between specification completion
and Tech Lead dispatch.

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
- [ ] handoff `architect -> dev`;
- [ ] include the specification artifact in the handoff;
- [ ] ensure `dispatch --role dev` returns the Card.

Role and Status remain separate mutations. If the second mutation fails, the
result must identify the partial state and fix-forward.

#### M3.3 Multi-Card decomposition

For a larger specification:

- [ ] expose a generic semantic `create-card` operation, distinct from
      analyst intake;
- [ ] require outcome, acceptance criteria, dependencies, and spec pointer;
- [ ] create flat implementation Cards in `(Ready, dev)`;
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

- one live analyst intake becomes at least one live `(Ready, dev)` Card;
- Tech Lead dispatch returns its Developer kickoff prompt;
- no manual Project field edit is needed between architect and Tech Lead;
- a too-thin requirement can return to analyst if that authority is adopted.

## 11. M4 - Developer execution and exclusive claim

Status: **Done except live proof** (2026-08-06)

Purpose: turn `dev` from a dispatch value into a real Consumer-shaped seat.

### Decision gate

- [ ] Choose the claim primitive after the disposable Project is working.

Recommended: retain the proposed architecture's remote claim-branch
compare-and-swap semantics and one worktree per Card, implemented in
cross-platform Python/Git rather than importing the earlier shell framework.

### Work items

#### M4.1 Claim operation

- [x] require `(Ready, dev)` (or `(Ready, architect)` for documentation Cards);
- [x] create a deterministic claim branch, `claim/<n>-<slug>`;
- [x] create an isolated worktree under the configured `workspace`;
- [x] make remote branch acquisition the exclusivity signal;
- [x] return a distinct race-lost result that must not retry;
- [x] transition to `In Progress` only with a documented compensation order
      (claim first: a won claim on a still-Ready Card waits for a re-run, but a
      Card moved by a session that then lost the race was mutated by a session
      that never owned it);
- [x] persist enough claim metadata for safe resume and cleanup;
- [x] add concurrency-focused tests using temporary Git remotes.

**The finding that shaped this operation.** The obvious implementation --
compare-and-swap by pushing the base SHA with an empty-expect lease -- gives
*two winners* in the common case. Pushing an identical SHA to an existing ref
is `Everything up-to-date`, exit `0`; git never evaluates the lease. Both
claimants proceed, and a coverage-only suite reports the path fully covered
while asserting the wrong outcome. The claim pushes a unique empty commit with
a session nonce instead. This is why the race tests run against real git rather
than a fake: a fake would have agreed with the wrong implementation.

#### M4.2 Sibling-plugin preflight

**Withdrawn, not delivered.** This item predates invariant 10. agent-teams
calls no other plugin, so there is no dependency to preflight and no
missing-dependency behaviour to document. The disciplines these siblings carry
were adopted as derived text with attribution instead -- see `ATTRIBUTION.md`
and `docs/skill_migration.md` sections 8 and 9. A grep for `superpowers:` or
`gstack:/` across `skills/` returns nothing, and that absence is the proof.

#### M4.3 Add Developer skill

Create `skills/consuming-card/SKILL.md` with:

- [ ] `[role:dev] [board-card:#N]` routing;
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
- [ ] handoff `dev -> qa`;
- [ ] preserve Pull Request URL, branch, test evidence, and known limitations in the
      handoff comment.

#### M4.5 Cleanup and resume

- [ ] define behavior for interrupted Developer sessions;
- [ ] define Blocked state without deleting work;
- [ ] remove worktree/branch only after verified merge or explicit
      cancellation;
- [ ] never recursively delete an unresolved path.

### Exit criteria

- two simultaneous attempts to claim one Card produce one winner;
- the winner can resume from durable state;
- one Developer Card is implemented with tests and a Pull Request;
- resulting board state is `(In Review, qa)`;
- Developer -> human is deterministically refused.

## 12. M5 - Quality Assurance verification and deterministic acceptance

Status: **Done except live proof** (2026-08-06)

Purpose: make Quality Assurance an independent, multidimensional review stage
that produces challenged evidence for deterministic merge eligibility rather
than sending every passing Pull Request to a second mandatory human gate.

### Work items

#### M5.1 Structured verdict and evidence contract

Define:

```text
verdict: pass | fail | blocked
head_sha: exact reviewed Pull Request head
design_baseline: specification, architecture, and decision references
review_dimensions: design, architecture, correctness, edge cases, security,
                   compatibility, cross-file risk, test strength
changed_files: complete enumerated set and bounded review units
conformance: requirement/invariant -> implementation evidence -> test evidence
test_strength: line, branch, mutation, scenario, and integration evidence
findings: evidence, challenge performed, challenge outcome
blind_spots: unresolved or unreviewed areas
artifacts: Pull Request, Card, commands, URLs, screenshots, and machine results
```

- [ ] reject a bare pass/fail without evidence;
- [ ] preserve reproducible findings;
- [ ] bind every verdict to the exact Pull Request head;
- [ ] reject a pass with missing changed files, required dimensions, or
      unresolved blind spots;
- [ ] publish one readable Pull Request report plus parseable evidence.

#### M5.2 Add Quality Assurance engineer skill

Create `skills/verifying-delivery/SKILL.md` with:

- [ ] `[role:qa] [board-card:#N]` routing;
- [ ] ownership precondition `(In Review, qa)`;
- [ ] Pull Request-contract validation;
- [ ] deterministic enumeration of every changed and new file;
- [ ] bounded splitting of large changes without omitting any review unit;
- [ ] design and architecture conformance review;
- [ ] correctness and edge-case review;
- [ ] security and compatibility review;
- [ ] cross-file and compound-risk review;
- [ ] test-strength review that does not equate line execution with tested
      behaviour;
- [ ] blind-spot detection and repeated review of affected dimensions;
- [ ] optional multiple bounded reviewer agents or independent passes by
      dimension, while the bound QA Consumer retains ownership and synthesis;
- [ ] browser-based verification for user-interface Cards and data-correctness
      checks for connector/metric Cards when applicable;
- [ ] locally owned review instructions; no runtime dependency on another
      plugin or its skills; compatible open instructions may be adapted into
      this skill with attribution rather than called at runtime;
- [ ] refusal to modify production code;
- [ ] evidence-backed verdict.

#### M5.3 Evidence grounding and challenge

- [ ] require every material finding to cite code, behaviour, design, test, or
      command evidence;
- [ ] challenge each material finding against callers, related files, intended
      behaviour, existing mitigations, and contrary evidence;
- [ ] retain the challenge outcome in the verdict;
- [ ] record unresolved uncertainty as `blocked`; deterministic policy may then
      classify it as a protected change, but QA never selects its own route;
- [ ] rerun a dimension when changed-file or review-dimension coverage exposes
      a blind spot.

#### M5.4 Deterministic eligibility and routing

Define a separate, policy-authored result:

```text
acceptance: eligible | defect | protected_change
head_sha: exact head for which the decision is valid
policy_version: deterministic policy version
reasons: satisfied requirements or exact refusal/escalation reasons
```

- [ ] validate verdict schema, exact head SHA, evidence completeness, required
      checks, mergeability, and protected-change policy before any mutation;
- [ ] eligible: preserve `In Review`, publish the acceptance status, and let the
      deterministic merge controller merge the same reviewed head;
- [ ] defect: write reproducible findings, transition `In Review -> In
      Progress`, hand off `qa -> dev`, and retain the same Pull Request/branch;
- [ ] protected change: preserve `In Review`, hand off `qa -> human`, and name
      the exact protected file, design decision, risk, or unresolved judgment;
- [ ] reject stale evidence immediately after any new Pull Request commit;
- [ ] prevent QA, Developer, or any other agent seat from directly merging or
      bypassing eligibility policy;
- [ ] ensure Tech Lead dispatch can resume each durable route.

#### M5.5 Post-merge reconciliation

- [ ] use an explicit reconciliation command after confirmed automated or human
      merge;
- [ ] represent Done Role consistently without inventing an automation seat;
- [ ] clean the claim worktree only after merge is confirmed.

### Exit criteria

- a QA pass publishes complete, challenged evidence for the current head;
- deterministic policy routes an eligible pass to merge without a mandatory
  human review;
- a QA defect creates `(In Progress, dev)` with actionable findings;
- a protected change creates `(In Review, human)` with an exact escalation
  reason;
- the entry router recognizes Quality Assurance engineer and Developer;
- one live failure/fix/pass/eligible-merge cycle completes;
- one live protected-change/human-decision cycle completes.

## 13. M6 - Tech Lead operations, work-in-progress, and recovery

Status: **Done except stale-claim detection**

`brief` and `triage` deliver the Role-lane view, work-in-progress policy,
handoff-cap visibility, and blocked-work recovery routing. Stale-claim
detection is deferred to M4, because claims do not exist until the Consumer
seat does.

Purpose: evolve prompt rendering into safe team operations without coupling
correctness to autonomous spawning.

### Work items

#### M6.1 Role-lane briefing

- [ ] group Cards by Role and Status;
- [ ] show automated-acceptance and protected-change queues separately;
- [ ] show Blocked Cards and aging;
- [ ] show handoff counts approaching the cap;
- [ ] identify missing Role/Status as data-quality errors.

#### M6.2 Work-in-progress policy

- [ ] define work-in-progress as active `In Progress` plus `In Review`;
- [ ] choose whether Blocked is excluded;
- [ ] start with a soft global cap;
- [ ] defer per-seat caps until live starvation or overload is observed;
- [ ] make over-cap dispatch explicit rather than silently suppressing work.

#### M6.3 Dispatch safety *(historical; superseded by the automation extension)*

- [ ] refuse dispatch when the target seat has no legal next action;
- [x] distinguish a planned action, started bounded worker, and durable GitHub
      completion state;
- [ ] include reason and required artifact in every queue entry;
- [ ] keep deterministic ordering;
- [ ] support one Role filter and a machine-readable JSON format.

#### M6.4 Recovery routines

- [ ] surface partial intake/handoff operations;
- [ ] surface stale claims;
- [ ] route Developer blockers to architect and unresolved architect blockers to
      Tech Lead;
- [ ] route handoff-cap breaches to Tech Lead;
- [ ] document safe fix-forward commands.

### Exit criteria

- Tech Lead sees an accurate team view;
- work-in-progress and handoff loops are visible;
- dispatch never claims it started an agent;
- recovery does not require inspecting raw Project node IDs.

Functional Phase 1 is complete at the end of M6.

## 13a. M6.5 - Blocker resolution and the escalation ladder

Status: **Pending** — depends on M4, because half of what a resolver must
observe (claims, worktrees, Pull Request state) does not exist until the
Consumer seat does.

Purpose: make [`ARCHITECTURE.md` §11.6-11.7](./ARCHITECTURE.md#116-failure-classes)
executable. `triage` today *lists* Blocked Cards grouped by responsible seat;
it does not classify a blocker, does not check whether a proposed recovery is
actually applicable, and does not emit the commands. That gap is currently
closed by a human reading an envelope and reconstructing the fix by hand.

### Decision gate

- [ ] Decide whether the resolver may **apply** a stale-block transition, or
      may only propose it. Recommended: **propose only**, matching every other
      recovery surface in this design — a resolver that mutates on inference
      re-opens the authority hole decisions 4-6 closed.

### Work items

#### M6.5.1 Failure classification in code

- [ ] Represent the four classes of §11.6 as a validated domain value.
- [ ] Tag every existing structured refusal and partial envelope with its class.
- [ ] Classify a Blocked Card's blocker as external-dependency,
      decision-pending, or stale-block from its structured comments.
- [ ] Refuse to classify when no blocker was named, rather than guessing —
      an unnamed blocker is a data-quality defect, and `brief` already reports
      those.

#### M6.5.2 Deterministic precondition checks

The point of the skill is that it *verifies* rather than *asserts*. Each
recovery names preconditions; a script establishes which actually hold:

- [ ] Does the referenced specification, Pull Request, or branch still exist?
- [ ] Is the claim branch still present on the remote, and how old is it?
- [ ] Does the Card's `(Status, Role)` still match what the blocker assumed?
- [ ] Did the handoff comment the partial envelope expected ever land?
- [ ] Report each check as pass/fail/unknown; **never report unknown as pass**.

#### M6.5.3 `resolving-issues` skill

Create `skills/resolving-issues/SKILL.md`:

- [ ] Producer-shaped, `lead`-seated, read-only by default.
- [ ] Input: one Blocked Card, or the Blocked queue.
- [ ] Output: classification, the checks that ran with their results, and the
      exact fix-forward commands — never a claim that it fixed anything.
- [ ] Refuse to touch production code, merge, or promote.
- [ ] Route a decision-pending blocker whose question is really a new
      requirement to intake instead of proposing a transition.

#### M6.5.4 Stale claim and worktree recovery

- [ ] Detect claim branches with no progress; adopt an explicit age threshold
      and record it in config rather than hard-coding it.
- [ ] Propose release as one atomic unit (branch delete **plus** the Status
      move), never as two independently approvable steps.
- [ ] Never delete an unresolved worktree path (§11.5).

#### M6.5.5 Ladder instrumentation

- [ ] Record which rung a Card is on, derived from durable state rather than
      from a counter no session can see.
- [ ] Surface Cards that have sat on one rung longer than a configured age.
- [ ] Document explicitly that the rung-1 "two attempts" bound remains skill
      prose, not an enforced counter — do not imply otherwise in output.

### Exit criteria

- every Blocked Card in a disposable board is classified, or explicitly
  reported as unclassifiable with the reason;
- each proposed recovery names the checks that were run and their results;
- no proposed command depends on a precondition that was reported `unknown`;
- one partial-mutation envelope and one stale claim are both recovered by
  following the emitted commands without hand-reconstruction;
- the skill never reports a mutation it did not perform.

## 14. M7 - Seat-aware governance and audit

Status: **Pending**

Purpose: reach the governed target proposed by the adaptation architecture.

### Work items

#### M7.1 Action catalog

- [ ] enumerate semantic mutations once, without duplicating IDs per Role;
- [ ] include create, transition, handoff, claim, release, Pull Request submit,
      verdict, eligibility, controlled merge, and cleanup;
- [ ] distinguish read-only events from mutations.

#### M7.2 Seat-aware policy

- [ ] classify `(action, seat)` as automatic, review-required, or forbidden;
- [ ] apply hard forbidden floors before overrides;
- [ ] make direct agent merge forbidden and non-overridable while allowing only
      the deterministic controller to execute an eligible merge;
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
- [ ] architect spec/decomposition -> `(Ready, dev)`;
- [ ] Tech Lead dispatch -> Developer prompt;
- [ ] Developer test-driven development/Pull Request -> `(In Review, qa)`;
- [ ] Quality Assurance engineer review/evidence/pass -> deterministic
      acceptance;
- [ ] eligible Pull Request -> automated merge -> Done;
- [ ] each step starts from only its Role/Card prompt and durable artifacts.

#### M8.3 Negative paths

- [ ] Quality Assurance engineer rejects at least once and Developer fixes the same Card;
- [ ] illegal Developer -> human handoff refuses;
- [ ] protected change routes to `(In Review, human)` with the exact reason;
- [ ] stale QA evidence cannot authorize merge after a new commit;
- [ ] missing changed-file or review-dimension coverage cannot produce pass;
- [ ] one claim race produces a clean loser;
- [ ] one partial comment failure produces a fix-forward;
- [ ] one handoff-cap breach routes to Tech Lead.

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

## 15a. Cross-cutting change - seat rename

Status: **Applied in this repository on 2026-07-31; one manual step remains**

Two seat tokens were renamed for external legibility:

| Before | After | Full name before | Full name after |
|---|---|---|---|
| `rd` | `dev` | Research and Development engineer | Developer |
| `em` | `lead` | Engineering Manager / Team Lead | Tech Lead |

Applied:

- [x] `scripts/agent_teams/model.py` — `Role.DEV` / `Role.LEAD` members, wire
      values, and `_FULL_NAMES`.
- [x] `scripts/agent_teams/policy.py` — handoff graph, refusal pairs,
      `CAP_BREACH_TARGET`, and every `(action, seat)` row.
- [x] `scripts/agent_teams/config.py` — `dispatch_roles` default is now
      `("architect", "dev", "qa")`.
- [x] `scripts/agent_teams/workflows.py`, `scripts/producer_board.py`.
- [x] All seven skill bodies, `docs/`, `README.md`, `HANDOFF.md`,
      `CLAUDE_TESTING.md`, and the plugin manifest description.
- [x] Tests, including the derived fake-`gh` option identifiers
      (`ROLE_RD` became `ROLE_DEV`) — those do not contain a word boundary at
      the token, so they survived the mechanical pass and were caught by the
      suite rather than by grep. **130/130 pass.**

Remaining, and it is not something this repository can do for you:

- [ ] **Rename the `Role` single-select options on every configured GitHub
      Project** from `rd` to `dev` and `em` to `lead`.

That step is a manual Project edit. Until it happens, `doctor` will fail on a
live board — correctly, because the configured options no longer match the six
this code governs. Two migration shapes, and the choice depends on how many
Cards exist:

1. **Rename the option in place** (GitHub keeps the option's node identifier,
   so every Card holding it follows automatically). Preferred.
2. **Add the new option, re-set each Card, delete the old one.** Only if
   renaming in place is unavailable; this leaves a window where both tokens
   exist, and `list` will read the stale one as *unset* rather than crashing.

Run `doctor` immediately after either path; it reports every missing option in
one pass, so a half-finished migration is visible in a single command.

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

- one-deep Tech Lead subagent for short Quality Assurance engineer/triage work;
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
| `skills/using-agent-teams/SKILL.md` | Developer/Quality Assurance engineer routing |
| `skills/authoring-spec/SKILL.md` | promotion/decomposition contract |
| `skills/dispatching-work/SKILL.md` | Role lanes/work-in-progress/recovery |
| `skills/consuming-card/SKILL.md` | new Developer workflow |
| `skills/verifying-delivery/SKILL.md` | new Quality Assurance engineer workflow |
| `skills/resolving-issues/SKILL.md` | new blocker-resolution workflow (M6.5) |
| `scripts/agent_teams/recovery.py` | blocker classification and precondition checks (M6.5) |
| `tests/test_recovery.py` | classification and precondition-check behaviour |
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
| Test strength | changed branches, mutation resistance, required scenarios, state-machine properties | none |
| Adapter contract | replay sanitized real `gh` fixtures | none |
| Git integration | claim races and worktrees with temp remotes | local only |
| Plugin validation | manifest and skill discovery | none |
| Claude smoke | router and refusal behavior | Claude runtime |
| Live board e2e | actual GitHub reads/mutations | opt-in, disposable only |

Required principles:

- fake `gh` remains injectable;
- live tests never use a production Project;
- expected failures are asserted as structured results;
- changed-line coverage is never accepted as sole evidence that behaviour is
  tested; branch outcomes, assertion strength, mutation resistance, and required
  positive/negative scenarios are evaluated where applicable;
- critical policy and transition changes have no unexplained surviving mutants
  and no untested legal or illegal state transition;
- no test depends on an installed audit DB client;
- tests distinguish planned actions, started bounded workers, and durable
  GitHub completion state;
- success claims always cite the latest observed run.

## 19. Dependency and sequencing rules

1. M1 precedes new GitHub mutation code; real response shapes first.
2. M2 policy precedes Developer/Quality Assurance engineer mutations; legality before workflows.
3. M3 closes architect -> Ready before Developer is implemented.
4. M4 claim precedes parallel Developer execution.
5. M5 Quality Assurance remains a separate session from Developer; its
   structured evidence contract precedes deterministic eligibility and merge.
6. M6 uses the current-session bounded subagent coordinator as the default
   carrier; human launch is a troubleshooting fallback.
6a. M6.5 follows M4: a resolver cannot verify claim, worktree, or Pull Request
    preconditions that do not exist yet, and one built against absent state
    would be re-derived rather than extended.
7. M7 governance is derived from implemented actions, not speculative rows.
8. M8 is the only point at which the whole Phase 1 team may be called
   complete.
9. Every milestone updates both status tables in these docs.
10. A live external side effect requires the disposable resource to be
    named and confirmed in the test record.

## 20. Immediate next actions

The Producer surface is code-complete and hermetically tested. Every
remaining Producer risk is the same risk: **none of it has met a real GitHub
CLI.** The next session should close that, in this order:

1. install `gh` and authenticate with Project scope;
2. create a disposable repository and Project with both six-option fields;
3. run `doctor` and confirm it reports what is actually missing;
4. capture the real `gh project view / field-list / item-list / item-add`
   JSON and convert the captures into hermetic fixtures, replacing the
   assumed shapes in `tests/fake_gh.py`;
5. confirm the `--limit` escalation in `github.fetch_all_items` matches how
   the installed `gh` really paginates -- if `gh` caps `--limit`, the
   escalation must become a documented ceiling instead;
6. run one disposable intake, one promote, and one handoff, and check the
   durable result against what the JSON envelope claimed;
7. run the unrelated-repository Claude load and confirm all seven skills
   appear;
8. update the section 4.4 verification table with the observed evidence.

Only then start Consumer work (M4/M5) or the audit system (M7). Building a
second seat on unverified response shapes would double the surface that has
to be re-checked when the first real `gh` call disagrees with a fixture.
