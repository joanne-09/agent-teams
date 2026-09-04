# Self-hosting: what makes it safe, and what is still a decision

**Date**: 2026-09-04
**Status**: the safety property is enforced; **adoption is not done** and needs
a board plus an explicit decision
**Closes the mechanism half of**: gap (A) of
[`docs/traces/2026-09-04-merge-mode-evidence-chain.md`](../traces/2026-09-04-merge-mode-evidence-chain.md)

## The objection that turned out to be wrong

Gap (A) — *agent-teams does not run its own work through its own pipeline* —
was filed as a scope decision, and defended with an objection that sounds
fatal:

> The QA that reviews a change to `policy.py` **runs on** `policy.py`. A diff
> that breaks `validate_verdict` is waved through by the code it broke, and the
> suite can be green because the assertions were edited with it.

That was stated in this session and it is **wrong for this codebase**. Every
seat invokes `${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py` — the
*installed* plugin, which is the last **merged** version — while the code under
review sits in the Pull Request and its detached worktree.

Old plugin reviews new plugin. It is the compiler bootstrap, and it was already
true here by accident of how Claude Code loads a plugin: the thing doing the
reviewing is not the thing being reviewed.

Verified rather than assumed: 25 executable invocations across `skills/` and
`agents/`, **all 25** through `${CLAUDE_PLUGIN_ROOT}`, none through a
repository-relative path.

## Decision

### 1. The fixed point is now checked, not merely true

`tests/test_self_hosting.py`. One skill rewritten to call
`scripts/producer_board.py` would silently convert self-review into
self-excusing, and — on today's evidence — nobody would notice for a week.
Mutation-checked: pointing `verifying-delivery` at the checkout fails the
suite; restoring it passes.

The check deliberately distinguishes an **invocation** from a **mention**.
`agents/*.md` say "run every `producer_board.py` command with
`AGENT_TEAMS_ACTING_ROLE=…`" as guidance, and `docs/CONFIGURATION.md` shows a
consuming user an absolute install path before any plugin exists. Neither can
bind the wrong copy. Only a real command line can.

### 2. Install only after merge

The fixed point is a property of *what is installed*, so it survives exactly as
long as that discipline does: **the installed plugin is updated after a merge,
never before.** Installing an unmerged build hands the fixed point back — the
code under review becomes the code reviewing.

This one is not checkable from inside the repository. It is a rule, it is
written here, and it is the single thing to get wrong.

### 3. Authority stays at the human gate regardless

`policy.py`, `model.py`, `workflows.py` and `git.py` are already protected
paths, joined today by `config.py` and `docs/CONFIGURATION.md`. Under
self-hosting a change to any of them routes to a person whatever the review
concluded.

That is what makes adoption a smaller decision than it looks: the blast radius
of a bad self-approval is bounded by a gate that already exists.

### 4. Adopt in one half, not all at once (**proposed, not taken**)

Everything except the protected authority code goes through the pipeline —
skills, references, documentation, tests, the config vocabulary. That covers
most of this session's work at a friction cost that can be measured before
committing further.

## What is genuinely not done

**The pipeline is not running on itself.** There is no board for this
repository, no `.agent-teams/config.json`, and `gh` is unauthenticated in this
environment, so none of that could be created here. Concretely, adoption needs:

1. a GitHub Project for `joanne-09/agent-teams`;
2. `producer_board.py init` against it, producing this repository's own
   `.agent-teams/config.json`;
3. `producer_board.py doctor` green;
4. a first Card, which is the bootstrap.

**Do not read this document as "we now self-host."** What is finished is that
self-hosting is *sound* — the objection that made it look impossible does not
apply, and the property it depends on is enforced rather than assumed.

## The honest cost, since it is why this never happened

Today's work would have been roughly six to eight Cards. Changing one line of a
reference document would need a Card, a spec baseline, a Pull Request and a
verdict. **That friction is the real reason it has not been done**, and it is a
judgment call about whether the evidence is worth it — not a technical
obstacle. It should be taken out loud, by a person, rather than left implicit
as it has been since the project started.

## What would falsify this

- **The installed plugin drifting from `main`.** If anyone installs an unmerged
  build, the bootstrap argument fails and self-review is worthless. Nothing here
  can detect it; a person has to hold the rule.
- **A seat needing to run the checkout's own entry point.** If some future
  workflow legitimately requires it, the fixed point needs a different
  construction rather than an exemption.
- **Adoption producing ceremony instead of evidence.** If every Card is
  approved without reading, self-hosting has bought paperwork. The measurable
  signal is whether any self-hosted Card ever produces a `fail`.
