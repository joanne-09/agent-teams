# agent-teams runbook

**Rebuild the whole pipeline from nothing, in order, without asking anyone.**

This is written for someone who has never used `agent-teams` and has never used
Claude Code. It starts at "I have a laptop and an email address" and ends at "an
AI team shipped a change to my repository and I approved one thing".

Every part ends with a **Checkpoint**: a command to run and the output you
should see. If a checkpoint fails, stop there — later parts assume it passed.
Do not skip ahead to "make it work later"; almost every confusing failure in
this system is an earlier checkpoint that was never actually green.

Read [Part 0](#part-0--what-you-are-building) before typing anything. Ten
minutes there saves an hour in Part 6.

**Total time**: about 2 hours for a first run, of which roughly 40 minutes is
GitHub configuration you only do once per repository.

| Part | What it does | Time |
|---|---|---|
| [0](#part-0--what-you-are-building) | Understand the machine before you build it | 10 min |
| [1](#part-1--accounts-and-tools) | Accounts, Claude Code, Git, Python, GitHub CLI | 25 min |
| [2](#part-2--claude-code-for-absolute-beginners) | What a session, skill, subagent, and plugin are | 15 min |
| [3](#part-3--install-the-agent-teams-plugin) | Install the plugin | 10 min |
| [4](#part-4--prepare-the-github-side) | Repository, Project, fields, CI, branch protection | 40 min |
| [5](#part-5--configure-agent-teams) | `init`, `doctor`, and reading the config | 15 min |
| [6](#part-6--the-first-run-end-to-end) | Ship one Card, start to finish | 30 min |
| [7](#part-7--the-dashboard-optional) | Watch it run (optional) | 20 min |
| [8](#part-8--troubleshooting) | Every failure we actually hit | as needed |

---

## Part 0 — What you are building

### The one-sentence version

You are giving a **GitHub Project board** to a team of AI agents, and keeping
exactly one decision for yourself.

### Why a board, and not a chat

Every AI coding tool loses its memory eventually. Conversations get compacted,
sessions end, laptops sleep. So `agent-teams` never stores the state of the work
in a conversation. It stores it in **GitHub**, where it survives everything:

- **A Card** is a GitHub Issue.
- **Where the work is** is the Issue's `Status` field: `Backlog`, `Ready`,
  `In Progress`, `Blocked`, `In Review`, `Done`.
- **Whose turn it is** is the Issue's `Role` field: `analyst`, `architect`,
  `dev`, `qa`, `lead`, `human`.

Those two fields are independent on purpose. "Where the work is" and "who has
it" are different questions, and a system that merges them cannot express
"finished, waiting for a person".

If you want to know what is happening, look at the board. **Not** at what an
agent said. An agent claiming "I'm done" proves nothing; the Issue moving to
`Done` is the proof. That distinction is the core of the whole design.

### The seats

| Seat | What it does |
|---|---|
| `analyst` | Asks you clarifying questions until the requirement is testable |
| `architect` | Writes the specification, splits big work into small Cards |
| `dev` | Claims one Card, writes tests first, implements, opens one Pull Request |
| `qa` | Independently reviews that exact Pull Request and publishes evidence |
| `lead` | Coordinates: reads the board, spawns the others, reconciles results |
| `human` | You |

They are separate AI agents, not one agent wearing hats. A `dev` agent
literally cannot mark its own work as reviewed — the permission check refuses it
before any network call happens.

### Where you come in

The routine path has **one mandatory human decision**:

> **Readiness.** After the architect writes a specification, you read it and
> change the Card's Status from `Backlog` to `Ready`. That is the whole
> decision.

Everything after that — claiming, implementing, reviewing, merging, closing —
happens without you, unless something unusual comes up.

Two other gates exist but do not fire on the routine path:

- **Spec merge** — only if you configure specifications to arrive as Pull
  Requests instead of direct commits.
- **QA exception** — only when a change touches something protected (CI config,
  authentication, the policy code itself) or QA is genuinely unsure. Then a
  person decides.

### The shape of one Card's life

```text
you say what you want
        ↓
   analyst asks questions until it is testable
        ↓
   architect writes docs/specs/card-N-*.md and commits it
        ↓
┌───────────────────────────────────────────┐
│  YOU: read the spec, set Status = Ready   │  ← the one gate
└───────────────────────────────────────────┘
        ↓
   dev claims the Card (a Git branch is the lock), writes tests, implements,
        opens one Pull Request
        ↓
   qa reviews that exact commit, drives the UI in a browser if it is user-facing,
        publishes structured evidence
        ↓
   policy — not QA — decides:
        eligible  → auto-merge → Card becomes Done
        defect    → back to dev, same branch, same PR
        protected → a person decides
```

### The one rule that explains all the strange parts

**Evidence must be checkable, or it does not count.**

You will meet this rule repeatedly and it will occasionally feel pedantic:

- QA cannot write "tests look good". It must name a test, break the code, and
  record which named test failed.
- QA cannot write "I clicked around, seemed fine". If the change touches the
  user interface, it must list the flows it drove, the garbage input it typed
  into each field, and what the browser console said.
- A merge never happens because an agent said the work was finished. It happens
  because a specific commit passed named CI checks.

This exists because the failure mode of AI agents is not refusing to work — it
is *reporting success convincingly*. Every rule that looks bureaucratic here is
closing a specific hole where that happened.

---

## Part 1 — Accounts and tools

You need five things. Do them in order.

### 1.1 A GitHub account

If you have one, skip this. Otherwise create one at
<https://github.com/signup>.

You need a real account, not an organization — the board and the repository can
live under your personal account.

### 1.2 A Claude account with Claude Code access

Sign in at <https://claude.ai>. Claude Code is included with Pro and Max
subscriptions; there is also an API-key route if your team pays per token.

> **If your team runs a different model** (the summer 2026 demos used GLM-5.2
> through an Ollama-compatible service), you still install Claude Code the same
> way — it is the harness, and the model behind it is configuration. There is
> one extra setting you will need; see [8.9](#89-most-skills-are-missing-from-a-non-claude-model).

### 1.3 Install Claude Code

The native installer is the current route. It needs no Node.js.

**Windows (PowerShell):**

```powershell
irm https://claude.ai/install.ps1 | iex
```

**macOS / Linux:**

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

It installs to `~/.local/bin/claude`. If your shell cannot find `claude`
afterwards, close and reopen the terminal — the installer adds that directory
to `PATH` and existing terminals do not pick it up.

Now log in:

```bash
claude
```

The first launch opens a browser to authenticate. Once you see the prompt, type
`/exit` to leave.

> **Checkpoint 1.3**
> ```bash
> claude --version
> ```
> Expect `2.1.x (Claude Code)` or newer. **This runbook was verified against
> 2.1.247.** Anything below 2.1.206 lacks the agent-to-agent messaging the QA
> seat uses; the system still works, it just loses the QA browser split.

### 1.4 Git and Python

`agent-teams` uses the Python standard library only. There is nothing to
`pip install`, no virtual environment, no `requirements.txt`.

- **Git**: <https://git-scm.com/downloads>. Version 2.30 or newer.
- **Python**: <https://www.python.org/downloads/>. Version 3.9 or newer.
  On Windows, tick **"Add python.exe to PATH"** in the installer — forgetting
  this is the single most common Part 1 failure.

> **Checkpoint 1.4**
> ```bash
> git --version
> python --version
> ```
> Expect `git version 2.30+` and `Python 3.9+`.
> On macOS/Linux you may need `python3` instead of `python`. If so, use
> `python3` everywhere in this runbook.

### 1.5 GitHub CLI, with the right permissions

This one has a trap, so read the whole section before running anything.

Install from <https://cli.github.com/>, then:

```bash
gh auth login
```

Answer: **GitHub.com** → **HTTPS** → **Login with a web browser**. Copy the
one-time code, paste it in the browser, approve.

**Now the trap.** The default login does *not* grant access to GitHub Projects.
Projects v2 is a separate API with a separate permission scope, and without it
every board read fails with a confusing message about missing fields. Add it:

```bash
gh auth refresh -s project -s read:project
```

This reopens the browser for a second approval. It is not optional.

> **Checkpoint 1.5**
> ```bash
> gh auth status
> ```
> Expect `✓ Logged in to github.com` **and** a `Token scopes:` line that
> includes `project`. If `project` is missing, run the `gh auth refresh`
> command again and make sure you clicked approve in the browser.

---

## Part 2 — Claude Code for absolute beginners

Skip this part only if you have driven Claude Code before. Everything here is
assumed knowledge in Part 6.

### 2.1 What it is

Claude Code is an AI assistant that runs **in your terminal** and can actually
do things — read your files, edit them, run commands, use `git`. It is not a
chat window that suggests code for you to copy. It has hands.

Start it inside a project folder:

```bash
cd path/to/your/project
claude
```

You get a prompt. Type in plain language. Type `/exit` to leave.

### 2.2 The five things you need to recognise

**Session.** One `claude` run. It remembers the conversation until you exit.
When a conversation gets very long, older parts are automatically summarised —
this is called **compaction**, and it is why `agent-teams` keeps all real state
in GitHub instead of in the conversation.

**Permission prompt.** Before Claude does anything consequential — editing a
file, running a command — it asks. You approve once, or approve a category for
the session. **Read these.** They are your last checkpoint before something
irreversible.

**Skill.** A packaged procedure Claude loads on demand. `agent-teams` ships ten
of them (`intaking-requirement`, `authoring-spec`, `verifying-delivery`, …).
You do not invoke them by name — you say "brief me" or "we need CSV export" and
the right one loads. Loading is lazy on purpose: a session that pre-loaded all
ten would waste most of its context on procedures it will not use.

**Subagent.** A separate Claude with its own fresh context, given one job. This
is the whole point of `agent-teams`: the `dev` agent and the `qa` agent are
different subagents, so QA reviewing dev's work is genuinely a second opinion
rather than the same context marking its own homework.

**Plugin.** A bundle of skills and subagents you install once.
`agent-teams` is a plugin.

### 2.3 Controls worth knowing before Part 6

| You want to | Do this |
|---|---|
| Stop it, right now | `Esc` — interrupts immediately, keeps the session |
| Stop it and everything it spawned | `Esc` twice |
| Leave | `/exit` |
| See what plugins are loaded | `/plugin` |
| Undo the last change | Ask: "undo that" — but prefer `git` for anything real |
| See the cost so far | `/cost` |

**During a long `agent-teams` run, nothing appearing on screen is normal.** A
`dev` subagent can work for several minutes silently. Look at the GitHub board,
not the terminal, to know whether progress is happening.

### 2.4 What "the coordinator" means

When you say "start the team", the session you are sitting in becomes the
**coordinator**. It reads the board, spawns worker subagents one Card-stage at a
time, waits for them, re-reads the board, and continues.

Two consequences that surprise people:

- **You do not open a second terminal.** Everything happens in the one session.
- **Closing that terminal stops the run.** Nothing is lost — all state is in
  GitHub — but nothing continues either. Reopen and say "continue the team".

---

## Part 3 — Install the agent-teams plugin

### 3.1 Get the code

```bash
cd ~/projects            # or wherever you keep things
git clone <THE-AGENT-TEAMS-REPO-URL> agent-teams
cd agent-teams
```

> Replace `<THE-AGENT-TEAMS-REPO-URL>` with the actual URL from whoever handed
> you this runbook. Keep the folder somewhere permanent — Claude Code will load
> the plugin from this path every time.

Note the absolute path; you will paste it repeatedly:

```bash
pwd            # macOS / Linux
```
```powershell
(Get-Location).Path    # Windows PowerShell
```

### 3.2 Check the code is healthy before trusting it

```bash
python -m unittest discover -s tests -p "test_*.py"
```

Takes about 60 seconds. Nothing to install first.

> **Checkpoint 3.2**
> Expect the last two lines to be a count and `OK`:
> ```text
> Ran 517 tests in 62.519s
> OK
> ```
> The exact number grows over time; what matters is `OK` and no `FAILED`.
> If tests fail here, stop. Do not configure a real repository against a broken
> checkout — you will spend hours blaming GitHub for a local problem.

### 3.3 Two ways to load the plugin

**Option A — per-run flag (recommended while learning).** Nothing is installed;
you point at the folder each time:

```bash
claude --plugin-dir /absolute/path/to/agent-teams
```

Easy to reason about, easy to undo, and you always run exactly what is in the
folder. Use this for your first run.

**Option B — install it permanently.** Available in every repository without
the flag:

```bash
claude plugin marketplace add /absolute/path/to/agent-teams --scope user
claude plugin install agent-teams@agent-teams --scope user
```

Two known annoyances with Option B, both real:

- **It copies the entire folder**, including anything large that is
  `.gitignore`d. If the repository contains a built slide deck with
  `node_modules`, that is hundreds of megabytes. Check the folder size first.
- **`claude plugin update` does nothing while the version string is
  unchanged.** After pulling new code, uninstall and reinstall, or you will be
  running yesterday's plugin while reading today's code and slowly losing your
  mind.

### 3.4 Confirm it loaded

Start a session with the plugin:

```bash
claude --plugin-dir /absolute/path/to/agent-teams
```

Inside the session, type:

```text
/plugin
```

> **Checkpoint 3.4**
> `agent-teams` appears in the list, enabled, with no errors.
> Then ask it, in plain language: `what agent-teams skills do you have?`
> It should be able to name several — `briefing-board`, `intaking-requirement`,
> `verifying-delivery` among them. If it cannot see any, see
> [8.9](#89-most-skills-are-missing-from-a-non-claude-model).

Type `/exit` for now.

---

## Part 4 — Prepare the GitHub side

This is the longest part and the one where mistakes hide. Every step has a
checkpoint; use them.

You are configuring the **target repository** — the one whose code the AI team
will write. This is *not* the `agent-teams` folder from Part 3. Keep the two
clearly separate in your head; conflating them is a common early mistake.

### 4.1 Create the target repository

```bash
gh repo create my-team-project --private --clone
cd my-team-project
```

It must have at least one commit, or branch protection cannot be configured:

```bash
echo "# my-team-project" > README.md
git add README.md
git commit -m "Initial commit"
git push -u origin main
```

> **Checkpoint 4.1**
> ```bash
> gh repo view --json nameWithOwner,defaultBranchRef
> ```
> Expect your `OWNER/REPO` and a default branch (usually `main`).

### 4.2 Create the Project board

GitHub Projects v2 boards are created in the web UI:

1. Go to `https://github.com/users/YOUR-USERNAME/projects`
2. **New project** → **Table** → name it → **Create**
3. Look at the URL: `.../projects/3` — **the number at the end is your project
   number.** Write it down. It is not the repository number and not an Issue
   number, and mixing these up is a classic Part 5 failure.

Now link the repository to the board: in the project, **⋯** (top right) →
**Settings** → **Manage access** is not it — instead use the project's
**+ Add item** → search your repo once, which associates them. Simpler: it will
associate automatically the first time `agent-teams` adds a Card.

### 4.3 Create the two fields — exact values matter

This is the highest-risk step in the entire runbook. The option names must
match **exactly**: lowercase for Role, capitalised as shown for Status. A field
called `Roles`, or an option called `Dev` instead of `dev`, fails later with a
message that does not obviously point back here.

**The `Status` field.** A default board already has one. Open it
(**⋯** on the column header → **Edit field**) and make its options exactly:

```text
Backlog
Ready
In Progress
Blocked
In Review
Done
```

Delete or rename anything else (`Todo`, `In review` with a lowercase r, and so
on). GitHub's defaults are close but not identical, so do not assume.

**The `Role` field.** Create it: **+** at the right of the field headers →
**New field** → name it exactly `Role` → type **Single select** → options,
all lowercase:

```text
analyst
architect
dev
qa
lead
human
```

> **Checkpoint 4.3**
> There is no clean CLI check for this yet — `doctor` in Part 5 is the real
> test, and it will name any missing option precisely. For now, re-read both
> option lists against the screen, character by character. Capitalisation
> counts. It is worth the thirty seconds.

### 4.4 Add a CI check

Deterministic acceptance requires at least one named CI check to be green
before anything merges. **If you configure none, nothing ever merges
automatically** — every passing delivery is routed to the human exception lane
instead. That is a deliberate fail-closed design, not a bug, but it does mean
you must do this step.

Create `.github/workflows/ci.yml` in the target repository:

```yaml
name: ci

on:
  pull_request:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run tests
        run: |
          echo "replace this with your real test command"
```

The job is named `test`. **That exact string is what you will configure as a
required check**, so if you rename the job, rename it everywhere.

```bash
git add .github/workflows/ci.yml
git commit -m "Add CI workflow"
git push
```

> **Checkpoint 4.4**
> ```bash
> gh run list --limit 3
> ```
> Expect at least one run, concluding `success`. If it has not appeared after a
> minute, check the **Actions** tab in the browser — Actions is sometimes
> disabled by default on new private repositories.

### 4.5 Turn on auto-merge

```bash
gh api -X PATCH repos/:owner/:repo -f allow_auto_merge=true
```

> **Checkpoint 4.5**
> ```bash
> gh api repos/:owner/:repo --jq .allow_auto_merge
> ```
> Expect `true`.
>
> A note that cost us real time: `gh repo view` has **no** `autoMergeAllowed`
> field despite what older documentation suggests. Use the REST field above.

### 4.6 Protect the branch

Auto-merge without branch protection is dangerous: GitHub merges *immediately*
rather than waiting for the checks, so the guarantee you think you have is
empty. Protection is what makes "eligible" mean anything.

```bash
gh api -X PUT repos/:owner/:repo/branches/main/protection \
  --input - <<'JSON'
{
  "required_status_checks": { "strict": true, "contexts": ["test"] },
  "enforce_admins": false,
  "required_pull_request_reviews": null,
  "restrictions": null
}
JSON
```

`"contexts": ["test"]` must match the CI job name from 4.4.
`"strict": true` means a branch must be up to date with `main` before merging.

> **Checkpoint 4.6**
> ```bash
> gh api repos/:owner/:repo/branches/main/protection --jq '.required_status_checks.contexts'
> ```
> Expect `["test"]`.
>
> Branch protection on **private** repositories requires a paid plan. On a free
> private repo this call returns 403. Two options: make the repository public,
> or accept that every delivery goes to the human exception lane and you merge
> by hand. Do not simply skip it and expect automation to work.

---

## Part 5 — Configure agent-teams

### 5.1 Generate the config

From inside the **target repository**:

```bash
python /absolute/path/to/agent-teams/scripts/producer_board.py init \
  --repo OWNER/REPO \
  --project-owner OWNER \
  --project-number 3 \
  --required-check test
```

Windows PowerShell uses backticks for line continuation:

```powershell
python C:\path\to\agent-teams\scripts\producer_board.py init `
  --repo OWNER/REPO `
  --project-owner OWNER `
  --project-number 3 `
  --required-check test
```

- `--repo` — `OWNER/REPO`, exactly as GitHub shows it
- `--project-owner` — your username (or the organization that owns the board)
- `--project-number` — the number from the project URL in 4.2
- `--required-check` — the CI job name from 4.4. Repeat the flag for each check.

This writes `.agent-teams/config.json`.

> **Checkpoint 5.1**
> The command prints a JSON object beginning `{"ok": true, ...}`, and
> `.agent-teams/config.json` now exists. **Every command in this system prints
> one JSON envelope, and `"ok": true` is the only proof of success.** Get into
> the habit of looking for it.

### 5.2 Run `doctor` — the real test of Part 4

```bash
python /absolute/path/to/agent-teams/scripts/producer_board.py doctor
```

`doctor` checks GitHub access, that the Project exists, that both fields exist
with all their options, and that the merge preconditions hold. It reports
*every* problem at once rather than the first, so one run tells you everything
to fix.

> **Checkpoint 5.2**
> Expect `"ok": true` and, importantly, an **empty** `acceptance_problems`:
> ```json
> { "ok": true, "acceptance_problems": [], "statuses_validated": [...], ... }
> ```
> If `acceptance_problems` is non-empty, read it literally — it names the exact
> missing precondition. Common entries:
> - `required_checks is empty` → you skipped `--required-check` in 5.1
> - `auto-merge is not enabled` → redo 4.5
>
> If `doctor` fails outright, the message names the missing Status or Role
> option. Go back to 4.3 and fix the spelling.
>
> **Do not continue past this checkpoint.** Everything in Part 6 assumes it is
> green.

### 5.3 Understand what you can tune

Open `.agent-teams/config.json`. The full reference is
[CONFIGURATION.md](./CONFIGURATION.md); these are the ones you will actually
touch.

**Who merges what.** Two Pull Requests exist in this system and they are
configured separately — the names say which is which:

| Key | Values | Default | Meaning |
|---|---|---|---|
| `spec_pr_merge_mode` | `direct`, `manual` | `direct` | `direct`: the architect commits the spec straight to your branch, no PR. `manual`: it opens a spec PR and waits for you |
| `code_pr_merge_mode` | `automatic`, `manual` | `automatic` | `automatic`: an eligible delivery auto-merges. `manual`: you merge it |
| `code_pr_merge_method` | `squash`, `merge`, `rebase` | `squash` | How agent-teams closes the code PR when it does the merging |

> If you are reading older notes that mention `spec_merge_mode`, `merge_mode`,
> or `merge_method` — those are the previous names for these three. Old config
> files still load; the names are rewritten the first time the file is saved.

**Retries, per seat.** Each role can have its own retry budget, because they
fail differently — an architect waiting on a slow read and a QA worker bounced
by a rate limit do not want the same number of attempts:

```json
{
  "recovery": { "max_retries": 1, "initial_backoff_seconds": 5.0 },
  "roles": {
    "qa": { "recovery": { "max_retries": 3 } }
  }
}
```

QA now retries three times, waiting 5s then 10s then 20s. Everyone else retries
once. A role inherits every field it does not restate, so you never have to copy
the whole block.

Valid seats: `analyst`, `architect`, `dev`, `qa`, `lead`, `merge_master`. Only
`architect` may set `spec_pr_merge_mode`; only `merge_master` may set the two
`code_pr_*` keys. Putting a key under the wrong seat is a validation error that
names the correct owner — it is never silently ignored.

**Other keys worth knowing:**

| Key | Default | Meaning |
|---|---|---|
| `wip_limit` | `5` | How many Cards may be active at once |
| `monitor_poll_seconds` | `30` | How often the coordinator re-checks GitHub |
| `ui_paths` | `[]` | Extra globs marking user-facing files; these force QA to produce browser evidence |
| `protected_paths` | 7 categories | Changes that must go to a human. You may add, never remove |

**Changes apply immediately.** Edit the file mid-run and the next command picks
it up; no restart. A command already running finishes with the settings it
started with, so a mid-flight edit never mixes two configurations into one
operation.

---

## Part 6 — The first run, end to end

Start a session **in the target repository**, with the plugin loaded:

```bash
cd path/to/my-team-project
claude --plugin-dir /absolute/path/to/agent-teams
```

### 6.1 Orient

Type:

```text
brief me
```

This is read-only and always safe to repeat. It reports the board state and
anything waiting on a human.

> **Checkpoint 6.1**
> You get a briefing, not an error. An empty board is correct at this point.

### 6.2 Ask for something

Say what you want in plain language:

```text
we need a page that lists our stores and lets people search by name
```

The **analyst** will ask you clarifying questions. Answer them properly — this
is the cheapest point in the entire pipeline to correct a misunderstanding, and
a vague answer here becomes a wrong specification, then a wrong implementation,
then a wasted QA cycle.

It ends by creating one Card at `(Backlog, architect)`.

> **Checkpoint 6.2**
> Open your Project board in the browser. **One new Issue is there**, Status
> `Backlog`, Role `architect`. If it is not on the board, the Project number in
> 5.1 is wrong.

### 6.3 Let the architect write the spec

```text
start the team
```

The session becomes the coordinator. It spawns an `architect` subagent, which
writes a Markdown specification under `docs/`, commits it to your current
branch, and records the exact commit on the Card.

Then it stops and tells you the Card is waiting for you.

> **Checkpoint 6.3**
> ```bash
> git log --oneline -3
> ls docs/specs/
> ```
> Expect a new commit and a `card-N-*.md` file. Read it — this is the moment
> the specification is cheap to fix.

### 6.4 The one human gate

Read the spec. If it is right, open the board and change that Card's Status
from `Backlog` to `Ready`.

**Do it in the GitHub UI, with your own hands.** This is deliberate: the check
that enforces it refuses `human` authority from inside any Claude Code session,
so asking the agent to promote the Card will be rejected by design. That
refusal is the gate working, not a bug.

If you prefer a terminal, run it **from your own shell, not from inside the
Claude session**:

```bash
python /absolute/path/to/agent-teams/scripts/producer_board.py promote N
```

> **Checkpoint 6.4**
> The Card shows Status `Ready` on the board.

### 6.5 Let it run

Back in the Claude session:

```text
continue the team
```

Now it goes. Expect, without further input from you:

1. `dev` claims the Card — a remote Git branch is the lock, so two workers can
   never claim the same Card
2. `dev` writes failing tests first, then implements until they pass
3. `dev` opens one Pull Request
4. CI runs
5. `qa` reviews that exact commit — and if the change touched anything
   user-facing, a separate browser agent drives the actual UI, types garbage
   into every input field, and reads the console
6. Policy decides the route: merge, back to dev, or ask you
7. On merge, the Card reconciles to `Done` and the Issue closes

This takes several minutes and is mostly silent. **Watch the board, not the
terminal.**

If QA finds a defect, the Card goes back to `dev` on the same branch and the
same Pull Request, and the loop repeats. No human action is needed for that —
it is the system working.

> **Checkpoint 6.5**
> ```bash
> gh pr list --state all --limit 5
> gh issue list --state all --limit 5
> ```
> Expect a merged Pull Request and a closed Issue. On the board, the Card is
> `Done` with Role `lead`.
>
> **If you reached here, the pipeline is rebuilt and working.**

### 6.6 If it stops and asks you something

Two gates can fire. Both print exactly what they need.

**`manual_merge`** — only if you set `code_pr_merge_mode: manual`. Merge the
named Pull Request in GitHub. Do not touch the Card; the coordinator sees the
merge and reconciles it.

**`qa_exception`** — the change touched a protected path, or QA was genuinely
unsure. Read the evidence on the Issue, then, **from your own terminal**:

```bash
python /absolute/path/to/agent-teams/scripts/producer_board.py approve-exception N
```

This verifies the reviewed commit has not moved since QA looked at it, merges,
and reconciles. If you disagree with the change instead, say so on the Issue and
hand it back to `dev`.

### 6.7 Stopping and resuming

Close the terminal whenever you like. Nothing is lost — all state is in GitHub.

To pick up later:

```bash
cd path/to/my-team-project
claude --plugin-dir /absolute/path/to/agent-teams
```
```text
brief me
continue the team
```

Half-finished work resumes from its claim branch. A `dev` worker interrupted
mid-implementation continues on the same branch rather than starting again.

---

## Part 7 — The dashboard (optional)

A web dashboard that watches a run: which agents are alive, what they are
doing, what it costs, and the full conversation of every subagent. It is a
**viewer plus a config editor** — nothing in Parts 1–6 depends on it, and the
pipeline runs identically without it.

It is a fork of the open-source **Claude Code Agent Monitor**
(`hoangsonww/Claude-Code-Agent-Monitor`) with tabs added for this project.

### 7.1 Install and run

```bash
cd ~/projects
git clone <THE-DASHBOARD-REPO-URL> agent-teams-dashboard
cd agent-teams-dashboard
npm install
```

The root install pulls the React client's dependencies too, so one `npm
install` is enough. It takes a few minutes.

```bash
npm start
```

> **Checkpoint 7.1**
> The console prints a local URL. Open **<http://localhost:4820>**.
> If that port is busy, set `DASHBOARD_PORT` and restart.
> If it says a dashboard is already running, it is — open the URL it names
> rather than starting a second one.

It reads the JSONL transcripts Claude Code already writes, so it works on runs
that already finished, not only live ones.

### 7.2 What each tab shows

| Tab | Content |
|---|---|
| Dashboard | Sessions, active agents, cost, token usage |
| Sessions | Every session with its history; open one to read it |
| Kanban Board | Each agent as working / waiting / complete. **Not** the GitHub Projects board — this is agent state |
| Activity Feed | Live: bash commands run, subagents spawned |
| Workflows | The spawn tree — which workers the lead created, and which helpers they created |
| Analytics | Usage and cost over time |
| CC Config | The skills and subagents Claude Code has loaded, plugin ones marked |
| Agent Teams | A form that edits `.agent-teams/config.json` |
| Run | Start a Claude Code session from the browser |

The per-subagent conversation log is the genuinely useful part. When a QA
worker reaches a conclusion you disagree with, you can read how it got there
instead of inferring it from the outcome.

### 7.3 The Agent Teams config tab

It never re-implements the plugin's validation rules. Every read and write goes
through the plugin's own Python `Config` class, so what the dashboard saves is
exactly what a coordinator session would accept, and a rejection shows the
plugin's own error message verbatim.

Point it at your target repository, and note:

- **Unset fields are greyed with a `default` chip.** That is not the same as
  the value being zero — it means the file does not set it, and the plugin's
  default applies.
- **Per-role fields show what they inherit.** A `roles.qa.recovery.max_retries`
  row greys the *top-level* `recovery.max_retries` value, and its dropdowns
  carry an explicit `inherit` option so an override can be cleared again.
- **Advanced is hidden by default.** Toggle it for the tuning fields.
- **Raw JSON mode** covers what the form does not — `protected_paths`,
  `status_overrides`, and a role's full backoff schedule.
- **Changes apply at the next command boundary.** No restart; the previous file
  is backed up on every save.

### 7.4 Verify the pieces fit

The dashboard talks to the plugin through a Python bridge that needs to know
where the plugin lives. Its own test suite exercises that path end to end:

```bash
AGENT_TEAMS_SCRIPTS=/absolute/path/to/agent-teams/scripts AGENT_TEAMS_PYTHON=python   node --test server/__tests__/agent-teams-config.test.js
```

> **Checkpoint 7.4**
> Expect `# pass 9` and `# fail 0`.
>
> If it reports `SKIP agent-teams package or python3 not available`, the bridge
> could not find one of the two. `AGENT_TEAMS_SCRIPTS` must point at the
> directory *containing* `agent_teams/` — that is `.../agent-teams/scripts`,
> not the repository root. On Windows, `AGENT_TEAMS_PYTHON=python` is required
> because the default is `python3`, which Windows installs do not provide.
>
> A skip is not a pass. It means nothing was tested.

Full suites, if you want them:

```bash
npm run test:server      # expect 0 failures
npm run test:client      # expect 0 failures
```

### 7.5 One thing to keep an eye on

The QA seat spawns helpers beneath itself, which makes the agent tree three
levels deep: coordinator → `qa-worker` → browser worker and review passes.

A bug in exactly this area was fixed in August 2026 — a nested helper finishing
used to mark the *wrong* worker complete, about 35 seconds after it started, on
every worker in a run. The fix is verified against the deeper tree the QA split
creates, and there is a regression test for it. But attribution among several
untyped helpers running at once still falls back to "oldest one working", so if
the Workflows tab shows review passes completing in an odd order, that is the
known soft edge rather than a new bug. A seat worker completing early is not,
and would be worth reporting.

## Part 8 — Troubleshooting

Every entry below is a failure this project actually hit.

### 8.1 `gh: command not found`, or Projects calls fail

Install the GitHub CLI, then check the scope:

```bash
gh auth status
```

The `Token scopes:` line must include `project`. If not:

```bash
gh auth refresh -s project -s read:project
```

Projects v2 is a separate API from Issues. A token that reads Issues perfectly
may have no board access at all, and the resulting error talks about missing
fields rather than missing permission.

### 8.2 `doctor` says a Status or Role option is missing

The names must match exactly, including case. Go back to
[4.3](#43-create-the-two-fields--exact-values-matter) and compare
character by character.

If your organization already uses different column names and you cannot change
them, map them instead of renaming — in `.agent-teams/config.json`:

```json
{
  "backlog_status": "Todo",
  "ready_status": "Approved",
  "status_overrides": { "In Progress": "Doing", "In Review": "Reviewing" }
}
```

`Role` option names **cannot** be remapped. Those six must exist as written.

### 8.3 Everything passes QA but nothing ever merges

Look at `doctor`'s `acceptance_problems`. Almost always one of:

- **`required_checks` is empty.** This fails closed on purpose: with no CI
  baseline, a passing QA verdict routes to the human exception lane instead of
  merging. Add `--required-check` and re-run `init`, or edit the config.
- **Auto-merge is off.** Redo [4.5](#45-turn-on-auto-merge).
- **Branch protection is missing.** Redo [4.6](#46-protect-the-branch). Note
  that without protection, auto-merge merges *immediately* without waiting for
  checks — so "it merged" is not evidence that this is configured correctly.

### 8.4 "The agent said it finished, but the board did not move"

Believe the board. A subagent's closing message is not evidence; only durable
GitHub state is. Run `brief me` or:

```bash
python /path/to/agent-teams/scripts/producer_board.py next-actions
```

This is read-only and shows what the system thinks is true, which is what
actually governs the next step.

### 8.5 `promote` or `approve-exception` is refused

Correct behaviour. Human authority cannot be exercised from inside a Claude
Code session — the command detects the session environment and refuses.

Run it in your own terminal, in a window where Claude is not running. Or just
change the Status in the GitHub UI, which is the intended route.

This exists because it happened for real: a lead agent ran `promote` without a
role flag, inherited the human default, and walked straight through the one gate
the system has.

### 8.6 A claim seems stuck

```bash
python /path/to/agent-teams/scripts/producer_board.py worktree-status N
```

Interrupted work resumes automatically — normally you do nothing. `release-claim`
exists but is emergency cleanup, not routine: it destroys the branch, and the
usual reason work looks stuck is that nobody has run `continue the team` since
the session ended.

### 8.7 GitHub rate limits during a run

The board is read through a lean GraphQL query costing one rate-limit point per
*page*. An older approach cost roughly one point per *item* and exhausted two
5000-point hourly budgets in a single run.

If you hit limits anyway, raise `monitor_poll_seconds` from `30`. Polling is
how the coordinator notices merges completing — the same way a person runs
`git pull` each morning — so the cost scales with how impatient it is.

### 8.8 QA refuses to publish its verdict

Read the refusal; it lists every problem at once. The common ones are all the
same rule in different clothes — evidence must be checkable:

- **`test_strength` has no `falsified_by`.** Coverage proves a line *ran*, not
  that its behaviour was *asserted*. QA must break the implementation and name
  the test that failed.
- **`browser_evidence` missing.** The change touched a user-facing path (see
  `ui_paths`), so a pass needs recorded browser flows, invalid-input cases, and
  the console state.
- **`changed_files` is incomplete.** An unenumerated file is an unreviewed file.
- **`blind_spots` is not empty.** Unresolved uncertainty is a `blocked` verdict,
  never a qualified pass.

None of these is a code defect, so none of them sends the Card back to `dev`.
The fix is for QA to re-review the current commit and publish again.

### 8.9 Most skills are missing from a non-Claude model

**Symptom:** plain-language routing silently stops working. "brief me" does
nothing useful, and the model appears not to know the plugin exists.

**Cause:** Claude Code budgets the skill list it shows the model as a fraction
of the assumed context window. A model it does not recognise — anything served
through Ollama, for example — is assumed to have a 200k window, and the default
1% budget drops most of the skill descriptions. Measured in August 2026: **8 of
10 `agent-teams` skills were silently omitted.**

**Fix.** In the `settings.json` of the config directory you launch with:

```json
{
  "skillListingBudgetFraction": 0.05,
  "skillListingMaxDescChars": 2048
}
```

Or give the model a name with an explicit context suffix, such as
`glm-5.2:cloud[1m]`.

### 8.10 A model that cannot accept images

Some models reject image input. QA's screenshot step then fails with an HTTP 400
saying the model does not support images.

This is handled: the coordinator noticed it live, and when it re-spawned the QA
worker it told it not to touch images. No human intervened. If it happens
repeatedly, either raise that role's `max_retries` in `roles`, or use a model
that accepts images for the QA seat.

### 8.11 Development worktrees colliding with claim worktrees

`../.worktrees` is the default `workspace` for claim worktrees
(`claim-<n>-<slug>`). If you also keep your own development worktrees there, do
not reuse that naming pattern, or change `workspace` in the config.

### 8.12 Getting help from the system itself

In a session with the plugin loaded, ask in plain language:

```text
what is waiting on me?
why is card 12 blocked?
show me the QA queue
```

And the read-only commands are always safe to run directly:

```bash
producer_board.py brief
producer_board.py next-actions
producer_board.py worktree-status
```

---

## Appendix A — Command reference

Every command prints one JSON envelope. **`"ok": true` is the only proof of
success.** A partial failure lists exactly which steps completed, so recovery
never has to guess.

```text
producer_board.py init --repo OWNER/REPO --project-owner OWNER --project-number N
producer_board.py doctor
producer_board.py brief [--format text|json]
producer_board.py next-actions [ISSUE]
producer_board.py bootstrap --role ROLE

producer_board.py intake --title T (--body B | --body-file F)
producer_board.py clarify ISSUE (--note N | --note-file F)
producer_board.py publish-spec ISSUE --path docs/...md
producer_board.py decompose PARENT --children F.json
producer_board.py promote ISSUE                      # human only
producer_board.py finalize-spec-merge ISSUE

producer_board.py claim ISSUE --acting-role dev|architect
producer_board.py submit-pr ISSUE --title T --body-file F
producer_board.py verdict ISSUE --evidence-file F
producer_board.py accept ISSUE
producer_board.py refresh-verification ISSUE
producer_board.py reconcile-done ISSUE
producer_board.py approve-exception ISSUE            # human only
producer_board.py worktree-status [ISSUE]
```

You will rarely type most of these. Plain language drives them.

Note what is deliberately absent: **no command takes a Pull Request to merge.**
QA cannot choose its own route, and no seat can request a merge of its choosing.

## Appendix B — Config quick reference

Full detail in [CONFIGURATION.md](./CONFIGURATION.md).

| Key | Default | Change it when |
|---|---|---|
| `required_checks` | `[]` | Always — empty means nothing ever auto-merges |
| `spec_pr_merge_mode` | `direct` | You want to review specs as Pull Requests |
| `code_pr_merge_mode` | `automatic` | You want to merge code yourself |
| `code_pr_merge_method` | `squash` | Your team prefers merge commits or rebase |
| `roles` | `{}` | One seat needs its own retry budget |
| `ui_paths` | `[]` | Your UI lives somewhere the defaults miss |
| `wip_limit` | `5` | Too much or too little runs at once |
| `monitor_poll_seconds` | `30` | You are hitting rate limits (raise it) |
| `protected_paths` | 7 categories | Something else in your repo needs a human |
| `workspace` | `../.worktrees` | It collides with your own worktrees |

## Appendix C — If you get stuck and need to hand it back

Collect these before asking:

1. `python /path/to/agent-teams/scripts/producer_board.py doctor` — full output
2. `python /path/to/agent-teams/scripts/producer_board.py next-actions` — full output
3. `gh auth status`
4. The Card number and a screenshot of its board row
5. Which **Checkpoint** in this runbook was the last one that passed

That last item is the most useful thing in the list and the one most often
missing.

---

## What this runbook does not cover

Stated plainly so nobody assumes coverage that is not here:

- **The dashboard is a separate repository** with its own lifecycle. Part 7
  was checked against its code and its test suite, but the two repositories can
  drift apart between updates.
- **The QA browser split has never run live.** The rules are enforced by 517
  passing tests, but no real run has yet shown a QA worker spawning its browser
  agent, that agent staying blind to the implementation diff, and Playwright
  driving the delivered application. The first real dataset run is the test.
- **Only Windows and GitHub.com are exercised.** macOS and Linux commands here
  are given in good faith; GitHub Enterprise is untested.
- **One repository, one board.** Multi-board and multi-repo setups are out of
  scope by design.

If you follow this and something is missing, the gap is a defect in this
document. Note where you stopped and what you had to work out yourself — that
note is worth more than the paragraph it replaces.
