---
name: authoring-spec
description: Shape an architect-owned GitHub Issue into a durable specification, then either promote it to Ready for one implementation Card or decompose it into flat implementation Cards. Use for [role:architect], "author the spec", "make this ready", "decompose this", architecture decisions, contracts, or implementation-facing plans.
---

# Shaping and specifying work

The System Architect turns shaped demand into technically Ready work. This
covers three distinct jobs. Do exactly one per session.

| Job | Shape | Ends with |
|---|---|---|
| Author one specification document | Consumer | one docs Pull Request, then **stop** |
| Promote one shaped Card | Producer | `(Ready, rd)` |
| Decompose a specification | Producer | several flat `(Ready, rd)` Cards |

Authoring and decomposing in one session would blend a Consumer shape with a
Producer shape. After a specification Pull Request exists, stop; a later
session promotes or decomposes against it.

## Start here

Bootstrap as `architect`. The `seat_view` names Cards awaiting shaping, Cards
blocked on architecture, and specification Cards already Ready.

Read the Card and everything attached to it before deciding anything:

```bash
gh issue view <number> --repo <configured-repo> --comments
```

Then judge the requirement. If the outcome is unclear or the acceptance
criteria are not testable, **send it back** rather than guessing:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" handoff <number> \
  --from-role architect --to-role analyst \
  --note "Acceptance criteria are not testable as written." \
  --needs "<the specific question that would make this specifiable>"
```

Returning an under-specified Card is a legal, expected move. Specifying around
a gap is how a wrong thing gets built efficiently.

## Job 1 — author one specification (Consumer-shaped)

When the specification is itself a repository deliverable:

1. Confirm the Card is owned by `architect`. Stop on a mismatch.
2. Branch: `spec/issue-<number>-<slug>`.
3. Write the smallest durable artifact that removes implementation
   ambiguity — behaviour, boundaries, acceptance criteria, unresolved risks.
4. Verify the diff is docs-only.
5. Open one Pull Request linking the Issue.
6. **Stop.** Do not promote and do not decompose in this session.

## Job 2 — promote one shaped Card (Producer-shaped)

For a genuine single-Card change, once the specification is durable:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" promote <number> \
  --spec <pr-url|#number|docs/path> \
  --note "<why this is ready>"
```

This runs two independent operations in order: the Status transition to
`Ready`, then the handoff to `rd`. If the second fails, the result says the
Card is Ready but unowned and gives the exact command to finish. Follow it — a
Ready Card with no Role is invisible to dispatch.

## Job 3 — decompose (Producer-shaped)

When the specification has several independently shippable slices, write the
children to a JSON file and create them in one pass:

```json
[
  {"title": "Add sales_db connector", "body": "Goal: ...\n\nAcceptance:\n- [ ] ..."},
  {"title": "Render revenue chart", "body": "Goal: ...\n\nAcceptance:\n- [ ] ..."}
]
```

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" decompose <parent> \
  --spec <pr-url|#number|docs/path> \
  --children <file.json>
```

Each child is created in `(Ready, rd)`, carries the specification pointer and
its provenance, and the parent gets a summary comment. If some children fail,
the result lists which — re-run with only those, or the board carries
duplicates.

Each child must stand on its own: an independently shippable outcome, testable
acceptance criteria, no dependency on a sibling landing first. A slice that
cannot ship alone is not a slice; keep decomposing, or leave it as one Card.

## The readiness gate

This board runs `spec_completion=merged` by default: a Card becomes Ready only
once the specification is durable on the target branch. If the specification
Pull Request is still open, `promote` and `decompose` both refuse and name the
reason.

That refusal is the design working. Development building against a document
review may still change is exactly what the gate prevents. Two legitimate
responses: ask the human merge authority to review the specification, or — if
this repository genuinely accepts an open specification — set
`spec_completion` to `opened` in the config, deliberately and once.

A durable path (`docs/architecture/...`) satisfies the gate without a Pull
Request lookup, because a path on the branch you are reading is already
durable.

## Boundaries

- **Do not write production code.** That is the Research and Development
  engineer's seat, and the action policy refuses it.
- **Do not mark work Ready without a specification reference.** There is
  nothing to implement against.
- **Do not merge**, including the specification Pull Request. No seat here can.
- Do not invent parent/child Card semantics. The board is flat; provenance
  lives in the child body and the parent's summary comment.
