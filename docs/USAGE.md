# Using agent-teams

Status: operational guide for a human running the Producer surface
Applies to: `agent-teams` v0.2.0
Design: [`ARCHITECTURE.md`](./ARCHITECTURE.md) · Delivery status: [`IMPLEMENTATION_PLAN.md`](./IMPLEMENTATION_PLAN.md)

This document is about *doing the work*: what you say, what happens, what you
own, and what refuses. For why the system is shaped this way, read the
architecture instead.

> **Scope honesty.** The Producer half is built: intake, specification,
> decomposition, briefing, triage, dispatch, and queue inspection. The Consumer
> half (`dev` implementation, `qa` verdicts) is **not built yet**. Where this
> guide describes a Consumer step, it says so.

---

## 1. The mental model in one minute

**You talk in plain language. The plugin decides which seat acts.**

You never name a role. You say what you want; the plugin runs its read-only
bootstrap, works out which seat that is, and runs that seat's routine.

```text
you say:    We need a CSV export on the reports page.
            └── the plugin bootstraps read-only and reads the live board
                └── it recognises this as new demand -> the `analyst` seat
                    └── it shapes the Card, writes to GitHub, and stops
```

```text
you say:    What's going on? What should I look at?
            └── orientation: lanes, blocked work, what is waiting on you,
                and one recommended next action
```

Four things follow, and they explain most of what you will see:

1. **Seats are internal.** `analyst`, `architect`, `lead`, `qa`, `dev` are how the
   plugin organises authority, not a menu you pick from. You will see them in
   output — that is reporting, not a request for input.
2. **Sessions do not talk to each other.** Everything one seat needs to tell the
   next is written to the Issue as a structured handoff comment. Close every
   terminal you have; the work is unaffected.
3. **You are the one seat the plugin may not take.** `human` holds readiness
   and protected-change exception authority. The plugin will never adopt it or
   run `promote` for you. No agent seat directly merges; after M5, a separate
   deterministic controller may merge only an eligible, currently reviewed
   Pull Request head.
4. **A refusal is a normal outcome.** When a seat asks for something outside its
   authority, the command exits non-zero with a JSON reason and changes nothing.
   That is the system working.

> **The `[role:...]` token.** You will see prompts like
> `[role:dev] [board-card:#12] …` in dispatch output. That is a **machine
> channel** — a kickoff artifact a carrier pastes into a fresh session. It is
> readable by accident, not an interface you are expected to type. If you do
> write one, the plugin honours it as an explicit override.

---

## 2. One-time setup

### 2.1 Install the prerequisites

```bash
gh --version           # GitHub CLI
gh auth login
gh auth refresh -s project    # the Project scope is separate; it is easy to miss
python --version       # 3.9+; no packages, no virtualenv
```

### 2.2 Create the board

Create a GitHub Project (v2) linked to your work repository, and add **two
single-select fields**:

| Field | Options (exact) |
|---|---|
| `Status` | `Backlog`, `Ready`, `In Progress`, `Blocked`, `In Review`, `Done` |
| `Role` | `analyst`, `architect`, `dev`, `qa`, `lead`, `human` |

The plugin **never creates fields for you**. It validates and explains; you
create. This is deliberate — silently provisioning a governance surface is how
you end up with two boards that disagree.

### 2.3 Point a repository at the board

From the repository the team will work in:

```bash
python /path/to/agent-teams/scripts/producer_board.py init \
  --repo OWNER/REPO \
  --project-owner OWNER \
  --project-number 7
```

That writes `.agent-teams/config.json`. Credentials are **not** in it — they
stay in the GitHub CLI's own store.

### 2.4 Prove the board before touching it

```bash
python /path/to/agent-teams/scripts/producer_board.py doctor
```

`doctor` checks authentication, the Project, both fields, and **all twelve
options in one pass**, reporting every defect together rather than making you
re-run it once per missing option. Do not proceed until it returns
`"ok": true`.

### 2.5 Load the plugin

```bash
claude --plugin-dir /path/to/agent-teams
```

All seven skills should appear in the `agent-teams:` namespace.

---

## 3. The daily loop

Everything below is something you *say*, not a command you memorise. The seat
and skill named after each example are what the plugin picks — shown so you can
tell whether it read you correctly, not so you have to drive it yourself. The
mandatory human command is the readiness gate in §3.4. Beyond that, human
action is required only for protected changes - an eligible delivery reaches
merge through deterministic acceptance, and a defect goes back to the
Developer, neither of which waits on you.

### 3.1 Get oriented — the default, and available whenever you want it

```text
you:  brief me
you:  where are we? what should I look at next?
you:  status
```

The plugin bootstraps read-only and runs `briefing-board`. You get lanes by
`Role`, work-in-progress against the limit, the blocked list, the verification
queue, **what is waiting on you**, data-quality problems (Cards with no `Role`
or no `Status` — invisible to every routine), and one recommended next action.

Two ways you get this, and they give the same report:

- **Ask for it directly, at any point.** "Brief me" mid-session is a normal
  request, not a reset. It is read-only, so ask as often as you like.
- **Open a session with nothing specific.** Orientation is the default opening
  move — you should get it without asking.

The recommendation is ranked, and the ranking is opinionated: **an unmerged
verified delivery outranks everything**, because nothing downstream moves until
you merge it. Then work-in-progress over limit, then the verification queue,
then Ready work, then blocked, then intake.

### 3.2 Bring in new work

```text
you:  users need to export the report table as CSV
you:  I want to add a bulk-delete button
```

The plugin recognises new demand and runs `intaking-requirement` as `analyst`. It will interview you for the things a Card is
useless without — outcome, scope and non-goals, testable acceptance criteria,
constraints, open questions and who decides them.

It ends at `(Backlog, architect)` with a handoff comment. **It cannot make the
Card Ready**, and it cannot hand to `dev`; both refuse. Shaping demand and
approving work are different jobs.

### 3.3 Shape it technically

```text
you:  how should we build #12?
you:  write the spec for the CSV export
you:  #12 is too big, split it up
```

The plugin runs `authoring-spec` as `architect`, which does exactly one of three
jobs per session:

| Job | Shape | Ends at |
|---|---|---|
| Author one specification document | Consumer | one docs Pull Request, then **stop** |
| Send one shaped Card to the gate | Producer | `(Backlog, human)` |
| Decompose a specification | Producer | several flat `(Backlog, human)` Cards |

Authoring and decomposing in one session would blend a Consumer shape with a
Producer shape, so the skill stops after the specification Pull Request. A later
session decomposes against the merged document.

### 3.4 Open the readiness gate — this one is yours

The architect **cannot** declare work Ready. Nor can `lead`, `analyst`, `qa`, or
`dev`. Every path — `promote`, `transition --to Ready`, `create-card --status
Ready` — refuses for every agent seat.

You approve it:

```bash
python .../producer_board.py promote 12 --spec https://github.com/OWNER/REPO/pull/5
```

That runs two operations: transition to `Ready`, then hand to `dev`. What you are
asserting by running it is the INVEST check — this is one independently
shippable slice, its acceptance criteria are testable, and it is the right size.

The command also refuses **you** if the specification is not durable. By default
`spec_completion=merged`, so an open specification Pull Request is not enough;
merge it first, or set `spec_completion=opened` deliberately.

### 3.5 Hand out the work

```text
you:  what's ready to work on?
you:  hand out the next piece of work
```

The plugin runs `dispatching-work` as `lead`. It is **read-only and deterministic**: configured seat
order, then Card number. It renders a kickoff prompt per Ready Card:

```text
[role:dev] [board-card:#12] Work on "Export report table as CSV". Read the
Card and its comments first, and do not change another Card.
```

Rendering a prompt is not starting a session. You (or another carrier) start it.
The skill will say "prompt rendered" and never "session started" — the
difference matters when you are reading a log later.

### 3.6 Unblock things

```text
you:  what's stuck?
you:  why hasn't #14 moved?
```

The plugin runs `triaging-board` as `lead`: Blocked Cards grouped by the seat that owes a decision,
with unowned Blocked Cards flagged first — a Blocked Card with no `Role` is
waiting on nobody and will sit there forever.

Triage routes; it does not resolve. It cannot promote to Ready and cannot merge.

### 3.7 Order the verification queue

```text
you:  what's waiting to be checked?
```

The plugin runs `inspecting-queue` as `qa`: Cards in `(In Review, qa)`, ordered,
one kickoff prompt each, plus protected changes already waiting in
`(In Review, human)`.

Inspection is **not** verification. A verdict belongs to a separately bound
Consumer session, which is not built yet.

### 3.8 Automated acceptance and protected-change review

The M5 target has QA publish a structured verdict, design/architecture
conformance, complete changed-file review coverage, challenged findings, and
test-strength metrics for the exact Pull Request head. Deterministic policy then
routes the result:

- eligible changes are merged by the non-agent merge controller;
- defects return to `dev` on the same Pull Request; and
- protected or ambiguous changes move to `(In Review, human)` with the exact
  reason human judgment is required.

No agent seat can directly merge. This target is not implemented yet: the
delivered Producer policy still contains the older human-only merge floor, so
merge remains manual until M5 replaces that floor and verifies the automated
path end to end.

---

## 4. Your human-attention boundaries

The target design spends mandatory human attention once and escalates only when
automation cannot safely establish acceptance:

| Boundary | You are deciding | Runs |
|---|---|---|
| **Backlog → Ready** | Is this the right work, sliced right, sized right? | `promote` |
| **Protected-change exception** | Does this protected, ambiguous, or policy-exception delivery remain acceptable? | Human review and, if accepted, merge |

Eligible routine changes do not enter the second row: QA evidence and
deterministic acceptance take them through merge. If routine changes repeatedly
require human attention, the QA evidence or protected-change policy needs
improvement.

---

## 5. Reading what comes back

Every command prints one JSON object on stdout and exits 0, or prints
`{"ok": false, "error": ...}` on stderr and exits 1.

**A mutation counts as done only on `"ok": true`.** A skill that says a Card
moved without that envelope is wrong, and this is the single most important
thing to check when something looks off.

### Partial failures

GitHub gives no transaction across Issue creation, Project writes, and comments.
When step three of four fails, you get the truth:

```json
{
  "ok": false,
  "partial": true,
  "completed": ["issue_created", "project_item_added"],
  "failed": "status_set",
  "recovery": ["Issue #61 is on the Project with no Status.", "..."]
}
```

Follow the `recovery` list. It replays only the missing step. **Nothing here
ever claims a rollback** — if a compensating call did not run, the result will
not pretend it did.

### Refusals

```json
{"ok": false, "error": "`architect` (System Architect) may not promote to ready. readiness is the human lifecycle gate. Hand the Card to `human` ...", "refusal": "ActionForbidden"}
```

A refusal is checked **before the first GitHub call**, so it costs nothing and
leaves no partial state. Do not work around one; the refusal names the route
that does exist.

---

## 6. Tuning

In `.agent-teams/config.json`:

| Key | Default | Effect |
|---|---|---|
| `wip_limit` | `5` | Reported by `brief`; nothing blocks on it yet |
| `handoff_cap` | `6` | Past this, a Card routes to `(Blocked, lead)` instead of ping-ponging |
| `spec_completion` | `merged` | Whether Ready needs a merged or merely open specification PR |
| `dispatch_roles` | `architect, dev, qa` | Which lanes dispatch considers, in order |
| `status_overrides` | — | Map a canonical Status to your board's option name |

---

## 7. When something is wrong

| Symptom | Check |
|---|---|
| Everything refuses at startup | `doctor` — usually a missing `Role` option or the `project` scope |
| A Card is invisible to dispatch | It has no `Role`, or its `Status` is not `Ready`. `brief` lists these under data quality |
| A Card keeps bouncing between seats | The handoff cap will stop it at `(Blocked, lead)`. The cap is a signal that the Card is under-specified, not a nuisance |
| `promote` refuses and you *are* the human | The specification is not durable. Merge the spec PR, or change `spec_completion` |
| A mutation half-landed | Read `completed` and `recovery` in the envelope; fix forward, do not undo |
| A half-landed `intake` or `decompose` | Replay only the pieces `recovery` names. **Never re-run the whole command** — Issue creation is not idempotent, so a second run files a second Card for the same requirement |

---

## 8. What this plugin does not do

- **It does not call other plugins.** Nothing in `skills/` or `scripts/`
  references `superpowers` or `gstack`. Those disciplines are referenced by name
  as recommended practice; correctness never depends on either being installed.
- **It does not create Project fields.** `doctor` validates and explains.
- **It does not start sessions.** Dispatch renders prompts; a carrier starts them.
- **No agent seat merges, and none may request a merge.** An eligible delivery
  reaches the merge controller only through deterministic acceptance policy;
  protected or ambiguous changes route to you.
- **It does not let a reviewer choose its own outcome.** QA publishes evidence;
  `accept` computes the route from that evidence plus the live Pull Request.
- **It does not clean up work it has not confirmed merged.** A worktree with
  uncommitted changes refuses removal and is reported instead.

---

## 9. Command reference

```bash
producer_board.py init --repo O/R --project-owner O --project-number N
producer_board.py doctor
producer_board.py bootstrap --role <seat>

producer_board.py list [--role <seat>] [--status <status>]
producer_board.py brief [--with-handoffs] [--format text|json]
producer_board.py triage
producer_board.py queue
producer_board.py dispatch [--role <seat>] [--format text|json]

producer_board.py intake --title T (--body B | --body-file F)
producer_board.py create-card --title T (--body B | --body-file F) \
    [--status Backlog] [--role human] [--acting-role architect]
producer_board.py promote <issue> --spec <ref> [--acting-role human] [--note N]
producer_board.py decompose <parent> --spec <ref> --children <file.json>
producer_board.py transition <issue> --to <status> --acting-role <seat>
producer_board.py handoff <issue> --from-role <seat> --to-role <seat> \
    --note N [--needs N] [--artifacts A]
producer_board.py release-claim <issue> --branch <branch> [--note N]

# Consumer: one Card, one session
producer_board.py claim <issue> --acting-role dev|architect
producer_board.py submit-pr <issue> --title T --body-file F [--acting-role dev]
producer_board.py verdict <issue> --evidence-file F
producer_board.py accept <issue>
producer_board.py reconcile-done <issue> [--acting-role lead]
producer_board.py worktree-status [<issue>]
```

`accept` returns exactly one of three routes, and the reviewer does not pick
which:

| Route | Board result | What you do |
|---|---|---|
| `eligible` | `In Review` -> merged -> `(Done, lead)` | Nothing. Eligibility already required the checks to be green, so the merge normally lands at once and `accept` completes the route. If the platform merges later, the Card waits until `reconcile-done` records it |
| `defect` | `(In Progress, dev)`, same branch and Pull Request | Nothing. A Developer session corrects it |
| `protected_change` | `(In Review, human)` | **Your decision.** The reasons name the exact protected files or unresolved judgment |

If `accept` refuses instead of routing, the evidence is stale or incomplete -
QA re-reviews the current head, and nothing on the board moved.
