---
name: using-agent-teams
description: Entry point for an automated agent-teams workflow over a GitHub Project. Runs read-only bootstrap, orients the user, routes plain-language intent, and starts the in-session subagent coordinator for "start/run/continue the team". Use for board work, requirements, specifications, readiness, blocked work, automated dispatch, delivery, and QA.
---

<!-- The state-on-disk table, non-signals list, and router anti-pattern are
     derived from board-superpowers `using-board-superpowers` (MIT, (c) 2026
     PanQiWei, github.com/PanQiWei/board-superpowers), adapted to the
     agent-teams flow. See ATTRIBUTION.md. -->

# Using agent-teams

GitHub is durable truth; this conversation and every child context are
disposable. Routing state lives in Project fields, requirements and handoffs in
Issues, claims in Git branches, deliveries and QA evidence in Pull Requests,
and policy in `.agent-teams/config.json`.

## Plain-language routing

The user states intent. Never ask which seat they are. A leading `[role:<seat>]`
token is a machine binding from `next-actions`, not the normal human interface.
Policy rechecks every action regardless of how the seat was selected.

| Intent | Seat | Routine |
|---|---|---|
| orient me, status, what is next | `lead` | `briefing-board` |
| new idea or requirement | `analyst` | `intaking-requirement` |
| specify, design, or decompose | `architect` | `authoring-spec` |
| diagnose blocked work | `lead` | `triaging-board` |
| start/run/continue/automate the team | `lead` | `dispatching-work` |
| inspect the QA queue without reviewing | `qa` | `inspecting-queue` |
| directly implement one named Card | `dev` | `consuming-card` |
| directly verify one named Card | `qa` | `verifying-delivery` |

A direct Consumer request names one Card. A team-orchestration request is the
deliberate exception: `dispatching-work` reads deterministic `next-actions` and
spawns one bounded child for each returned Card. The coordinator does not make
up its own Card selection.

General programming or Git questions without board intent are not routing
requests. A kickoff token the user is merely quoting is not a request to act.

## Bootstrap first

Choose the seat, then run this before any mutation:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" bootstrap --role <seat>
```

Startup is read-only. Live board state overrides prompts and child reports. If
an expected pair is stale, stop that Card stage rather than changing the board
to match it.

When intent is absent or the user asks for status, bootstrap as `lead`, invoke
`briefing-board`, and lead with:

1. Cards at `(Backlog, human)` awaiting the Ready decision;
2. Cards at `(In Review, human)` awaiting a protected/ambiguous QA decision;
3. in-flight, blocked, Ready, and verification work;
4. one recommended next action.

## Never act as human

You may bind any agent seat. You may never bind `human` or run a human command
on the user's behalf. The only human gates are:

- readiness: the person moves the specified Card Status to `Ready`; the
  coordinator validates the recorded Git specification and hands it to dev;
- final QA exception: `producer_board.py approve-exception N`; this validates
  and merges only the exact reviewed protected head, then reconciles Done.

Present the evidence and recommendation, then stop that Card. Other independent
Cards may continue through the orchestrator.

This boundary is instructional: the CLI receives a seat token and cannot know
whether a person or model supplied it. Keep the rule rather than pretending the
parser can enforce identity.

## Workflow boundaries

- Specifications are written below `docs/` and published directly on the
  current branch with `publish-spec`. No spec branch, worktree, or PR exists.
- `dispatching-work` spawns bounded subagents in the current session. Never ask
  the human to open a terminal or paste a prompt.
- One worker owns one Card and one stage. Workers cannot spawn grandchildren.
- Dev never merges. QA publishes evidence and cannot choose its route.
- `accept` deterministically selects eligible, defect, or protected change.
- Eligible heads auto-merge and the coordinator reconciles them automatically.
- Never report an external mutation as successful without `"ok": true`.
- A partial result is fix-forward evidence. Run only its recovery steps; do not
  replay already completed creation.
- A refusal is durable information, not permission to route around policy.
