---
name: dispatching-work
description: |
  Use when an EM-seat session must decide which role-owned cards should run
  next, render kickoff prompts for the selected seats, or inspect whether WIP
  and repeated handoffs make a dispatch unsafe. Trigger on `[role:em]` with
  "dispatch", "assign the queues", "who works next", or "start the team".
  Do not use for a personal board briefing with no dispatch decision.
when_to_use: |
  Use for team queue selection and carrier-neutral kickoff generation after
  the board has Role lanes. A missing Role field routes to bootstrap instead.
user-invocable: true
---

# dispatching-work

Produce a deterministic dispatch queue from durable board state. A dispatch
queue is an artifact, not an in-memory org chart: every seat can be started by
a human terminal, a one-deep subagent carrier, or cron without changing the
decision.

Required skills:

- `board-superpowers:board-canon` for Role authority, handoff cap, Status, and WIP.
- `board-superpowers:operating-kanban` for `read_board` and Card reads.
- `board-superpowers:classifying-actions` for action 303 with seat `em`.
- `board-superpowers:auditing-actions` for each emitted dispatch decision.

## Preconditions

1. Bind seat `em`. A human may explicitly run the routine as an overseer.
2. Resolve the active projection from repository settings.
3. Confirm the projection exposes Role. If Role is absent, invoke
   `board-superpowers:bootstrapping-repo`; do not fabricate lanes.
4. Load the WIP limit and handoff cap. Invalid values use their documented
   defaults and surface a warning.

## Read the durable queue

Invoke `read_board` without a Status filter. Preserve `role: null`; missing Role
is a triage defect, not an implicit RD assignment. For every non-Done Card,
collect:

- key, title, Status, Role, labels, and URL;
- claim branch or open PR when the Status requires one;
- count of comments carrying `board-superpowers:handoff`;
- latest structured handoff comment;
- hard dependencies still not Done.

Group by Role first, then by Status. Show a separate `unassigned` lane. Never
use GitHub Assignees as Role.

## Guard the lanes

For each seat, calculate active WIP using `board-superpowers:board-canon`.
Blocked Cards do not count. A seat at its cap may continue its already-active
Card but receives no additional claim dispatch.

Apply the default handoff cap of six. At five, annotate `near-cap`; at six, do
not dispatch another transfer. Route the Card to EM triage.

Reject candidates with:

- a missing or illegal Role value;
- a hard dependency that is not Done;
- Status/Role mismatch, such as Ready work assigned to QA without an open PR;
- no legal next action in the seat matrix;
- a claim race or another session already owning the claim branch;
- a handoff cap breach.

Do not fix these while dispatching. Emit them under `Refused` with the exact
rule and recommended triage routine.

## Order the candidate queue

Use this stable priority order:

1. `(In Review, qa)` verification obligations with open PRs.
2. `(Backlog, architect)` specification or decomposition work whose input is sufficient.
3. `(Backlog, analyst)` requirements explicitly returned for clarification.
4. `(Ready, rd)` implementation Cards, dependency-free, oldest first.
5. `(Blocked, architect|em)` explicit escalation reviews; these are triage
   dispatches, not new implementation WIP.
6. Other legal seat-owned work, oldest board entry first.

Within a tier, prefer the Card closest to unblocking other Cards, then oldest.
Do not prioritize by size alone. Do not dispatch more than the caller's stated
limit; default one Card per seat per pass.

## Validate each dispatch

For each candidate:

1. Identify the concrete next action and its action id.
2. Consult `board-superpowers:classifying-actions` with that seat. A returned
   `N` refuses the candidate. A returned `R` produces a proposal, not a launch.
3. Classify action 303 with seat `em`.
4. Render the kickoff through:

```bash
bash <plugin-root>/scripts/dispatch-agent.sh --seat <seat> --card <N> --format paste
```

Use `subagent` or `cron` only when the caller selected that carrier. The prompt
content remains equivalent across formats.

## Audit boundary

Rendering a prompt is pure. Choosing and publishing it as the next team action
is action 303. For every emitted queue entry, write one audit row with:

- `actor_seat: em`;
- destination seat and Card key;
- selected action id and reason;
- carrier format;
- WIP and handoff counts observed at decision time.

If classification is R, follow the two-entry approval sequence. Never audit a
refused illegal seat action as a successful dispatch.

## Output

Return one compact table:

| Order | Seat | Card | Next action | Why now | WIP | Handoffs | Kickoff |
|---:|---|---|---|---|---:|---:|---|

Then include `Refused` and `Needs human approval` sections when non-empty. The
queue must be reproducible from the snapshot: state the active projection and
snapshot time. Do not claim an agent was launched unless the chosen carrier
actually launched it.

## Lane-to-routine map

A dispatch identifies the receiving obligation, not merely the seat name.
Use the following mapping after the queue rules have selected a Card:

| Seat | Eligible work | Kickoff routine | Required durable input |
|---|---|---|---|
| analyst | unclear requirement or returned question | `board-superpowers:intaking-requirement` | request, evidence, latest handoff |
| architect | specification, ADR, decomposition, design correction | `board-superpowers:authoring-spec` or `board-superpowers:decomposing-into-milestones` | Backlog Card and source pointer |
| rd | implementation-ready vertical slice | `board-superpowers:consuming-card` | Ready Card with specification pointer |
| qa | independent delivery review | `board-superpowers:reviewing-pr-queue` in this producer slice | In Review Card and open PR |
| human | merge or product judgment | no autonomous skill | explicit question and evidence |

The `qa` row intentionally routes to the existing review-queue routine in this
producer slice. Do not claim `board-superpowers:verifying-delivery` exists until
the QA slice ships it. EM has no self-dispatch row: EM continues the current
routine or performs `board-superpowers:triaging-board` directly.

## Carrier selection

Carrier is an execution detail chosen after the queue is valid:

- `paste` is the safe default and always available. Return the prompt for a
  human or external orchestrator to start.
- `subagent` is allowed only when the host exposes a one-deep agent carrier and
  the chosen receiving routine is procedural at that depth.
- `cron` renders a persistent-state-oriented command. It does not grant new
  authority and must not embed credentials or transient context.

Never infer that a carrier exists because a prompt format can be rendered.
`dispatch-agent.sh` is a pure renderer; it launches nothing. If the caller asks
to launch work and the platform exposes no authorized carrier, return the paste
form and label the dispatch `not launched`.

For a launched subagent, the kickoff must include the role token, Card token,
and obligation. Do not send the entire board snapshot. The receiving session
must re-read durable board state and the latest handoff before acting.

## Snapshot rules

The dispatch decision is valid only for the snapshot it names. Record:

1. repository and active projection;
2. board identifier;
3. snapshot time in UTC;
4. WIP limit and handoff cap used;
5. the selected Card's Status and Role;
6. unresolved dependency keys;
7. claim or PR evidence relevant to eligibility.

If a mutation occurs after the snapshot and before launch, re-read the selected
Card. A changed Status, Role, claim, dependency, or handoff count invalidates
the decision. Re-run candidate validation; do not reuse the stale ranking.

A partial board response is not a smaller snapshot. It is an invalid snapshot.
This includes pagination truncation, a failed comment read, or Role omitted by
the projection. Surface the missing read explicitly.

## Repeated-handoff handling

Handoff count is a coordination-risk signal, not a performance score.

- Counts zero through four do not affect eligibility.
- Count five annotates `near-cap` and requires the dispatch reason to explain
  why another seat boundary is preferable to resolving in place.
- Count six or more refuses transfer and routes to EM triage.
- A malformed handoff comment is reported but does not increment the count.
- Reassigning Role without the structured marker is a board defect and must not
  be treated as a legal handoff.

Never reset the counter by deleting comments, recreating the Card, or editing an
old marker. The cap protects context continuity across sessions.

## Approval handling

An `R` classification creates a proposed dispatch entry containing the exact
seat, Card, carrier, and reason. Wait for the approving actor before launch.
Approval of one entry does not approve adjacent queue entries. If state changes
while approval is pending, invalidate the proposal and classify a fresh one.

An `N` classification is a hard floor. No config override, carrier selection,
or human phrasing inside an EM prompt converts it to A or R. State the matrix
cell and the legal escalation destination.

Human approval does not legalize an authority-invalid handoff. Authority is
checked before autonomy because they answer different questions: whether an
actor may perform the action at all, then whether the legal action needs
approval.

## Failure-mode table

| Failure | Result | Recovery |
|---|---|---|
| Role field absent | stop bootstrap-required | run `board-superpowers:bootstrapping-repo` |
| Role option set malformed | stop config-repair | repair the Project field, then re-run bootstrap |
| unknown Role value | refuse Card | EM triage and canonical Role assignment |
| dependency unreadable | refuse Card | restore the dependency link or board read |
| claim collision | refuse launch | receiving routine reclaims after collision clears |
| WIP limit reached | omit new work | finish, block, or release current WIP |
| handoff cap reached | refuse transfer | EM resolves ownership or asks human |
| audit sink unavailable | follow audit degradation policy | recover sink or obtain required approval |
| carrier unavailable | return paste form | human starts a session |
| dispatch script failure | no launch claim | show stderr and preserve queue evidence |

Do not hide failures by returning an empty queue. Distinguish `no eligible work`
from `unable to determine eligible work`.

## Rationalization guards

Reject these shortcuts:

- "RD usually owns unassigned cards" ? missing Role remains unassigned.
- "QA can just fix it" ? QA owns evidence; production fixes return to RD.
- "The Card is tiny" ? size does not bypass Role, dependency, claim, or WIP.
- "The last dispatch worked" ? every pass uses a fresh durable snapshot.
- "The human asked for everyone" ? limits and hard floors still apply.
- "This is only a prompt" ? publishing a selected next action is audited.
- "Subagent is faster" ? carrier speed does not alter procedural compatibility.
- "One more handoff is harmless" ? the cap is enforced before mutation.

## Verification checklist

Before returning the queue, verify:

- every selected Card appeared exactly once;
- every selected Role is canonical;
- every kickoff token matches the selected Role and Card;
- every implementation Card is Ready before RD dispatch;
- every QA entry has an In Review Card and discoverable PR;
- every architect entry is docs/spec work, not production implementation;
- every analyst entry names the missing requirement decision;
- no new dispatch exceeds seat WIP;
- no transfer exceeds the handoff cap;
- A/R/N was resolved with the destination seat;
- every published dispatch has the required audit evidence;
- the output says whether work was launched or only rendered.

## Stop conditions

Stop and surface instead of dispatching when the board read is incomplete, the
Role field is malformed, the Project has more than one active kanban while
runtime support is unavailable, or a candidate would violate authority.

Read `references/queue-ordering.md` for tie-break examples and
`references/dispatch-formats.md` for carrier output contracts.
