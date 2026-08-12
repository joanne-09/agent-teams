# Demo transcripts - 2026-08-06/07 毒油地圖 run

Complete conversation records of every Claude Code session in the demo, 
exported from the cc_team session store. One file per session.

- [`01-intake-and-spec.md`](./01-intake-and-spec.md) - Steps 1-2 - analyst intake (7 clarifying questions -> card #12), then architect spec (research subagent -> spec PR #13)
- [`02-decompose-and-promote.md`](./02-decompose-and-promote.md) - Steps 4-5 - architect decompose (#14 walking skeleton + #15 + #16), then the human promote of #14 (typed CLI command)
- [`03-dispatch.md`](./03-dispatch.md) - Step 6 - lead dispatch: 'what's ready to work on?' -> one [role:dev] [board-card:#14] kickoff rendered
- [`04-dev-implement.md`](./04-dev-implement.md) - Step 7 - dev consuming-card: pasted kickoff -> preflight, claim, worktree, TDD implement, one PR (#17), handoff to qa
- [`05-qa-first-look-paused.md`](./05-qa-first-look-paused.md) - QA 'verify card #14' - found the empty delivery (0 changed files) plus a QA-tooling bug; session paused before publishing
- [`06-qa-fail-verdict.md`](./06-qa-fail-verdict.md) - QA kickoff -> published the fail verdict (empty claim-marker head); policy routed defect -> (In Progress, dev)
- [`07-dev-defect-fix.md`](./07-dev-defect-fix.md) - Dev fix-forward on the same Card/branch/PR: pushed the missing implementation commit 7538441 via submit-pr
- [`08-qa-pass-verdict.md`](./08-qa-pass-verdict.md) - QA re-verify -> pass verdict bound to head 7538441, superseding the fail; handoff to the human merge gate
- [`spec-0004-taiwan-oil-violation-map.md`](./spec-0004-taiwan-oil-violation-map.md) - full text of the merged spec (PR #13), copied from the workload repo's `specs/` directory
