---
name: classifying-actions
description: |
  Use when a board-superpowers workflow is about to mutate board, git,
  configuration, audit, or session state and must decide whether the bound
  seat may act automatically, must request approval, or must refuse. Use at
  every mutation gate, including handoffs and dispatches. Do not use for
  read-only work or for writing the audit row after the decision.
user-invocable: false
---

# classifying-actions

This is the single decision-table authority for mutating actions. Call it
with `(action_id, seat)`. It returns `A`, `R`, or `N`.

- `A`: execute, then write one audit row.
- `R`: write a proposal row, wait for human resolution, then write the
  approved or rejected row.
- `N`: refuse before mutation and record the refusal when a refusal action id
  exists.

## Algorithm

1. Find the action in `references/action-id-catalog.md`.
2. If a valid seat is bound, read its cell in `references/matrix.md`.
   Missing seat preserves the legacy one-dimensional behavior. Unknown seats
   warn and use the legacy default.
3. Treat `N` as an authority hard floor. Configuration cannot promote it.
4. Apply `references/triage-rule.md`; a matching safety condition may promote
   `A` to `R`, never the reverse.
5. Resolve configuration with:

```bash
bsp_resolve_autonomy_class <action_id> <repo_root> [seat]
```

6. Use the returned class. Never infer permission from job title or from an
   earlier action on the same Card.

## Override precedence

The helper recognizes legacy and modular settings. Precedence is:

```text
project generic/seat override
  > user generic/seat override
  > built-in seat cell
  > legacy action default
```

Read `references/override-parsing.md` for accepted YAML shapes. Project and
user layers may tune `A` versus `R`; neither can promote an `N` seat cell.

## Non-negotiable examples

- Merge action 12 is `N` for analyst, architect, RD, QA, and EM.
- Architect may split a Card automatically; RD may not split it.
- RD may claim implementation work; analyst and EM may not.
- QA verdict action 304 belongs to QA; another seat cannot self-certify.
- Handoff action 300 still requires the separate authority edge check in
  `board-superpowers:board-canon`.

## Reference routing

| Need | Read |
|---|---|
| Exact seat class | `references/matrix.md` |
| Action meaning | `references/action-id-catalog.md` |
| Safety escalation | `references/triage-rule.md` |
| YAML and precedence | `references/override-parsing.md` |

This skill classifies. `board-superpowers:auditing-actions` records.
