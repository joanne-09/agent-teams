# The Pull Request delivery contract

<!-- Derived from board-superpowers `enforcing-pr-contract`, including
     references/section-templates.md and references/filler-detection.md. MIT.
     See ATTRIBUTION.md. -->

Every governed delivery uses one fixed body shape. `submit-pr` validates it
before any GitHub call, and reports every violation at once.

## The shape

```markdown
## Summary
What changed and why, in the terms the Card used.

## Test Plan
What you intended to check, and how.

## Automated Verification
`python -m unittest discover -s tests`: 326 passed, 0 failures.
`claude plugin validate .`: passed.

## Human Verification TODO
- Confirm the exported CSV opens correctly in Excel, which we cannot automate.

## Retro Notes
Empty headers were the case the spec did not name; the parser now rejects them
explicitly rather than producing an empty row.

Closes #23.

<!-- agent-teams:pr -->
```

## Rules

**All five headings are required.** A missing one refuses.

**`## Automated Verification` must not be empty.** Name the concrete commands,
their output, and any specialist review that actually ran. This is the section
QA reads first, and an empty one means the delivery has no evidence.

**`Closes #<issue>` is required.** Without it GitHub does not close the Issue
on merge, and the Card and the delivery drift apart.

**The `<!-- agent-teams:pr -->` marker is required.** It is how queue
inspection distinguishes a governed delivery from any other Pull Request.

**Human Verification TODO is optional, but every item present must earn its
place.** An item any reviewer could write without reading the change is filler,
and a list of filler trains people to skip the section. These refuse:

> "Check that it works" · "Verify it works" · "Make sure it works" ·
> "Test the feature" · "Looks good" · "N/A" · "None" · "TBD"

A real item names something automation genuinely cannot judge: a visual result,
a device, a third-party account, a judgment call about tone or layout.

If nothing needs human judgment, leave the section with a single honest line
saying so — do not manufacture work.

**Retro Notes carry knowledge, not metrics.** What surprised you, what the
specification did not say, what the next person should know. Not how long it
took.

## Acceptance-criteria sync

Before submitting, every acceptance criterion on the Card must be in a terminal
state:

- `- [x]` — done.
- `- [!] reason` — waived, with a real reason. "Deferred to #99 because the
  connector is not built yet" is a reason; `- [!]` alone is a box nobody
  ticked, and refuses.
- `- [ ]` — **refuses.** A bare open criterion at submit time means the Card
  still claims work the delivery did not do.

Prose that merely mentions brackets is not a criterion; only list items are
checked.

## One Pull Request per Card

`submit-pr` keys off the claim branch, so a resumed or corrected session
updates the Pull Request it already opened rather than opening a second one.

This matters after a QA defect: the Card returns as `(In Progress, dev)` on the
same branch and the same Pull Request. Correct, re-verify, re-submit. Two Pull
Requests for one Card breaks the review trail and the recovery path.
