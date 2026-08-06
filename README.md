# agent-teams

This repository is the `agent-teams` Claude Code plugin: the Producer side of
an artificial intelligence engineering board, running over a GitHub Project.

A **Producer** session shapes work — it creates, refines, routes, prioritises,
and unblocks Cards. A **Consumer** session resolves exactly one Card. This
plugin implements the Producer half completely; Consumer execution
(implementation and independent verification) is a separate, later milestone.

The durable board is a GitHub Project. Cards are GitHub Issues carrying two
orthogonal single-select fields: `Status` (where the work is) and `Role`
(whose turn it is).

**New here? Read [`docs/USAGE.md`](./docs/USAGE.md)** — setup, the daily loop,
the readiness gate, protected-change exceptions, and how to read what comes
back. This README is the reference; that is the walkthrough.

The human holds the mandatory **`Backlog -> Ready`** gate and reviews protected
or ambiguous changes. The target QA workflow sends eligible Pull Requests to a
deterministic merge controller; no agent seat can directly merge. See
[`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) Appendix A, decisions 4-8.

agent-teams calls **no other plugin**. `superpowers` and `gstack` are
referenced by name as recommended disciplines; nothing in `skills/` or
`scripts/` invokes them, and correctness never depends on either being
installed.

## The nine workflows

| Skill | Seat | What it does |
|---|---|---|
| `using-agent-teams` | any | Read-only session bootstrap, then route by seat |
| `intaking-requirement` | analyst | Shape a requirement into one Backlog Card |
| `authoring-spec` | architect | Specify, then promote to Ready or decompose |
| `briefing-board` | lead | Whole-team flow, work in progress, merge queue |
| `triaging-board` | lead | Blocked work, grouped by who owes a decision |
| `dispatching-work` | lead | Render deterministic kickoff prompts |
| `inspecting-queue` | qa | Order the verification queue (no verdicts) |

The seven above are Producer-shaped: they shape the board and never write
implementation code. Two are Consumer-shaped and resolve exactly one Card:

| Skill | Seat | What it does |
|---|---|---|
| `consuming-card` | dev, architect | Claim one Card, implement it in an isolated worktree, open one Pull Request |
| `verifying-delivery` | qa | Review one delivery, publish evidence, run deterministic acceptance |

## What is intentionally absent

No audit database, no schema migrations, no lifecycle hook, no automatic field
provisioning, no Codex package, no multi-backend adapter, and no autonomous
agent spawning. The plugin renders kickoff prompts; a human or an external
carrier starts sessions.

No seat can directly merge. The delivered Producer policy still enforces the
older human-only merge floor; M5 will replace it atomically with deterministic
acceptance plus a human protected-change exception. Until M5 is implemented,
the automated merge path described in the architecture is not available.

## Requirements

- Claude Code 2.1+
- Python 3.9+ (standard library only — no third-party dependencies)
- GitHub CLI (`gh`), authenticated with repository and Project access
- a GitHub Project with single-select `Status` and `Role` fields

Required options — all six of each, validated by `doctor`:

```text
Status: Backlog, Ready, In Progress, Blocked, In Review, Done
Role:   analyst, architect, dev, qa, lead, human
```

## Configure a consuming repository

```powershell
python "C:\path\to\this-plugin\scripts\producer_board.py" init `
  --repo OWNER/REPO `
  --project-owner OWNER `
  --project-number 1
```

This writes `.agent-teams/config.json` in the consuming repository. It holds
board coordinates and a few tuning knobs, never credentials.

```powershell
python "C:\path\to\this-plugin\scripts\producer_board.py" doctor
```

`doctor` validates authentication, Project access, both fields, and all twelve
options — and reports every defect it finds in one response rather than the
first.

It also reports two **acceptance preconditions** as non-fatal
`acceptance_problems`: whether the repository has auto-merge enabled, and
whether `required_checks` is configured. Neither is required for Producer work,
but without both the automated merge path either fails or is vacuous — with no
required checks, `--auto` merges immediately and nothing is retested against
the current base. `doctor` explains them; it never creates them.

## Tuning

| Key | Default | Meaning |
|---|---|---|
| `wip_limit` | 5 | Cards in `In Progress` + `In Review` before the briefing warns |
| `workspace` | `../.worktrees` | Where claim worktrees live. Must resolve outside the repository tree |
| `required_checks` | `[]` | Checks that must be green before a delivery is eligible. **Empty fails closed: nothing is ever eligible**, and every pass routes to the human lane |
| `merge_method` | `squash` | How the controller closes an eligible Pull Request |
| `protected_paths` | 7 categories | Globs whose change forces human review. Policy may add categories; emptying a default one is a configuration error |
| `claim_ttl_hours` | 72 | Age past which `worktree-status` flags a claim as stale |
| `handoff_cap` | 6 | Handoffs before a Card is routed to `(Blocked, lead)` |
| `spec_completion` | `merged` | Whether Ready requires a merged or merely opened specification |

`spec_completion=merged` means implementation becomes Ready only after the
specification is durable on the target branch. Set it to `opened` only if this
repository genuinely accepts building against an unmerged specification.

## Test as a development plugin

```powershell
claude --plugin-dir "C:\path\to\this-plugin"
```

Inside Claude:

```text
[role:lead] morning briefing
[role:analyst] Intake this requirement: improve the setup documentation.
[role:architect] Make issue #12 ready against docs/architecture/0007-parser.md
[role:qa] show the verification queue
```

Use a disposable repository and Project for the first mutation test.

## Board CLI

```text
producer_board.py init        --repo OWNER/REPO --project-owner OWNER --project-number N
                              [--wip-limit N] [--handoff-cap N]
                              [--spec-completion merged|opened]
producer_board.py doctor
producer_board.py bootstrap   --role ROLE
producer_board.py list        [--role ROLE] [--status STATUS]
producer_board.py brief       [--with-handoffs] [--format text|json]
producer_board.py triage
producer_board.py queue
producer_board.py dispatch    [--role ROLE] [--format text|json]
producer_board.py intake      --title TITLE (--body BODY | --body-file PATH)
producer_board.py create-card --title TITLE (--body BODY | --body-file PATH)
                              [--status STATUS] [--role ROLE] [--acting-role ROLE]
producer_board.py promote     ISSUE --spec REF [--acting-role ROLE] [--note TEXT]
producer_board.py release-claim ISSUE --branch BRANCH [--acting-role ROLE] [--note TEXT]
producer_board.py decompose   PARENT --spec REF --children FILE.json
producer_board.py transition  ISSUE --to STATUS --acting-role ROLE
producer_board.py handoff     ISSUE --from-role ROLE --to-role ROLE --note TEXT
                              [--needs TEXT] [--artifacts TEXT]

producer_board.py claim       ISSUE --acting-role dev|architect
producer_board.py submit-pr   ISSUE --title TITLE --body-file PATH [--acting-role ROLE]
producer_board.py verdict     ISSUE --evidence-file PATH
producer_board.py accept      ISSUE
producer_board.py reconcile-done ISSUE [--acting-role ROLE]
producer_board.py worktree-status [ISSUE]
```

`accept` deliberately takes no argument but the Issue number. Every input to
the acceptance decision is read from live GitHub state, so there is no flag
through which a caller could steer the route — that is what makes "no agent
seat chooses its own merge outcome" a property of the interface rather than a
promise in prose.

Every command prints one JSON envelope and exits 0, or prints
`{"ok": false, "error": ...}` on stderr and exits 1. A multi-step mutation that
fails part-way returns `partial: true` with the exact `completed` prefix and a
`recovery` recipe — nothing ever claims a rollback that did not run.

## Layout

```text
scripts/producer_board.py   stable CLI entry point
scripts/agent_teams/
  model.py                  validated Role, Status, Card, Handoff, Verdict
  policy.py                 pure legality: transitions, authority, caps, seats
  config.py                 configuration and its validation
  github.py                 gh invocation, pagination, error classification
  board.py                  semantic board operations
  workflows.py              transactions with partial-failure recovery
tests/                      144 tests, no network
```

`policy.py` imports nothing that touches the network, which is why every
transition edge and every seat pair is asserted rather than sampled.

## Tests

```powershell
python -m unittest discover -s tests -p "test_*.py"
```
