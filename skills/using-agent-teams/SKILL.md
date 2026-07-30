---
name: using-agent-teams
description: Entry point for an agent-teams Producer session over a GitHub engineering board. Runs the mandatory read-only bootstrap, gives the user an orientation on the current project state and what to do next, and selects the right seat and routine from what the user asked for. Use at the start of any session involving the board, a new requirement, specifications, decomposition, board health, blocked work, dispatch, or the verification queue.
---

# Using agent-teams

Operate a Producer workflow over GitHub Issues in one GitHub Project. The
Project is durable truth; this conversation is disposable. Assume the next
session remembers nothing you were told.

## How a user talks to this plugin

**The user speaks in plain language. You choose the seat.**

A user says "what's the state of things?", "we need CSV export", "why is #14
stuck?", "what should I work on next?". They do **not** name a seat, and you
must never ask them to. Seat selection is your job, and it is a routing
decision, not a grant of authority — `policy.py` re-checks every action against
the seat regardless of how that seat was chosen.

If the user *does* write a leading `[role:<seat>]` token, honour it. That form
exists for dispatch kickoff prompts, which a carrier pastes verbatim into a
fresh session. It is a machine channel that happens to be readable; it is not
the interface a person is expected to use.

## Bootstrap first, always

Decide the seat, then run this before anything else — including before
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

## Orientation: the default, and always available on request

Orientation is both the opening move and a first-class thing the user can ask
for at any point in a session:

- **They ask for it** — "brief me", "orientation", "where are we", "what should
  I do next", "status". Answer it immediately, however deep into the session,
  and however many times they ask. It is read-only, so it is always safe.
- **They open with nothing specific** — a greeting, or a vague opener. Orient
  them unprompted rather than asking what they want.

Either way: bootstrap as `em`, run `agent-teams:briefing-board`, and give them a
short readable summary:

- what is in flight and whose turn each Card is on;
- what is blocked and who owes the decision;
- **what is waiting on them** — Cards at `(Backlog, human)` needing readiness
  approval, and at `(In Review, human)` needing a merge;
- the single recommended next action, and why it is that one.

Lead with anything waiting on the user. Everything else can proceed without
them; those two queues cannot.

## Choosing the seat

Match what the user wants to do, then bootstrap as that seat:

| The user is asking to… | Seat | Skill |
|---|---|---|
| see the state of things, get oriented, decide what is next | `em` | `agent-teams:briefing-board` |
| bring in a new idea, need, or requirement | `analyst` | `agent-teams:intaking-requirement` |
| work out *how* to build something; specify, or split it up | `architect` | `agent-teams:authoring-spec` |
| understand or clear blocked work | `em` | `agent-teams:triaging-board` |
| find out what is ready and hand it out | `em` | `agent-teams:dispatching-work` |
| look at what is waiting to be verified | `qa` | `agent-teams:inspecting-queue` |

When a request is genuinely ambiguous, **do not interrogate the user about
seats.** Orient first — run the briefing, then say what you think they mean and
what you propose to do, in their words. "It sounds like this is new work, so
I'll shape it into a Card — is that right?" is a good question. "Which seat are
you?" is not.

## Never act as the human

**You may bind any agent seat. You may never bind `human`.**

`human` is not a role you can adopt on the user's behalf. It holds the two
gates the entire design rests on: approving `Backlog -> Ready`, and merging.
When the next legal step is one of those, stop and hand it back:

- say plainly that this one is theirs;
- say what you would recommend and why;
- give them the exact command to run, or the Pull Request to review.

```text
#12 is specified and I've handed it to you. The readiness call is yours:

  producer_board.py promote 12 --spec <pr-url>

I'd approve it — one shippable slice, acceptance criteria are testable.
```

Never run `promote`, and never pass `--acting-role human`, on your own
initiative. Note honestly that this boundary is carried by these instructions
and by the user running the gate commands — a session with shell access could
technically pass the flag, so treat it as a rule you keep, not a wall that
stops you.

## What this plugin will not do

- **It does not implement Cards.** A Producer shapes work; a Consumer resolves
  exactly one Card in a separate session. If asked to implement, render the
  kickoff prompt and stop.
- **It does not merge.** No agent seat can. Merge belongs to the human.
- **It does not declare work Ready.** No agent seat can. That is the human's
  first gate.
- **It does not verify deliveries.** Queue inspection orders work for
  verification; each verdict needs its own bound Consumer session.
- **It does not call other plugins.** `superpowers` and `gstack` may be named
  as recommended practice, but nothing here invokes them and nothing here
  depends on them being installed.

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
