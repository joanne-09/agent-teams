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

Every successful result includes `config_revision` and `recovery_policy`.
`next-actions` reloads the dashboard-managed config on every invocation.
Replace the cached policy with the newest result before continuing.

`recovery_policy` is `{"default": {...}, "roles": {"architect": {...}, ...}}`.
**Retry budgets are per role**, because the seats fail differently: an
architect stalled on a slow read and a QA worker bounced by a rate limit do not
want the same number of attempts. Every returned action also carries its own
resolved `recovery`, so use the action's copy and never a global one.
`max_retries` counts retries after the initial attempt, and
`retry_delays_seconds` is the exact bounded wait before retry 1, retry 2, and
so on. Do not substitute a hard-coded retry count or delay, and do not apply
one seat's budget to another's action.

If `config_revision` changes, discard every unstarted action from the older
plan and use the new result. Do not interrupt an already running CLI command or
child; it owns one consistent snapshot. Re-read `next-actions` when it
finishes. A config change alone does not erase retry attempts already consumed
for an unchanged Card/routine/state signature; apply the new maximum and delays
to the remaining attempts. If the user reports that the dashboard saved new
settings, re-run `next-actions` before starting another returned action.

2. Handle every returned `action`:

- `kind: spawn`: invoke the foreground plugin subagent named in the action's
  `agent` field (one per seat: `agent-teams:architect-worker`,
  `agent-teams:analyst-worker`, `agent-teams:dev-worker`,
  `agent-teams:qa-worker`, `agent-teams:lead-worker`) with the returned
  `prompt` verbatim. Never substitute a different seat's worker. The action's
  `skill` field is the one qualified workflow skill the worker must invoke on
  demand through its Skill tool; no other workflow bodies are preloaded. If
  that plugin agent is not exposed by the carrier, invoke the carrier's
  general-purpose child agent with the same prompt and explicitly load only
  that `skill`. This
  fallback still happens inside the current session; it is never handed to the
  human. The action's `env` field (`AGENT_TEAMS_ACTING_ROLE=<seat>`) is the
  worker's process binding; the prompt already tells the worker to set it.
  A `qa-worker` may spawn its own review passes and one
  `agent-teams:qa-browser-worker` beneath itself. Those are its evidence
  producers, not actions for you to plan or dispatch: keep planning one spawn
  per Card stage, and expect the extra agents to appear nested under it.
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
architect -> manual spec mode: human spec merge -> architect resumes
qa defect -> dev -> qa
qa eligible -> automatic mode: auto-merge -> reconcile -> Done
qa eligible -> manual mode: human merge gate -> reconcile -> Done
```

4. Prevent a spin loop. Track `(Card, routing_state, routine)` during this run.
If a child returns without changing durable state, or a retry-safe controller
fails for the same Card, routine, and head, use **that action's own**
`recovery` (falling back to `recovery_policy.roles[<the action's role>]`):

- retry no more than `max_retries` times after the initial attempt;
- before retry *n*, wait entry *n* from `retry_delays_seconds`;
- include the unchanged-state or controller-error evidence in the retry;
- reset that signature's retry count only after durable state changes; and
- after the schedule is exhausted, stop retrying and report the last error,
  attempt count, Card, routine, and durable state so the user can see why the
  workflow stopped.

A new acceptance comment alone does not count as progress if auto-merge remains
unarmed. Policy refusals, claim-race losses, and partial-mutation envelopes are
not transient failures: follow their named route or recovery list instead of
replaying them. The GitHub adapter independently applies this policy only to
safe read commands; it never blindly retries Issue creation, field writes,
comments, Pull Request creation, or merge commands.

## Human gates

`human_gates` contains the only work the coordinator may not perform:

- `spec_merge`: `spec_pr_merge_mode: manual` published the exact specification
  head in a Pull Request. Ask the human to merge that Pull Request in GitHub.
  Never merge it or move the Card. On the next loop, a confirmed merge becomes
  an automatic `finalize-spec-merge` action and architect shaping resumes.
- `readiness`: the specification is already durable on the base branch and
  recorded on the Card. Ask the human only to move the Card Status to `Ready`.
  On the next loop the `finalize-readiness` controller validates the unchanged
  specification and hands ownership to `dev` automatically. `promote N`
  remains a convenience, not an additional required operation.
- `qa_exception`: QA or policy found a protected or genuinely ambiguous change.
  Present the evidence and recommendation. If the human approves, their one
  command is `approve-exception N`, which validates the exact reviewed head,
  merges it, and reconciles the Card to `Done`.
- `spec_change`: QA found the defect is in the **specification**, not the
  implementation, and recorded what it says should change. Present each
  request's document, clause, conflict, and suggested change. If the human
  approves, their one command is `approve-spec-change N`, which hands the Card
  to the architect at `(In Progress, architect)` with the approved request
  recorded on it. **This gate offers no merge**, and that is deliberate rather
  than an omission: the delivery was built against a baseline QA says is wrong,
  so "approve it anyway" is not one of the honest answers. If the human
  disagrees with QA, they reject it — say so on the Card and hand it on; do not
  reach for `approve-exception`, which answers a different question.
- `manual_merge`: deterministic acceptance found the exact head eligible, but
  `code_pr_merge_mode` assigns routine merge execution to the user. Present the
  returned Pull Request and ask the human to merge it in GitHub. Never issue a
  merge command for this gate. On the next loop, a confirmed merge becomes an
  automatic `reconcile-done` action.

Every gate carries `argv` when a plugin command opens it and `pull_request`
when GitHub does. If the human is running the CCAM dashboard, say that the
Agent Teams page lists these gates with a button; it changes where they act,
never that they must. Whichever surface they use, you wait for the durable
GitHub state to change -- never for them to tell you they are done.

Keep other independent actions moving even while one Card waits at a human
gate. Stop the overall loop only when there are no actions or monitors, leaving
only human gates or durable blockers.

## Rules

- Never invoke a worker as `human` and never run a human-gate command yourself.
  The CLI enforces this: inside any agent session (the harness stamps
  `CLAUDECODE` on every shell) a command that claims or defaults to `human`
  is refused. Run your own CLI calls with `--acting-role lead` (or
  `AGENT_TEAMS_ACTING_ROLE=lead`) and let policy answer; when it refuses
  `promote`, that is the human gate, not an obstacle to route around.
- Never create a specification branch or Pull Request yourself.
  `publish-spec` owns the configured direct or manual publication route.
- Never treat a child response as durable state. Re-read the board.
- Never spawn two authoring workers for the same Card. The remote claim remains
  the final mutual-exclusion check.
- Dispatch a Blocked Card to one bounded `triaging-board` worker. If that
  worker cannot change durable state after configured recovery, report the exact
  external blocker; never turn mechanical recovery into a human gate.
- Never let a child choose another Card or spawn grandchildren.
- Never report a mutation as successful without an `"ok": true` envelope.
