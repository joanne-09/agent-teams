# Using agent-teams

This guide describes the automated operating path. The normal interface is
plain language; command examples show the governed operations underneath it.

## Mental model

```text
request
  -> analyst clarification
  -> architect publishes specification directly by default
  -> optional manual spec mode: HUMAN merges spec PR, architect resumes
  -> HUMAN: Ready decision
  -> coordinator spawns dev worker
  -> coordinator spawns QA worker
  -> defect: coordinator repeats dev -> QA on the same delivery
  -> eligible: auto-merge by default OR user merge in manual mode
  -> confirmed merge: automatic reconciliation -> Done
  -> protected/ambiguous only: HUMAN final QA exception
```

GitHub state, not conversations or child responses, is authoritative.

## Setup

From the repository whose work will be managed:

```powershell
python C:\path\to\agent-teams\scripts\producer_board.py init `
  --repo OWNER/REPO --project-owner OWNER --project-number 1 `
  --required-check build --required-check test
python C:\path\to\agent-teams\scripts\producer_board.py doctor
claude --plugin-dir C:\path\to\agent-teams
```

See [CONFIGURATION.md](./CONFIGURATION.md) for the complete configuration
reference and merge-mode combinations.

The Project needs all six Status and Role values documented in the README. For
deterministic acceptance, configure required CI checks and pass those exact
names through repeatable `--required-check`. In the default `automatic`
implementation merge mode, unattended delivery also requires repository
auto-merge and branch protection; `doctor` reports these missing
preconditions. `code_pr_merge_mode: manual` does
not require GitHub auto-merge.

## Daily operation

### Orient

Say “brief me” or “what is next?”. The report leads with the two human queues,
then active, blocked, Ready, and QA work.
In manual mode, `next-actions` adds an eligible-merge gate for the user.


### Intake and specification

State a requirement normally. The analyst researches and clarifies until the
outcome and acceptance criteria are testable, then hands one Card to architect.

The architect writes one Markdown specification below `docs/` in the current
checkout and publishes it through the configured route:

```bash
producer_board.py publish-spec N --path docs/specs/card-N-name.md
```

This command:

- requires `(Backlog, architect)`;
- refuses a detached HEAD and unrelated checkout changes;
- publishes only the requested `docs/**/*.md` file;
- records the path and exact commit on the Card.

The modes are:

- `"spec_pr_merge_mode": "direct"` (default): commit and push the current
  branch, then continue shaping. The user only makes the later Card readiness
  edit.
- `"spec_pr_merge_mode": "manual"`: create a deterministic spec branch and Pull
  Request, then stop. The user merges that Pull Request. The coordinator runs
  `finalize-spec-merge`, verifies the exact reviewed head and base, syncs the
  base branch, records the durable commit, and starts architect shaping again.

The architect never creates the spec branch or Pull Request manually;
`publish-spec` owns either route.

The architect either hands a single Card to `(Backlog, human)` or decomposes it:

```bash
producer_board.py decompose N --children children.json
```

Each implementation child waits at `(Backlog, human)` with the durable spec
reference. A completed decomposition is marked durably so the coordinator does
not respawn architecture for the parent.


### Optional human gate: specification merge

This gate exists only with `"spec_pr_merge_mode": "manual"`. After
`publish-spec`, `next-actions` returns a `spec_merge` human gate containing
the exact Pull Request. Merge it in GitHub; do not move the Card or run the
finalizer yourself. The coordinator confirms the exact recorded head is merged,
runs `finalize-spec-merge`, and resumes the architect.

This setting is independent of `code_pr_merge_mode`, which controls implementation
Pull Requests after QA.

### Human gate 1: readiness

Review the Card and recorded specification, then move its Project Status from
`Backlog` to `Ready`. That Status edit is the complete human decision.

On the next coordinator loop, `finalize-readiness` loads the Card's structured
spec record, verifies the path is still tracked at the exact recorded commit,
and hands ownership to development automatically. If the spec changed,
architect republishes it first. `promote N` remains an optional CLI
convenience that performs the Status change and handoff together.

### Run the team

Say:

```text
start the team
run the workflow
continue the team
```

The current session invokes `dispatching-work`. It repeatedly runs:

```bash
producer_board.py next-actions
```

For each `kind: spawn`, it starts the foreground bounded seat subagent named
in the action's `agent` field (`agent-teams:dev-worker`,
`agent-teams:qa-worker`, `agent-teams:architect-worker`,
`agent-teams:analyst-worker`, or `agent-teams:lead-worker`) and supplies the
returned one-Card prompt directly. You do not open another session or paste anything.

The worker has the Skill tool but no `skills:` preload list. Every spawn
action carries exactly one `skill: agent-teams:<routine>` value and matching
prompt marker. The worker invokes that skill on demand; unrelated intake,
architecture, development, triage, and QA bodies never enter that child
context.

The coordinator supports these stages:

| Live state | Automatic action |
|---|---|
| `(Backlog, analyst)` | Load only `clarifying-card`; resolve the existing Card |
| `(Backlog, architect)` | Publish/finalize the configured spec route, then shape |
| `(Ready, human)` | Validate the spec record and hand to dev automatically |
| `(Ready, dev|architect)` | Spawn claim and delivery |
| `(In Progress, dev|architect)` | Materialise and resume the durable claim |
| `(Blocked, any role)` | Spawn one bounded lead-triage stage |
| pending checks/mergeability | Monitor and re-read; never route as a defect |
| `(In Review, qa)` | Spawn independent QA and deterministic acceptance |
| eligible exact head queued | Monitor GitHub auto-merge in this session |
| pending manual specification PR | Ask the user to merge, then finalize it |
| eligible exact head in `manual` mode | Ask the user to merge the linked PR |
| eligible exact head confirmed merged | Run `reconcile-done` itself |
| stale protected exception head | Return automatically to QA for fresh evidence |

Each worker owns one Card and one stage, persists to GitHub, and stops. It cannot
spawn grandchildren. Different Cards may run concurrently below the WIP limit;
stages for the same Card are sequential.

After every child, the coordinator rereads GitHub. `next-actions` includes the
configured `recovery_policy` and exact capped exponential-backoff delay
sequence. If an identical stage still does not change durable state after those
retries, the coordinator reports the last error, attempts, Card, routine, and
durable state, then stops that action instead of spawning forever.

### QA outcomes

| Route | Result | Human work |
|---|---|---|
| `eligible` + `automatic` | GitHub auto-merge, then automatic `(Done, lead)` reconciliation | None |
| `eligible` + `manual` | Wait for the user to merge the linked PR, then reconcile automatically | Merge the PR |
| `defect` | `(In Progress, dev)` on the same branch/worktree/PR, then QA again | None |
| `protected_change` | `(In Review, human)` with exact files/reason | Final decision |

Empty `required_checks` deliberately makes a pass a protected exception rather
than silently merging without a CI baseline.

### Optional human gate: eligible manual merge

Set `"code_pr_merge_mode": "manual"` when the user wants to merge routine eligible
Pull Requests. After deterministic acceptance, `next-actions` returns a
`manual_merge` human gate with the exact Pull Request. Merge it in GitHub; do
not change the Card or run `reconcile-done` yourself. The coordinator confirms
the Pull Request is `MERGED`, then reconciles the Card to `(Done, lead)`.

### Human gate 2: QA exception

Only protected or genuinely ambiguous changes reach this gate. Review the
Card's verdict, acceptance record, exact head, reasons, and PR. If accepted:

```bash
producer_board.py approve-exception N
```

This is one human command. It refuses every agent seat, derives the PR from the
Card, verifies the head has not changed since the exception record, merges, and
reconciles to `(Done, lead)`. There is no separate manual `gh pr merge` plus
`reconcile-done` sequence.

## Recovery

- Retry count and backoff live under `recovery` in
  `.agent-teams/config.json`; `monitor_poll_seconds` controls pending-check and
  merge observation frequency.
- Classified network, server, and rate-limit failures retry only for safe
  GitHub reads. Authentication, permission, protocol, and policy errors stop
  immediately.
- GitHub mutations are never blindly replayed after an ambiguous failure.
- A lost claim race is a clean stop. Another worker owns the Card.
- A partial result lists completed steps; the coordinator runs missing steps.
- `reconcile-done` remains an idempotent recovery command, but the coordinator
  normally invokes it automatically.
- Dirty worktrees are never force-removed automatically.
- Interrupted claims are resumed from the Card-owned remote branch; ending a
  worker session never creates another human gate.
- Blocked workers write what they tried, what they need, and where work remains;
  they never wait synchronously for a human inside a child context.

## Commands

```text
producer_board.py doctor
producer_board.py bootstrap --role ROLE
producer_board.py brief [--format text|json]
producer_board.py next-actions [ISSUE]
producer_board.py intake --title T (--body B | --body-file F)
producer_board.py clarify ISSUE (--note N | --note-file F)
producer_board.py publish-spec ISSUE --path docs/...md
producer_board.py decompose PARENT --children F
producer_board.py promote ISSUE
producer_board.py finalize-spec-merge ISSUE
producer_board.py claim ISSUE --acting-role dev|architect
producer_board.py submit-pr ISSUE --title T --body-file F
producer_board.py verdict ISSUE --evidence-file F
producer_board.py accept ISSUE
producer_board.py refresh-verification ISSUE
producer_board.py reconcile-done ISSUE
producer_board.py approve-exception ISSUE
producer_board.py worktree-status [ISSUE]
```

`next-actions` is read-only. `accept`, `refresh-verification`, and
`approve-exception` take only an Issue number; none accepts a caller-chosen PR
or route. Every mutation must return `"ok": true` before it is reported as
successful.

`--acting-role` is a claim, not an authority. The seat a command actually acts
as is resolved per process: `AGENT_TEAMS_ACTING_ROLE` (set for spawned
workers) wins over the flag, and inside any Claude Code session a command that
claims or defaults to `human` is refused. Run `promote`, `approve-exception`,
and `release-claim` from your own terminal; from the lead's session they are
refused by design.

Completion has one owner. A delivery Pull Request names its Card as
`Card: #<issue>` and must not use `Closes`/`Fixes`/`Resolves`; `reconcile`
sets Done, hands the Card to `lead`, and then closes the Issue itself.

## Deliberate exclusions

There is no daemon, audit database, automatic Project-field provisioning,
multi-board abstraction, or runtime dependency on another plugin. Subagents are
bounded to the current coordinating session; a later run resumes from GitHub.
