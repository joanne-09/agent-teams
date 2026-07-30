# 06 — Operating runbook (running the team once it is built)

> The *how to actually use it* document. Assumes
> [`04-implementation-plan.md`](./04-implementation-plan.md) M0–M4 have
> landed. Written as if the team already works, so you can see what you are
> aiming at — and so Card 24 has something to check itself against.
>
> Commands marked **[verify]** could not be executed here (`gh` is not
> installed on this machine). Confirm them on first run.

---

## 1. What you are operating

Five agent seats, each a Claude Code session, coordinating through one
GitHub Project. Nothing is nested; nothing runs as a daemon. You — the
human — sit outside the team at the merge gate.

```
   analyst ──▶ architect ──▶ rd ──▶ qa ──▶ 👤 human (merge)
                   ▲          │      │
                   └──────────┴──────┘      escalate / reject
                   ▲
                  em  ── dispatches, rebalances, unblocks
```

---

## 2. One-time setup

### 2.1 Prerequisites

```bash
gh --version          # gh CLI with `project` scope — REQUIRED
gh auth status        # must show project scope
uv --version          # per-repo Python venv manager
python3 --version
shellcheck --version  # only if you will edit the plugin
```

Install the two sibling plugins — you kept them, and the plugin refuses to
run without them (ADR-0004):

```
/plugin add superpowers
/plugin add gstack
/plugin add board-superpowers      # your fork
```

Then in a fresh session:

```bash
bash scripts/check-deps.sh
```

Anything under `Missing:` is a hard stop.

### 2.2 Create the board

Two manual UI steps — ADR-0001 deliberately refuses to script Project
creation, and the `Role` field may follow the same rule:

1. Create a **GitHub Project v2** on your dashboard repo.
2. Set `Status` options to exactly, in order:
   `Backlog` · `Ready` · `In Progress` · `Blocked` · `In Review` · `Done`
3. Add a **`Role`** single-select field with exactly:
   `analyst` · `architect` · `rd` · `qa` · `em` · `human`

Step 3 may be scriptable — **[verify]**:

```bash
gh project field-create <NUMBER> --owner <OWNER> \
  --name Role --data-type SINGLE_SELECT \
  --single-select-options "analyst,architect,rd,qa,em,human"
```

If that fails on your `gh`, do it in the UI. It is a one-time cost, not a
blocker.

### 2.3 Bootstrap the dashboard repo

In a session opened at the dashboard repo:

```
set up board-superpowers
```

`bootstrapping-repo` runs every stage. Expect it to create the 13 standard
labels, validate both field option sets, write `.board-superpowers/`
config, create the per-repo venv, and initialise the audit DB at schema v3.

Verify:

```bash
bash scripts/read-board.sh --owner <OWNER> --project <N>   # [] is fine
sqlite3 .board-superpowers/audit.db "SELECT version FROM audit_schema_meta;"
```

Expect `3`. If you get `2`, the migration did not run — `audit-init.sh` is
the fix, not a manual `ALTER TABLE`.

### 2.4 Set the autonomy posture

`<repo>/.board-superpowers/config.local.yml`:

```yaml
wip_limit: 5
handoff_cap: 6

seat_overrides:
  architect:
    3: A     # split card — the architect's job; R would stall the seat
    5: A     # Backlog → Ready
  qa:
    6: A     # → Blocked, when QA finds a genuine external blocker
```

Start with **exactly this**. Every promotion you add is autonomy you have
not yet earned evidence for. Row 12 (merge) is `N` for every agent seat and
is not overridable — that is P6, and it is the reason you can leave the team
running at all.

---

## 3. Starting a seat

Every session begins with a seat token. Three carriers, same token.

**Paste (Phase 1 default)** — open a session in the dashboard repo:

```
[role:analyst] we need revenue broken down by region for the last 30 days
[role:architect] decompose card #12
[role:em] morning briefing
[role:rd] [board-card:#42]
[role:qa] review the queue
```

**Generated** — let the plugin write the prompt:

```bash
bash scripts/dispatch-agent.sh --seat rd --card 42
bash scripts/dispatch-agent.sh --seat qa --format cron
```

**Subagent** — from inside an EM session, for a short pass:

> Spawn a subagent with the prompt from
> `dispatch-agent.sh --seat qa --card 42 --format subagent`.

One rule: **one seat per session.** Do not tell an RD session to "also do
the QA pass." The seat separation is what makes the QA verdict worth
anything — an agent will not find its own blind spots, and the autonomy
matrix will refuse the actions anyway.

---

## 4. A day in the life

### Morning — the EM briefing

```
[role:em] morning briefing
```

```
Board: 11 cards · WIP 4/5

By lane
  analyst    1   #55 payment metrics (Backlog, 2d)
  architect  2   #52 cohort retention (Backlog) · #48 (Blocked, 3d) ⚠
  rd         3   #42 revenue chart (In Progress, 4h)
                 #44 sales_db connector (Ready)
                 #45 date-range picker (Ready)
  qa         1   #41 latency panel (In Review, PR #63)
  human      1   #39 CSV export (In Review, PR #61) ← waiting on you

⚠  #48 blocked 3 days on a schema decision — escalate to em?
⚠  #44 has 5 handoffs, cap is 6

Recommended next: dispatch qa on #41. It is the oldest thing
between RD and your merge gate.

Dispatch queue
  1. [role:qa] [board-card:#41]
  2. [role:rd] [board-card:#44]
  3. [role:architect] resolve the blocker on #48
```

Two things worth noticing: the board reads as a team status, and the human
lane surfaces your own queue — the plugin treats your attention as the
scarce resource it is (P1).

### Mid-morning — run the queue

Open a session per queue entry. Paste. Let each run.

An RD session on #44 will claim the card (branch push + worktree), work
through TDD via `superpowers:test-driven-development`, run the verification
chain, open a PR under the three-section contract, and hand off to `qa`.
You do not steer it.

Sessions are independent — start #41's QA pass and #44's RD work at the same
time in two tabs. `claim-card.sh` makes concurrent claims safe: first push
wins, and the loser exits `10` and stops rather than retrying.

### Afternoon — the merge gate

This is your actual job.

```bash
gh pr view 63
```

Read `## Human Verification TODO`. It is short by design — the things the
agents could not verify themselves. Check those, and only those:

```markdown
## Human Verification TODO
- [ ] Confirm the revenue figures match the finance dashboard for
      2026-07-01..2026-07-27
- [ ] Confirm the empty state reads correctly with no data in range
```

Everything above it in `## Automated Verification` already ran. If the TODO
list is filler, `enforcing-pr-contract` should have caught it — if it did
not, that is a bug worth filing against the fork.

Merge. `post-merge-cleanup.sh` removes the worktree and branch; the card
goes `Done`.

### When QA rejects

The card comes back as `(In Progress, rd)` with a verdict comment:

```markdown
<!-- board-superpowers:handoff -->
**Handoff**: `qa` → `rd`
**Reason**: verdict FAIL — 2 findings
**Needs from you**:
  1. Chart renders 31 days, AC says 30 (off-by-one on the range boundary)
  2. Empty state throws instead of rendering the placeholder
**Artifacts**: PR #63 · screenshots in the PR thread
```

You do nothing. Re-dispatch RD on the same card; it reads the comment on
claim. The loop closes without you.

---

## 5. What the human actually does

| You do | You do not |
|---|---|
| Verify `## Human Verification TODO` and merge | Review every line of every diff |
| Answer questions handed to the `human` seat | Sit in the middle of every handoff |
| Break decision deadlocks the architect escalates | Make routine technical calls |
| Tune `seat_overrides`, WIP, handoff cap | Approve individual A-class actions |
| Decide what the product should be | Decide how it gets built |

If you are doing anything in the right-hand column regularly, something is
mis-tuned. Usually it is an over-conservative `seat_overrides` — or a seat
whose skill body is vague enough that the agent keeps asking.

---

## 6. Health checks

```bash
# unflushed audit rows
ls ~/.board-superpowers/audit-pending.sentinel 2>/dev/null && echo "outbox has rows"

# dead-lettered rows — the signal to move off SQLite
sqlite3 .board-superpowers/audit.db \
  "SELECT count(*) FROM audit_log WHERE payload LIKE '%audit-dead-letter%';"

# stale claims
bash scripts/read-board.sh --owner <OWNER> --project <N> --status "In Progress"

# a card's full history, seat by seat
sqlite3 .board-superpowers/audit.db \
  "SELECT timestamp, actor_seat, action_id, approval_stage, outcome
   FROM audit_log ORDER BY timestamp;"
```

That last query is the one that pays for the whole governance layer: any
card's path through the team, reconstructible in one line.

Weekly: `[role:em] triage the board`.

---

## 7. Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Session ignores the seat | Token malformed or not in the **first** message | Exact form `[role:rd]`, first message |
| "Illegal handoff refused" | Authority matrix says no | Correct — route through the right lead. If the matrix is wrong, fix `board-canon`, not the call site |
| Handoff cap hit | Card is ping-ponging | Real signal, not a nuisance. The card is under-specified — send it to `architect`, not around the loop again |
| RD claim exits `10` | Race lost; another session claimed it | **Never retry.** Pick another card |
| Agent asks for approval constantly | Over-conservative `seat_overrides` | Promote the specific `action_id` for that seat |
| Agent acts outside its seat | Skill body too vague | Add an explicit refusal section to that role skill |
| Audit rows missing | DB unreachable | Expected. Writes degraded to jsonl and flush later — `audit-log-write.sh` always exits 0 by design |
| `audit-dead-letter` rows appear | SQLite contention | Now migrate to Postgres. Not before |
| WIP climbing, nothing merging | You are the bottleneck | Correct diagnosis, and it is P1's thesis. Merge, or lower WIP so agents stop starting work |

---

## 8. Tuning

| Knob | Where | Start | Raise when |
|---|---|---|---|
| `wip_limit` | `config.local.yml` | 5 | You merge faster than the team fills the queue |
| `handoff_cap` | `config.local.yml` | 6 | Never — lower it if ping-pong appears |
| Consumer concurrency | C-PLUGIN-3 config | 2 | You have watched 2 run cleanly |
| `seat_overrides` | `config.local.yml` | § 2.4 only | A specific approval proved to be pure friction |
| Audit backend | `credentials.yml` | SQLite | Dead-letter rows appear |

Tune one at a time, and only after you have watched the current setting be
wrong. This is the same demand-pull discipline ADR-0011 applies to deferred
routines, and it works.

---

## 9. Growing the team

**Phase 2 — OPS and dedicated security.** Both are additive and neither
needs new architecture:

1. Add the seat to the `Role` field options.
2. Add its row and column to the authority matrix in `board-canon`.
3. Add its column to the autonomy matrix in `classifying-actions`.
4. Write its role skill, or bind it to existing routines.

Splitting security out of QA is mostly step 3 and moving the `gstack:/cso`
invocation from `verifying-delivery` to the new seat's skill.

**Phase 3 — team-of-teams.** The design already carries it: seats are board
state, so depth is free. Two viable shapes —

- *One board, more seats* (`team-a-rd`, `team-b-rd`, …). Simplest. Works
  today with no code change.
- *One board per team* + a coordinating seat. Needs ADR-0026's multi-kanban
  runtime support, which is not shipped.

Start with the first. The second is a real project.

---

## 10. First-week checklist

- [ ] Both repos exist; the fork is installed into the dashboard repo
- [ ] Board has both six-option fields
- [ ] `check-deps.sh` clean; `audit_schema_meta.version` is 3
- [ ] `config.local.yml` matches § 2.4 exactly
- [ ] One card driven through all five seats by hand — the Card 24 golden path
- [ ] One QA rejection observed and recovered from
- [ ] One out-of-seat action attempted and refused
- [ ] The audit query in § 6 returns the full path for that card
- [ ] Only then: run two RD sessions concurrently

The last one matters. Concurrency is where a coordination design either
holds or does not, and you want the single-threaded path proven before you
find out.

---

*Runbook for the target state. Reflects the design in
[`03-target-architecture.md`](./03-target-architecture.md) as of 2026-07-28.*
