---
name: authoring-spec
description: Deliver an architect-owned GitHub Issue as a focused specification or architecture document and docs-only pull request. Use for [role:architect], "author the spec", architecture decisions, contracts, or implementation-facing plans.
---

# Authoring a specification

Turn one architect-owned Card into one focused docs PR. Do not implement
production code in this routine.

## Workflow

1. Read the Card:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" list --role architect
gh issue view <number> --repo <configured-repo>
```

2. Confirm the selected Card is owned by `architect`. Stop on an ownership
   mismatch.
3. Create a short branch named `spec/issue-<number>-<slug>`.
4. Write the smallest durable artifact that removes implementation ambiguity:
   behavior, boundaries, acceptance criteria, and unresolved risks.
5. Review the diff and verify that it is docs-only.
6. Commit and open one PR linking the Issue.
7. Hand the Card to RD only after the PR exists:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" handoff <number> \
  --from-role architect \
  --to-role rd \
  --note "Specification PR: <url>. Implement against the documented acceptance criteria."
```

8. Report the Issue, PR, and resulting Role.

## Boundaries

- Do not write production code.
- Do not hand off before a durable specification PR exists.
- Do not merge the PR unless the user explicitly asks and repository policy
  permits it.
- This MVP assigns the existing Card; it does not automatically decompose a
  specification into multiple implementation Cards.
