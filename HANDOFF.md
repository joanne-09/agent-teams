# board-superpowers Producer MVP handoff

Last updated: 2026-07-30

## Repository state

- Working directory:
  `C:\Users\User\Documents\intern\ITRI\agent-teams`
- Current branch: `mvp/producer-from-scratch`
- MVP root commit: `d9b739a`
- Plugin name: `board-superpowers-producer`
- Plugin version: `0.1.0`
- The branch is an orphan branch: it has no parent and inherited no files from
  the earlier implementation.
- Nothing from this MVP has been pushed or merged.

The previous full implementation and its documentation remain on `main` at
commit `e2e1dec`. Switching between the two versions:

```powershell
git switch main
git switch mvp/producer-from-scratch
```

## Goal

Build the smallest useful Claude Code plugin that demonstrates the Producer
side of board-superpowers without carrying the infrastructure and maintenance
cost of the full implementation.

The MVP answers four questions:

1. Can Claude route a session by Producer seat?
2. Can an analyst create a durable requirement and hand it to an architect?
3. Can an architect deliver a focused specification and hand the Card to RD?
4. Can an EM read Ready work and render deterministic kickoff prompts?

## Deliberate scope

The MVP contains four Claude skills:

| Skill | Seat | Purpose |
|---|---|---|
| `using-board-superpowers` | router | Parse role tokens and route intent |
| `intaking-requirement` | analyst | Create a Backlog Issue and hand it to architect |
| `authoring-spec` | architect | Produce a docs-only specification PR and hand the Card to RD |
| `dispatching-work` | EM | Read Ready Cards and render kickoff prompts by Role |

The durable coordination surface is one GitHub Project. Cards are GitHub
Issues with two single-select fields:

```text
Status: Backlog, Ready, In Progress, In Review, Done, Blocked
Role: analyst, architect, rd, qa, em, human
```

The plugin does not hold an in-memory team. A rendered kickoff prompt may be
consumed by a human-started Claude session, another carrier, or future
automation.

## Intentionally excluded

The following were deliberately omitted from the MVP:

- audit database and JSONL outbox;
- audit schema versions and migrations;
- setup-stage registry and lifecycle diff;
- SessionStart hooks;
- automatic Project-field creation;
- Codex plugin manifest;
- multi-backend board adapter;
- WIP policy engine;
- handoff-count persistence;
- automatic agent or terminal spawning;
- Consumer/RD implementation workflow;
- QA delivery workflow;
- large architecture dossier;
- per-skill metadata and evaluation framework;
- sibling-plugin orchestration;
- shell runtime and virtual environment management.

These are not accidental omissions. They are candidates for later additions
only when an observed test or user workflow justifies them.

## File map

```text
.claude-plugin/
├── plugin.json
└── marketplace.json

skills/
├── using-board-superpowers/SKILL.md
├── intaking-requirement/SKILL.md
├── authoring-spec/SKILL.md
└── dispatching-work/SKILL.md

scripts/
└── producer_board.py

tests/
└── test_producer_board.py

README.md
HANDOFF.md
```

## Runtime design

### Configuration

A consuming repository stores board coordinates in:

```text
.board-superpowers/producer.json
```

Example:

```json
{
  "repo": "OWNER/REPO",
  "project_owner": "OWNER",
  "project_number": 1,
  "role_field": "Role",
  "status_field": "Status",
  "backlog_status": "Backlog",
  "ready_status": "Ready",
  "dispatch_roles": [
    "architect",
    "rd",
    "qa"
  ]
}
```

This file contains board coordinates and workflow names, not credentials.
GitHub authentication remains owned by `gh`.

Create the configuration from the consuming repository:

```powershell
python "C:\Users\User\Documents\intern\ITRI\agent-teams\scripts\producer_board.py" init `
  --repo OWNER/REPO `
  --project-owner OWNER `
  --project-number 1
```

### Board CLI

The entire deterministic runtime is:

```text
scripts/producer_board.py
```

It uses only the Python standard library and the `gh` executable.

Commands:

```text
producer_board.py init
producer_board.py doctor
producer_board.py list [--role ROLE] [--status STATUS]
producer_board.py dispatch [--role ROLE] [--format text|json]
producer_board.py intake --title TITLE (--body BODY | --body-file PATH)
producer_board.py handoff ISSUE --from-role ROLE --to-role ROLE --note TEXT
```

Mutating commands print JSON only after the requested durable operation has
completed.

### Handoff authority

The MVP enforces this source-to-target map:

```text
analyst   → architect, em, human
architect → rd, qa, em, human
rd        → architect, qa, em
qa        → architect, rd, em, human
em        → analyst, architect, rd, qa, human
human     → analyst, architect, rd, qa, em
```

The current Role must match `--from-role`. Handoff changes the Project Role
field and then posts a structured Issue comment.

### Intake behavior

Intake:

1. creates a GitHub Issue;
2. adds it to the configured Project;
3. sets Status to `Backlog`;
4. sets Role to `analyst`;
5. hands Role to `architect`;
6. posts an analyst-to-architect handoff comment.

It intentionally does not mark the Card Ready.

### Dispatch behavior

Dispatch:

1. reads Project items;
2. keeps only Issues from the configured repository;
3. keeps only Cards whose Status equals `ready_status`;
4. keeps only configured dispatch roles;
5. sorts by configured role order and Issue number;
6. renders prompts containing:

```text
[role:<role>] [board-card:#<number>]
```

Dispatch is read-only. It does not start agents or mutate Role/Status.

## Validation performed

Only focused, necessary checks were run.

### Python syntax

```powershell
python -m py_compile scripts\producer_board.py tests\test_producer_board.py
```

Result: passed.

### Focused unit tests

```powershell
python -m unittest discover -s tests -v
```

Result:

```text
9 tests passed
```

Covered behavior:

- configuration round-trip;
- rejection of unknown dispatch roles;
- Project-item normalization;
- repository filtering;
- Ready/Role dispatch filtering;
- deterministic dispatch ordering;
- unauthorized handoff rejection;
- Role mutation and handoff comment;
- intake remaining Backlog and ending with architect ownership;
- required Project-field validation.

The tests use a fake `gh` adapter. They do not access GitHub or mutate a live
Project.

### Claude plugin validation

```powershell
claude plugin validate .
```

Result:

```text
Validation passed
```

There are no manifest warnings.

### Git whitespace validation

```powershell
git diff --cached --check
```

Result: passed before commit.

### Actual Claude runtime load

The following non-mutating runtime check was executed:

```powershell
claude `
  --plugin-dir "." `
  --permission-mode dontAsk `
  --no-session-persistence `
  -p "/board-superpowers-producer:using-board-superpowers Without using tools or changing anything, confirm this MVP loaded and name its three downstream Producer routines in one line."
```

Claude returned:

```text
Loaded — the board-superpowers Producer router is active; its three downstream
routines are intaking-requirement, authoring-spec, and dispatching-work.
```

## Test in another repository

### Safe load and routing test

From another repository:

```powershell
cd C:\path\to\another-repository

claude --plugin-dir "C:\Users\User\Documents\intern\ITRI\agent-teams"
```

Inside Claude:

```text
/help
/board-superpowers-producer:using-board-superpowers
```

Verify these commands appear:

```text
/board-superpowers-producer:using-board-superpowers
/board-superpowers-producer:intaking-requirement
/board-superpowers-producer:authoring-spec
/board-superpowers-producer:dispatching-work
```

Non-mutating prompts:

```text
[role:analyst] Explain how you would intake a requirement. Do not use tools.
```

```text
[role:architect] Explain how you would author a specification. Do not use tools.
```

```text
[role:em] Explain the dispatch queue. Do not use tools.
```

Expected routing:

```text
analyst   → intaking-requirement
architect → authoring-spec
em        → dispatching-work
```

### Persistent local installation

Add this branch's directory as a local marketplace:

```powershell
claude plugin marketplace add `
  "C:\Users\User\Documents\intern\ITRI\agent-teams" `
  --scope user
```

Install:

```powershell
claude plugin install `
  board-superpowers-producer@board-superpowers-producer-local `
  --scope user
```

Verify:

```powershell
claude plugin list --json
```

Expected plugin:

```text
board-superpowers-producer@board-superpowers-producer-local
version 0.1.0
enabled
no errors
```

During active development, prefer `--plugin-dir`; it reads the current branch
directly and avoids a stale cached installation.

## Live GitHub test

No live GitHub mutation was performed during implementation.

Prerequisites:

```powershell
winget install --id GitHub.cli
gh auth login
gh auth refresh -s project
gh auth status
```

Use a disposable repository and Project. Ensure the required Status and Role
fields/options exist before running `doctor`.

Configure:

```powershell
cd C:\path\to\disposable-repository

python "C:\Users\User\Documents\intern\ITRI\agent-teams\scripts\producer_board.py" init `
  --repo OWNER/REPO `
  --project-owner OWNER `
  --project-number 1
```

Validate:

```powershell
python "C:\Users\User\Documents\intern\ITRI\agent-teams\scripts\producer_board.py" doctor
```

Read-only dispatch:

```powershell
python "C:\Users\User\Documents\intern\ITRI\agent-teams\scripts\producer_board.py" dispatch `
  --format json
```

Only after reviewing the disposable Project, test intake:

```text
[role:analyst] Intake this disposable requirement:
Add a short development-setup document.
```

Verify:

- a new Issue exists;
- the Issue is on the configured Project;
- Status is Backlog;
- final Role is architect;
- the handoff comment exists.

Then test EM dispatch after manually making a disposable Card Ready:

```text
[role:em] Show the dispatch queue.
```

Verify that the kickoff prompt contains the correct Role and Card number.

## Known limitations

### Project shape assumptions

The CLI expects the JSON shapes returned by current `gh project` commands. Unit
tests cover the common shape but a live Project test is still required.

### No automatic field provisioning

`doctor` validates fields and options; it does not create them. This avoids
turning setup into another framework in the MVP.

### Partial handoff failure

Handoff changes Role before posting the comment. If the comment fails after the
field mutation, the command reports failure but does not roll the Role back.
The Project remains the source of truth and should be inspected.

### No WIP or claim mechanism

Dispatch filters Ready Cards but does not reserve them, enforce concurrency, or
prevent two humans from launching the same prompt. Add a claim primitive only
if MVP usage demonstrates that this is a real failure mode.

### No automatic decomposition

`authoring-spec` hands the existing Card to RD. It does not create multiple
implementation Cards. This keeps the first version understandable but is not
sufficient for large specifications.

### No Consumer or QA workflow

RD and QA appear as durable Role values and dispatch targets, but this plugin
does not define their implementation or verification routines.

## Recommended next steps

Do not restore the full implementation wholesale. Extend only in response to
observed MVP failures.

Recommended order:

1. run safe routing tests in an unrelated repository;
2. install `gh` and run `doctor` against a disposable Project;
3. test one intake;
4. test one architect-to-RD handoff;
5. test one EM dispatch;
6. record concrete failures;
7. add only the smallest mechanism that closes the highest-cost failure.

Likely first candidates, if justified:

- a local `claim` action to prevent duplicate dispatch;
- a small setup command for Role/Status fields;
- decomposition into multiple implementation Cards;
- RD and QA skills;
- an append-only audit file before considering an RDBMS.

## Useful commands

Current branch and status:

```powershell
git branch --show-current
git status
git log -1 --oneline
```

Focused validation:

```powershell
python -m unittest discover -s tests -v
claude plugin validate .
```

Inspect the MVP root commit:

```powershell
git show --stat d9b739a
git show d9b739a
```

Return to the previous full version:

```powershell
git switch main
```

Return to the MVP:

```powershell
git switch mvp/producer-from-scratch
```
