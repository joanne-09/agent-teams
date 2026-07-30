# Seat-aware decision matrix

Missing seat preserves the legacy one-dimensional class. With a known seat, this table is the authority hard floor before configurable overrides. `N` cannot be promoted by an override.

| action_id | Action | analyst | architect | rd | qa | em | human |
|---:|---|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | Create cards | A | A | N | N | A | A |
| 2 | Edit card body | A | A | N | N | A | A |
| 3 | Split card | N | A | N | N | R | A |
| 4 | Update agent instruction source | N | R | N | N | R | A |
| 5 | Backlog to Ready | N | A | N | N | A | A |
| 6 | Move active work to Blocked | R | R | R | R | R | A |
| 7 | Close stale card | N | R | N | N | R | A |
| 8 | Cancel claim | N | R | R | N | R | A |
| 9 | Adjust WIP limit | N | A | N | N | A | A |
| 10 | Modify board-superpowers config | N | R | N | N | R | A |
| 11 | Extend board fields | N | A | N | N | A | A |
| 12 | Merge PR | N | N | N | N | N | A |
| 13 | Dispatch Consumer session | N | A | N | N | A | A |
| 14 | Auto-trigger report | N | N | N | N | A | A |
| 100 | Claim card | N | A | A | A | N | A |
| 101 | Surface and suspend | N | R | R | R | N | A |
| 102 | Terminate success | N | A | A | A | N | A |
| 103 | Terminate failure | N | R | R | R | R | A |
| 104 | Write retro notes | N | A | A | A | N | A |
| 105 | Direct review fix | N | A | A | A | N | A |
| 106 | Review re-delegation | N | A | A | A | N | A |
| 107 | Verification chain | N | A | A | A | N | A |
| 108 | Cross-platform review | N | A | A | A | N | A |
| 109 | QA pass | N | A | A | A | N | A |
| 110 | Security audit | N | A | A | A | N | A |
| 111 | Review cycle completion | N | A | A | A | N | A |
| 112 | PR preflight card sync | N | A | A | N | N | A |
| 113 | Post-merge cleanup | N | A | A | A | N | A |
| 200 | Bootstrap host | N | A | N | N | A | A |
| 201 | Ensure labels | N | A | N | N | A | A |
| 202 | Write repo config | N | A | N | N | A | A |
| 203 | Append gitignore | N | A | N | N | A | A |
| 204 | Write audit credentials | N | A | N | N | A | A |
| 205 | Sync venv | N | A | N | N | A | A |
| 206 | Initialize audit DB | N | A | N | N | A | A |
| 207 | Inject routing block | N | A | N | N | A | A |
| 208 | Write repo state | N | A | N | N | A | A |
| 300 | Handoff card | A | A | A | A | A | A |
| 301 | Escalate to lead seat | A | A | A | A | A | N |
| 302 | Reject or bounce card | N | A | N | A | A | A |
| 303 | Emit agent dispatch | N | A | N | N | A | A |
| 304 | Write QA verdict | N | N | N | A | N | A |
| 305 | Refuse illegal handoff | A | A | A | A | A | A |

## Invariants

- Row 12 is `N` for every agent seat. Only the human merge gate acts.
- Unknown action ids retain the legacy safe-on-execution fallback when no seat is bound.
- Unknown seats produce a warning and use the legacy class; they never abort routing.
- Legal handoff destinations are validated separately by `board-canon`; action 300 being `A` does not make an illegal edge legal.
