---
name: intaking-requirement
description: Convert a new product or engineering requirement into a Backlog GitHub Issue and hand it from analyst to architect. Use for messages beginning with [role:analyst], "new requirement", "intake this", or "I have an idea".
---

# Intaking a requirement

Create one durable, reviewable Card without prematurely making it Ready.

## Workflow

1. Restate the requirement in one sentence.
2. Ask only for information needed to avoid a materially wrong Card.
3. Shape:
   - a concrete outcome-oriented title;
   - context and problem;
   - acceptance criteria;
   - explicit non-goals when useful.
4. Announce the mutation: create a Backlog Issue, add it to the configured
   Project, assign Role `analyst`, then hand it to `architect`.
5. Put the body in a temporary UTF-8 file and run:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" intake \
  --title "<title>" \
  --body-file "<temporary-file>"
```

6. Report the returned Issue URL, Status, Role, and handoff comment.

## Invariants

- Initial Status is `Backlog`, never `Ready`.
- The durable result ends with Role `architect`.
- Do not decompose implementation work during intake.
- Do not claim success from partial prose output; require the CLI JSON result.
