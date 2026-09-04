# Evidence chain: the merge-mode split

**Date**: 2026-09-04
**Traces**: the 2026-08-21 rename of `merge_mode` into `spec_pr_merge_mode` and
`code_pr_merge_mode`, as implemented on 2026-08-27
**Asked for by**: the team lead, 2026-08-28 review, todo item 1
**Answer in one line**: there is no chain. The change never entered the
pipeline, and the two places it failed to reach were found by accident a week
apart — one of them not until this trace was written.

---

## The question

The team lead asked for four links to be followed, in order:

1. **Who initiated it** — did we change it ourselves, or was it delegated to
   the architect to change?
2. **Was it written into the spec** during that process?
3. **Once the spec was agreed, did the developer change the code to match?**
4. **Did QA actually generate a check plan covering the two variants?**

And the instruction attached to it: *if it did not flow through as one chain,
we failed to delegate somewhere — find the break.* His stated motive was that
this is the same problem as agent-level observability: when something changes,
we have to know who initiated it and how it travelled.

## Method

Everything below is reproducible from this checkout. What was searched:

- `git log --follow -- scripts/agent_teams/config.py`, and the full history of
  `mvp/producer-from-scratch`.
- `docs/specs/`, `docs/decisions/`, `docs/plans/` — every artifact the pipeline
  writes or reads as a design baseline.
- Every occurrence of the three old and three new names across `scripts/`,
  `skills/`, `agents/`, `docs/`, `tests/`, and `README.md`.
- The sibling consumer of the same vocabulary,
  `../agent-teams-dashboard/server/lib/agent-teams/config-schema.js`.
- `HANDOFF.md` session logs 12, 12b, 13, 14, 15.

No board was queried: `gh` is unauthenticated in this environment. That does
not weaken the finding — see link 4, where the absence is established from the
repository itself rather than from the board.

---

## The four links

### 1. Who initiated it — **a human, outside the pipeline**

The team lead raised it verbally in the 2026-08-21 review ("the names cannot be
told apart"). An intern carried it into a Claude Code session, which
implemented it directly on the plugin checkout.

Evidence: commit `9cc1983` (Joanne, 2026-08-27 18:58 +0800, *"implement qa
rebuild and config per role"*), 20 files, +1891/−113. The rename arrives inside
that commit together with the per-role config block and the whole QA
decomposition — three of the five 08-21 todo items in one commit.

There is no Card, no Issue, and no intake record for it. Nothing was delegated
to the architect.

### 2. Was it written into the spec — **no**

`docs/specs/` contains exactly one document that describes configuration:
`2026-08-06-consumer-flow-design.md`, the approved Consumer design. Its
configuration table still reads:

```text
docs/specs/2026-08-06-consumer-flow-design.md:179
| `merge_method` | string | `"squash"` | One of `squash`, `merge`, `rebase` |
```

Nine days after the rename, the approved specification still documents the
retired name and knows nothing about the split. No spec was written, amended,
or superseded for this change. `docs/decisions/` gained a record on 08-27, but
for the QA decomposition — not for the rename.

This is the break the team lead guessed at before the trace was run.

Worth noting precisely because it is invisible: `docs/specs/**` is one of the
seven **protected path categories** (`config.DEFAULT_PROTECTED_PATHS`,
`architecture-and-design`). A delivery touching it routes to a human. The
rename changed the exact subject matter that file governs without touching the
file, so the protection never engaged. Protection is on the path, and the
authority it guards is the content.

### 3. Did the developer sync the code — **yes, in the same keystroke, which is the problem**

The code and the naming decision are the same commit by the same author in the
same session. There was no spec to sync *to* and no handoff to sync *across*,
so link 3 cannot be said to have succeeded or failed: it did not occur.

What did occur is a rename sweep of the surrounding text, and it was
incomplete. Session 12 swept README, USAGE, ARCHITECTURE, and
IMPLEMENTATION_PLAN. Session 13 found `dispatching-work` had been missed and
fixed it. Two more were missed and survived:

- **`skills/authoring-spec/SKILL.md`** lines 15 and 17 still said
  `spec_merge_mode` — the skill belonging to the **architect, the one seat that
  consumes this setting**. Found by this trace on 2026-09-04 and fixed here.
- **`tests/test_workflows.py`** asserted `assertIn("spec_merge_mode: manual",
  skill)`. So the stale name was not merely missed, it was *pinned*: a green
  suite was positive evidence that the rename had not propagated. Corrected
  here, with the assertion inverted to refuse the old spelling.

### 4. Did QA generate a check plan for the two variants — **no, and it could not have**

No QA verdict exists that mentions either name; no Card carries the change; the
QA seat never saw it. Two structural reasons, and the second is the one worth
fixing:

1. **This repository is not governed by its own pipeline.** agent-teams governs
   *consuming* repositories. Its own source is edited by hand. Every 08-21 todo
   item was implemented this way.
2. **`.agent-teams/config.json` is not a reviewable artifact even inside a
   consuming repository.** It is read by `Config`, edited through the
   dashboard, and never enters a Card, a diff, a spec, or a verdict. There is
   no path by which QA could be asked to check a configuration change, because
   configuration is not something this system knows how to route.

---

## What actually happened

```text
lead (verbal, 08-21)
   └─> intern
        └─> one Claude session
             └─> 9cc1983 : code + docs + tests, all at once
                  ├─> README / USAGE / ARCHITECTURE / IMPLEMENTATION_PLAN   swept 08-27
                  ├─> skills/dispatching-work                    missed, fixed 08-28
                  ├─> skills/authoring-spec                      missed, found 09-04 (this trace)
                  ├─> docs/specs/2026-08-06-consumer-flow-design still wrong today
                  └─> ../agent-teams-dashboard (separate repo)   missed, broke live
```

Four consumers of the renamed vocabulary. The sweep reached one group of them
and missed three, and each miss was found by a different accident, at a
different time, by a different person.

## The two live breaks the compatibility shim hid

**The dashboard, found 2026-08-27 (session 12b).** The config form kept writing
`merge_mode`. The plugin accepted it as a legacy name and saved
`code_pr_merge_mode` — so the key the form looked for had disappeared from the
file it had just written, and the user's merge-mode choice appeared to revert
to "default" on the next read. Nothing threw. Nothing logged. It was found
because someone opened the form for an unrelated reason. Fixed in the dashboard
as `8e09e4c`.

**The architect's own skill, found 2026-09-04 (this trace).** Above.

Both are the same failure with different surfaces: **a rename that the tooling
absorbs is a rename nothing downstream is ever forced to notice.** The
compatibility layer was added so old test projects would not break. It worked —
and in doing so it converted a loud, immediate, one-line failure into a silent
one that took a week to surface and a second one that took nine days.

That is the evidence for the team lead's position on todo 2, and it is why the
old names are now refused rather than translated
([`docs/decisions/2026-09-04-retiring-renamed-config-keys.md`](../decisions/2026-09-04-retiring-renamed-config-keys.md)).
The change was made, the suite was run, fifteen tests failed at once and named
every call site — the pipeline self-correcting, exactly as he described it.

## Where the handoff was missing

Three distinct gaps, only one of which is the one that was guessed at:

| # | Gap | Where it bites |
|---|---|---|
| A | **The plugin does not eat its own dog food.** Its source is hand-edited; the pipeline governs consuming repositories only. | Every change to agent-teams itself is unrouted, unspecified, and unreviewed by the machinery it ships. |
| B | **Configuration is not a governed artifact.** No Card, spec, diff, or verdict can carry a config change, in this repository or a consuming one. | QA structurally cannot be asked to check a config change, so link 4 has no mechanism to fail — it has no mechanism at all. |
| C | **The vocabulary has consumers outside the repository, tracked by nothing.** The dashboard's `config-schema.js` is documentation-derived, hand-copied, and not imported from `Config`. | A rename or an addition here is silently absent there. Already recorded in HANDOFF Known Issues, and now with a second instance behind it. |

Gap A is a scope decision, not a defect, and it should be stated as one rather
than left implicit. Gap B is the actionable one. Gap C is known and unfixed;
the dashboard test pins the three renamed keys, which catches a *rename* and
cannot catch an *addition*.

## What follows from this

1. **Done here** — the old names are refused, not translated (todo 2). The
   fifteen failing tests are the mechanism the team lead described.
2. **Done here** — `authoring-spec` corrected, and the test that pinned the
   stale name inverted.
3. **Still open** — `docs/specs/2026-08-06-consumer-flow-design.md:179` still
   documents `merge_method`. It is an *approved, historical* design record, so
   editing it in place is itself a decision: either amend it with a dated note,
   or supersede it. Not done unilaterally in a trace document.
4. **Still open — gap B.** Making configuration routable is the natural first
   real observability requirement, and it is a narrower question than "add
   observability": *which artifacts can carry a change, and what does the
   system do when someone changes one that cannot?*
5. **Feeds todo 4.** This trace was assembled by hand from git history, four
   documents, and two repositories, over about an hour. The lead's stated
   motive for asking was to see whether such a trace can be produced at all.
   The answer is that it can, and only by hand — which is the argument for the
   observability work rather than a preamble to it.
