# Consumer flow — design

Status: approved design, not yet implemented
Date: 2026-08-06
Applies to: `agent-teams` (Claude Code plugin)
Normative parent: [`../ARCHITECTURE.md`](../ARCHITECTURE.md) §7, §9.5–9.8, §11
Status ledger: [`../IMPLEMENTATION_PLAN.md`](../IMPLEMENTATION_PLAN.md) (M4 + M5 rows)

---

## 1. Purpose and scope

The Producer surface is complete. This design specifies the **Consumer half**: the
one lifecycle of ARCHITECTURE §7.1 and the three routines that instantiate it,
through to a merged Pull Request and a reconciled `Done` Card.

M4 and M5 are ordering labels in the status ledger, not two subsystems. There is
**one** Consumer lifecycle. The Developer, Architect-documentation, and Quality
Assurance routines share one preflight, one authority model, one partial-failure
envelope, and one stopping contract. They differ in exactly two ways: whether the
routine claims, and which durable outcome it produces.

This design implements Appendix A decision 8 in full — deterministic acceptance
plus a non-agent merge controller — under the constraint that no agent seat may
directly merge (§4.5, invariant 5).

### Out of scope

Unchanged from the standing exclusions: audit database, schema migrations,
lifecycle hooks, automatic field provisioning, Codex packaging, multiple board
backends, autonomous agent spawning. Additionally out of scope here: shadow-mode
calibration against historical Pull Requests (a rollout activity, not a code
deliverable), and any runtime dependency on another plugin.

---

## 2. The one lifecycle

```
bind ─▶ preflight ─▶ [claim] ─▶ [worktree] ─▶ routine ─▶ verify ─▶ outcome ─▶ transition + handoff ─▶ stop
        (Status, Role,      remote-branch
         authority, PR)      compare-and-swap
```

| Routine | Precondition | Claims | Durable outcome | Lands at |
|---|---|---|---|---|
| Developer implement | `(Ready, dev)` | yes | one Pull Request | `(In Review, qa)` |
| Architect document | `(Ready, architect)` | yes | one documentation Pull Request | `(In Review, qa)` |
| QA verify | `(In Review, qa)` + linked Pull Request | no | verdict, then acceptance route | `(In Review, qa)` \| `(In Progress, dev)` \| `(In Review, human)` |

Merge and reconciliation are not a fourth routine. They are the deterministic
tail of the QA routine, executed by a controller that is not a seat.

Every routine obeys §7.5: exactly one durable outcome, never a silent
abandonment, never a second Card, never a merge chosen by the session.

---

## 3. The claim primitive

### 3.1 Verified git semantics

The claim is a remote branch compare-and-swap (§5.3, §9.7). The obvious
implementation is wrong, and this was established by direct test rather than by
reading documentation:

| Race case | `git push origin <sha>:<ref> --force-with-lease=<ref>:` | Verdict |
|---|---|---|
| Both claimants push the **same** base SHA | both exit `0` | **Two winners.** Git reports `Everything up-to-date` and never evaluates the lease |
| Each claimant pushes a **unique** commit | second is rejected `(stale info)`, exit `1` | Correct |
| Second claimant's commit is a **descendant** of the first | rejected `(stale info)`, exit `1` | Correct — the lease outranks fast-forward rules |

Two Consumers claiming the same Card normally branch from the same base commit,
so case 1 is the *common* case, not the exotic one. A naive implementation would
hand exclusive ownership to both sessions and report success to each.

**Normative rule.** A claim pushes a unique **empty claim commit**, never a bare
base SHA. Uniqueness is guaranteed by a session nonce, because two sessions on
one machine within the same clock second would otherwise produce an identical
commit object and collapse back into case 1.

```
claim: #<n> <title>

<!-- agent-teams:claim -->
card: <n>
seat: dev
base: <base-sha>
session: <uuid4>
claimed-at: <ISO 8601 UTC>
```

The empty-expect lease (`--force-with-lease=<ref>:` — trailing colon, empty
expected value) means *this ref must not already exist*. Combined with a unique
commit it is a true compare-and-swap.

### 3.2 Claim branch and worktree naming

Both derive deterministically from Card identity so any session can recompute
them without stored state:

```
branch:   claim/<n>-<slug>
worktree: <workspace>/claim-<n>-<slug>
slug:     title casefolded, non-alphanumeric runs -> "-", trimmed, max 40 chars
```

`<workspace>` defaults to `../.worktrees` relative to the repository root,
preserving the established convention. It is configurable and must resolve
outside the repository tree.

### 3.3 Mutation order and compensation

```
1. read Card; require (Ready, <seat>)                 refusal — no state written
2. policy.check_action("claim_card", seat)            refusal — no state written
3. verify declared dependencies are satisfied         refusal — no state written
4. compare-and-swap push of the claim commit          race lost — clean exit, nothing written
5. create the worktree from the claim ref             partial — recovery replays 5-6
6. transition Ready -> In Progress                    partial — recovery replays 6
```

Claim-first is deliberate and the failure modes are asymmetric. A won claim with
the Card still `Ready` is a Card that waits for a re-run. A Card moved to
`In Progress` by a session that then loses the race is a Card mutated by a
session that never owned it. The first is recoverable; the second is a
correctness violation.

Role does **not** change during claim. `Status` and `Role` are orthogonal (§9.2);
the Card is already owned by `dev`, so a claim is a transition and nothing else.

Race loss is failure class 1 — a normal structured outcome, exit code and
envelope distinct from an error, and explicitly **not retried** (§11.3).

---

## 4. New module: `git.py`

A peer of `github.py` in the adapter layer. Dependency direction is unchanged and
still strictly downward:

```
model      validated Role, Status, Card, Handoff, Verdict, Acceptance
policy     pure legality — transitions, authority, caps, seat actions,
           protected classification, acceptance evaluation
config     configuration and its validation
github     gh invocation, pagination, error classification
git        local Git and remote ref arbitration          <-- new
board      semantic board operations
workflows  transactions with partial-failure recovery
errors     AgentTeamsError
```

`git.py` owns four things and knows nothing about GitHub:

- canonical claim branch and worktree paths from Card identity;
- the compare-and-swap claim push of §3.1, returning a distinct `ClaimRaceLost`
  outcome rather than a generic failure;
- worktree create, resume, and enumerate;
- worktree removal **guards** — refuses to remove a worktree with uncommitted
  changes, untracked files, or commits absent from the merged Pull Request, and
  never recursively deletes an unresolved path (§9.7 rule 6).

Raw `git` output never escapes this module, mirroring the rule that raw GitHub
shapes never escape `github.py`.

---

## 5. Configuration additions

`config.py` gains five keys, each validated with the existing report-every-defect
behaviour:

| Key | Type | Default | Meaning |
|---|---|---|---|
| `workspace` | string | `"../.worktrees"` | Worktree root; must resolve outside the repository tree |
| `protected_paths` | object | §7.2 defaults | Category name → glob patterns |
| `required_checks` | list | `[]` | Check names that must conclude `SUCCESS` before eligibility |
| `merge_method` | string | `"squash"` | One of `squash`, `merge`, `rebase` |
| `claim_ttl_hours` | integer | `72` | Age past which triage flags a claim as stale |

`policy_version` is deliberately **not** configuration. It is a constant in
`policy.py`, because it identifies the code that made a decision.

**`protected_paths` may only grow.** A configuration that omits a default
category key is a validation error, not an implicit removal — §4.5 requires that
repository policy may add categories but must not silently remove one. Removing
protection is therefore a visible, deliberate edit that fails `doctor` loudly.

**Empty `required_checks` fails closed.** With no required checks configured,
`evaluate_acceptance` never returns `eligible`; it returns `protected_change`
with the reason *no required checks configured; automated acceptance cannot
establish a green baseline*. Without this, a repository lacking branch protection
would auto-merge immediately and the retest guarantee would be vacuous.

---

## 6. Contracts in `model.py`

### 6.1 `Verdict` — evidence, written by QA

The existing eight-field `Verdict` grows to the §9.6 contract. `VERDICT_MARKER`
already exists. Validation in `__post_init__` keeps "looks good" unconstructible:

```
verdict            pass | fail | blocked
card               Card and Issue identity
pull_request       URL and node identity
head_sha           exact reviewed Pull Request head
design_baseline    specification, architecture, and decision identifiers
review_dimensions  design, architecture, correctness, edge cases, security,
                   compatibility, cross-file, test strength
changed_files      complete enumerated set plus the bounded review units
design_conformance requirement/invariant -> implementation evidence -> test evidence
test_strength      line, branch, mutation, scenario, integration evidence
checks             commands, URLs, screenshots, observations, machine results
findings           reproducible expected-versus-actual plus supporting evidence
challenges         falsification attempt per material finding, and its outcome
blind_spots        unreviewed or uncertain areas
limitations        checks not performed, and why
next_role          qa | dev | human | architect | lead
```

### 6.2 `Acceptance` — decision, written by policy

A separate frozen dataclass. Keeping these distinct **in the type system**, not
merely in prose, is what makes "QA cannot select its own route" structural:
neither type is constructible from the other, and the acceptance route is not a
field QA can write.

```
acceptance      eligible | defect | protected_change
head_sha        exact head for which the decision is valid
policy_version  deterministic policy version
reasons         satisfied requirements, or exact refusal/escalation reasons
```

---

## 7. `policy.py` — pure additions

Still no network, still exhaustively assertable edge by edge. That property is
what caught two authority holes; the acceptance decision table is exactly the
kind of rule that must not be sampled.

### 7.1 Three new pure functions

```python
classify_protected(changed_paths, protected_paths) -> tuple[str, ...]
validate_verdict(verdict, live_head_sha, live_changed_files) -> list[str]
evaluate_acceptance(verdict, pr_facts, config) -> Acceptance
```

`evaluate_acceptance` receives already-fetched facts as plain data. It performs
no I/O, so every route can be asserted directly.

Glob matching needs `**`, which `fnmatch` does not support. A small
glob-to-regex translator lives in `policy.py` and is unit-tested on its own.

### 7.2 Default protected categories

From §4.5, expressed as repository-relative globs:

| Category | Patterns |
|---|---|
| `authority-and-policy` | `scripts/agent_teams/policy.py`, `scripts/agent_teams/model.py` |
| `acceptance-and-merge` | `scripts/agent_teams/git.py`, `scripts/agent_teams/workflows.py` |
| `github-workflows-and-credentials` | `.github/workflows/**`, `**/*credential*` |
| `dependencies-and-manifests` | `.claude-plugin/**`, `**/package.json`, `**/pyproject.toml`, `**/requirements*.txt` |
| `agent-instructions` | `skills/**`, `CLAUDE.md`, `AGENTS.md` |
| `security-boundaries` | `**/auth/**`, `**/*secret*` |
| `architecture-and-design` | `docs/ARCHITECTURE.md`, `docs/specs/**` |

### 7.3 The acceptance decision table

Two stages, because a refusal is not an acceptance value. `validate_verdict`
runs first and returns a list of problems; a non-empty list makes `accept` raise
a `PolicyError` before any mutation, so `evaluate_acceptance` is only ever
reached with evidence already known to be current and complete. That keeps its
return type honestly closed over the three acceptance values.

**Stage 1 — `validate_verdict`, refusal conditions.** Any of these refuses; no
board mutation occurs.

| # | Condition |
|---|---|
| 1 | `verdict.head_sha` ≠ live head — stale evidence |
| 2 | verdict schema invalid, a required dimension missing, `changed_files` ≠ live changed files, `blind_spots` non-empty, or `test_strength` is line-coverage-only |

Conditions 2 apply only to a `pass`. A `fail` or `blocked` verdict still requires
a current `head_sha` and a valid schema, but is not required to be complete —
that is the point of reporting one.

**Stage 2 — `evaluate_acceptance`, routing.** Evaluated in order; first match
wins.

| # | Condition | Result |
|---|---|---|
| 3 | `verdict == "fail"` | `defect` |
| 4 | `verdict == "blocked"` | `protected_change` |
| 5 | any changed path matches a protected category | `protected_change` |
| 6 | `required_checks` empty | `protected_change` |
| 7 | any required check not `SUCCESS` | `defect` |
| 8 | Pull Request not mergeable, or draft | `defect` |
| 9 | otherwise | `eligible` |

Stage 1 refuses rather than routes because stale or incomplete evidence is not a
code defect and must not push the Card into the Developer lane; the correct
recovery is QA re-running its review against the current head. A refusal is
failure class 1 and costs nothing (§11.6).

Row 6 is the fail-closed default of §5. Rows 3 and 4 implement §7.4 —
unresolved uncertainty becomes a protected change, and QA still never selects
its own route.

### 7.4 The merge floor

`merge_pull_request` — free-form direct merge of a caller-chosen Pull Request —
**stays in `HARD_FLOORS` and keeps refusing every agent seat.** Decision 8 does
not remove that invariant; it removes the *mandatory human review of every
passing delivery*.

The controller reaches merge through a different door that no seat can steer:
arming auto-merge is a consequence of `evaluate_acceptance` returning `eligible`,
not an action a seat may request. There is no command-line flag that merges a
Pull Request of the caller's choosing. `accept` takes one argument — an Issue
number — and every other input to the decision is read from live GitHub state.

This is the honest reading of "no agent seat directly merges" alongside
"deterministic policy merges only eligible reviewed heads".

---

## 8. `board.py` additions

Semantic operations only. No generic setter is introduced (§9.8).

| Operation | Purpose |
|---|---|
| `pull_request(number)` | linked Pull Request, head SHA, state, mergeability, draft flag |
| `changed_files(pr)` | complete changed-path enumeration for conformance and protection |
| `check_conclusions(pr)` | required-check names and conclusions |
| `link_pull_request(number, url)` | record the delivery link |
| `record_verdict(number, verdict)` | verdict comment carrying `VERDICT_MARKER` plus a fenced machine-readable block |
| `record_acceptance(number, acceptance)` | acceptance comment carrying `<!-- agent-teams:acceptance -->` |
| `arm_auto_merge(pr, method)` | `gh pr merge --auto --<method> --delete-branch` |
| `merge_state(pr)` | `state`, `mergedAt`, `mergeCommit` for reconciliation |

---

## 9. `workflows.py` — the `Consumer` class

Mirrors `Producer`. Every multi-step method returns the existing envelope on
partial failure and never claims a rollback that did not run (§11.2).

### 9.1 `claim(number, seat)`

Per §3.3. Returns claim branch, worktree path, base SHA, and resume instructions.
A race loss returns `{"ok": false, "race_lost": true, ...}` with no `partial` key
— nothing was written, so there is nothing to recover.

### 9.2 `submit(number, seat, title, body_file)`

```
1. require (In Progress, <seat>) and a claim owned by this worktree
2. acceptance criteria terminal: every item [x] or [!]<reason>; a bare [ ] refuses
3. Pull Request body contract §9.5: five sections, closing trailer, PR marker
4. push branch; create or update exactly one Pull Request
5. transition In Progress -> In Review
6. handoff dev -> qa with Pull Request URL, branch, tests, limitations
```

Steps 1–3 are refusals. Steps 4–6 are the multi-step prefix the envelope
reports. Step 4 is idempotent by branch: an existing Pull Request for the claim
branch is updated, never duplicated, preserving the one-Card-one-delivery
invariant.

### 9.3 `verdict(number, verdict_file, head_sha)`

Requires `(In Review, qa)` and a linked Pull Request. Refuses when `head_sha`
differs from the live head. Validates the schema, then posts the verdict comment.

**No transition and no handoff.** A verdict is evidence; the route comes from
`accept`. This separation is the structural half of "QA cannot select its own
route".

### 9.4 `accept(number)`

```
1. require (In Review, qa)
2. read the latest verdict comment and the live Pull Request facts
3. policy.validate_verdict(...)                        non-empty problems -> refuse, no mutation
4. policy.evaluate_acceptance(...)                     pure, no I/O
5. post the acceptance comment                         always, whatever the route
6. route:
   eligible          -> arm auto-merge; Card stays (In Review, qa) until merge confirms
   defect            -> In Review -> In Progress; handoff qa -> dev; same PR and branch
   protected_change  -> Status unchanged; handoff qa -> human; names the exact
                        protected file, decision, risk, or unresolved judgment
```

Arming auto-merge is a single GitHub call and cannot partial-fail midway. The
`defect` route is two mutations and carries the usual envelope.

GitHub, not this code, guarantees the reviewed head is retested against the
current base before merging, and disarms automatically if a new commit lands.
That is why auto-merge was chosen over an immediate merge: the stale-base problem
is delegated to the platform that owns the base.

### 9.5 `reconcile(number)`

```
1. require merge state MERGED           refuses otherwise; never assumes
2. transition In Review -> Done
3. handoff qa -> lead                   Done is owned by lead; no automation seat is invented
4. remove the worktree and local branch  only after merge is confirmed, guards per §4
```

---

## 10. Command-line surface

Six new commands on the existing stable entry point. No existing command's
syntax or envelope changes.

```
claim ISSUE --acting-role dev|architect
submit-pr ISSUE --title TEXT --body-file PATH
verdict ISSUE --verdict pass|fail|blocked --evidence-file PATH --head-sha SHA
accept ISSUE
reconcile-done ISSUE
worktree-status [ISSUE]
```

`worktree-status` is read-only and enumerates claims, worktrees, ages, and
divergence — the input triage needs for stale-claim detection, which has been
waiting on claims existing.

---

## 11. Skills

Two new skill directories, one router update. Both follow the established
conventions: lowercase verb-led names, frontmatter `name` plus a trigger-rich
`description`, orchestration and refusal boundaries only, every mutation through
`scripts/producer_board.py`.

### 11.1 `skills/consuming-card/`

Developer and Architect-documentation routines. `SKILL.md` plus
`references/claim-and-worktree.md`, `references/tdd-discipline.md`,
`references/pr-contract.md`.

Derived from board-superpowers `consuming-card` stages 1–4 and
`enforcing-pr-contract`, plus superpowers `test-driven-development`,
`verification-before-completion`, `using-git-worktrees`, and
`finishing-a-development-branch`.

### 11.2 `skills/verifying-delivery/`

QA verification. `SKILL.md` plus `references/review-dimensions.md`,
`references/evidence-and-challenge.md`, `references/verdict-schema.md`.

Derived from gstack `/review` — confidence calibration 1–10, the **pre-emit
verification gate** (a finding must quote the code lines motivating it or it is
suppressed), specialist dispatch by dimension with deduplication and
multi-specialist confirmation, conditional red-team pass on large diffs or when
critical findings exist, scope-drift detection, and the plan-completion audit
with `DONE` / `PARTIAL` / `NOT DONE` / `CHANGED` / `UNVERIFIABLE` — plus gstack
`/qa` screenshot-evidence discipline for user-interface Cards, superpowers
`requesting-code-review`, and board-superpowers `reviewing-pr-queue`.

### 11.3 Rejections

Recorded per item in `docs/skill_migration.md` and the audit, in the established
disposition format.

| Rejected | Reason |
|---|---|
| gstack `/review` **fix-first triage** (auto-fix + batched ASK) | §7.4 forbids QA touching production code. Auto-fixing findings collapses independent verification — the single most important rejection in this migration |
| gstack telemetry, `cross_project_learnings`, artifact sync | Out-of-band data flow; no consuming repository opts into it by installing a board plugin |
| gstack health score / PR quality score as authority | Useful as reported evidence, never as an acceptance input. `evaluate_acceptance` reads the decision table, not a score |
| board-superpowers audit rows, `classifying-actions` autonomy matrix | `policy.py` refuses in code before any GitHub call — stronger than prose governance |
| board-superpowers Mode-2 subagent callback protocol | We render kickoff prompts and stop; no Producer spawns a Consumer |
| Every `superpowers:` and `gstack:` runtime invocation | Invariant 10. A grep for those prefixes across `skills/` must return nothing |
| board-superpowers post-merge webhook assumption | Our `reconcile-done` confirms merge explicitly rather than trusting a Status flip to arrive |

### 11.4 Router update

`skills/using-agent-teams/SKILL.md` gains the two Consumer routes and the
`[board-card:#N]` binding. Unchanged: the router may never infer `human`.

### 11.5 Attribution

`ATTRIBUTION.md`'s two `(planned)` rows — superpowers and gstack — become real
derivation records. Each derived file carries a header comment naming its source.
gstack is MIT-licensed, confirmed at the source repository.

---

## 12. Failure handling

Failure classes are unchanged (§11.6). What each new operation produces:

| Situation | Class | Durable outcome |
|---|---|---|
| Claim race lost | 1 | Nothing written; distinct `race_lost` result; **never retried** |
| Wrong `(Status, Role)`, unmet dependency, non-terminal acceptance criteria, bare `[ ]` | 1 | Nothing written |
| Stale verdict head, invalid pass | 1 | Nothing written; names exactly what is missing |
| Worktree created, transition failed | 2 | Envelope with `completed` prefix and replay recipe |
| Pull Request opened, handoff failed | 2 | Envelope; recovery replays the handoff, never the Pull Request |
| Verdict `fail`, checks red, unmergeable | 3 | `(In Progress, dev)`, same Card, claim, branch, Pull Request |
| Verdict `blocked`, protected change | 3 | `(In Review, human)` with the exact escalation reason |
| Technical ambiguity during implementation | 4 | `(Blocked, architect)`, claim and worktree preserved |
| Handoff cap breached | 4 | `(Blocked, lead)` |

Creation steps are never replayed wholesale (§11.2): recovery for `submit`
replays the transition or handoff, never the Pull Request creation.

---

## 13. Testing

Standard library only, no network, no real Project.

**Claim exclusivity against real git.** A `tmpdir` bare repository as origin and
two clones racing the compare-and-swap. This exercises actual git ref semantics —
which is the only reason the two-winners hazard of §3.1 was found — and remains
hermetic, because a local bare repository needs no network.

**`fake_gh.py`** gains Pull Request fixtures: `pr view` (head SHA, state,
mergeable, draft), `pr create`, `pr merge --auto`, `pr checks`, and changed-file
listing.

**`policy` decision table** asserted row by row: every acceptance route, every
protected category, every invalid-pass condition, the empty-`required_checks`
fail-closed default, and the glob translator on its own.

**Partial-failure boundaries** for each new multi-step mutation.

Current suite is 145. Expect roughly 230.

**Test strength applies to this work too.** The QA standard this design
implements says line execution is not proof of behaviour, so the new tests carry
branch and scenario assertions and explicit negative paths — including the
two-winners case, which a coverage-only suite would have reported as fully
covered while asserting the wrong outcome.

---

## 14. Assumptions and live-verification gaps

Stated rather than hidden, because none can be closed until `gh auth login` runs:

1. **Auto-merge requires branch protection with required checks.** Without it,
   `--auto` merges immediately and the retest guarantee is vacuous. The
   fail-closed empty-`required_checks` rule (§5) prevents silent reliance on this,
   but the disposable repository must configure protection before the merge path
   means anything.
2. **Auto-merge must be enabled at the repository level**; otherwise
   `gh pr merge --auto` errors. `doctor` should check this and report it with the
   other preflight validations.
3. **Pull Request JSON shapes are assumed**, exactly as the board shapes already
   are. `pr view`, `pr checks`, and changed-file listing must be confirmed against
   a real `gh` before the acceptance path is trusted.
4. **No merge, verdict, or acceptance path has ever run live.** This design is
   testable hermetically end to end except for the final GitHub merge itself.

---

## 15. Documentation to update in the same change

- `docs/ARCHITECTURE.md` §10.1 component table — Consumer skills, git claim
  service, and Pull Request contract service move from **designed** to **built**;
  §9.8 operation table likewise.
- `docs/IMPLEMENTATION_PLAN.md` — the sole status ledger; M4 and M5 rows.
- `docs/USAGE.md` — the daily loop gains claim, submit, verify, accept, reconcile.
- `README.md` — CLI reference for the six new commands and the five config keys.
- `ATTRIBUTION.md`, `docs/skill_migration.md`, `docs/skill_migration_audit.md`.
- `CLAUDE_TESTING.md` is already stale for the seven-skill layout; it is corrected
  here rather than left to rot further.
