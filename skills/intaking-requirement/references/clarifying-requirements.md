<!-- Derived from superpowers `brainstorming` (MIT, (c) 2025 Jesse Vincent,
     github.com/obra/superpowers) — the requirement-elicitation phase only,
     with wording kept close to the source where it applies. The design half
     of that skill (approach proposals, design doc, writing-plans handoff) is
     deliberately NOT adopted: design belongs to the architect seat. See
     ATTRIBUTION.md and docs/skill_migration.md §8. -->

# Clarifying a requirement

The analyst's product is problem clarity. A Card whose acceptance criteria a
third person could check is the input the architect's spec depends on; a Card
built on unexamined quality words ("good", "popular") pushes clarification
into the spec session, where it is more expensive and reaches the human later.

## The question protocol

- **Explore context before asking.** Check the board, the repository's docs,
  and recent activity first. Never ask what the project already answers.
- **One question per message.** If a topic needs more exploration, break it
  into multiple questions across multiple messages. Batched questionnaires
  get shallow answers; a conversation gets real ones.
- **Prefer multiple choice when possible** — concrete options are easier to
  react to than a blank page — but open-ended is fine too.
- **Focus on purpose, constraints, success criteria.** In that order: who is
  this for and what decision or outcome does it serve; what must it respect
  (data sources, platforms, deadlines, budgets); how will we know it worked.
- **Shape before detail.** Shape judgment (workflow step 3) runs first —
  do not spend questions refining details of a requirement that is going to
  be split or declined.

## The operationalization table

Every quality word must leave the conversation in one of two states:
operationalized, or an open question with a named owner. Typical ladders:

| Vague | Questions that operationalize it |
|---|---|
| "good" / "user-friendly" | For whom? Doing what task? What would make them abandon it? |
| "popular" / "hot" | Measured by what — reviews, rankings, foot traffic? From which source? |
| "safe" / "violation" | Whose definition — which agency, which regulation, which list? |
| "fast" / "real-time" | How stale is acceptable? Seconds, hours, last published dataset? |
| "on a map" | What granularity — address pins, district shading, city counts? |
| "dashboard" | Which questions must a viewer be able to answer at a glance? |

Also pin down, for any data-backed requirement: the data source by name, its
update frequency, its license/terms, and what happens when it is unavailable.

## Termination checklist

Stop asking when every box is checked — not after a fixed question count:

- [ ] Acceptance criteria could be checked by a third person with no access
      to this conversation.
- [ ] No requirement in the body could be interpreted two different ways.
- [ ] Data sources and scope are named; non-goals a reader would otherwise
      assume are stated.
- [ ] Every remaining unknown is recorded as an open question with the seat
      or person who must decide it.

## The human override

The human can end the loop at any time: "enough, file it." Comply — file the
Card with what you have, and record in the Card's notes which questions were
cut short. The override is the human's right; the record keeps it honest.

## Boundary: clarification is not design

Approaches, trade-offs, technology choices, and architecture belong to the
architect. If the human answers a question with "how would you build it?",
record the topic as an open question for the architect and continue
clarifying the problem. The analyst leaves the conversation knowing *what*
and *why*; *how* is the next seat's job.

## Relationship to the returned-Card loop

The architect can still return a Card with a specific question. That loop is
the backstop for what questioning could not have caught — it is not a license
to under-ask. Clarification that could have happened at intake and didn't is
a defect in this step.
