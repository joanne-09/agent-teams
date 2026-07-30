# Queue ordering examples

A QA Card in In Review outranks new RD work because it releases an existing
WIP slot. A dependency-free architect spec that unblocks three RD Cards outranks
an older isolated spec. A Blocked Card is never presented as ordinary claimable
work; it appears as an escalation review. Missing Role always appears in the
unassigned lane.

Tie-break order: downstream unblock count, board age, then stable Card key.
