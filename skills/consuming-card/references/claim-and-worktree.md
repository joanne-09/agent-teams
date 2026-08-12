# Claim and worktree

<!-- Derived from board-superpowers `consuming-card` references/stage-1-claim.md
     and references/post-merge-cleanup.md, and superpowers
     `using-git-worktrees`. Both MIT. See ATTRIBUTION.md. -->

## Why the remote branch is the claim

Two Consumers can read the same `(Ready, dev)` Card at the same instant. A
Project field cannot arbitrate that — reading and writing it is not atomic, so
both sessions observe "unclaimed" and both proceed.

The remote claim branch can. Exactly one compare-and-swap push of
`claim/<n>-<slug>` succeeds. The loser exits having written nothing.

**A local worktree is not a claim.** Another machine cannot see it. Creating a
worktree without winning the remote push means two sessions building the same
Card in mutual ignorance.

### The detail that makes it work

The claim pushes a *unique empty commit*, never the base commit both claimants
are standing on. Pushing the same SHA to an existing ref is `Everything
up-to-date`, exit 0 — git never evaluates the lease and **both claimants
believe they won**. Since both normally branch from the same base, that is the
common case, not an exotic one.

You do not have to do anything about this; `claim` handles it. It is recorded
here because it is the kind of bug that reads as correct in review and passes a
coverage-only test suite.

## Losing the race

```json
{ "ok": false, "race_lost": true, "issue": 12, "branch": "claim/12-parser" }
```

Exit code 1. This is a **normal outcome**, not a failure to recover from:

- **Do not retry.** The ref exists; retrying cannot change that.
- **Do not force-push.** That steals a claim from a session doing the work.
- **Do not delete the branch.** It is the Card's durable work, not a session's.
- **Do pick up different work** — `dispatch` will name some.

The coordinator re-reads the board. Once the Card is In Progress, a later
bounded worker materialises that same durable branch with:

```bash
producer_board.py resume N --acting-role dev
```

## Resuming an interrupted session

`resume` resolves the remote claim SHA, reuses the existing worktree when
present, or recreates it from the durable remote branch in another session.

This is why an interrupted Consumer picks up the *same logical assignment*
rather than starting a second delivery chain. The claim branch, the worktree,
and the Pull Request are all keyed to the Card, not to a session.

To see what is claimed and whether its worktree is still present:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" worktree-status
```

Read-only. It reports; it does not clean up.

## Cleanup

Only after a confirmed merge, and only through `reconcile-done`.

Two guards apply, and only one is waivable:

1. **The path must be a worktree this repository knows.** Not waivable, even
   with force. A wrong argument must never recursively delete an unrelated
   directory.
2. **The worktree must be clean.** Uncommitted or untracked files refuse the
   removal and are listed. Waivable with force, deliberately, after you have
   looked at what would be lost.

If cleanup fails during `reconcile-done`, the reconciliation still succeeds —
the Card reaching `Done` is the durable outcome. The failure is reported with a
recovery command rather than silently forced.

## Naming

Both derive from Card identity, so any session can recompute them without
stored state:

```
branch:   claim/<n>-<slug>
worktree: <workspace>/claim-<n>-<slug>
slug:     title casefolded, non-alphanumeric runs collapsed to "-", max 40 chars
```

`<workspace>` comes from configuration and resolves outside the repository
tree. Repo-internal worktrees get scanned by editors and file watchers, and
create real confusion about which checkout is canonical.
