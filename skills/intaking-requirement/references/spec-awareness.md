<!-- Derived from board-superpowers `intaking-requirement`
     references/spec-first-checklist.md and references/intake-decision-tree.md
     Tables 2-3 (MIT, (c) 2026 PanQiWei, github.com/PanQiWei/board-superpowers).
     Their project-specific rows are generalized to agent-teams; their sibling
     routing table is not carried (design questions route to our own seats). -->

# Spec awareness — intaking-requirement reference

Read this at workflow step 5 when the requirement embeds design decisions and
you need to place each one: settled before Ready, or deferred to the
implementing session.

## Why the body must not pre-decide design

The board contract assumes every Card lands in a context where the
architect's reserved decisions are already settled. A Card that needs one of
those decisions made during implementation puts the dev session in an
architect role it does not have. In agent-teams every Card already passes
through the architect and the human readiness gate before implementation, so
there is no separate spec-first gate at intake — intake's job is writing the
body so each decision lands in the right place.

## Locked before Ready vs deferrable to implementation

| Decision class | Lock before Ready? | Why |
|----------------|--------------------|-----|
| Cross-Card contract (data shape shared between Cards) | **Locked** | Deferring forces dependent Cards to wait or ship against a placeholder. |
| ADR-level decision (architecture trade-off worth recording) | **Locked** | ADRs are immutable once accepted; decide before implementation. |
| Schema change (board fields, Card body sections, result envelopes) | **Locked** | Schema is shared; mid-flight changes break every session that reads it. |
| Scope crossing multiple areas of the system | **Locked** | Cross-area decisions need the architect's view of all of them. |
| In-Card design A/B that affects no other Card | **Deferrable** (template below) | The implementing session has context the architect lacks. |
| Implementation-style choices (naming, function decomposition, test layout) | **Deferrable** | Taste choices; pre-deciding adds no value. |
| Local refactor scope (adjacent cleanup while implementing) | **Deferrable** | The implementer decides if local; escalate if it crosses Cards. |

### Red lines — never deferrable to an implementing session

These must be settled before the Card reaches Ready. Putting one in a
deferrable acceptance criterion violates the architect's reserved-power
boundary:

- authority and policy code (`policy.py` action rows, hard floors, the
  transition table);
- the board schema: Status and Role option sets, Card body sections, the
  handoff comment format;
- the specification-gate configuration (`spec_completion`);
- result-envelope semantics (`ok` / `partial` / `completed` / `recovery`);
- plugin manifest and skill instruction files;
- ADR-level architecture decisions.

If a dev session meets one of these as an open question mid-implementation:
stop, record the blocker, hand the Card to the architect.

## The "design-left-to-dev" acceptance-criterion template

When an in-Card design A/B is genuinely deferrable, capture it like this in
the Card body:

```markdown
- **AC<N> — <decision name> (design-left-to-dev).**
  <One-sentence framing of the trade-off.>

  **Options** (pick one in implementation):

  - **Option A**: <description>. Pros: <bullets>. Cons: <bullets>.
  - **Option B**: <description>. Pros: <bullets>. Cons: <bullets>.

  **Architect's leaning**: <Option X> — because <one-sentence rationale>.
  The implementer is **not bound** to this leaning; picking a different
  option is fine if the PR description states the reason.

  **Verifiable**: the PR description states which option was picked plus a
  1–3 sentence rationale, and the Card records the chosen option once
  delivered.
```

Do NOT use this template when the decision is locked per the table above,
when only one option is viable, or when an existing specification already
dictates the answer.

## Sequencing a spec edit

When a requirement needs a specification or ADR change, the architect
chooses:

- **Separate PR, sequenced**: the spec PR lands; the Card is promoted against
  the merged spec; implementation claims it. Highest discipline; use when the
  spec change is shared across several downstream Cards.
- **Same PR, paired**: spec edit and implementation land together. Use when
  the change is local to one Card and not shared.
- **Spec-only work**: the work IS the spec — the Card's Goal is "land this
  document", and its acceptance criteria describe the document.

## Anti-patterns

- **Discovering the spec edit mid-implementation**: stop; surface to the
  architect. The spec edit routes back through intake; the Card resumes after
  it lands.
- **Backfilling spec after the fact**: spec edits become archaeology. Catch
  them at intake.

## Failure modes

| Situation | Correct handling |
|-----------|-----------------|
| The human says "just make one card" but the shape judgment fires multi-card | Surface the conflict explicitly. Record the override in the Card's notes if the human insists. Do NOT silently create a single Card as if the judgment never fired. |
| A locked decision is unsettled but the human wants the Card filed now | Record the skip in the Card's notes: "Spec precondition skipped — <reason>. Follow-up spec edit pending." Do NOT refuse to file the Card. |
| The intake command fails | Surface the JSON error verbatim; read `completed` and `recovery`; show the draft body so the human can file it manually if needed. Never re-run blindly — a second run files the requirement twice. |
