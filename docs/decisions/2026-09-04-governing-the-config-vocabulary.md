# Governing the configuration vocabulary

**Date**: 2026-09-04
**Status**: accepted, implemented, not yet exercised on a live Card
**Repairs**: link 2 and link 4 of
[`docs/traces/2026-09-04-merge-mode-evidence-chain.md`](../traces/2026-09-04-merge-mode-evidence-chain.md)
**Amends**: [`2026-08-06-consumer-flow-design.md`](../specs/2026-08-06-consumer-flow-design.md)
(one row's key name, in place, with a dated note)

## The problem being solved

The trace answered the team lead's question and stopped there. It established
that the `merge_mode` rename never became a Card, a specification, a Pull
Request, or a verdict — and then filed three reasons and changed nothing. A
diagnosis is not a repair, and the deck was about to present one as the other.

Of the three reasons, exactly one is a missing mechanism:

**A configuration change reaches five consumers and nothing checks that it
reached them.** One setting, five places that named it, three missed. Each miss
surfaced later by a different accident, on a different day, to a different
person. None was found by a check, because there was no check to find it.

A second turned out to be a mechanism after all. (C) *the dashboard copies our
setting names by hand* looked like someone else's repository until you ask what
would stop the copy drifting — and the answer was a comment. It is closed too;
see **Still open** below for what that took.

Only (A) is genuinely not a mechanism: *the plugin does not run its own work
through its own pipeline* is a scope decision — agent-teams governs consuming
repositories and its own source is hand-edited — and reversing it is a much
larger question than this. It stays open.

## What "make it a chain" actually requires

The trace drew five links. Only two of them were missing a mechanism; the
others were missing discipline, which is a different problem with a different
fix.

| Link | What was missing | Fixed here |
|---|---|---|
| requirement → Card | discipline. Anyone may file a Card | no |
| **Card → spec** | **mechanism.** A config change touched no governed artifact, so nothing routed it to anybody | **yes** |
| spec → dev | nothing. It is a diff | n/a |
| **dev → QA** | **mechanism.** QA cannot check "did every consumer get updated" when the consumers are not enumerable | **yes** |
| QA → merge | nothing, once the link above works | n/a |

## Decision

### 1. The vocabulary is a protected path

`scripts/agent_teams/config.py` and `docs/CONFIGURATION.md` become a new
`configuration-vocabulary` category in `DEFAULT_PROTECTED_PATHS`. Those two
files *are* the vocabulary: the module decides which keys exist and which are
retired, the reference is where every consumer looks them up.

This does not make the vocabulary harder to change. It makes changing it
**visible**, by routing the delivery through the human gate that already
exists — which is precisely what link 2 had no way to do.

Note what this does *not* buy, because the trace already found the limit the
hard way: `docs/specs/**` was protected the whole time, and the rename changed
the exact subject matter that document governs *without touching the file*, so
the protection never engaged. **Protection is on the path; the authority it
guards is the content.** That is why the checks below exist rather than
trusting the path rule.

### 2. Two audiences, two rules, and the asymmetry is the point

`tests/test_config_vocabulary.py` sweeps for retired names, and treats agent-
facing and human-facing files differently on purpose:

- **`scripts/`, `skills/`, `agents/`, `.claude-plugin/` — any mention at all
  fails.** An agent reading a skill file cannot tell narration from
  instruction; a retired key named anywhere in there is a key some seat will
  use. This is exactly the miss that survived nine days in
  `skills/authoring-spec/SKILL.md`. `config.py` is exempt, since `RETIRED_KEYS`
  has to be able to spell the names it refuses.
- **`docs/`, `README.md` — prose may name an old key; a settings-table row may
  not define one.** A document that could not name `merge_mode` could not
  explain what happened. But a table row is the shape a *live setting* has, so
  a row whose first cell is a retired key is a stale definition — unless the
  same row also names the replacement, which is a migration table and the one
  place the old name belongs in a first cell. `docs/decisions`, `docs/traces`
  and `docs/plans` are records and exempt entirely.

**This is the check that would have failed on 2026-08-27**, the day of the
rename, instead of on 2026-09-04 when someone finally went looking.

### 3. The vocabulary is one vocabulary, checked both ways

`Config`'s own fields and the settings tables in `docs/CONFIGURATION.md` must
be the same set. A key the code accepts and the reference does not document is
unreachable; a key the reference documents and the code rejects is a lie. Both
directions, with a guard test so an empty parse cannot pass for the wrong
reason — the same technique `tests/test_findings.py` applied to the code-smell
catalogue earlier the same day, on a different vocabulary.

The reference's `Consumed by` column must also be non-empty for every setting.
*"You could not tell which agent read which setting"* is the sentence the whole
rename came from; the column existed and nothing checked it was filled in.

## What the checks found on their first run

Six failures, all real, none of them the ones expected:

1. **`docs/specs/2026-08-06-consumer-flow-design.md:179`** still documented
   `merge_method` — nine days after the rename, in an approved specification.
   Known, and finally fixed.
2. **`recovery` had no row in any settings table.** A top-level `Config` field
   documented only through JSON examples and the per-seat table. Nobody could
   look it up. Now documented.
3. **`skills/verifying-delivery/references/code-smells.md`** named `merge_mode`
   in the *Mysterious Name* entry — written that same morning, by the session
   that wrote the trace, in an agent-facing file. Reworded to describe the
   setting without spelling the retired key. Worth recording: the rule caught
   its own author, hours after the incident that motivated it.
4-6. The two protected-path assertions and the category-reachability test in
   `tests/test_acceptance.py`, which correctly refused a new default category
   with no sample path.

## Amending the approved specification

`docs/specs/2026-08-06-consumer-flow-design.md` was **amended in place with a
dated note**, not superseded. HANDOFF recorded this as an open decision —
whether approved specs here are living documents or records of a decision — and
it is decided narrowly rather than in general: *the row documented one key's
name, and the design decision it belongs to did not change.* A superseding
document would have said the same thing at ten times the length and left the
protected document still wrong.

The general question stays open. A spec whose *decision* changes is a different
case and is not settled by this.

## What would falsify this

- **A rename that the sweep misses.** The sweep keys off `RETIRED_KEYS`, so a
  key renamed without being recorded there is invisible to it. The
  document-versus-code test catches the reference going stale, but not an old
  name lingering in a skill file. Recording the rename is still a human step.
- **The agent-facing rule blocking a legitimate explanation.** If a skill ever
  genuinely needs to name a retired key — a migration instruction, say — the
  rule is wrong rather than the file. The fix would be a narrow exemption with
  a reason, not switching the rule off.
- **Protection producing noise instead of review.** If every routine config
  edit starts routing to a human and being waved through, the gate has become
  a formality and the category should be narrowed.

## Still open, and what closed after this was first written

- **Gap (A)**: the plugin does not run its own work through its own pipeline.
- ~~**Gap (C)**~~ **closed, later the same day.** `config.vocabulary()` now
  exports the shape — names, types, defaults, enumerations, retirements, every
  value read off `Config` rather than restated — and the dashboard renders it
  through a new `config_bridge.py vocabulary` verb instead of keeping a copy.
  Its `config-schema.js` is presentation only: section order, wording, which
  fields are "advanced". A setting we add reaches the form with no edit there;
  a key the form names that we do not declare is dropped and fails a test.
  **The copy had drifted twice** — writing `merge_mode` for a week after the
  rename, then describing the retirement as if it had not happened — and
  neither was found by a check, because a hand-maintained duplicate has nothing
  that can notice it is wrong. Tests: `tests/test_config_vocabulary_export.py`
  here, and the `config schema merge` block plus the "names no setting this
  build of the plugin does not declare" case in the dashboard's
  `server/__tests__/agent-teams-config.test.js`.
- The trace's original motive — **agent-level observability**, item 4 of the
  2026-08-28 review — is broader than configuration and is not answered by
  this. Configuration was the first case, which is what HANDOFF's Next Step 2
  asked for: *start from the concrete question, not from a protocol.*

**None of this has run on a live Card.** It is tests, refusals, and documents.
