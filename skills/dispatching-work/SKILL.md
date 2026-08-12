---
name: dispatching-work
description: Run the agent-teams workflow from the current session by repeatedly reading deterministic next actions, spawning one bounded subagent per Card stage, and automatically reconciling confirmed merges. Use for [role:lead], "dispatch work", "start the team", "run the team", "continue the workflow", or "automate the board". Stops only at the human readiness gate, the protected/ambiguous QA exception gate, or a durable blocker.
---

# Run the team from this session

The current session is the coordinator. **Do not ask the human to open another
session or paste a kickoff prompt.** Spawn the worker yourself and wait for its
durable result.

## Loop

1. Bootstrap as `lead`, then run:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" next-actions
```

2. Handle every returned `action`:

- `kind: spawn`: invoke the foreground `agent-teams:agent-teams-worker`
  subagent with the returned `prompt` verbatim. If that plugin agent is not
  exposed by the carrier, invoke the carrier's general-purpose child agent with
  the same prompt. This fallback still happens inside the current session; it
  is never handed to the human.
- `kind: controller` or `kind: reconcile`: invoke the plugin CLI with the
  returned `argv`, prefixed by
  `python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py"`. These are
  deterministic policy/reconciliation steps, not subagents and not human
  judgment.
- `kind: monitor`: keep this coordinator alive, wait the returned bounded
  `poll_after_seconds`, and run `next-actions` again. Do not busy-poll and do
  not end the workflow merely because GitHub's merge queue is still working.
  Continue until the exact head is merged, auto-merge is disarmed/failed, the
  head changes, or another durable route appears.

Different implementation or verification Cards may run in parallel when the
carrier supports parallel child calls and `next-actions` admits them below the
WIP limit. Direct specification authoring is serialized because its workers
share the current checkout. Stages for the same Card are always sequential.
Each child owns exactly one Card and one stage.

3. After the children finish, ignore conversational success claims and run
`next-actions` again. GitHub state is the completion signal. Continue through:

```text
architect -> human readiness gate -> dev -> qa
qa defect -> dev -> qa
qa eligible -> auto-merge -> reconcile -> Done
```

4. Prevent a spin loop. Track `(Card, routing_state, routine)` during this run.
If a child returns without changing durable state, retry that identical action
at most once with the unchanged-state evidence. If it still does not move,
report a durable blocker; do not keep spawning copies.

Apply the same one-retry ceiling to a failing `controller` action for the same
Card, routine, and head. A new acceptance comment alone does not count as
progress if auto-merge remains unarmed. Surface the controller error as a
durable blocker instead of retrying forever.

## Human gates

`human_gates` contains the only work the coordinator may not perform:

- `readiness`: the specification is already committed directly to Git and
  recorded on the Card. Ask the human only to move the Card Status to `Ready`.
  On the next loop the `finalize-readiness` controller validates the unchanged
  specification and hands ownership to `dev` automatically. `promote N`
  remains a convenience, not an additional required operation.
- `qa_exception`: QA or policy found a protected or genuinely ambiguous change.
  Present the evidence and recommendation. If the human approves, their one
  command is `approve-exception N`, which validates the exact reviewed head,
  merges it, and reconciles the Card to `Done`.

Keep other independent actions moving even while one Card waits at a human
gate. Stop the overall loop only when there are no actions or monitors, leaving
only human gates or durable blockers.

## Rules

- Never invoke a worker as `human` and never run a human-gate command yourself.
- Never create a specification branch or Pull Request. Specifications publish
  directly on the current Git branch via `publish-spec`.
- Never treat a child response as durable state. Re-read the board.
- Never spawn two authoring workers for the same Card. The remote claim remains
  the final mutual-exclusion check.
- Dispatch a Blocked Card to one bounded `triaging-board` worker. If that
  worker cannot change durable state after the bounded retry, report the exact
  external blocker; never turn mechanical recovery into a human gate.
- Never let a child choose another Card or spawn grandchildren.
- Never report a mutation as successful without an `"ok": true` envelope.
