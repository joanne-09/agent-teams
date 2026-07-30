---
name: intaking-requirement
description: Convert a new product or engineering requirement into a Backlog GitHub Issue and hand it from analyst to architect. Use for messages beginning with [role:analyst], "new requirement", "intake this", "I have an idea", or "we need to build".
---

# Intaking a requirement

Create one durable, reviewable Card. The System Analyst owns problem clarity,
not technical design — resist solving it.

## Workflow

1. Bootstrap as `analyst`. Check the `backlog` view first: if this requirement
   already exists, add to that Card instead of filing a second one.
2. Restate the requirement in one sentence and confirm you have it right.
3. Ask only what would otherwise make the Card materially wrong. One or two
   questions, not an interview — an unclear Card can be returned to you later,
   and that path exists precisely so intake does not have to be perfect.
4. Shape the body. It carries what *this Card* is — never project context,
   which is repository-side and reloaded by every session anyway:
   - the user or business outcome, not an implementation;
   - context and the problem being solved;
   - acceptance criteria a different person could check;
   - explicit non-goals, when a reader would otherwise assume them;
   - known dependencies, including other Cards this one waits on;
   - open questions and who must decide each.

   Do **not** invent a specification pointer here. There is no durable
   specification yet — the architect creates one, and `promote` or `decompose`
   writes the reference into the Card. A Card that points at a document nobody
   wrote is worse than one that admits it has none.
5. Announce the mutation: create a Backlog Issue, add it to the Project, set
   Role `architect`, and record the handoff.
6. Write the body to a temporary UTF-8 file and run:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" intake \
  --title "<outcome-oriented title>" \
  --body-file "<temporary-file>"
```

7. Report the Issue URL, Status, Role, and the handoff comment.

## Invariants

- **Initial Status is `Backlog`, never `Ready`.** Readiness is the architect's
  decision, and the action policy refuses it from this seat.
- **The Card ends owned by `architect`.** The analyst cannot hand to `rd`
  directly; nothing reaches implementation without passing through technical
  shaping.
- **Do not decompose during intake.** One requirement, one Card. Decomposition
  needs a durable specification first.
- **Do not claim success from prose.** Require `"ok": true` in the JSON result.

## If intake fails part-way

The result names exactly what already landed. Read `completed` and `recovery`
rather than re-running the whole command — a second run files the requirement
twice.

The common case: the Issue exists but is not on the Project. The result keeps
the Issue number and URL, and the recovery lines give the one command that
finishes the job.

## What a returned Card means

The architect may hand a Card back with `Role=analyst` and a specific
question. That is the design working, not a rejection. Resume from the same
Issue — add the clarification as a comment and hand it forward again. Do not
open a replacement Card; the history on the original is what makes the second
attempt cheaper than the first.
