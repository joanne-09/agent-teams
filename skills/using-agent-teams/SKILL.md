---
name: using-agent-teams
description: Route an agent-teams Producer session by a leading role token or user intent, and run the mandatory read-only startup bootstrap. Use at the start of sessions involving a GitHub engineering board, requirement intake, architect specifications, Role handoffs, EM briefing or dispatch, or the QA verification queue.
---

# Using agent-teams

Operate a Producer workflow over GitHub Issues in one GitHub Project. The
Project is durable truth; this conversation is disposable. Assume the next
session remembers nothing you were told.

## Bootstrap first, always

Every governed session runs this before anything else, including before
answering a question about the board:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" bootstrap --role <seat>
```

It is read-only and mutates nothing. It returns your seat, the standing
repository context pointers, a live board projection, and the seat-specific
view your routine consumes.

Three rules:

- **No mutation before bootstrap completes.** A session that cannot establish
  where it is has no business changing anything.
- **Live board state beats the prompt.** If a kickoff says a Card is
  `(Ready, rd)` and the board says otherwise, the board is right and the
  kickoff is stale. Say so and stop.
- **Run it once.** If intent is obvious and you route straight to a downstream
  skill, that skill still needs the bootstrap to have happened. Do not run it
  twice.

Open the documents named in `standing_context` on demand. Do not paste them
wholesale into the conversation; the bootstrap returns pointers precisely so
context stays compact.

## Route

Read a leading role token before the rest of the request.

| Token | Intent | Skill |
|---|---|---|
| `[role:analyst]` | a new idea or requirement | `agent-teams:intaking-requirement` |
| `[role:architect]` | shape, specify, promote, or decompose | `agent-teams:authoring-spec` |
| `[role:em]` | "what is going on", board health | `agent-teams:briefing-board` |
| `[role:em]` | blocked work, recovery | `agent-teams:triaging-board` |
| `[role:em]` | dispatch, queue, "who works next" | `agent-teams:dispatching-work` |
| `[role:qa]` | the verification queue | `agent-teams:inspecting-queue` |

No token, or an ambiguous request: explain this router, report what the
bootstrap found, and ask which seat is acting. Never guess a seat — a seat is
an authority boundary, not a preference.

## What this plugin will not do

- **It does not implement Cards.** A Producer shapes work; a Consumer resolves
  exactly one Card in a separate session. If asked to implement, render the
  kickoff prompt and stop.
- **It does not merge.** No seat here can. Merge belongs to the human.
- **It does not verify deliveries.** Queue inspection orders work for
  verification; each verdict needs its own bound Consumer session.

## Safety

- Reads may proceed immediately.
- Before any mutation, state the Issue, its current `(Status, Role)`, the
  intended change, and the expected result.
- Every command prints one JSON envelope. **Never report a mutation as
  successful without `"ok": true` in that output.**
- A result carrying `"partial": true` is not a failure to retry blindly. It
  names what already landed and what to do next. Read `recovery` and follow
  it — re-running the whole command duplicates the completed steps.
- A refusal is information. `IllegalHandoff`, `IllegalTransition`,
  `HandoffCapExceeded`, and `ActionForbidden` each mean the board is telling
  you something true. Explain it; do not route around it.
