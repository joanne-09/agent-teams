---
name: dispatching-work
description: Read Ready GitHub Project Cards and render deterministic kickoff prompts by Role for an EM. Use for [role:em], "dispatch work", "assign the queue", "who should work next", or "start the team".
---

# Dispatching work

Produce a dispatch queue; do not spawn agents. A human, terminal, CI job, or
other carrier can consume the rendered prompts.

## Workflow

1. Verify board access:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" doctor
```

2. Read the Ready queue:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" dispatch --format json
```

3. Present entries in the returned order. Each entry must include:
   - Role;
   - Issue number and title;
   - Issue URL;
   - a kickoff prompt containing `[role:<role>]` and `[board-card:#<number>]`.
4. Explain skipped Cards only when that helps the EM act.

## Rules

- Dispatch only Cards whose Status equals configured `ready_status`.
- Dispatch only configured roles.
- Never infer a missing Role.
- Never change Role or Status during dispatch.
- Never claim that a session was started; this MVP renders prompts only.
- An empty queue is a valid result.
