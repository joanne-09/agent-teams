# ADR 0030: Seat-dimension autonomy and handoff authority

**Status:** accepted
**Date:** 2026-07-30
**Deciders:** PanQiWei (maintainer)
**Supersedes:** ADR-0006, except its historical audit rationale remains useful

## Context

A one-dimensional action class allows any agent shape to perform an action
once the generic row permits it. That cannot enforce the organization encoded
by Role lanes.

## Decision

Classify every mutation as `(action_id, seat) -> A | R | N`. Missing seat
preserves the former one-dimensional default. Unknown seats warn and use that
legacy default. A known-seat `N` is an authority hard floor and cannot be
promoted by configuration.

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

Row 12 is `N` for every agent seat. Humans merge; agents only propose.

### Handoff authority

| From / To | analyst | architect | rd | qa | em | human |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| analyst | - | shape | - | - | escalate | question |
| architect | return | - | dispatch | dispatch | escalate | question |
| rd | - | escalate | - | PR ready | escalate | - |
| qa | - | escalate | reject | - | escalate | merge gate |
| em | route | route | route | route | - | route |
| human | route | route | route | route | route | - |

A dash is an unconditional refusal before mutation. Legal edges still pass
through action classification. The default handoff cap is six; a further
attempt is refused and escalated to EM.

### Override precedence

Settings may carry generic `autonomy_overrides` plus `seat_overrides`. The
resolver applies project > user > seat > legacy default. Within one file, a
generic entry wins over a seat-specific entry. Project settings win over user
settings. No layer promotes a known-seat `N`.

### New action identifiers

| action_id | Action | Legacy default |
|---:|---|:---:|
| 300 | Handoff Card | A |
| 301 | Escalate to lead seat | A |
| 302 | Reject or bounce Card | A |
| 303 | Emit agent dispatch | A |
| 304 | Write QA verdict | A |
| 305 | Refuse illegal handoff | A |

Existing actions retain their identifiers; the audit seat distinguishes the
actor.

## Consequences

Authority is enforced at the mutation boundary, not documented as etiquette.
The architect can split Cards automatically while RD cannot. QA cannot certify
work from another seat. Legacy sessions remain operational without a seat.

## Alternatives considered

Per-seat action-id ranges were rejected as duplicate semantics. Advisory-only
roles were rejected because they do not enforce reporting lines. Configurable
N promotion was rejected because it would erase the authority boundary and the
human merge floor.

## Related

- ADR-0006 is immutable historical context and is superseded by this ADR.
- ADR-0029 defines seats.
- ADR-0031 defines handoff semantics.
