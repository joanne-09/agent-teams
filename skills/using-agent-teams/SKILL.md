---
name: using-agent-teams
description: Route an agent-teams Producer session by a leading role token or user intent. Use at the start of sessions involving a GitHub engineering board, requirement intake, architect specifications, Role handoffs, or EM dispatch.
---

# Using agent-teams

Operate a small Producer workflow over GitHub Issues in one GitHub Project.
Treat the Project as durable truth and conversation state as disposable.

## Route

Inspect a leading role token before the rest of the request:

- `[role:analyst]` plus a new idea or requirement: use
  `agent-teams:intaking-requirement`.
- `[role:architect]` plus a specification Card: use
  `agent-teams:authoring-spec`.
- `[role:em]` plus dispatch, queue, assignment, or "who works next": use
  `agent-teams:dispatching-work`.
- An explanation or ambiguous request: explain this router, then ask for the
  intended seat or Card.

Do not silently treat RD or QA implementation work as Producer work. This MVP
stops after assigning or handing off the Card.

## Preconditions

Before a board operation, run:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" doctor
```

If configuration is missing, explain the `init` command from the root README.
If `gh`, authentication, Project access, `Status`, or `Role` is missing, stop
with the reported fix. Do not invent board state.

## Safety

- Reads may proceed immediately.
- Before a mutation, state the Issue, current Status/Role, intended mutation,
  and expected result.
- Use a direct downstream skill when the intent is clear.
- Never claim that a handoff or issue creation succeeded unless the CLI
  returned success JSON.
