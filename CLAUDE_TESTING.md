# Testing agent-teams automation in Claude Code

Last updated: 2026-08-12

## Current plugin

- Source directory:
  `C:\Users\User\Documents\intern\ITRI\agent-teams-project\agent-teams`
- Branch: `mvp/producer-from-scratch`
- Plugin: `agent-teams`
- Version: `0.2.0`
- Skills: 9, plus one bounded worker agent

## Current automation contract

This section supersedes any older example below that asks a person to merge a
specification Pull Request, open another Claude session, paste a kickoff prompt,
or manually reconcile a routine eligible merge.

- Product specs publish directly below `docs/` on the current branch with
  `publish-spec`; no spec PR exists.
- The user's current Claude session runs `next-actions`, spawns
  the seat's `agent-teams:<seat>-worker` for each admitted Card stage, and executes
  controller/reconcile actions itself.
- A `monitor` action keeps the same session alive and rechecks delayed
  auto-merge; it is not a stop condition.
- Human interaction is limited to moving the specified Card's Status to
  `Ready` and, only for a protected or ambiguous QA result, approving the
  exception. The controller performs the resulting role handoff.
- `Done` requires current exact-head eligible evidence plus a confirmed merge;
  generic `transition --to Done` must refuse.

Before testing, verify that the source directory is still on the MVP branch:

```powershell
cd C:\Users\User\Documents\intern\ITRI\agent-teams-project\agent-teams
git branch --show-current
```

Expected:

```text
mvp/producer-from-scratch
```

If this directory is on `main`, Claude will load the older, larger plugin
instead of this MVP.

## 1. Validate the plugin

From the plugin directory:

```powershell
claude plugin validate .
```

Expected:

```text
Validation passed
```

The current MVP manifest validates without warnings.

## 2. Recommended test: load directly from another repository

Open a new PowerShell window and enter the repository where you want to test
the plugin:

```powershell
cd C:\path\to\another-repository
```

Start Claude Code with the current plugin source:

```powershell
claude --plugin-dir "C:\Users\User\Documents\intern\ITRI\agent-teams"
```

`--plugin-dir` is the recommended development mode:

- Claude reads the files from the current branch directly;
- installation is not required;
- an older cached plugin cannot replace the development copy;
- source edits are available after restarting Claude or running
  `/reload-plugins`.

A plugin loaded through `--plugin-dir` may not appear in the `/plugin`
Installed tab. Verify it through `/help` and the namespaced skill commands.

Do not use:

```text
--safe-mode
--disable-slash-commands
```

Those options disable the relevant plugin or skill behavior.

## 3. Verify skill discovery

Inside Claude:

```text
/help
```

Search for `agent-teams`.

You should find these ten focused skills:

```text
/agent-teams:using-agent-teams
/agent-teams:intaking-requirement
/agent-teams:authoring-spec
/agent-teams:dispatching-work
/agent-teams:clarifying-card
/agent-teams:briefing-board
/agent-teams:triaging-board
/agent-teams:inspecting-queue
/agent-teams:consuming-card
/agent-teams:verifying-delivery
```

You can also type:

```text
/agent-teams:
```

and use Claude Code's completion menu.

If these ten skills appear, the plugin has loaded.

## 4. Test the router without tools or mutations

Invoke the entry skill:

```text
/agent-teams:using-agent-teams
```

Then ask:

```text
Without running tools or changing anything, explain the three Producer routes
and their role tokens.
```

Expected routes:

```text
[role:analyst]   → intaking-requirement
[role:architect] → authoring-spec
[role:lead]        → dispatching-work
```

The router should also explain that Dev and QA are dispatch targets, not
implemented workflows in this MVP.

## 5. Test analyst routing

Inside the same Claude session:

```text
[role:analyst] Explain how you would intake a requirement.
Do not run tools, create an Issue, or mutate a board.
```

Expected:

- Claude selects `intaking-requirement`;
- it shapes an outcome-oriented Issue;
- initial Status remains `Backlog`;
- ownership moves from analyst to architect;
- it does not make the Card Ready.

## 6. Test architect routing

```text
[role:architect] Explain how you would author the specification for issue #12.
Do not run tools, create a branch, or change files.
```

Expected:

- Claude selects `authoring-spec`;
- it describes a direct `docs/*.md` write on the current branch followed by
  `publish-spec`;
- it refuses to implement production code in this routine;
- it creates no spec branch, worktree, or Pull Request and stops at readiness
  or decomposition.

## 7. Test Lead routing

```text
[role:lead] Explain how you would dispatch the Ready queue.
Do not run tools or mutate the board.
```

Expected:

- Claude selects `dispatching-work`;
- it filters by configured `ready_status`;
- it requires a durable Role;
- it sorts by configured role order and Issue number;
- it renders kickoff prompts;
- it does not spawn agents or modify Status/Role.

## 8. One-command non-interactive smoke test

This command tests Claude discovery and routing, prints one response, and exits:

```powershell
cd C:\path\to\another-repository

claude `
  --plugin-dir "C:\Users\User\Documents\intern\ITRI\agent-teams" `
  --permission-mode dontAsk `
  --no-session-persistence `
  -p "/agent-teams:using-agent-teams Without using tools or changing anything, confirm this MVP loaded and name its three downstream Producer routines in one line."
```

Expected output contains:

```text
Loaded
intaking-requirement
authoring-spec
dispatching-work
```

This runtime smoke test passed during MVP implementation.

## 9. Persistent installation

Direct `--plugin-dir` loading is sufficient for development. Use the following
only when you want the MVP available in every repository without passing the
flag.

Add the current directory as a local marketplace:

```powershell
claude plugin marketplace add `
  "C:\Users\User\Documents\intern\ITRI\agent-teams" `
  --scope user
```

Install the plugin:

```powershell
claude plugin install `
  agent-teams@agent-teams-local `
  --scope user
```

Inspect the result:

```powershell
claude plugin marketplace list --json
claude plugin list --json
```

Expected:

```text
plugin: agent-teams@agent-teams-local
version: 0.1.0
enabled: true
errors: none
```

Start Claude normally in another repository:

```powershell
cd C:\path\to\another-repository
claude
```

Inside Claude:

```text
/reload-plugins
/help
```

During active development, continue to prefer `--plugin-dir`. Persistent
installation copies the plugin into Claude's cache and can become stale after
source edits.

## 10. Prepare for a live GitHub Project test

The loading and routing tests above do not require GitHub CLI or a board.

Live intake, handoff, and dispatch require:

- `gh` installed;
- GitHub authentication;
- repository access;
- GitHub Project access;
- an existing Project with the required fields and options.

Install and authenticate:

```powershell
winget install --id GitHub.cli
gh auth login
gh auth refresh -s project
gh auth status
```

Use a disposable repository and Project for the first live test.

Required fields:

```text
Status: Backlog, Ready, In Progress, In Review, Done, Blocked
Role: analyst, architect, dev, qa, lead, human
```

The MVP validates these fields but does not create them.

## 11. Configure the consuming repository

From the disposable consuming repository:

```powershell
cd C:\path\to\disposable-repository

python "C:\Users\User\Documents\intern\ITRI\agent-teams\scripts\producer_board.py" init `
  --repo OWNER/REPO `
  --project-owner OWNER `
  --project-number 1
```

This creates:

```text
.agent-teams/config.json
```

The configuration contains board coordinates, not credentials.

Validate GitHub access and Project shape:

```powershell
python "C:\Users\User\Documents\intern\ITRI\agent-teams\scripts\producer_board.py" doctor
```

Expected JSON includes:

```json
{
  "ok": true,
  "repo": "OWNER/REPO",
  "project_number": 1,
  "role_field": "Role",
  "status_field": "Status"
}
```

If `doctor` fails, fix the reported field, option, authentication, or access
problem before asking Claude to mutate the Project.

## 12. Read-only planning and current-session launch test

This command accesses GitHub but does not mutate the Project:

```powershell
python "C:\Users\User\Documents\intern\ITRI\agent-teams-project\agent-teams\scripts\producer_board.py" next-actions
```

Expected:

- only Cards from the configured repository;
- only legal actions for current live routing pairs;
- Ready work admitted only under configured WIP limits and dispatch ordering;
- at most one direct-spec authoring action because spec workers share checkout;
- each spawn prompt contains `[role:<role>] [board-card:#<number>]`;
- `human_gates` contains only readiness or protected QA exceptions.

An empty JSON array is valid when there is no Ready work.

Then test through Claude:

```powershell
claude --plugin-dir "C:\Users\User\Documents\intern\ITRI\agent-teams-project\agent-teams"
```

Inside Claude:

```text
Run the team until a human decision is genuinely needed.
```

Claude should stay in this session, start bounded workers itself, re-read
GitHub after every child, run deterministic controller actions, and stop only
at a readiness gate, protected/ambiguous QA exception, or durable blocker. It
must not display a prompt for the human to carry elsewhere.

## 13. Live intake test

Only continue with a disposable Project.

Inside Claude:

```text
[role:analyst] Intake this disposable requirement:

Add a short page explaining the repository's development setup.
```

Before mutation, Claude should describe the intended result:

```text
create Issue
→ add to Project
→ Status Backlog
→ Role analyst
→ handoff to architect
→ structured Issue comment
```

After completion, verify manually:

- the Issue exists;
- it belongs to the configured Project;
- Status is `Backlog`;
- final Role is `architect`;
- the analyst-to-architect handoff comment exists;
- the Card was not marked Ready.

## 14. Live architect handoff test

Choose an architect-owned disposable Card:

```text
[role:architect] Author a small specification for issue #<number>.
```

Expected workflow:

1. verify Role is architect;
2. create `spec/issue-<number>-<slug>`;
3. write only specification or documentation files;
4. create one docs PR;
5. hand the Card from architect to Dev;
6. post a handoff comment containing the PR URL.

Verify:

- the PR is docs-only;
- Role remains architect until the PR exists;
- final Role is Dev;
- the handoff comment contains the PR URL.

Do not use an important repository for this first test.

## 15. Troubleshooting

### Skills do not appear

Confirm:

```powershell
git -C "C:\Users\User\Documents\intern\ITRI\agent-teams" branch --show-current
claude plugin validate "C:\Users\User\Documents\intern\ITRI\agent-teams"
```

Exit Claude completely, then restart with the quoted `--plugin-dir` path.

Verify that neither `--safe-mode` nor `--disable-slash-commands` was used.

### Plugin does not appear in `/plugin`

This is expected for a session-only `--plugin-dir` load. Check `/help` for the
four namespaced commands.

Use persistent installation only if it must appear in the Installed tab.

### Claude reports missing configuration

Run `producer_board.py init` from the consuming repository. Configuration is
repository-local.

### `doctor` reports that `gh` is missing

Install GitHub CLI and open a new terminal:

```powershell
winget install --id GitHub.cli
```

### `doctor` reports missing fields or options

Create the required single-select Status and Role fields on the disposable
Project. This MVP does not provision them automatically.

### Persistent installation loads an old version

Use direct development loading:

```powershell
claude --plugin-dir "C:\Users\User\Documents\intern\ITRI\agent-teams"
```

or remove and reinstall only
`agent-teams@agent-teams-local`.

## 16. Acceptance checklist

### Safe plugin verification

- [ ] source directory is on `mvp/producer-from-scratch`;
- [ ] `claude plugin validate .` passes;
- [ ] `/help` shows exactly ten skills;
- [ ] analyst routes to `intaking-requirement`;
- [ ] architect routes to `authoring-spec`;
- [ ] a returned `(Backlog, analyst)` Card routes to `clarifying-card`;
- [ ] Lead routes to `dispatching-work`;
- [ ] "work on #N" routes to `consuming-card`;
- [ ] "verify #N" routes to `verifying-delivery`;
- [ ] a request naming no Card does NOT route to a Consumer skill;
- [ ] no-tool prompts cause no mutations.


- [ ] worker frontmatter has the `Skill` tool and no `skills:` preload list;
- [ ] every spawn action names exactly one qualified `skill`;
### Consumer verification (hermetic)

- [ ] `python -m unittest tests.test_git` passes -- two clones racing one Card
      produce exactly one winner, against real git;
- [ ] `python -m unittest tests.test_acceptance` passes -- every acceptance
      decision-table row and every protected category;
- [ ] `python -m unittest tests.test_consumer` passes;
- [ ] `grep -rE "superpowers:|gstack:/" skills/` returns nothing.

### Consumer verification (live, still unperformed)

Needs an authenticated `gh`, a disposable repository with branch protection and
required checks, and auto-merge enabled:

- [ ] `doctor` reports no `acceptance_problems`;
- [ ] one claim, one Pull Request, one verdict, one `accept`;
- [ ] an eligible delivery is monitored and automatically reconciles to `(Done, lead)`;
- [ ] a defect returns `(In Progress, dev)` on the same Pull Request;
- [ ] a protected-path change routes `(In Review, human)`;
- [ ] a push after a verdict makes `accept` refuse as stale.

### Optional persistent installation

- [ ] installed plugin version is `0.2.0`;
- [ ] plugin is enabled;
- [ ] `claude plugin list --json` contains no errors;
- [ ] commands remain available without `--plugin-dir`.

### Optional live board verification

- [ ] `doctor` passes;
- [ ] `next-actions` is read-only, deterministic, WIP-aware, and emits typed actions;
- [ ] intake creates a Backlog Card;
- [ ] intake ends with architect ownership;
- [ ] architect publishes the product spec directly on the current branch and records its exact commit;
- [ ] decomposed children inherit that structured spec record and need only a
  human Status change to `Ready`;
- [ ] the current session starts the Dev worker after human readiness;
- [ ] structured handoff comments exist.

For basic proof that the current agent-teams MVP works in Claude, only the
Safe plugin verification section is required.
