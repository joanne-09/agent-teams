# The browser pass

<!-- Browser-evidence discipline derived from gstack `/qa` (MIT, (c) 2026
     Garry Tan, github.com/garrytan/gstack); the spec-blind framing is
     agent-teams' own, from the 2026-08-21 team-lead review.
     Per-element DERIVED / INVENTED labels: ATTRIBUTION.md. -->

**This file is the only place the browser procedure lives.** It is loaded by
the `qa-browser-worker`, or — when no browser worker was dispatched — by the
`verifying-delivery` reviewer running the pass itself. Exactly one of those
happens per Card. If you are reading this because a sibling is already doing
the browser pass, stop: you are duplicating it.

## Why this seat is blind to the diff

You review from the **Card, the specification, and the running application**.
You do not read the implementation diff, and you are not given it.

That is the point. The 2026-08-21 review found QA mostly re-running the
Developer's own unit tests — work already done once, by someone with more
context — while the one bug the suite missed was a blank page caught by an
incidental screenshot. A reviewer who has read the implementation tests what
the implementation does. A reviewer who has read only the acceptance criteria
tests what the product promised, which is the only way to find the promise
that was never implemented at all.

This mirrors how the team lead described real QA: integration and load
scenarios designed from the specification's requirements, deliberately without
the development team seeing them first.

The blindness is enforced by what you are given, not by a sandbox. Do not go
looking for the diff to "check your understanding" — that trades the one thing
this seat contributes for a second opinion on work already reviewed.

## Get the application running

Never in the repository root: the coordinator and every other worker run from
that checkout, and a root left on a Pull Request branch sends the next commit
to the wrong branch. Use a detached review worktree at the exact head.

```bash
# <workspace> is the config's `workspace` (default ../.worktrees); <n> the Card
git fetch origin "<head_sha>"
git worktree add --detach "<workspace>/review-<n>" "<head_sha>"
# install and start the app from inside that worktree, then drive it
git worktree remove --force "<workspace>/review-<n>"   # when the pass is done
```

Record the exact `head_sha` you started from. Everything below is evidence
about that commit; a new push invalidates all of it.

If the application cannot be started, that is a `blocked` outcome with the
reason recorded — not a pass with a note, and not a silent skip.

## Drive it with Playwright

**Playwright, headless Chromium, run from `Bash`.** Not the agent's own browser
tooling: that drives the operator's real logged-in session, and step 2 below
submits injection strings to every field.

It is not installed for you — `npm install --no-save playwright` and, on a
fresh machine, `npx playwright install chromium`, inside the review worktree.
If it cannot be obtained, that is `blocked` with the reason recorded, not a
pass with a note.

Any suite producing the same evidence is acceptable. Whatever you used goes in
`tool` **with its engine and version** (`playwright (chromium headless)
1.62.1`), because a console listing cannot be checked by someone who does not
know which engine produced it.

Which suite, why this one rather than Puppeteer / Selenium / Cypress /
browser-use, and what the choice does not cover:
`references/browser-tooling.md`.

### 1. Walk each acceptance criterion as a user would

One flow per criterion, named for what it does. A flow is a journey, not a
page load: **at least two steps**, and the last step observes a result.

```text
name:  search by destination
steps: filled #search with "Taoyuan"
       clicked button[type=submit]
       read 3 result rows, all containing "Taoyuan"
```

Test as a user before reading anything else. Screenshot each flow.

### 2. Feed every input field garbage

This is the part the team lead asked for by name, and the part a code review
structurally cannot do. For each field that accepts input, try at minimum:

- **empty** — submit with nothing in it;
- **wrong type** — letters into a number, a date that is not a date;
- **boundary** — zero, negative, one past the documented maximum;
- **over-long** — a few thousand characters;
- **injection-shaped** — `'; DROP TABLE x;--`, `<script>alert(1)</script>`,
  `../../etc/passwd`, a Unicode right-to-left override;
- **whitespace-only** — spaces and tabs, which often bypass a naive check.

Record what you expected and what actually happened, per case. A field that
accepts `<script>` and renders it back is a finding; so is one that rejects
valid input, and so is one that fails with a raw stack trace.

**Never enter real credentials, and never record any.**

### 3. Read the console after every interaction

Not once at the end. A silent console error behind a green test suite is
precisely the ES-module blank page that got past QA before.

Record errors and warnings. An **empty** errors list is a finding — it says you
looked and it was quiet. An **absent** one says you did not look, and policy
refuses the pass for it.

### 4. Look for what no criterion mentions

Before finishing, spend a pass on what the specification did not think of:
double-submit, browser back after a mutation, reload mid-flow, a narrow
viewport, a slow or failed network response. Anything you find here is worth
more than a confirmation, because nobody designed for it.

## Publish

Produce the `browser_evidence` block (full shape in
`references/verdict-schema.md`), then hand it back:

- **as a `qa-browser-worker`** — send it to the reviewer that dispatched you,
  as data. You do not publish a verdict, you do not run `accept`, and you do
  not change any Card field. One head gets one verdict, and it is not yours.
- **as the reviewer running this pass yourself** — fold it into your verdict
  document directly.

Report what you did not cover, and why, in `limitations`. A pass that quietly
skipped half the criteria is worse than an honest partial.
