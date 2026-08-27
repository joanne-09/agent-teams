# agent-teams configuration reference

`agent-teams` reads configuration from `.agent-teams/config.json` in the
consuming repository. Pass `--config PATH` before the CLI subcommand to use a
different file.

Create an initial file with:

```powershell
python C:\path\to\agent-teams\scripts\producer_board.py init `
  --repo OWNER/REPO `
  --project-owner OWNER `
  --project-number 1 `
  --required-check build `
  --required-check test
```

`init` exposes the identity, WIP, handoff, and required-check settings as
flags. Edit the generated JSON for the other supported settings, then run:

```powershell
python C:\path\to\agent-teams\scripts\producer_board.py doctor
```

`doctor` validates GitHub access, Project fields and options, and the
preconditions for deterministic acceptance. Configuration parsing reports all
validation errors together.

Every settings table below has the same five columns. **Values** is the full
set a field accepts, so the accepted input is readable without consulting the
validator. **Consumed by** names the seat that actually reads the setting,
which is what makes a per-role override meaningful: a setting no seat reads
under a given role is refused by the parser rather than silently ignored. A
setting read on every board access is marked *all seats*; `doctor` reads most
of them again to report preconditions.

## Live dashboard updates

A running coordinator does not cache the config file for the whole session.
Every `producer_board.py` invocation loads and validates a new snapshot.
Therefore a dashboard change applies at the next command boundary; no daemon or
session restart is required.

Every `next-actions`, `bootstrap`, and `doctor` result includes
`config_revision`, a SHA-256 identity of the normalized active snapshot. The
coordinator treats the newest `next-actions` result and its
`recovery_policy` as authoritative. When the revision changes, it discards
unstarted actions from the older plan and replans from live GitHub state.

One command already in progress finishes with the snapshot it loaded at start.
The following command uses the dashboard update. This prevents one mutation
from mixing settings halfway through its transaction.

Dashboard writers must replace the complete JSON file atomically:

1. validate the complete object with `Config.from_dict` or equivalent rules;
2. write a temporary file in the same directory; and
3. atomically replace `.agent-teams/config.json`.

`Config.write` implements that sequence. Do not truncate and rewrite the live
file in place, because a concurrent session could otherwise read partial JSON.
An invalid replacement is never ignored or merged with old values: the next
command refuses with all validation errors, and work can continue after the
dashboard saves a valid snapshot.

Durable in-flight state remains authoritative across a config change. A manual
specification PR already recorded on a Card must still be merged and finalized;
changing `spec_pr_merge_mode` does not retroactively bypass it. Existing claim
worktrees are resolved by their claim branch, so changing `workspace` affects
new claims while an active claim resumes at its original checkout. Exact-head
QA and merge evidence remains bound to the recorded head.

`config_revision` is runtime metadata, not a JSON setting.

## Complete example

This example includes every supported setting. `status_overrides` is omitted
from generated files when it is empty, but an empty object is valid.

```json
{
  "repo": "OWNER/REPO",
  "project_owner": "OWNER",
  "project_number": 1,
  "role_field": "Role",
  "status_field": "Status",
  "backlog_status": "Backlog",
  "ready_status": "Ready",
  "status_overrides": {},
  "dispatch_roles": [
    "architect",
    "dev",
    "qa"
  ],
  "wip_limit": 5,
  "handoff_cap": 6,
  "monitor_poll_seconds": 30,
  "board_page_limit": 100,
  "board_max_items": 2000,
  "recovery": {
    "max_retries": 1,
    "initial_backoff_seconds": 5.0,
    "backoff_multiplier": 2.0,
    "max_backoff_seconds": 60.0
  },
  "roles": {
    "architect": {
      "recovery": { "max_retries": 2 },
      "spec_pr_merge_mode": "direct"
    },
    "dev": { "recovery": { "max_retries": 1 } },
    "qa": { "recovery": { "max_retries": 3 } },
    "merge_master": {
      "code_pr_merge_mode": "automatic",
      "code_pr_merge_method": "squash"
    }
  },
  "workspace": "../.worktrees",
  "protected_paths": {
    "authority-and-policy": [
      "scripts/agent_teams/policy.py",
      "scripts/agent_teams/model.py"
    ],
    "acceptance-and-merge": [
      "scripts/agent_teams/git.py",
      "scripts/agent_teams/workflows.py"
    ],
    "github-workflows-and-credentials": [
      ".github/workflows/**",
      "**/*credential*"
    ],
    "dependencies-and-manifests": [
      ".claude-plugin/**",
      "**/package.json",
      "**/pyproject.toml",
      "**/requirements*.txt"
    ],
    "agent-instructions": [
      "skills/**",
      "CLAUDE.md",
      "AGENTS.md"
    ],
    "security-boundaries": [
      "**/auth/**",
      "**/*secret*"
    ],
    "architecture-and-design": [
      "docs/ARCHITECTURE.md",
      "docs/specs/**"
    ]
  },
  "required_checks": [
    "build",
    "test"
  ],
  "spec_pr_merge_mode": "direct",
  "code_pr_merge_mode": "automatic",
  "code_pr_merge_method": "squash",
  "ui_paths": [],
  "claim_ttl_hours": 72
}
```

`roles` and `ui_paths` are omitted from generated files when they are empty,
like `status_overrides`. Every role in `roles` is optional, and so is every
field inside one: what a role does not restate, it inherits.

## Repository and Project

| Setting | Values | Default | Consumed by | Meaning |
|---|---|---|---|---|
| `repo` | string in `OWNER/REPO` form | required | all seats, every command | GitHub repository the board Cards and Pull Requests live in. |
| `project_owner` | string | required | all seats, every command | User or organization that owns the GitHub Project. |
| `project_number` | positive integer | required | all seats, every command | GitHub Project number, not an Issue number or database ID. |
| `role_field` | non-empty string | `"Role"` | all seats, every board read and write | Project single-select field that stores the current seat. |
| `status_field` | non-empty string | `"Status"` | all seats, every board read and write | Project single-select field that stores lifecycle state. |
| `backlog_status` | non-empty string | `"Backlog"` | all seats, every board read and write | Project option used for canonical `Backlog`. |
| `ready_status` | non-empty string | `"Ready"` | all seats, every board read and write | Project option used for canonical `Ready`. |
| `status_overrides` | object; keys from `Backlog`, `Ready`, `In Progress`, `Blocked`, `In Review`, `Done` | `{}` | all seats, every board read and write | Maps other canonical Status names to repository-specific option names. |

The Role field must contain these exact option values:
`analyst`, `architect`, `dev`, `qa`, `lead`, and `human`. Role option
names cannot currently be remapped.

Valid `status_overrides` keys are `Backlog`, `Ready`, `In Progress`,
`Blocked`, `In Review`, and `Done`. `backlog_status` and `ready_status`
take precedence over overrides for those two states. For example:

```json
{
  "backlog_status": "Todo",
  "ready_status": "Approved",
  "status_overrides": {
    "In Progress": "Doing",
    "In Review": "Reviewing",
    "Done": "Completed"
  }
}
```

## Dispatch and lifecycle limits

| Setting | Values | Default | Consumed by | Meaning |
|---|---|---|---|---|
| `dispatch_roles` | non-empty array of unique Role tokens: `analyst`, `architect`, `dev`, `qa`, `lead` | `["architect", "dev", "qa"]` | lead (`next-actions`, `brief`) | Allow-list and priority order for Ready work. |
| `wip_limit` | non-negative integer | `5` | lead (`next-actions` admission) | Maximum active Cards admitted before new Ready work waits. Active means `In Progress` plus `In Review`. `0` disables the limit. |
| `handoff_cap` | non-negative integer | `6` | every seat that hands off; qa when returning a stale exception | Refuses another handoff once the Card already has this many handoffs. `0` disables the cap. |
| `workspace` | non-empty string beginning `..` | `"../.worktrees"` | dev (claim worktree), qa (review worktree) | Parent directory for claim worktrees. It must begin with `..` so worktrees stay outside the repository. |
| `claim_ttl_hours` | non-negative integer | `72` | lead and human (`worktree-status`) | Stale-claim observation threshold reported with claim/worktree status. It never authorizes automatic branch or worktree deletion. |

When WIP capacity is limited, earlier entries in `dispatch_roles` sort ahead of
later entries; Issue number is the deterministic tie-breaker.

## Specification and implementation merges

There are two Pull Requests in this system and they are governed separately.
The **spec** Pull Request carries a product specification and is the
architect's business. The **code** Pull Request carries an implementation and
is closed by the merge executor after QA. Each setting names its Pull Request,
so the pair can be told apart without reading this page:

| Setting | Values | Default | Consumed by | Meaning |
|---|---|---|---|---|
| `spec_pr_merge_mode` | `direct`, `manual` | `direct` | architect (`publish-spec`, and the planner's spec gate) | How a product specification reaches the base branch. |
| `code_pr_merge_mode` | `automatic`, `manual` | `automatic` | merge executor, inside `accept` | Who merges an eligible implementation Pull Request after QA. |
| `code_pr_merge_method` | `squash`, `merge`, `rebase` | `squash` | merge executor, inside `accept` and `approve-exception` | How agent-teams closes the code Pull Request when it issues the merge itself. |

These three were named `spec_merge_mode`, `merge_mode`, and `merge_method`
before 2026-08-21. The old names still load, so an existing repository keeps
working untouched; they are dropped the first time agent-teams writes the file.
See [Renamed settings](#renamed-settings).

### `spec_pr_merge_mode`

- `direct`: `publish-spec` commits and pushes only the requested
  `docs/**/*.md` file to the current branch. Architect shaping continues.
  The user's normal action is only the later Card Status change to `Ready`.
- `manual`: `publish-spec` creates a deterministic spec branch and Pull
  Request, then stops. The user merges the spec PR. The coordinator verifies
  the exact head and base, runs `finalize-spec-merge`, records the durable
  base-branch commit, and resumes architect shaping.

### `code_pr_merge_mode`

- `automatic`: an exact implementation head that passes deterministic
  acceptance is armed for GitHub auto-merge. The coordinator confirms the
  merge and reconciles the Card to `Done`.
- `manual`: the same eligible result creates a `manual_merge` human gate.
  The user merges the linked implementation PR; the coordinator confirms it
  and still performs `Done` reconciliation.

`code_pr_merge_method` does not control a merge performed manually in the
GitHub UI, including a manual specification PR. It applies when agent-teams
issues the merge command, including automated eligible merges and approved QA
exceptions.

Common combinations:

| Spec | Implementation | Human actions on the routine path |
|---|---|---|
| `direct` | `automatic` | Change the shaped Card to `Ready`. |
| `manual` | `automatic` | Merge the spec PR, then later change the Card to `Ready`. |
| `direct` | `manual` | Change the Card to `Ready`, then merge the eligible implementation PR. |
| `manual` | `manual` | Merge the spec PR, change the Card to `Ready`, then merge the eligible implementation PR. |

## Per-role overrides

Every setting above is a **default**. The optional `roles` block lets one role
depart from it, because architect, dev, QA, and the merge executor fail in
different ways: an architect stalled on a slow specification read and a QA
worker bounced by a rate limit do not want the same number of attempts.

| Setting | Values | Default | Consumed by | Meaning |
|---|---|---|---|---|
| `roles` | object keyed by seat; accepted seats and fields are in the table below | `{}` | the seat named by each key | Per-role overrides. Absent seats, and absent fields within a seat, inherit the top-level default. |

Valid seats and what each accepts:

| Seat | Accepts | Why |
|---|---|---|
| `analyst` | `recovery` | Clarification work; no merge authority. |
| `architect` | `recovery`, `spec_pr_merge_mode` | Publishes specifications. |
| `dev` | `recovery` | Implements; never merges. |
| `qa` | `recovery` | Reviews and runs `accept`; does not choose the route. |
| `lead` | `recovery` | Coordinates, dispatches, reconciles. |
| `merge_master` | `recovery`, `code_pr_merge_mode`, `code_pr_merge_method` | The merge executor. Not a board `Role`: it is the function inside `accept` and `approve-exception` that closes a code Pull Request, tunable on its own because the team lead asked for merge behaviour to be separable from whoever's process runs it. |

Two rules make this checkable rather than decorative:

- **A field under a seat that does not consume it is a validation error**, not
  a silent no-op. `roles.dev.spec_pr_merge_mode` refuses and names `architect`
  as the owner. The whole reason this block exists is that you could not tell
  which agent read which field, and a key that parses but does nothing is the
  worst version of that.
- **Overrides apply field by field.** A role that restates only `max_retries`
  keeps the backoff it did not mention. Values are resolved on every read, so
  editing a top-level default in the dashboard still reaches the roles that
  inherit it.

```json
{
  "recovery": { "max_retries": 1, "initial_backoff_seconds": 5.0 },
  "roles": {
    "qa": { "recovery": { "max_retries": 3 } }
  }
}
```

QA now retries three times at 5s, 10s, 20s. Every other seat retries once at
5s. Nothing else changed.

`next-actions` reports the whole surface as
`recovery_policy: {default, roles}`, listing every seat even where it only
inherits — an absent seat would leave the coordinator guessing between "same
as default" and "not applicable". Each returned action additionally carries
its own resolved `recovery`, so the retry budget travels with the work rather
than having to be matched back to a seat by the reader.

## Required checks and protected paths

| Setting | Values | Default | Consumed by | Meaning |
|---|---|---|---|---|
| `required_checks` | array of exact GitHub check names | `[]` | merge executor (`accept`), lead (`next-actions`), `doctor` | Checks that must conclude `SUCCESS` before an implementation is eligible. |
| `protected_paths` | object of glob arrays; built-in categories can be extended but never emptied or removed | built-in categories | qa (verdict classification), merge executor (`accept`) | Category-to-glob mapping that routes matching changes to the human QA-exception lane. |

An empty `required_checks` fails closed: no delivery becomes routinely
eligible, even with a passing QA verdict. Configure the same check names in
branch protection. `code_pr_merge_mode: automatic` additionally requires
repository auto-merge; `doctor` reports missing acceptance preconditions.

Repository `protected_paths` extend the built-in policy:

- patterns added to a built-in category are merged with its defaults;
- new categories are allowed;
- duplicate patterns are removed; and
- a built-in category cannot be emptied or removed through configuration.

Patterns use repository-relative paths. `*` matches within one path segment,
`**` spans directories, and `?` matches one non-separator character.

Example:

```json
{
  "protected_paths": {
    "security-boundaries": ["infra/**"],
    "billing": ["src/billing/**", "tests/billing/**"]
  }
}
```

The default security patterns still apply in this example.

## User-facing paths and browser evidence

| Setting | Values | Default | Consumed by | Meaning |
|---|---|---|---|---|
| `ui_paths` | array of glob patterns | `[]` | qa (`validate_verdict`, when the verdict is a `pass`) | Extra globs marking user-facing files. Merged with the built-in list; the defaults always apply. |

A QA `pass` whose changed files match any of these is refused unless the
verdict carries a `browser_evidence` block. This exists because QA was found
in the 2026-08-21 review to be mostly re-running the Developer's own unit
tests — work the Developer had already done — while the one bug the unit tests
missed (a blank page from an ES-module version mismatch) was caught by a
screenshot taken incidentally. Prose in a skill cannot make that check
standard; a validated field can.

Built-in patterns:

```text
**/*.html   **/*.htm    **/*.css   **/*.scss  **/*.sass  **/*.less
**/*.jsx    **/*.tsx    **/*.vue   **/*.svelte
**/components/**        **/pages/**           **/views/**
```

The block a pass must carry, and what each part must contain:

| Key | Required | Meaning |
|---|---|---|
| `flows` | at least one | Named journeys actually driven through the interface. Each needs a `name` and at least **two** `steps` — opening a page and screenshotting it is the incidental check this rule replaces. |
| `input_validation` | at least one | A field fed invalid or garbage input. Each case needs `field`, `input`, `expected`, and `actual`. |
| `console` | yes | Console state, including an `errors` list. An empty list is a finding; an absent one is a gap. |
| `tool`, `base_url`, `screenshot` | recommended | What drove the browser, against what, and where the image landed. |

Deliveries touching no user-facing path are unaffected: a mandatory browser
section on a parser change would be theatre. Only a `pass` carries the burden —
a `fail` already stops the delivery, and demanding full evidence to report a
defect would push a reviewer towards a pass.

The full document shape is in
`skills/verifying-delivery/references/verdict-schema.md`; the procedure for
producing it is `references/browser-pass.md`.

## Monitoring, pagination, and recovery

`recovery` is an object containing the four `recovery.*` settings listed
below.

| Setting | Values | Default | Consumed by | Meaning |
|---|---|---|---|---|
| `monitor_poll_seconds` | positive integer | `30` | lead (`next-actions`) | Coordinator wait before re-reading pending checks or merge state. |
| `board_page_limit` | positive integer | `100` | all seats, every board read | Project items requested per GraphQL page (GitHub caps a page at 100). |
| `board_max_items` | positive integer, at least `board_page_limit` | `2000` | all seats, every board read | Ceiling on Project items read in one command. |
| `recovery.max_retries` | non-negative integer | `1` | lead, retrying a spawned seat; all seats, retrying a transient GitHub read | Retries after the initial attempt. `0` disables retries. |
| `recovery.initial_backoff_seconds` | finite non-negative number | `5.0` | lead; all seats | Wait before retry 1. |
| `recovery.backoff_multiplier` | finite number at least `1.0` | `2.0` | lead; all seats | Exponential multiplier for later retry delays. |
| `recovery.max_backoff_seconds` | finite non-negative number, at least `recovery.initial_backoff_seconds` | `60.0` | lead; all seats | Per-retry delay cap. |

The retry delay before retry number *n* is:

```text
min(initial_backoff_seconds * backoff_multiplier^(n - 1),
    max_backoff_seconds)
```

The recovery schedule applies to unchanged coordinator actions and transient,
safe GitHub reads. Authentication, permission, protocol, and policy errors stop
immediately. GitHub mutations such as Issue creation, field edits, comments,
Pull Request creation, and merge commands are never blindly replayed.

Project reads follow GraphQL cursors `board_page_limit` items at a time using
a query that asks only for the Status and Role single-selects. That costs one
GitHub rate-limit point per page regardless of board size (`gh project
item-list` requests every field of every item and costs about one point per
item: 101 points for a 4-card board, measured 2026-08-21; two 5000-point hourly
budgets were exhausted in one live run). If the board still has a next page at
`board_max_items`, the command refuses to return a possibly truncated board.
Within one command the board is read once and reused until that command
itself mutates GitHub.

## Process environment

These are read from the environment of the process running `producer_board.py`,
not from the config file.

| Variable | Meaning |
|---|---|
| `AGENT_TEAMS_ACTING_ROLE` | Binds the process to one seat. Every command acts as that seat; a `--acting-role` that disagrees is refused (`SeatMismatch`). Dispatch actions carry it in their `env` field and the worker prompt tells the worker to set it. |
| `CLAUDECODE`, `CLAUDE_CODE_SESSION_ID` | Stamped by Claude Code on every shell it runs. When either is present, a command that claims or defaults to `human` is refused: human authority is exercised from the human's own terminal, never from a model session. This closed the live bypass where the lead ran `promote` without `--acting-role` and inherited the human default. It is a process-level floor, not a cryptographic one; the merge floor remains GitHub branch protection. |
| `AGENT_TEAMS_HUMAN_ORIGIN` | Names the surface a person opened a human gate from: `terminal` (the default, and what an absent variable means) or `dashboard`. It is a **provenance label, not an authority grant** -- the refusal above keys on the agent markers and never on this variable, so setting it inside an agent session buys nothing. What it earns is a durable trail: `promote` appends the surface to the handoff comment and `approve-exception` records it on the Card before it merges. Any value outside the closed vocabulary is refused, because the value reaches a GitHub comment. |

### Host settings for unrecognised models

Claude Code budgets the skill listing it shows the model as a fraction of the
assumed context window. A model it does not recognise (for example any model
served through Ollama) is assumed to have a 200k window, and the default 1 %
budget drops most plugin skill descriptions, so intent routing ("brief me",
"what's ready to work on?") silently fails. In the host's `settings.json`
(the `CLAUDE_CONFIG_DIR` you launch with) set:

```json
{
  "skillListingBudgetFraction": 0.05,
  "skillListingMaxDescChars": 2048
}
```

or use a model name with an explicit context suffix such as
`glm-5.2:cloud[1m]`. Verified 2026-08-21: with the defaults 8 of the 10
`agent-teams` skill descriptions were omitted from the listing.

## Renamed settings

Three merge settings were renamed on 2026-08-21. The old names could not be
told apart by reading them: neither `spec_merge_mode` nor `merge_mode` said
which Pull Request it governed, and `merge_method` read as though it belonged
to whichever of the two you had looked at last.

| Old name | Current name |
|---|---|
| `spec_merge_mode` | `spec_pr_merge_mode` |
| `merge_mode` | `code_pr_merge_mode` |
| `merge_method` | `code_pr_merge_method` |

Old names still load, with the same values and the same meaning, so no
consuming repository breaks on upgrade. They are dropped the first time
agent-teams writes the file — a repository migrates by letting it save once.
A file carrying both names for one setting takes the current one, which is
what a dashboard mid-migration emits. Validation always reports the current
name, so an error teaches the name to migrate to rather than echoing the dead
one. The same aliases are accepted inside a `roles` block.

## Legacy setting

Older files may contain `spec_completion`. It is accepted for compatibility,
ignored, and omitted when configuration is written. Use `spec_pr_merge_mode`
instead.
