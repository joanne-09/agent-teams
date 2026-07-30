# Producer adaptation session handoff

Last updated: 2026-07-30

## Current repository state

- Main repository: `C:\Users\User\Documents\intern\ITRI\agent-teams`
- Implementation commit: `a14ef29 feat: implement producer`
- Plugin version: `0.8.0`
- Git observed `main`, `origin/main`, and `feat/agent-team-producer` at
  `a14ef29` when this handoff was created.
- The external worktree `C:\tmp\board-superpowers-producer` was created because
  the repository's `AGENTS.md` required feature work in an external Git
  worktree while the primary checkout remained on `main`. It is another
  checkout of this repository, not a separate clone or source of truth.

Before removing the worktree, verify it contains no uncommitted changes:

```powershell
git -C "C:\tmp\board-superpowers-producer" status
git worktree remove "C:\tmp\board-superpowers-producer"
```

## Original request

The requested work was:

1. read `docs/agent-team-adaptation` thoroughly;
2. implement the Producer portion of the proposed agent-team adaptation;
3. update the adaptation documentation after implementation;
4. make the result usable and testable as a Claude Code plugin in another
   repository.

The complete `docs/agent-team-adaptation` dossier was read, together with the
applicable skill, script, architecture, plugin, board, setup-stage, and
multi-agent project contracts.

## Delivered Producer scope

### New Producer skills

`skills/dispatching-work/`

- EM-seat dispatch routine;
- reads Role lanes and WIP;
- selects safe work;
- renders deterministic carrier-neutral kickoff prompts;
- observes handoff caps and audit rules.

`skills/authoring-spec/`

- architect-seat specification routine;
- claims one Card in an isolated worktree;
- produces a docs-only PR;
- routes durable specifications, ADRs, contracts, and implementation plans;
- hands decomposed implementation work to RD;
- does not implement production code.

The runtime catalog is now 16 skills: the original 14 plus these two Producer
skills.

### Agent seats and Role ownership

The implementation introduces plugin-layer seats:

- `analyst`
- `architect`
- `rd`
- `qa`
- `em`
- `human`

GitHub Project `Role` is durable Card ownership. The setup registry provisions
that field through:

```text
m3.repo.ensure-role-field
```

M3 was selected instead of the dossier's proposed M11 because field
provisioning belongs to the existing board-provisioning module and the shipped
registry currently ends at M10.

### Ninth Kanban action

`handoff_card` was added as the ninth protocol action. The implementation:

- validates source-seat authority;
- validates positive Card/project/cap values;
- enforces the handoff cap;
- mutates the Card Role field;
- posts a structured handoff comment;
- records audit actions 300/305;
- surfaces partial external failure without claiming rollback.

Primary implementation:

```text
scripts/handoff-card.sh
skills/board-canon/references/handoff-authority.md
```

### Dispatch renderer

`scripts/dispatch-agent.sh` is a pure kickoff-prompt renderer. It validates the
seat, Card identifier, and output format without coupling dispatch decisions to
a specific Claude carrier.

### Seat-aware autonomy

Action classification now accepts an actor seat while preserving legacy
behavior when no seat is given. The hard `N` floor is applied before
configuration overrides. Project configuration has precedence over user
configuration.

### Audit schema v3

Audit schema v3 adds nullable `actor_seat` while retaining `actor_role`.

New migration:

```text
scripts/migrations/audit-v2-to-v3.sh
scripts/migrations/audit-v2-to-v3-impl.py
```

The audit writer and JSONL fallback can record explicit actor role and seat,
and the flush path replays both fields.

### Existing Producer routines updated

- entry routing parses leading `[role:<seat>]`;
- daily briefing groups Role lanes;
- intake hands analyst work to architect;
- decomposition hands implementation Cards from architect to RD;
- triage uses seat authority for escalation;
- bootstrap provisions Role;
- board reads emit `role` and accept `--role`;
- operating-kanban dispatches `handoff_card`;
- auditing and action classification understand seats.

### Architecture decisions

Added:

```text
docs/architecture/adr/0029-agent-seats-at-plugin-layer.md
docs/architecture/adr/0030-seat-dimension-autonomy.md
docs/architecture/adr/0031-handoff-card-protocol-action.md
```

The associated role, Producer surface, bootstrap, invariants, domain model,
component architecture, Kanban protocol, configuration, audit, observability,
skill contract, and session protocol documents were updated.

## Intentionally deferred scope

The implementation is the Producer slice, not the entire target team model.
Still deferred:

- new QA-owned `verifying-delivery`;
- full QA conversion of `reviewing-pr-queue`;
- RD/Consumer terminal handoff to QA;
- remaining Consumer-side changes described by the adaptation dossier.

These must not be described as shipped.

## Verification evidence

Passed:

- `claude plugin validate` for the development plugin;
- 21 focused M2 cross-platform venv-stage tests;
- 32 focused M3 Role, M4 audit, and M7 routing tests;
- dispatch renderer unit tests;
- handoff unit tests;
- seat-autonomy unit tests;
- fresh audit-schema-v3 test;
- routing-block parity tests.

Claude validation had one non-blocking warning: the marketplace manifest did
not have a top-level `description`.

Not completed:

- complete Python/stage suite;
- complete shell suite;
- final metadata/frontmatter verification;
- final `git diff --check`;
- shellcheck;
- a live GitHub Project mutation;
- a full fresh-repository bootstrap.

Environment limitations during the session:

- `gh` was not installed;
- `shellcheck` was not installed;
- `gstack` was not installed;
- `superpowers` was installed.

No live board mutation was performed.

## Known Windows audit failure

`tests/unit/test-schema-migration-idempotent.sh` failed under Git Bash with:

```text
sqlite3.OperationalError: unable to open database file
```

Cause:

- Git Bash creates an MSYS/POSIX temporary path;
- the migration invokes native Windows Python from
  `.board-superpowers\.venv\Scripts\python.exe`;
- the SQLite DSN is not translated consistently to a native Windows path.

This does not prevent Claude from discovering or invoking the plugin skills.
It must be fixed before claiming complete Windows audit-migration support.

The remaining normalization should be applied consistently to audit init,
write, flush, migration, and health-check paths, not only to the failing test.

## Review warning: generated files

Commit `a14ef29` includes:

```text
.board-superpowers/pyproject.toml
.board-superpowers/uv.lock
```

They appeared while audit tests created the per-repository runtime
environment. The `.board-superpowers/.venv/` directory is ignored and was not
committed.

Review whether the two committed files are intentional dogfood configuration
for this repository. The session had planned to remove them as generated test
artifacts before the implementation was externally committed.

## Adaptation documentation still requiring final update

The canonical architecture documents were updated, but the original
`docs/agent-team-adaptation` implementation-status material was not completed
before work stopped.

Update at least:

- `docs/agent-team-adaptation/README.md`;
- `04-implementation-plan.md`;
- `05-file-change-map.md`;
- `06-operating-runbook.md`.

Record the delivered Producer slice, the deferred QA/RD slice, the actual M3
Role-field stage, the new files, and current verification status.

## How to test the modified Claude plugin

### Direct development load

Open PowerShell in another repository:

```powershell
cd C:\path\to\another-repository
claude --plugin-dir "C:\Users\User\Documents\intern\ITRI\agent-teams"
```

Inside Claude Code, run:

```text
/help
```

Search for:

```text
/board-superpowers:using-board-superpowers
/board-superpowers:dispatching-work
/board-superpowers:authoring-spec
```

`--plugin-dir` is session-only. It may not appear in the `/plugin` Installed
tab. The namespaced commands appearing in `/help` prove that the plugin loaded.

Do not use `--safe-mode` or `--disable-slash-commands`.

### Non-mutating behavior checks

Run:

```text
/board-superpowers:using-board-superpowers
```

Ask:

```text
List the 16-skill board-superpowers catalog and explain the new Producer seats.
Do not mutate a board.
```

Then verify EM routing:

```text
[role:em] Explain which routine handles dispatching and stop before any board mutation.
```

Expected routine: `dispatching-work`.

Verify architect routing:

```text
[role:architect] Explain the spec-authoring workflow and stop before any board mutation.
```

Expected routine: `authoring-spec`.

### Persistent local installation

```powershell
claude plugin marketplace add "C:\Users\User\Documents\intern\ITRI\agent-teams" --scope user
claude plugin install board-superpowers@board-superpowers-local --scope user
```

Restart Claude or run:

```text
/reload-plugins
```

If a stale marketplace entry exists, inspect it first:

```powershell
claude plugin marketplace list --json
```

### Live board test prerequisites

Skill discovery and non-mutating routing do not need GitHub. Live board
operations require:

- GitHub CLI;
- authenticated repository access;
- GitHub Project scope;
- completed board-superpowers setup stages;
- sibling plugins required by the chosen workflow;
- a configured audit database or acceptance of documented JSONL degradation.

Typical GitHub setup:

```powershell
winget install --id GitHub.cli
gh auth login
gh auth refresh -s project
```

Use a disposable Project for the first live test. A handoff changes the Role
field, posts a comment, and emits audit records.

## Recommended continuation

1. Decide whether the two committed `.board-superpowers` files belong.
2. Fix Windows SQLite DSN normalization.
3. Complete the adaptation-dossier status update.
4. Add the marketplace description.
5. Run all project verification gates.
6. Perform a fresh-repository `--plugin-dir` smoke test.
7. Perform a disposable-board live handoff test after installing `gh` and
   sibling dependencies.

## Main source locations

```text
skills/dispatching-work/
skills/authoring-spec/
scripts/dispatch-agent.sh
scripts/handoff-card.sh
scripts/migrations/audit-v2-to-v3.sh
scripts/migrations/audit-v2-to-v3-impl.py
scripts/stages_lib/m3_repo_ensure_role_field.py
docs/architecture/adr/0029-agent-seats-at-plugin-layer.md
docs/architecture/adr/0030-seat-dimension-autonomy.md
docs/architecture/adr/0031-handoff-card-protocol-action.md
```

Inspect the implementation:

```powershell
git show --stat a14ef29
git show a14ef29
```
