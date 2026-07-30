---
theme: default
colorSchema: light
title: AI Agent Dev Team
class: text-left
highlighter: shiki
lineNumbers: false
transition: slide-left
mdc: true
aspectRatio: 16/9
canvasWidth: 980
fonts:
  sans: Noto Sans TC
  serif: Newsreader
  mono: IBM Plex Mono
  provider: google
---

# AI Agent Dev Team

<hr class="rule" />

Understanding board-superpowers, and what we build from it  
<span class="muted">ITRI</span>

<!--
Presenter notes go here.
-->

---
layout: center
---

<div class="chapter">
  <div class="chapter-num">Part 1</div>
  <div class="chapter-title">board-superpowers</div>
  <div class="chapter-sub">How the reference project works</div>
</div>

<!--
Reference: github.com/PanQiWei/board-superpowers.
Our assignment's reference architecture; we studied it before designing our own.
-->

---
layout: ppt
class: dense
---

# What It Is

- A <span class="accent">scheduling layer</span> for Claude Code, packaged as a plugin
- No server, no database, no UI — only skills, hooks, and bash scripts
- The <span class="accent">GitHub Project board is the single source of truth</span> and dispatcher
- Work is delegated: `superpowers` (TDD, planning) · `gstack` (review, QA, security)
- Design thesis: AI throughput scales 100x — <span class="accent">human attention does not</span>

<!--
Not an app. Plugin = folders of instruction files + scripts, inert until a session starts.
State lives on the board and in git — kill every session, nothing is lost.
Sprint / story points deliberately removed: they assume implementation is the bottleneck.
-->

---
layout: ppt
class: dense
---

# Two Session Roles

<div class="grid-2" style="max-width:100%;">
  <div class="card">
    <h3>Producer — Manager</h3>
    <p>Long-lived, interactive.<br/>
    Intake, decompose, dispatch, triage, review.<br/>
    <span class="accent">Never writes code.</span></p>
  </div>
  <div class="card">
    <h3>Consumer — Implementer</h3>
    <p>Disposable, unattended.<br/>
    Claim one card, TDD, open one PR, terminate.<br/>
    <span class="accent">Never merges its own PR.</span></p>
  </div>
</div>

<br/>

- Core invariant: <span class="accent">one card = one session = one PR</span>
- SA / Architect / Dev / QA are lifecycle phases, not standing agents

<!--
A role = which instructions the session loaded. Nothing more.
The real seam: interactive-with-human (Manager) vs unattended (Consumer).
-->

---
layout: ppt
class: dense
---

# Card Lifecycle

```text
Backlog → Ready → In Progress → In Review → Done
                     ↕              │
                  Blocked    (rework loops back)
```

- Card = GitHub Issue: Goal · Acceptance criteria · Out of scope · Dependencies · spec link
- <span class="accent">Gate 1</span> — human approves Backlog → Ready (INVEST, vertical slice, sized)
- <span class="accent">Gate 2</span> — human reviews and merges the PR; agents only propose
- Between the gates: fully autonomous

<!--
Cards are thin pointers to specs — no spec, no card (anti-slop rule).
Gates are cheap: read a one-screen card, read a PR. Minutes of attention govern hours of machine work.
-->

---
layout: ppt
class: dense
---

# Key Mechanisms

<div class="grid-2" style="max-width:100%;">
  <div class="card">
    <h3>Claim = branch push</h3>
    <p>Push empty <code>claim/42-slug</code> — first push wins.<br/>
    <span class="accent">Git is the lock</span>; no server.</p>
  </div>
  <div class="card">
    <h3>Worktree isolation</h3>
    <p>One git worktree per Consumer.<br/>
    N parallel sessions, zero shared state.</p>
  </div>
  <div class="card">
    <h3>PR contract</h3>
    <p>Auto Verification · Human TODO · Retro Notes.<br/>
    <span class="accent">Validated by a script</span>, not the model.</p>
  </div>
  <div class="card">
    <h3>Audit trail</h3>
    <p>Every mutation: auto / propose / never, then logged.<br/>
    Overrides leave traces.</p>
  </div>
</div>

<!--
Pattern everywhere: judgment in prompts, enforcement in code (exit codes).
TDD: for unattended LLMs the green suite is the only ground-truth feedback signal.
-->

---
layout: ppt
class: dense
---

# What We Take From It

| Their design | Our team |
|---|---|
| Manager intake conversation | <span class="accent">SA</span> — requirement → spec |
| Decomposition into cards | <span class="accent">Architect</span> — spec → INVEST cards |
| Consumer TDD loop | <span class="accent">Dev</span> — card → tested PR |
| Verification chain + review queue | <span class="accent">QA</span> — evidence → verdict |
| CI / merge machinery | <span class="accent">OPS</span> — phase 2 |

- Keep: board as truth · one card = one PR · git as lock · two human gates
- Drop: multi-backend, BYO database, dual-platform — demo-grade by choice

<!--
Our deviation: make the five roles explicit named skills for demo legibility.
Scope honesty: happy path in days; reliability tuning is where real time goes.
-->

---
layout: center
---

<div class="chapter">
  <div class="chapter-num">Part 2</div>
  <div class="chapter-title">Demo Projects</div>
  <div class="chapter-sub">Our agent team at work</div>
</div>

<!--
Joanne's repo: the agent team implementation (agent-teams) drives demo projects here.
-->

---
layout: ppt
class: dense
---

# Our Seats

| Seat | Token | Skill | Does |
|---|---|---|---|
| <span class="accent">analyst</span> | `[role:analyst]` | `intaking-requirement` | requirement → Backlog card → hand to architect |
| <span class="accent">architect</span> | `[role:architect]` | `authoring-spec` | docs-only spec PR → hand to rd |
| <span class="accent">em</span> | `[role:em]` | `dispatching-work` | find Ready cards → render kickoff prompts |
| rd | `[role:rd]` | <span class="muted">not yet</span> | claim → TDD → code PR → hand to qa |
| qa | `[role:qa]` | <span class="muted">not yet</span> | verify vs acceptance criteria; only seat that reaches human |
| human | — | — | <span class="accent">merge gate</span> — the one thing agents never do |

- Routing is a leading token: skill descriptions name their triggers, the model matches
- Handoff authority lives in `producer_board.py` — <span class="accent">illegal handoffs are refused in code</span>

<!--
A seat = which skill the session loads, nothing more. Sessions are peers, not a call stack.
Two layers: routing is soft (prompt matching), authority is hard (Python raises on illegal handoff).
Producer slice implemented (analyst/architect/em); consumer slice (rd/qa) is the next milestone.
-->

---
layout: ppt
class: dense
---

# One Card, End to End — Live Run

| # | Who | What we typed / did | Result |
|---|---|---|---|
| 1 | em | `[role:em] dispatch work` | empty queue reported — <span class="accent">no invented work</span> |
| 2 | analyst | `[role:analyst] New requirement: … Tetris …` | Issue #1 · Backlog · handed to architect |
| 3 | architect | `[role:architect] author the spec for card #1` | PR #2, docs-only spec · handed to rd |
| 4 | human | board UI: Status → <span class="accent">Ready</span> | the human lifecycle gate |
| 5 | em | `[role:em] dispatch work` | renders `[role:rd] [board-card:#1] …` kickoff |
| 6 | rd | paste the kickoff | <span class="muted">no rd skill — edge of the MVP</span> |

- Every mutation announced before it ran; every claim backed by CLI JSON
- Handoff = Role flip + comment; Status untouched — <span class="accent">ownership ⊥ lifecycle</span>

<!--
Step 1 and the pre-Ready dispatch are negative tests: dispatch keys on Status, not Role.
Step 6 finding: the model admits no procedure exists, then freelances — why rd must be a skill.
-->

---
layout: ppt
class: dense
---

# The Board in Action

<!-- Drop screenshots into slides/images/ and swap the src below.
     Suggested shots: full board view, one card open, a PR with the 3-section body. -->

<img src="./images/board.png" style="max-height: 380px; border: 1px solid var(--line); border-radius: 4px;" />

- Live board of `agent-teams-test` — cards flowing Backlog → Done

<!--
Walk the audience across the columns; point at a claimed card and its branch.
-->

---
