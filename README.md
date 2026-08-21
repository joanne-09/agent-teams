# agent-teams

`agent-teams` is a Claude Code plugin that runs an AI engineering workflow over
one GitHub Project. The Project is the durable routing plane; Issues carry work
and handoffs, Git branches carry exclusive implementation claims, and Pull
Requests carry deliveries and QA evidence.

The coordinating session can run the workflow itself. It reads deterministic
`next-actions`, spawns one bounded subagent per Card stage, waits for durable
GitHub state, and continues through implementation, QA, correction, merge, and
Done. A person never has to copy a kickoff prompt into another session.

## Human attention

There is one mandatory human boundary, one optional specification-merge
boundary, and one conditional QA exception boundary. The optional boundary
exists only when `spec_merge_mode` is `manual`:

1. **Specification merge (optional):** merge the generated specification Pull
   Request. The coordinator verifies it and resumes architect shaping.
2. **Readiness:** after reviewing the committed specification, move the Card
   Status from `Backlog` to `Ready`. The coordinator validates the exact
   spec commit and hands the Card to dev automatically.
3. **QA exception:** only when QA or deterministic policy identifies a protected
   or genuinely ambiguous change, review it and optionally run
   `approve-exception N`.

By default, specifications publish directly, routine passing deliveries use
deterministic acceptance and GitHub auto-merge, and Done reconciliation is
automatic, so readiness is the only routine Card edit a person makes. Set
`merge_mode` to `manual` when the user should merge eligible implementation
Pull Requests themselves; the coordinator then
waits for the confirmed merge and still reconciles Done automatically. Defects
loop from QA back to development on the same Card, branch, worktree, and Pull
Request.

## Specification publication

Specifications are Markdown files below `docs/`. The default
`spec_merge_mode: direct` commits and pushes the requested file directly on
the consuming repository's current branch:

```text
producer_board.py publish-spec 12 --path docs/specs/card-12-export.md
```

The command refuses unrelated checkout changes, publishes only the requested
specification, and records its exact path and commit on the Card. With
`spec_merge_mode: manual`, the same command creates a deterministic
specification branch and Pull Request instead. The user merges that Pull
Request; the coordinator verifies the exact head, synchronizes the base branch,
records the durable base commit, and resumes architect shaping.

After shaping, the architect hands the Card to the human. The human changes
only the Project Status from `Backlog` to `Ready`; the coordinator verifies
the recorded Git artifact and hands the Card to dev automatically.

## Skills and worker

| Skill | Purpose |
|---|---|
| `using-agent-teams` | Bootstrap, orientation, and plain-language routing |
| `intaking-requirement` | Clarify one requirement and hand it to architecture |
| `clarifying-card` | Resolve one question on an existing returned Card |
| `authoring-spec` | Publish a spec by the configured route and shape Cards |
| `briefing-board` | Whole-team state and human gates |
| `triaging-board` | Diagnose blocked and stale work |
| `dispatching-work` | Run the current-session subagent orchestration loop |
| `inspecting-queue` | Read-only QA queue inspection |
| `consuming-card` | Claim and deliver one Card through one Pull Request |
| `verifying-delivery` | Independently review one exact PR head and accept it |

`agents/<seat>-worker.md` (architect, analyst, dev, qa, lead) are the flat,
bounded children used by the coordinator. They share one contract and one
tool set; the seat-specific names exist so the Claude Code agent list and any
external monitor show which role each spawned worker holds. Each
`next-actions` spawn names the seat's agent and one qualified skill; the
worker preloads no workflow skill, invokes only that skill through Claude
Code's Skill tool, and any deeper reference loads only when its condition
applies. A worker handles exactly one Card and one stage and cannot spawn a
child of its own.

## Reuse plus agent-teams architecture

This plugin does not replace good engineering disciplines with one monolithic
"team skill." It keeps them as focused, attributed procedures and adds a small
governance/orchestration layer:

| Reused discipline | Source | agent-teams addition |
|---|---|---|
| Requirement shaping, board triage, vertical decomposition | board-superpowers | `(Status, Role)` routing and the Ready gate |
| Clarification, TDD, worktree isolation, evidence before claims | superpowers | durable claim/resume and one-Card execution |
| Review passes, challenge/falsification, browser evidence | gstack | structured exact-head verdict and deterministic acceptance |

The source procedures are adapted locally and attributed in
`ATTRIBUTION.md`, so the plugin remains usable without requiring three other
plugins to be installed. The adaptation is deliberately narrow: board
mutations go through `producer_board.py`, agent seats cannot cross the human
gate, and QA evidence cannot choose its own merge route.

## Requirements

- Claude Code 2.1+
- Python 3.9+; standard library only
- Git and authenticated GitHub CLI (`gh`)
- GitHub Project fields:

```text
Status: Backlog, Ready, In Progress, Blocked, In Review, Done
Role:   analyst, architect, dev, qa, lead, human
```

Configure at least one required CI check and matching `required_checks` in
`.agent-teams/config.json`; empty checks fail closed into the protected-change
exception lane. Automatic mode also requires repository auto-merge and branch
protection. Manual mode does not require GitHub auto-merge because the user
merges eligible Pull Requests.

## Setup

From a consuming repository:

```powershell
python "C:\path\to\agent-teams\scripts\producer_board.py" init `
  --repo OWNER/REPO `
  --project-owner OWNER `
  --project-number 1 `
  --required-check build --required-check test

python "C:\path\to\agent-teams\scripts\producer_board.py" doctor
claude --plugin-dir "C:\path\to\agent-teams"
```

Then speak normally:

```text
brief me
we need CSV export
start the team
continue card 12
```

“Start the team” invokes `dispatching-work`; the current session spawns the
workers. It does not print a prompt for you to carry elsewhere.

## Configuration

See [docs/CONFIGURATION.md](./docs/CONFIGURATION.md) for every supported key,
validation rule, live-dashboard update contract, interaction, and a complete
JSON example.

| Key | Default | Meaning |
|---|---|---|
| `wip_limit` | `5` | Warning threshold for In Progress + In Review |
| `handoff_cap` | `6` | Maximum handoffs before lead recovery |
| `workspace` | `../.worktrees` | Claim worktrees, outside the repository |
| `required_checks` | `[]` | Checks required for eligible acceptance; empty fails closed |
| `merge_mode` | `automatic` | `automatic` arms eligible merges; `manual` waits for the user to merge |
| `merge_method` | `squash` | Automatic eligible and human-exception command merge method |
| `spec_merge_mode` | `direct` | `direct` publishes to the current branch; `manual` waits for the user to merge a spec PR |
| `protected_paths` | seven categories | Changes requiring human QA review; defaults may only grow |
| `claim_ttl_hours` | `72` | Stale-claim observation threshold |
| `monitor_poll_seconds` | `30` | Delay between pending-check and auto-merge observations |
| `board_page_limit` | `100` | Initial Project item read size |
| `board_max_items` | `2000` | Refuse rather than silently truncate beyond this ceiling |
| `recovery.max_retries` | `1` | Retries after the initial attempt; `0` disables retries |
| `recovery.initial_backoff_seconds` | `5` | Wait before the first retry |
| `recovery.backoff_multiplier` | `2` | Multiplier that lowers retry frequency after each failure |
| `recovery.max_backoff_seconds` | `60` | Upper bound for one retry delay |

Operational excerpt from the generated config:

```json
{
  "merge_mode": "automatic",
  "merge_method": "squash",
  "spec_merge_mode": "direct",
  "monitor_poll_seconds": 30,
  "board_page_limit": 100,
  "board_max_items": 2000,
  "recovery": {
    "max_retries": 1,
    "initial_backoff_seconds": 5,
    "backoff_multiplier": 2,
    "max_backoff_seconds": 60
  }
}
```

The recovery schedule is used by the coordinator and by transient GitHub
reads. Authentication, permission, protocol, and policy errors stop
immediately. GitHub mutations are never blindly replayed because a command can
succeed remotely even when its response is lost; partial mutations continue
through their structured recovery instructions instead.

Older configs may contain `spec_completion`; it is accepted for compatibility
but ignored. Use `spec_merge_mode` to choose the supported publication
contract.

## CLI

```text
producer_board.py doctor
producer_board.py bootstrap --role ROLE
producer_board.py brief [--format text|json]
producer_board.py next-actions [ISSUE]
producer_board.py intake --title TITLE (--body BODY | --body-file FILE)
producer_board.py clarify ISSUE (--note NOTE | --note-file FILE)
producer_board.py publish-spec ISSUE --path docs/...md
producer_board.py decompose PARENT --children FILE.json
producer_board.py promote ISSUE
producer_board.py finalize-spec-merge ISSUE
producer_board.py claim ISSUE --acting-role dev|architect
producer_board.py submit-pr ISSUE --title TITLE --body-file FILE
producer_board.py verdict ISSUE --evidence-file FILE
producer_board.py accept ISSUE
producer_board.py refresh-verification ISSUE
producer_board.py reconcile-done ISSUE
producer_board.py approve-exception ISSUE
producer_board.py worktree-status [ISSUE]
```

`next-actions` is read-only and returns `actions`, `human_gates`, and `waiting`.
The orchestration skill spawns `kind: spawn` actions, executes deterministic
`kind: controller` and `kind: reconcile` actions, waits and rechecks
`kind: monitor`, rereads GitHub, and stops only when no automatic action
remains.

Interrupted In Progress work resumes from its durable Card branch. Blocked Cards
receive one bounded lead-triage subagent; neither path adds a human gate.

`accept` takes only an Issue number. QA cannot choose its route, and no command
accepts a caller-selected Pull Request to merge. `approve-exception` is
human-only and derives the exact reviewed head from durable Card evidence.

Every command emits one JSON envelope. Never treat a mutation as successful
without `"ok": true`; partial results name their completed prefix and precise
fix-forward recovery.

See [docs/USAGE.md](./docs/USAGE.md) for the operational flow and
[docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) for authority and invariants.
