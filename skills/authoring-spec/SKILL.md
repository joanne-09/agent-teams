---
name: authoring-spec
description: Shape an architect-owned GitHub Issue into a durable specification, then either send it to the human readiness gate or decompose it into flat implementation Cards. Use for [role:architect], "author the spec", "make this ready", "decompose this", architecture decisions, contracts, or implementation-facing plans.
---

# Shaping and specifying work

The System Architect turns shaped demand into technically sound work and puts
it in front of the human who decides it is ready. This covers three distinct
jobs. Do exactly one per session.

| Job | Shape | Ends with |
|---|---|---|
| Author one specification document | Consumer | one docs Pull Request, then **stop** |
| Send one shaped Card to the gate | Producer | `(Backlog, human)` |
| Decompose a specification | Producer | several flat `(Backlog, human)` Cards |

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

## Job 2 — send one shaped Card to the readiness gate (Producer-shaped)

For a genuine single-Card change, once the specification is durable, hand it to
the human. **You may not make a Card `Ready`** — `promote_to_ready` refuses
every agent seat, and so do `transition --to Ready` and `create-card --status
Ready`, because authority is keyed to the destination.

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" handoff <number> \
  --from-role architect --to-role human \
  --note "<why this is technically ready>" \
  --needs "Approve into Ready, or send it back with what is missing." \
  --artifacts "<spec pr-url|docs/path>"
```

The human then runs `promote <number> --spec <ref>`, which transitions the Card
to `Ready` and hands it to `dev` in one routine. Your job is to make that
decision easy: state the scope, the acceptance criteria, and the risk, and put
the specification link in `--artifacts`.

If you try to promote anyway, the refusal tells you this and exits 1. Do not
work around it — it is one of the two human gates the whole design rests on.

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

Each child is created in `(Backlog, human)` — waiting at the readiness gate,
not past it — carries the specification pointer and its provenance, and the
parent gets a summary comment. The human approves each child individually with
`promote`. If some children fail, the result lists which — re-run with only
those, or the board carries duplicates.

Each child must stand on its own: an independently shippable outcome, testable
acceptance criteria, no dependency on a sibling landing first. A slice that
cannot ship alone is not a slice; keep decomposing, or leave it as one Card.

## The readiness gate

Two things stand between shaped work and `Ready`, and you control neither:

1. **The human decides.** `promote` is the human's routine. You propose;
   they approve. Hand the Card to `human` with everything they need.
2. **The specification must be durable.** This board runs
   `spec_completion=merged` by default, so if the specification Pull Request is
   still open, `promote` and `decompose` both refuse and name the reason.

That refusal is the design working. Development building against a document
review may still change is exactly what the gate prevents. Two legitimate
responses: ask the human merge authority to review the specification, or — if
this repository genuinely accepts an open specification — set
`spec_completion` to `opened` in the config, deliberately and once.

A durable path (`docs/architecture/...`) satisfies the gate without a Pull
Request lookup, because a path on the branch you are reading is already
durable.

## Boundaries

- **Do not write production code.** That is the Developer's seat, and the action policy refuses it.
- **Do not mark work Ready without a specification reference.** There is
  nothing to implement against.
- **Do not merge**, including the specification Pull Request. No seat here can.
- Do not invent parent/child Card semantics. The board is flat; provenance
  lives in the child body and the parent's summary comment.
