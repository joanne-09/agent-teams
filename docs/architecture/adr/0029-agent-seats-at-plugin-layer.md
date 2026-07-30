# ADR 0029: Model agent seats at the plugin layer

**Status:** accepted
**Date:** 2026-07-30
**Deciders:** PanQiWei (maintainer)

## Context

Multi-architect symmetry deliberately treats GitHub maintainer identities as
peers. An agent team needs work-specialization without turning GitHub users,
assignees, or platform subagent topology into the organization model.

## Decision

Add an orthogonal **Seat** dimension with six values: `analyst`, `architect`,
`rd`, `qa`, `em`, and `human`. GitHub Project v2 projects it as a `Role`
single-select field. A Card is observed as `(Status, Role)`; Status remains the
six-state delivery lifecycle and Role records the next work obligation.

A `[role:<seat>]` session token binds a seat before existing intent routing.
No token preserves the existing Producer/Consumer behavior. Producer and
Consumer remain execution shapes, not job titles. Architect and QA may use
either shape, so audit records keep `actor_role` and `actor_seat` separate.

Human identity remains flat. Seat is never inferred from GitHub Assignees,
comment author, account identity, or team membership. The board and structured
handoff comments are the durable coordination channel.

The existing stakeholder-routing rule remains comment-source agnostic: it
answers the named stakeholder regardless of seat. Producer blocked-work views
remain unfiltered by human architect identity; Role lanes specialize the work
obligation, not the person.

## Consequences

The plugin can express an organization without nested agents or in-memory IPC.
Every projection that supports team mode declares a Role-field setup capability.
Cards on an unupgraded board surface `role: null` and route to bootstrap/triage.

## Alternatives considered

GitHub Assignees were rejected because they model identities, not portable
agent obligations. Role-specific Status values were rejected because they
multiply the lifecycle state machine. Nested subagents were rejected as a
correctness dependency because host depth and session lifetime are transient.

## Related

- I-3 in the cross-cutting invariants, narrowed by this ADR.
- ADR-0007 and ADR-0008 runtime constraints, unchanged.
- ADR-0030 seat-aware autonomy.
- ADR-0031 semantic handoff action.
