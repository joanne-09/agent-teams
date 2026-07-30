---
name: inspecting-queue
description: Inspect and order the Quality Assurance verification queue and render one kickoff prompt per delivery awaiting a verdict. Use for [role:qa] plus queue, backlog, or "what needs verifying"; never for issuing a verdict on a delivery.
---

# Inspecting the verification queue

A Producer-shaped routine that surveys deliveries awaiting independent
verification and orders them for separate sessions.

**This routine does not verify anything.** Inspection and verification are
different jobs: a session that both surveys the queue and judges a delivery
has stopped being independent, and independence is the entire reason the
Quality Assurance seat exists. Each verdict belongs to its own Consumer
session bound to exactly one Card.

## Workflow

1. Bootstrap as `qa`.
2. Read the queue:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" queue
```

3. For each entry, check whether it is genuinely verifiable before ordering
   it. Read the Card and its linked Pull Request:

```bash
gh issue view <number> --repo <configured-repo> --comments
gh pr view <pr-number> --repo <configured-repo>
```

Flag anything that would waste a verification session:

- no linked Pull Request, or the link is stale;
- the Pull Request body has no `## Automated Verification` content;
- acceptance criteria on the Card are still unchecked with no reason;
- the delivery handoff comment does not say what to verify.

4. Report the ordered queue. For each Card give the number, title, Pull
   Request, what verification it appears to need, and the kickoff prompt.
5. Report separately what is already past you in the human lane — that is
   waiting on a merge, not on verification.
6. Stop.

## Rules

- **Order by age, then by Card number.** Oldest first: a delivery sitting in
  the queue is finished work that nobody can use yet.
- **Rendering a kickoff prompt is not starting a session.** Say "prompt
  rendered", never "verification started".
- **Do not issue a pass or fail here**, not even for an obvious case. An
  obvious case is exactly where a rushed verdict does the most damage.
- **Do not modify production code**, and do not modify the Card's Status or
  Role. Inspection is read-only.
- An empty queue is a valid and useful result. Say so plainly.

## What a verifiable delivery looks like

Worth flagging when it is missing, because the Consumer session will otherwise
discover it and stall:

- a Pull Request linked to the Issue, with a closing trailer;
- concrete automated verification evidence — commands run and their results;
- acceptance criteria in a terminal state, or an explicit waiver;
- a handoff comment naming what the previous seat could not verify itself.
