# Retiring the renamed config keys

**Date**: 2026-09-04
**Status**: Accepted, implemented on `mvp/producer-from-scratch`
**Decides**: todo item 2 from the 2026-08-28 review, which the team lead left
to the interns after rejecting the rationale behind the current behaviour
**Depends on**:
[`docs/traces/2026-09-04-merge-mode-evidence-chain.md`](../traces/2026-09-04-merge-mode-evidence-chain.md)

## The problem being solved

On 2026-08-21 three settings were renamed:

| Old | Current |
|---|---|
| `spec_merge_mode` | `spec_pr_merge_mode` |
| `merge_mode` | `code_pr_merge_mode` |
| `merge_method` | `code_pr_merge_method` |

The old names were kept working, and the stated reason was backward
compatibility: existing test projects should not break.

The team lead rejected that reason in the 2026-08-28 review. His argument was
not about tidiness. It was that **the correct behaviour after a change is for
the tests to surface it and the pipeline to correct itself** — and that a
compatibility shim is precisely what prevents that from happening. If real
multi-version compatibility were wanted, he said, then it is a feature: two
user scenarios and test cases covering both.

## The evidence, which turned out to be stronger than the argument

The compatibility layer did not merely fail to surface a change. It concealed
two, for a week and for nine days respectively.

**The dashboard, 2026-08-21 to 08-27.** The config form kept writing
`merge_mode`. The plugin accepted it as a legacy name and wrote
`code_pr_merge_mode` on save. So the key the form read back had vanished from
the file it had just written, and the user's merge-mode choice appeared to
revert to "default" on every reload. Nothing raised, nothing logged. It was
found by someone opening the form for an unrelated reason.

**`skills/authoring-spec/SKILL.md`, 2026-08-21 to 09-04.** The architect's own
skill — the single seat that consumes `spec_pr_merge_mode` — still named
`spec_merge_mode`, and `tests/test_workflows.py` asserted that it did. The
stale name was pinned by a passing test, so a green suite was positive evidence
that the rename had *not* propagated.

Both are the same shape: **a rename the tooling absorbs is a rename nothing
downstream is forced to notice.**

## Options considered

### A. Keep both names, add two user scenarios and two test suites

The team lead's own alternative, and the honest version of "we want
compatibility". Rejected, on the grounds that it answers a question nobody
asked: agent-teams has one consuming repository under our control and one
sibling dashboard, both of which we edit. There is no installed base, no
release cadence, and no external user pinned to an old version. Paying for
multi-version support here buys a guarantee to nobody and doubles the spec and
test surface of the merge settings permanently.

If that ever changes — a real external consumer on a pinned version — this is
the option to take, and it should be taken deliberately as a feature rather
than resumed as a default.

### B. Delete the aliases

The obvious reading of "drop the old names". **Rejected, because it is worse
than the compatibility it removes.**

`Config.from_dict` ignores keys it does not recognise. Deleting `LEGACY_KEYS`
would therefore make

```json
{ "merge_mode": "manual" }
```

mean `code_pr_merge_mode: "automatic"` — the default, silently. A file that
reads as though it were honoured and is not, with no error anywhere. That
converts the current *concealed rewrite* into a *concealed reversion*, which is
the same failure mode with a worse outcome, since the reverted value is the one
that merges without asking.

### C. Retire the names — refuse them, and name the replacement (**chosen**)

A retired name is a validation error carrying its own migration instruction.

```text
$ python scripts/producer_board.py doctor
configuration is invalid:
  - 'merge_mode' was renamed to 'code_pr_merge_mode' on 2026-08-21 and is no
    longer accepted; rename the key. Its values are unchanged, so only the
    name has to move.
```

## Decision

`RETIRED_KEYS` replaces `LEGACY_KEYS`. `_retired_key_problems` runs at the top
of `Config.from_dict` and again for each seat inside `_parse_roles`, so the
refusal covers both placements. Four properties, each pinned by a test in
`tests/test_config_roles.py`:

1. **Refused, not translated.** No code path reads a value from a retired key.
2. **Refused, not ignored.** The error is the mechanism; see option B.
3. **All of them in one pass**, matching the rest of this module — a session
   that has to run `doctor` three times to learn three renames has been failed
   by its tooling.
4. **Refused even beside the replacement.** Both names present is exactly what
   a half-migrated writer emits, and it is exactly the case where the old code
   silently let the writer keep emitting a dead key.

A retired key under a seat does *not* additionally report as an unknown setting
for that seat. One mistake, one message.

### `spec_completion` is deliberately left alone

It stays accepted-and-ignored, and the asymmetry is intentional. The three
above are **renames**: the value carries over untouched, so the refusal can
state the complete migration in one line. `spec_completion` is a **removed
feature** whose values (`opened` and so on) have no equivalent in
`spec_pr_merge_mode`. A refusal could say only "delete this", which is a
migration a person has to think about rather than perform, and turning it into
a hard error would break files for no gain in information. Recorded so the
inconsistency is a decision rather than an oversight.

## Cost, paid immediately

Fifteen tests failed on the first run after the change, across
`test_workflows.py`, `test_consumer.py`, and `test_producer_board.py`. Each one
named its call site. That is not the cost of the decision — **it is the
decision working**, and it is the behaviour the team lead described: change it,
let the tests surface it, correct what they name. Suite is 537/537 after.

Two of the fifteen were not mechanical, and both were real:

- `tests/test_producer_board.py` had three tests feeding a legacy name and
  asserting the current name appeared in the message. Under retirement that
  assertion passes for the *wrong reason* — the retirement error also contains
  the current name — so it would have silently stopped testing value
  validation. Split, with the reason recorded inline.
- `tests/test_workflows.py` pinned the stale `spec_merge_mode` in
  `authoring-spec`. Inverted to refuse the old spelling.

## Out of scope here, and owed

`../agent-teams-dashboard/server/lib/agent-teams/config-schema.js` carries a
help string still describing the old behaviour ("old files still load and are
rewritten"). That repository is not on this branch and was not touched. It
writes only the current names since `8e09e4c`, so nothing there is broken — but
the sentence is now wrong and should be corrected when that repo is next
opened.

## What would falsify this

- **A real external consumer appears on a pinned older version.** Then option A
  becomes correct and this decision should be reversed deliberately, as a
  feature with its two scenarios, rather than by re-adding an alias.
- **The refusal starts firing on files nobody can fix** — for example a
  dashboard that writes a retired name and cannot be updated in step. That
  would mean the coupling in gap C of the evidence-chain trace is tighter than
  believed, and the fix is to import the schema rather than to soften the
  refusal.
