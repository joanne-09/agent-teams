# Attribution

agent-teams ships every skill it uses — nothing is invoked from another plugin
at runtime. Where a skill's text is substantially derived from an open-source
project, that derivation is recorded here and marked with a comment at the top
of the derived file.

Three of the four sources are MIT-licensed and the notices below satisfy their
conditions. The fourth, **alibaba/open-code-review, is Apache-2.0**, whose
conditions differ: a derivative must retain the attribution notice and **state
that changes were made**. Both are done — the row below names what was taken,
the derived files carry the header comment, and
`docs/decisions/2026-09-04-adopting-open-code-review.md` records exactly what
was changed in adapting it. Nothing was copied verbatim; what was taken is
review *coverage* — a category of question nobody here was asking — restated in
this repository's own terms and enforcement shape.

| Source | License | Derived into |
|---|---|---|
| [board-superpowers](https://github.com/PanQiWei/board-superpowers) — MIT, (c) 2026 PanQiWei | MIT | `skills/intaking-requirement/` (shape judgment, spec awareness, decline policy), `skills/briefing-board/` (report template, recommendation ladder, stale-claim check), `skills/triaging-board/` (stale-claim sweep, blocker classes, evidence rules), `skills/using-agent-teams/` (state table, non-signals, router anti-pattern), `skills/inspecting-queue/` (observation guards), `skills/authoring-spec/` (decomposition gates: INVEST, vertical slicing, SPIDR, sizing); each including any `references/` files. Details: `docs/skill_migration.md` + `docs/skill_migration_audit.md` |
| [superpowers](https://github.com/obra/superpowers) — MIT, (c) 2025 Jesse Vincent | MIT | `skills/consuming-card/` (test-driven-development Iron Law and Red-Green-Refactor cycle, the rationalizations table, the evidence-before-claims gate and its claim/requires table, worktree isolation discipline) incl. `references/tdd-discipline.md` + `references/claim-and-worktree.md`; `skills/verifying-delivery/` (evidence-before-claims from `verification-before-completion`); `skills/intaking-requirement/` (clarification loop, from `brainstorming`'s elicitation phase; incl. `references/clarifying-requirements.md`). Details: `docs/skill_migration.md` sections 8 + 10 |
| [gstack](https://github.com/garrytan/gstack) — MIT, (c) 2026 Garry Tan | MIT | `skills/verifying-delivery/` (from `/review`: pre-emit verification gate, confidence calibration 1-10, specialist dispatch with dedup and multi-pass confirmation, conditional adversarial pass, scope-drift detection, DONE/PARTIAL/NOT DONE/CHANGED/UNVERIFIABLE audit vocabulary; from `/qa`: screenshot evidence, repro-is-everything, console checks, credential redaction) incl. `references/review-dimensions.md`, `references/evidence-and-challenge.md`, `references/verdict-schema.md`, `references/browser-pass.md`. Details: `docs/skill_migration.md` section 9 |
| [open-code-review](https://github.com/alibaba/open-code-review) — Apache-2.0, (c) Alibaba Group | Apache-2.0 | `skills/verifying-delivery/` (the `resource-safety` review dimension, from the default ruleset's "are resources properly released" and "obvious performance issues" categories; the `critical`/`high`/`medium`/`low` severity vocabulary and the rule that severity is a separate axis from confidence; the asymmetric false-positive rule in `references/evidence-and-challenge.md`, from its review-filter prompt) incl. `references/code-smells.md` operational entries. **Not a runtime dependency and not installed** — the `ocr` CLI is an optional accelerator only. Details and gap analysis: `docs/decisions/2026-09-04-adopting-open-code-review.md` |

## INVENTED by agent-teams (2026-08-27)

The QA decomposition is not derived from any source above. gstack's `/qa`
supplies browser-evidence discipline -- repro-is-everything, console checks,
credential redaction -- applied by a reviewer who has read the code. What is
agent-teams' own:

- **The spec-blind browser seat** (`agents/qa-browser-worker.md`): a reviewer
  given the Card, the specification, and the running application but *not* the
  diff. Modelled on the team lead's account of how a real QA team designs
  scenarios without the development team's input, not on any source plugin.
- **`browser_evidence` as a validated field** (`policy.validate_verdict`):
  browser work is refused-if-absent on a user-facing pass rather than requested
  in prose. The enforcement shape mirrors this repository's own
  `falsified_by` rule.
- **The three review bundles** (`structure` / `behaviour` / `risk`): gstack
  dispatches specialists per concern; the specific grouping of eight
  dimensions into three, and the reasoning that eight passes duplicate the
  diff for overlapping findings, is agent-teams'.
- **Per-role recovery and merge configuration** (`config.roles`): no source.

Rationale and falsification conditions:
`docs/decisions/2026-08-27-qa-decomposition.md`.

`clarifying-card` is the focused existing-Card route extracted from intake.
Its preserve-one-Card rule comes from board-superpowers; its bounded
question-and-evidence discipline comes from superpowers. It introduces no new
runtime dependency on either plugin.

Derived text is adapted, not vendored: board mutations are rewired to
`scripts/producer_board.py`, sibling-plugin routing is removed, and procedures
are adjusted to agent-teams' authority model (human-only readiness, policy
refusals in code). A grep for `superpowers:` or `gstack:/` across `skills/`
must return nothing — that absence is the proof that these are derivations,
not runtime dependencies.

MIT license text of the sources is available in each linked repository.

---

## Provenance labels (2026-08-06)

Every element of the two Consumer skills carries one of three labels. The
table below is the authority; the per-file header comments summarise it.

| Label | Meaning |
|---|---|
| **DERIVED** | The idea comes from the named source. Its text was read and the claim checked against it. Wording is ours; the rule is theirs. |
| **INVENTED** | Ours. Either original to this work or pre-existing agent-teams design (ARCHITECTURE), with no counterpart in any source. |
| **REJECTED** | Present in a source and deliberately not adopted, with the reason recorded. |

### Verification status of each source

Recording *how* each claim was checked, because an attribution nobody verified
is a guess with a citation attached.

| Source | Verified how |
|---|---|
| board-superpowers `consuming-card/SKILL.md` | Read in full from `../agent-teams-main/`. |
| board-superpowers `enforcing-pr-contract/SKILL.md` | Read in full. Contracts A/B/C and the executable-check rule checked line by line against our implementation. |
| board-superpowers `enforcing-pr-contract/references/filler-detection.md` | Read in full. See the correction below. |
| superpowers `test-driven-development` | Read in full from the plugin cache. |
| superpowers `verification-before-completion` | Read in full. |
| superpowers `using-git-worktrees` | Read in full. |
| gstack `/review/SKILL.md` | Fetched verbatim (1852 lines) and each adopted rule located in the source text. |
| gstack `/qa/SKILL.md` | Fetched verbatim (1684 lines); each adopted rule confirmed present. |

### Not used, and previously over-claimed

An earlier revision of this file and of `docs/skill_migration.md` cited four
sources that did not in fact contribute. Corrected rather than quietly
dropped, because the point of these documents is that nothing is claimed
without evidence:

| Previously cited | Reality |
|---|---|
| superpowers `finishing-a-development-branch` | Read only *after* the skill was written. No content derives from it. Citation removed. |
| superpowers `requesting-code-review` | Read on review. Its substance is dispatching a reviewer *subagent* with crafted context, which we deliberately do not do. The "independent second pair of eyes" framing is a commonplace, and our bounded-pass model came from gstack's specialist dispatch. Citation removed. |
| board-superpowers `reviewing-pr-queue` | Never read. Three audit rows asserted dispositions for it. Rows removed; `inspecting-queue` remains its only derived consumer, from the earlier migration. |
| board-superpowers `consuming-card/references/stage-*.md` | Never read. The stage content we used came from the F1-F4 summaries in `SKILL.md`, which was read. Citation narrowed. |

### Corrections to specific claims

**Filler detection — part derived, part invented.** The source's implemented
set is whole-section phrases: `TBD`, `tbd`, `TODO: write tests`, `(none)`,
`n/a`, `N/A`, `nothing to verify`. Ours keeps `tbd` / `n/a` / `none` from that
set and adds `looks good` plus four "check that it works" variants, which
appear only in the source's *future, unimplemented* semantic-grade list. Our
matcher also differs in mechanic: the source rejects a phrase that forms an
entire section, ours rejects it per list item. **The four "works" phrases and
the per-item mechanic are INVENTED.**

**Auto-close keyword — a defect the unread source would have prevented.** Our
validator originally accepted only `Closes #N`. Contract C accepts
`Closes` / `Fixes` / `Resolves`, case-insensitively, and so does GitHub, so
the narrower rule would have refused Pull Request bodies GitHub handles
correctly. Fixed on 2026-08-06 once the source was actually read; a test now
asserts all three keywords in both cases.

**Confidence thresholds — adapted, not copied.** The source's table is 9-10
and 7-8 both "show normally", 5-6 "show with caveat", 3-4 "appendix only",
1-2 "only if P0". Ours compresses to "below 7 carries a caveat, 3-4 to
limitations". Same shape, different cut points.

**Acceptance-criteria waiver — stricter than the source.** Contract B requires
a `[!]` line to continue with at least 5 characters of prose. Ours requires at
least 3 words.

### What is INVENTED, in one place

Nothing below has a counterpart in any of the three sources:

- the claim compare-and-swap that pushes a unique commit, and the two-winners
  hazard it defends against;
- claim-first compensation ordering, and race-lost as a non-retryable,
  non-partial outcome;
- the `(Status, Role)` orthogonality and the `[expected:...]` staleness check;
- partial-failure envelopes with a never-replay-creation rule;
- the required review dimensions and the structured verdict document
  (ARCHITECTURE 7.4 and 9.6, which predate this work); eight of the nine are
  ours, `resource-safety` is derived — see the open-code-review row;
- the verdict/acceptance split as two types neither of which converts into the
  other, and the deterministic acceptance decision table;
- in `references/code-smells.md`, everything except the smell *names*: the
  grouping by review dimension, the per-entry descriptions tied to this
  codebase, and the "deliberately not in this catalogue" section — the
  judgment that Comments, Data Class, Refused Bequest, Alternative Classes
  with Different Interfaces and Loops would misfire here is ours. The names
  themselves are Fowler & Beck's published taxonomy (*Refactoring* ch. 3),
  cited in that file; the four `resource-safety` entries are derived — see the
  open-code-review row. `model.CODE_SMELLS` and the tests that hold the two in
  sync are ours;
- the validated finding object (`severity`, `dimension`, `confidence`,
  `evidence`, catalogue `smell`), the confidence floor that routes to
  `limitations` rather than deletion, and the refusal of a `pass` carrying a
  `critical` or `high` finding — the severity vocabulary itself is derived,
  per the open-code-review row;
- exact head-SHA binding, empty-`blind_spots`-for-a-pass, and the changed-file
  enumeration check against the live diff;
- protected-path classification and the human exception lane;
- every refusal in `policy.py`.

The sources supply engineering discipline. The authority model, the board
contracts, and the acceptance machinery are this project's own.
