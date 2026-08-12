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

There are only two human boundaries:

1. **Readiness:** after reviewing the committed specification, move the Card
   Status from `Backlog` to `Ready`. The coordinator validates the exact
   spec commit and hands the Card to dev automatically.
2. **QA exception:** only when QA or deterministic policy identifies a protected
   or genuinely ambiguous change, review it and optionally run
   `approve-exception N`.

Routine passing deliveries use deterministic acceptance, GitHub auto-merge,
and automatic Done reconciliation. Defects loop from QA back to development on
the same Card, branch, worktree, and Pull Request.

## Direct specifications

Specifications are Markdown files below `docs/` committed and pushed directly
on the consuming repository's current branch:

```text
producer_board.py publish-spec 12 --path docs/specs/card-12-export.md
```

The command creates no branch, worktree, or Pull Request. It refuses unrelated
checkout changes, stages only the requested specification, and records its exact
path and commit on the Card. The human later runs only:

```text
producer_board.py promote 12
```

`promote` retrieves and verifies the recorded Git artifact; the human does not
merge or paste a specification reference.

## Skills and worker

| Skill | Purpose |
|---|---|
| `using-agent-teams` | Bootstrap, orientation, and plain-language routing |
| `intaking-requirement` | Clarify one requirement and hand it to architecture |
| `authoring-spec` | Write a direct Git spec and shape implementation Cards |
| `briefing-board` | Whole-team state and human gates |
| `triaging-board` | Diagnose blocked and stale work |
| `dispatching-work` | Run the current-session subagent orchestration loop |
| `inspecting-queue` | Read-only QA queue inspection |
| `consuming-card` | Claim and deliver one Card through one Pull Request |
| `verifying-delivery` | Independently review one exact PR head and accept it |

`agents/agent-teams-worker.md` is the flat, bounded child used by the
coordinator. It handles exactly one Card and one stage and cannot spawn a child
of its own.

## Requirements

- Claude Code 2.1+
- Python 3.9+; standard library only
- Git and authenticated GitHub CLI (`gh`)
- GitHub Project fields:

```text
Status: Backlog, Ready, In Progress, Blocked, In Review, Done
Role:   analyst, architect, dev, qa, lead, human
```

For routine auto-merge, also configure repository auto-merge, branch protection,
at least one required CI check, and matching `required_checks` in
`.agent-teams/config.json`. Empty checks fail closed into the human exception
lane.

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

| Key | Default | Meaning |
|---|---|---|
| `wip_limit` | `5` | Warning threshold for In Progress + In Review |
| `workspace` | `../.worktrees` | Claim worktrees, outside the repository |
| `required_checks` | `[]` | Checks required for eligible auto-merge; empty fails closed |
| `merge_method` | `squash` | Eligible and human-exception merge method |
| `protected_paths` | seven categories | Changes requiring human QA review; defaults may only grow |
| `claim_ttl_hours` | `72` | Stale-claim observation threshold |
| `handoff_cap` | `6` | Maximum handoffs before lead recovery |

Older configs may contain `spec_completion`; it is accepted for compatibility
but ignored. Specifications now always use the direct tracked-Git contract.

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
