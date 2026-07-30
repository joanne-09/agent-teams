# Testing the board-superpowers Producer plugin in another repository

Last updated: 2026-07-30  
Plugin source: `C:\Users\User\Documents\intern\ITRI\agent-teams`  
Tested implementation: `main` at `a14ef29`  
Plugin version: `0.8.0`

## 1. What this procedure verifies

This procedure tests the current Producer implementation at progressively
stronger levels:

1. manifest validation;
2. direct development loading from `main`;
3. skill discovery;
4. role-to-skill routing without mutations;
5. persistent marketplace installation;
6. SessionStart/bootstrap detection;
7. optional live Producer behavior against a disposable GitHub Project.

You do not need GitHub access for levels 1–4. Stop after those levels if the
goal is only to prove that the modified plugin loads and routes correctly.

## 2. Current Producer features under test

The v0.8.0 catalog contains 16 skills. The two new Producer-team skills are:

- `dispatching-work`: EM-seat queue selection and kickoff rendering;
- `authoring-spec`: architect-seat delivery of one specification Card as one
  docs-only PR.

The implementation also adds:

- plugin-layer seats: analyst, architect, RD, QA, EM, and human;
- durable GitHub Project `Role` ownership;
- the ninth Kanban action, `handoff_card`;
- seat-aware action classification;
- audit schema v3 with nullable `actor_seat`;
- Role-aware intake, briefing, decomposition, triage, board reads, and
  bootstrap.

## 3. Validate the plugin manifest

From PowerShell:

```powershell
cd C:\Users\User\Documents\intern\ITRI\agent-teams
claude plugin validate .
```

Expected:

```text
Validation passed
```

The current manifest may also report this non-blocking warning:

```text
No marketplace description provided
```

The warning does not prevent the plugin from loading.

## 4. Recommended development test: load directly from `main`

Open PowerShell in the repository where the plugin should be tested:

```powershell
cd C:\path\to\your-other-repository

claude --plugin-dir "C:\Users\User\Documents\intern\ITRI\agent-teams"
```

This is the recommended method while developing the plugin:

- Claude reads the current files directly from `main`;
- no plugin installation is required;
- no stale cached copy is used;
- a local plugin with the same name takes precedence for that session;
- the plugin is loaded only for the current Claude session.

A `--plugin-dir` development plugin might not appear in the `/plugin`
Installed tab. Verify it through `/help` and its namespaced commands instead.

Do not start this test with:

```text
--safe-mode
--disable-slash-commands
```

Those options disable the required plugin or skill behavior.

## 5. Verify skill discovery

Inside the Claude session:

```text
/help
```

Search for `board-superpowers`. At minimum, verify that these commands exist:

```text
/board-superpowers:using-board-superpowers
/board-superpowers:dispatching-work
/board-superpowers:authoring-spec
/board-superpowers:briefing-daily
/board-superpowers:intaking-requirement
/board-superpowers:triaging-board
/board-superpowers:bootstrapping-repo
```

You can also type:

```text
/board-superpowers:
```

and use Claude Code's completion menu.

Seeing `dispatching-work` and `authoring-spec` proves that Claude loaded the
modified Producer catalog rather than the older v0.7.0 catalog.

## 6. Test the manual page

Invoke:

```text
/board-superpowers:using-board-superpowers
```

Then ask:

```text
Without using tools or changing files or boards, list the board-superpowers
catalog, state its version, and explain the new Producer seats.
```

Expected:

- version `0.8.0`;
- 16 skills;
- `dispatching-work` identified as the EM routine;
- `authoring-spec` identified as the architect routine;
- analyst, architect, RD, QA, EM, and human identified as seats.

## 7. Non-mutating role-routing tests

These prompts verify routing only. They explicitly prohibit tool use and board
mutation.

### 7.1 EM dispatch routing

```text
[role:em] Explain how you would dispatch the next eligible Cards.
Do not run tools and do not mutate the board.
```

Expected routine:

```text
dispatching-work
```

Expected explanation:

- read Role lanes;
- inspect Status and WIP;
- exclude blocked or unsafe Cards;
- respect handoff limits;
- render deterministic kickoff prompts.

### 7.2 Architect specification routing

```text
[role:architect] Explain how you would deliver a specification Card.
Do not run tools, create a worktree, or mutate the board.
```

Expected routine:

```text
authoring-spec
```

Expected explanation:

- one architect-owned Card;
- one isolated worktree;
- one docs-only PR;
- no production-code implementation;
- decomposition and architect-to-RD handoff after the specification is ready.

### 7.3 Analyst intake routing

```text
[role:analyst] Explain how a new requirement moves from analyst to architect.
Do not create a Card or mutate the board.
```

Expected routine:

```text
intaking-requirement
```

Expected flow:

```text
intake requirement
→ create Backlog Card
→ initial analyst ownership
→ handoff to architect
```

### 7.4 Daily briefing routing

```text
Give me a morning briefing grouped by Role.
Do not access GitHub; explain the expected output only.
```

Expected routine:

```text
briefing-daily
```

## 8. Non-interactive one-command smoke test

This test loads the plugin, invokes its manual page, prints one response, and
exits without saving the session:

```powershell
cd C:\path\to\your-other-repository

claude `
  --plugin-dir "C:\Users\User\Documents\intern\ITRI\agent-teams" `
  --permission-mode dontAsk `
  --no-session-persistence `
  -p "/board-superpowers:using-board-superpowers Without using tools or mutating anything, confirm the plugin loaded, state its catalog size, and name the two new Producer skills. Keep the answer to one line."
```

Expected output should contain:

```text
board-superpowers loaded
16-skill catalog
dispatching-work
authoring-spec
```

This exact class of smoke test has already passed against the current `main`.

## 9. Repair the persistent installation

The machine previously had a stale marketplace registered at:

```text
C:\Users\User\Documents\intern\ITRI\board-superpowers
```

That installation reported:

```text
version: 0.7.0
error: marketplace cache-miss
```

The current source is:

```text
C:\Users\User\Documents\intern\ITRI\agent-teams
```

First remove only the stale board-superpowers marketplace:

```powershell
claude plugin marketplace remove board-superpowers-local
```

Add the current directory:

```powershell
claude plugin marketplace add `
  "C:\Users\User\Documents\intern\ITRI\agent-teams" `
  --scope user
```

Install the current plugin:

```powershell
claude plugin install `
  board-superpowers@board-superpowers-local `
  --scope user
```

Inspect the result:

```powershell
claude plugin marketplace list --json
claude plugin list --json
```

Expected:

```text
id: board-superpowers@board-superpowers-local
version: 0.8.0
enabled: true
errors: none
```

Start Claude normally in the other repository:

```powershell
cd C:\path\to\your-other-repository
claude
```

Inside Claude:

```text
/reload-plugins
/help
```

The persistently installed plugin should now also appear in `/plugin`.

## 10. Direct loading versus persistent installation

| Method | Source | Installed tab | Recommended use |
|---|---|---:|---|
| `--plugin-dir` | Current files from `main` | May not appear | Development and immediate verification |
| Marketplace installation | Versioned Claude cache | Appears | Normal use across repositories |

During development, prefer `--plugin-dir`. Marketplace plugins are copied into
Claude's cache. A source edit without a version bump or reinstall might leave
the installed copy stale.

## 11. Test SessionStart and bootstrap detection

Choose a repository that has not been bootstrapped with board-superpowers:

```powershell
cd C:\path\to\clean-test-repository
claude --plugin-dir "C:\Users\User\Documents\intern\ITRI\agent-teams"
```

Ask:

```text
What board-superpowers setup stages are required for this repository?
Do not run them yet.
```

Expected:

- the SessionStart hook detects missing or stale setup stages;
- routing points to `bootstrapping-repo`;
- the plan includes GitHub Project Role-field provisioning;
- stages that have never run are reported as such.

You can invoke bootstrap directly:

```text
/board-superpowers:bootstrapping-repo
```

Then constrain it to inspection:

```text
Inspect only. Explain the required stages and stop before mutations.
```

## 12. Requirements for a live GitHub-board test

The loading and routing tests above do not require GitHub CLI. Live board
operations do.

Install GitHub CLI:

```powershell
winget install --id GitHub.cli
```

Authenticate and add Project scope:

```powershell
gh auth login
gh auth refresh -s project
```

Verify:

```powershell
gh --version
gh auth status
```

Verify the other repository has a GitHub remote:

```powershell
cd C:\path\to\your-other-repository
git remote -v
gh repo view --json nameWithOwner
```

Use a disposable repository and disposable GitHub Project for the first live
test.

## 13. Sibling-plugin requirements

At the time this document was written:

- `superpowers` was installed;
- `gstack` was not installed;
- `gh` was not installed.

Basic discovery and non-mutating routing still work. Complete routines may
stop at the dependency gate because board-superpowers delegates:

- implementation discipline to `superpowers`;
- planning, QA, review, and security bookends to `gstack`.

Install the missing dependencies before evaluating a complete Card-to-PR
workflow.

## 14. Minimal live Producer scenario

Only continue after the non-mutating checks pass and the test Project is safe
to modify.

### 14.1 Bootstrap the disposable repository

Inside Claude:

```text
/board-superpowers:bootstrapping-repo
```

Follow the elicitation prompts for the disposable GitHub Project.

Verify that bootstrap provisions or recognizes:

- the canonical Status field and options;
- the Role field and seat options;
- repository configuration and local state;
- audit configuration or documented local JSONL degradation.

### 14.2 Test analyst intake

```text
[role:analyst] Intake this disposable requirement:

Add a documentation page explaining the repository's development setup.
```

Expected board behavior:

```text
Card created in Backlog
→ initially owned by analyst
→ handed to architect
→ Role becomes architect
→ structured handoff comment added
→ audit event emitted
```

Intake must not silently mark the Card Ready.

### 14.3 Test architect planning without mutation

```text
[role:architect] Inspect the disposable specification Card and explain the
authoring plan. Stop before claiming it.
```

Expected route:

```text
authoring-spec
```

If the plan is correct, explicitly authorize the full disposable test. A full
architect run may:

- claim the Card;
- create an isolated worktree and branch;
- edit documentation;
- open a docs PR;
- decompose downstream implementation Cards;
- hand implementation Cards to RD.

### 14.4 Test EM dispatch

```text
[role:em] Dispatch the next eligible disposable Cards.
Show the selected queue and kickoff prompts.
```

Expected:

- Role-grouped queue;
- WIP enforcement;
- blocked Cards excluded;
- handoff caps respected;
- deterministic kickoff prompts;
- audit-aware dispatch decisions.

## 15. Verify live board state

After each live action, inspect the disposable Project and affected Cards.

Verify:

- Status is correct;
- Role is correct;
- the structured handoff comment exists;
- the handoff count does not exceed its cap;
- intake did not incorrectly move work directly to Ready;
- handoff and Status transition are distinct board mutations;
- audit output records the expected action and actor seat;
- when no database is configured, the documented JSONL degradation occurs.

## 16. Known limitations of the current `main`

These limitations do not prevent direct skill-loading and routing tests:

- Windows SQLite migration testing still has an MSYS/native-Python path issue;
- no live GitHub Project mutation was completed during implementation;
- the complete repository test suite was not run;
- `shellcheck` was unavailable;
- `gh` and `gstack` were unavailable;
- the marketplace manifest validates with a missing-description warning;
- the adaptation dossier still needs its final delivered/deferred status update;
- `.board-superpowers/pyproject.toml` and `.board-superpowers/uv.lock` entered
  commit `a14ef29` and should be reviewed as possible generated test artifacts.

See `HANDOFF.md` for the detailed implementation handoff.

## 17. Acceptance checklist

### Plugin loading

- [ ] `claude plugin validate` passes.
- [ ] `/help` lists namespaced board-superpowers commands.
- [ ] `dispatching-work` appears.
- [ ] `authoring-spec` appears.
- [ ] the manual page reports 16 skills.

### Routing

- [ ] `[role:em]` dispatch request selects `dispatching-work`.
- [ ] `[role:architect]` specification request selects `authoring-spec`.
- [ ] `[role:analyst]` intake request selects `intaking-requirement`.
- [ ] daily briefing request selects `briefing-daily`.

### Persistent installation

- [ ] installed version is `0.8.0`.
- [ ] the marketplace path points to `agent-teams`.
- [ ] `claude plugin list --json` reports no `cache-miss`.
- [ ] `/plugin` shows the enabled plugin.

### Bootstrap and live board

- [ ] a fresh repository routes to bootstrap.
- [ ] bootstrap provisions the Role field.
- [ ] analyst-to-architect handoff works.
- [ ] structured handoff comment is created.
- [ ] EM dispatch respects Role and WIP.
- [ ] audit output includes actor seat or documented degraded JSONL.

For a basic proof that the modified plugin works, completion of the Plugin
loading and Routing sections is sufficient.
