---
name: intaking-requirement
description: Convert a new product or engineering requirement into a Backlog GitHub Issue and hand it from analyst to architect. Use for messages beginning with [role:analyst], "new requirement", "intake this", "I have an idea", "we need to build", "add a card", "found a bug", or casual phrasings of new work ("I've been thinking about X", "can we add Y"). Do NOT use for an existing returned Card (clarifying-card), board state (briefing-board), blocked work (triaging-board), or dispatch (dispatching-work).
---

<!-- Portions of the shape-judgment, spec-awareness, and decline sections are
     derived from board-superpowers `intaking-requirement` (MIT, (c) 2026
     PanQiWei, github.com/PanQiWei/board-superpowers). The clarification loop
     (step 4 + references/clarifying-requirements.md) is derived from
     superpowers `brainstorming` (MIT, (c) 2025 Jesse Vincent,
     github.com/obra/superpowers). Both adapted to the agent-teams flow.
     See ATTRIBUTION.md. -->

# Intaking a requirement

Create one durable, reviewable Card. The System Analyst owns problem clarity,
not technical design — resist solving it. Intake is a gateway, not a design
session: its job is to judge the shape of the work and capture it faithfully,
then hand it to the seat whose job the next decision is.

## Workflow

1. Bootstrap as `analyst`. Check the `backlog` view first: if this requirement
   already exists, add to that Card instead of filing a second one.
2. Acknowledge: restate the requirement in one or two sentences and confirm
   you have it right before shaping it.
3. Judge the shape. Evaluate top-down; the first row that fires wins:

   | Shape | Fires when | Outcome |
   |---|---|---|
   | Roadmap-level | Bundles features that cannot ship as one coherent unit, or names a cross-version umbrella | Stop. Surface: "this is roadmap-level — it needs a positioning decision before any Card." No Card yet. |
   | Multi-card | Two or more independent capabilities, or you estimate more than ~5 internal chunks of work | Create **one** Card carrying the whole requirement. State the expected split in the body and handoff — decomposition is the architect's job, after the spec. |
   | Single card | One user- or developer-visible capability in one area of the system | Proceed. |

   Do not decompose during intake, whatever the shape says — one requirement,
   one Card. Decomposition needs a durable specification first, and that is
   the architect's pipeline. If the requirement targets a brand-new surface,
   add a note for the architect: the first child should be a walking skeleton
   (the smallest end-to-end slice through every layer).

   If the human disputes the shape call ("just make one card"), say what fired
   and defer — record the override in the Card's notes so the decision is
   traceable.

   When the call is not obvious, read `references/shape-judgment.md` for the
   full trigger tables, the ">5 chunks" rationale, and the cross-Card
   dependency mechanisms the architect will use after decomposition.
4. Clarify until the Card can be written honestly. This is the analyst's core
   job — an under-asked requirement becomes a spec the architect cannot write.
   The method:
   - Ask questions **one at a time — only one question per message**. If a
     topic needs more exploration, break it into multiple questions.
   - Prefer multiple-choice questions when possible, but open-ended is fine
     too.
   - Focus on understanding: **purpose, constraints, success criteria.**
   - Quality words are not requirements. "Good", "popular", "safe", "fast"
     must leave the conversation either operationalized (measurable, a third
     person could check it) or parked as an open question with a named owner.

   Stop when — not after a fixed number of questions — both hold: the
   acceptance criteria you are about to write could be checked by a third
   person, and no requirement in the body could be interpreted two different
   ways. The human can end the loop at any time ("enough, file it") — file
   with what you have and record the early stop in the Card's notes.

   Do not drift into design: purpose, constraints, and success criteria are
   analyst territory; approaches, trade-offs, and architecture belong to the
   architect. Record "how should we build it" answers as open questions.

   Read `references/clarifying-requirements.md` for the question protocol,
   the operationalization table, and the termination checklist.
5. Spec awareness. Every Card already passes through the architect and the
   readiness gate before implementation, so there is no separate spec-first
   gate here. Two cases still change how you write the body:
   - **The work IS a spec** (an ADR, a contract page, a design doc): the Goal
     is "land this document"; acceptance criteria describe the document.
   - **The requirement embeds an architecture decision** ("use storage X",
     "change the schema"): record it as an open question for the architect,
     not as an acceptance criterion. Intake must not pre-decide design.

   Read `references/spec-awareness.md` for which decisions must be locked
   before Ready versus deferred to implementation, the red-line list, and the
   "design-left-to-dev" acceptance-criterion template.
6. Shape the body. It carries what *this Card* is — never project context,
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
7. Announce the mutation: create a Backlog Issue, add it to the Project, set
   Role `architect`, and record the handoff.
8. Write the body to a temporary UTF-8 file and run:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" intake \
  --title "<outcome-oriented title>" \
  --body-file "<temporary-file>"
```

9. Report the Issue URL, Status, Role, and the handoff comment.

## When not to intake

- **Too small for a Card.** A one-line typo or trivial config change does not
  warrant board tracking. Say so and stop — the human makes the change
  directly, or insists on a Card anyway.
- **Conflicts with the project's stated premises or non-goals.** Decline with
  a clear "this conflicts with <premise> because..." rather than filing it.
  The human can override — surface the conflict explicitly so the override is
  conscious, and record it in the Card's notes.

## Invariants

- **Initial Status is `Backlog`, never `Ready`.** Readiness is the human's
  gate, and the action policy refuses it from this seat.
- **The Card ends owned by `architect`.** The analyst cannot hand to `dev`
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
