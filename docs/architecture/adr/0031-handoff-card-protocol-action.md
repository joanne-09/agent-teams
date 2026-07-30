# ADR 0031: handoff_card as the ninth Kanban Protocol action

**Status:** accepted
**Date:** 2026-07-30
**Deciders:** PanQiWei (maintainer)
**Extends:** ADR-0025

## Context

Role is a semantic work obligation. A generic field setter would leak one
backend's storage model and would omit authority, the durable receiving
contract, and audit behavior.

## Decision

Extend the Kanban Protocol with:

```text
handoff_card(card, from_seat, to_seat, reason)
```

Preconditions: Card exists; current Role equals `from_seat` when set; the
authority edge is legal; the handoff count is below the configured cap; and
the projection supports Role. Postconditions: Role equals `to_seat`, one
structured handoff comment exists, and one action-300 audit row records the
seat and edge. Status is unchanged. A lifecycle move is a separate
`transition_card` action.

The GitHub Project v2 Form A projection performs: (1) set Role option, (2)
post the marker comment, (3) write the audit row. Illegal edges and cap
breaches refuse before mutation and use action 305. A Role write followed by
comment failure is a surfaced partial failure, never a blind retry.

```markdown
<!-- board-superpowers:handoff -->
**Handoff**: `<from>` -> `<to>`
**Reason**: <reason>
**Needs from you**: <receiving obligation>
**Artifacts**: <links and identifiers>
```

## Consequences

Every backend projection must implement handoff for full team compliance. Role
writes and Status transitions remain independently idempotent and auditable.

## Alternatives considered

A generic `set_card_field` was rejected because the protocol is semantic, not
an SDK. Status-per-role was rejected because it couples ownership to lifecycle.
Comments without a Role write were rejected because they cannot be queried as
lanes.

## Related

- ADR-0025 remains accepted and is extended, not superseded.
- ADR-0029 defines Role and seats.
- ADR-0030 defines handoff authority.
