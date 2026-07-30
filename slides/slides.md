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
| <span class="accent">architect</span> | `[role:architect]` | `authoring-spec` | spec → **promote** to Ready, or **decompose** into cards |
| <span class="accent">em</span> | `[role:em]` | `briefing-board` · `triaging-board` · `dispatching-work` | flow + WIP · blocked work · kickoff prompts |
| <span class="accent">qa</span> | `[role:qa]` | `inspecting-queue` | order the verification queue — <span class="muted">verdicts are Consumer work</span> |
| rd | `[role:rd]` | <span class="muted">not yet</span> | claim → TDD → code PR → hand to qa |
| human | — | — | <span class="accent">merge gate</span> — the one thing agents never do |

- Routing is a leading token: skill descriptions name their triggers, the model matches
- Authority lives in `policy.py` — <span class="accent">illegal handoffs and out-of-seat actions refuse before any GitHub call</span>

<!--
A seat = which skill the session loads, nothing more. Sessions are peers, not a call stack.
Two layers: routing is soft (prompt matching), authority is hard (Python raises before mutating).
Producer surface now complete across all four Producer seats; the rd Consumer slice is next.
qa appears twice in the architecture: queue inspection is Producer-shaped, a verdict is Consumer-shaped.
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

- Every mutation announced before it ran; every reported result backed by CLI JSON
- Handoff = Role flip + comment; Status untouched — <span class="accent">ownership ⊥ lifecycle</span>
- <span class="muted">Since this run:</span> step 4's manual board edit is now `promote`, which gates on a <span class="accent">merged spec</span> and hands to rd in one governed operation

<!--
This trace is the record of an actual run against the earlier MVP; it is left unedited on purpose.
Repeatable live GitHub contract proof still remains pending.
Step 1 and the pre-Ready dispatch are negative tests: dispatch keys on Status, not Role.
Step 6 finding: the model admits no procedure exists, then freelances — why rd must be a skill.
What changed since: step 4 no longer needs a human at the board UI, though the human still merges the spec PR that unlocks it.
-->

---
layout: ppt
class: dense
---

# The Board in Action

<div class="kanban">
  <div><h3>Backlog</h3><span>#42 · architect</span></div>
  <div><h3>Ready</h3><span>#47 · rd</span></div>
  <div><h3>In Progress</h3><span>#44 · rd</span></div>
  <div><h3>In Review</h3><span>#39 · qa</span></div>
  <div><h3>Done</h3><span>#31 · human</span></div>
</div>

- Illustrative target board — live Project proof remains an implementation milestone
- Demo target: `agent-teams-test`; plugin source and documentation: `agent-teams`

<!--
This replaces the missing screenshot placeholder with a truthful architecture view.
The demo workload now belongs in the sibling agent-teams-test repository, while the plugin remains in agent-teams.
The current implementation plan still marks disposable-Project e2e proof as pending.
-->

---
layout: center
---

<div class="chapter">
  <div class="chapter-num">Part 3</div>
  <div class="chapter-title">Project Architecture</div>
  <div class="chapter-sub">Independent sessions, one durable coordination plane</div>
</div>

<!--
The next three slides move from system context and scope hierarchy, to internal layers, to the Card data model.
The architecture is the complete Phase 1 contract; implementation status is shown later.
-->

---
layout: ppt
class: dense
---

# GitHub Is the Team's Shared Memory

<div class="eyebrow">TARGET PHASE 1</div>

<div class="architecture-map">
  <div class="human-band">
    <div><strong>Human stakeholder</strong><span>originates demand · launches sessions · owns merge</span></div>
    <div class="carrier-note">human terminal · bounded subagent · scheduled command</div>
  </div>
  <div class="map-arrow">launches a fresh session with one seat, one execution shape, and one scope anchor ↓</div>
  <div class="scope-architecture">
    <div class="scope-node board-scope">
      <div class="node-label">BOARD LEVEL · GITHUB PROJECT</div>
      <strong>Producer session</strong>
      <span>lives with the board · shapes, routes, prioritizes, and dispatches</span>
      <div class="scope-seats">analyst · architect · em · qa</div>
    </div>
    <div class="scope-flow">
      <span>dispatch artifact →</span>
      <b>BOARD → CARD</b>
      <span>← PR · verdict · handoff</span>
    </div>
    <div class="scope-node card-scope">
      <div class="node-label">CARD LEVEL · ONE WORK ITEM</div>
      <strong>Consumer session</strong>
      <span>lives with exactly one Card · claims and resolves one bounded stage</span>
      <div class="scope-seats">architect · rd · qa</div>
    </div>
  </div>
  <div class="plugin-bridge"><strong>agent-teams</strong><span>skills interpret intent · deterministic services enforce policy</span></div>
  <div class="artifact-row">
    <div><strong>Project</strong><span>Status + Role</span></div>
    <div><strong>Issues</strong><span>scope + comments</span></div>
    <div><strong>Git</strong><span>claims + worktrees</span></div>
    <div><strong>Pull Requests</strong><span>delivery + verdict</span></div>
  </div>
</div>

<p class="takeaway">Scope hierarchy is Board → Card; durable artifacts carry dispatch down and results back up.</p>

<!--
"Lives with" means durable scope anchor, not where a process is stored.
Normal flow: Producer observes the board, writes a durable dispatch artifact for one Card, a fresh Consumer claims that Card, and the Consumer's Pull Request, verdict, transition, or handoff returns durable state to the board.
The hierarchy is operational scope, not a required nested runtime stack: the Producer process does not have to remain alive while the Consumer runs.
Architect and QA appear at both levels because each can start separate Producer and Consumer sessions; one session never holds both shapes.
Kill every process: the durable GitHub artifacts still carry the work.
-->

---
layout: ppt
class: dense
---

# Three Layers Keep the System Governed

<div class="eyebrow">TARGET COMPONENT MODEL</div>

<div class="layer-stack">
  <div class="arch-layer"><span class="layer-index">01</span><div class="layer-copy"><strong>Workflow skills</strong><span>Interpret the request, choose one bounded routine, gather context, and explain refusals.</span></div><div class="layer-examples">router · intake · specification · dispatch · implementation · verification</div></div>
  <div class="layer-arrow">semantic operation ↓</div>
  <div class="arch-layer"><span class="layer-index">02</span><div class="layer-copy"><strong>Deterministic services</strong><span>Validate authority and live preconditions; perform transitions, handoffs, claims, PR checks, and recovery.</span></div><div class="layer-examples">policy · workflows · kanban protocol · git · PR contract · audit</div></div>
  <div class="layer-arrow">validated mutation ↓</div>
  <div class="arch-layer"><span class="layer-index">03</span><div class="layer-copy"><strong>Durable coordination plane</strong><span>GitHub stores the Card, lifecycle, ownership, context, delivery evidence, and human decision.</span></div><div class="layer-examples">Project · Issue · comment · branch · worktree · Pull Request · review</div></div>
</div>

<p class="principle-line"><strong>Design rule:</strong> judgment lives in skills; external mutation lives in code; truth lives on GitHub.</p>

<!--
Layer 2 is now six modules, split where real seams appeared: model, policy, config, github, board, workflows.
The split was earned, not planned: policy separated from the adapter the moment transitions and caps needed testing without GitHub.
producer_board.py remains the stable public entry point every skill invokes.
-->

---
layout: ppt
class: dense
---

# Status Says Where; Role Says Who Acts Next

<div class="axis-grid">
  <div class="axis-block">
    <div class="axis-label">LIFECYCLE AXIS</div><h3>Status</h3>
    <div class="token-line"><span>Backlog</span><b>→</b><span>Ready</span><b>→</b><span>In Progress</span><b>→</b><span>In Review</span><b>→</b><span>Done</span></div>
    <p><code>Blocked</code> interrupts the path; QA rejection moves <code>In Review → In Progress</code>.</p>
  </div>
  <div class="axis-block">
    <div class="axis-label">OWNERSHIP AXIS</div><h3>Role</h3>
    <div class="role-tokens"><span>analyst</span><span>architect</span><span>rd</span><span>qa</span><span>em</span><span>human</span></div>
    <p>A handoff changes Role and writes context. It does not silently change Status.</p>
  </div>
</div>

<div class="pair-row">
  <div class="pair-example"><code>(Backlog, architect)</code><span>shaped demand awaits technical work</span></div>
  <div class="pair-example"><code>(Ready, rd)</code><span>implementation can be claimed</span></div>
  <div class="pair-example"><code>(In Review, qa)</code><span>independent verification is next</span></div>
  <div class="pair-example"><code>(In Review, human)</code><span>only human review and merge remain</span></div>
</div>

<p class="takeaway">The routing state is the pair <code>(Status, Role)</code> — ownership and lifecycle remain orthogonal.</p>

<!--
When both coordinates move, transition_card and handoff_card are separate semantic operations.
That separation makes a partial external mutation visible and recoverable.
-->

---
layout: center
---

<div class="chapter">
  <div class="chapter-num">Part 4</div>
  <div class="chapter-title">Work Flow & Plugin Mechanics</div>
  <div class="chapter-sub">How one request becomes one reviewable delivery</div>
</div>

<!--
This section follows the target Card lifecycle, then zooms into one session and the shipped prompt-to-GitHub path.
-->

---
layout: ppt
class: dense
---

# One Card Moves One Session at a Time

<div class="eyebrow">PHASE 1 GOLDEN PATH</div>

<div class="journey">
  <div class="journey-step"><strong>Human</strong><span>request</span><small>goal + constraints</small></div><div class="journey-arrow">→</div>
  <div class="journey-step"><strong>Analyst</strong><span>shape demand</span><small>Backlog · architect</small></div><div class="journey-arrow">→</div>
  <div class="journey-step"><strong>Architect</strong><span>spec + decompose</span><small>Ready · rd</small></div><div class="journey-arrow">→</div>
  <div class="journey-step"><strong>EM</strong><span>dispatch</span><small>kickoff prompt</small></div><div class="journey-arrow">→</div>
  <div class="journey-step"><strong>RD</strong><span>claim + TDD + PR</span><small>In Review · qa</small></div><div class="journey-arrow">→</div>
  <div class="journey-step"><strong>QA</strong><span>evidence + verdict</span><small>In Review · human</small></div><div class="journey-arrow">→</div>
  <div class="journey-step"><strong>Human</strong><span>verify + merge</span><small>Done</small></div>
</div>

<div class="rework-loop"><strong>QA fail path</strong><code>(In Review, qa) → (In Progress, rd)</code><span>Fix the same Card, branch, and Pull Request — do not start a second delivery chain.</span></div>

<p class="takeaway">Each arrow is a durable artifact or field change, not an invisible agent-to-agent message.</p>

<!--
The optional specification PR is a separate architect Consumer session and human merge before decomposition resumes.
EM renders the next legal kickoff artifact; the carrier actually starts the session.
-->

---
layout: ppt
class: dense
---

# Every Session Runs the Same Five-Step Protocol

<div class="protocol">
  <div class="protocol-step"><span class="protocol-num">1</span><strong>Bind</strong><code>[role:rd] [board-card:#42]</code><p>One seat, one execution shape, and—when Consumer-shaped—exactly one Card.</p></div><div class="protocol-arrow">→</div>
  <div class="protocol-step"><span class="protocol-num">2</span><strong>Preflight</strong><code>expected == live?</code><p>Validate configuration, credentials, authority, Status, Role, and required artifacts.</p></div><div class="protocol-arrow">→</div>
  <div class="protocol-step"><span class="protocol-num">3</span><strong>Rehydrate</strong><code>Issue + comments + spec + PR</code><p>Recover the assignment from durable state; stale dispatch refuses instead of overwriting.</p></div><div class="protocol-arrow">→</div>
  <div class="protocol-step"><span class="protocol-num">4</span><strong>Resolve one stage</strong><code>produce | deliver | verify</code><p>Mutate only the permitted queue or bound Card and collect concrete evidence.</p></div><div class="protocol-arrow">→</div>
  <div class="protocol-step"><span class="protocol-num">5</span><strong>Persist + stop</strong><code>transition + handoff + artifact</code><p>Verify the result, leave the next seat enough context, then terminate without merging.</p></div>
</div>

<p class="principle-line"><strong>Recovery rule:</strong> resume or fix forward from the completed mutation prefix; never pretend a partial GitHub operation rolled back.</p>

<!--
Producer sessions may inspect a bounded queue; Consumer sessions may mutate only one bound Card and its artifacts.
The conversational summary helps the human, but GitHub remains authoritative.
-->

---
layout: ppt
class: dense
---

# A Prompt Becomes a Governed GitHub Operation

<div class="eyebrow">SHIPPED PRODUCER SURFACE · v0.2.0</div>

<div class="plugin-flow">
  <div class="plugin-node"><span class="node-label">1 · INPUT</span><strong>Role-marked request</strong><code>[role:analyst] Intake …</code></div><div class="plugin-arrow">→</div>
  <div class="plugin-node"><span class="node-label">2 · BOOTSTRAP</span><strong>Read-only orientation</strong><code>bootstrap --role</code></div><div class="plugin-arrow">→</div>
  <div class="plugin-node"><span class="node-label">3 · ORCHESTRATION</span><strong>Workflow skill</strong><code>intake | promote | brief</code></div><div class="plugin-arrow">→</div>
  <div class="plugin-node"><span class="node-label">4 · ENFORCEMENT</span><strong>Policy, then adapter</strong><code>policy.py → board.py</code></div><div class="plugin-arrow">→</div>
  <div class="plugin-node"><span class="node-label">5 · DURABLE EFFECT</span><strong><code>gh</code> → GitHub</strong><code>Project + Issue + comment</code></div>
</div>

<div class="mechanics-grid">
  <div><strong>Bootstrap is mandatory</strong><span>No mutation before it completes. Live board state overrides a stale kickoff prompt — the session refuses rather than acting on it.</span></div>
  <div><strong>Refusals cost nothing</strong><span>Authority is checked <em>before</em> the first GitHub call, so an illegal handoff leaves no partial state to clean up.</span></div>
  <div><strong>Result channel</strong><span>Mutations succeed only on structured JSON; errors return non-zero and the skill must not invent success.</span></div>
</div>

<!--
The model chooses and follows a skill, but it never sets arbitrary Project fields: there is no set_card_field operation.
Step 4 is two things in order — policy decides legality with no network access, then board.py performs the mutation.
Dispatch is read-only: a human or another carrier must start the rendered prompt.
-->

---
layout: center
---

<div class="chapter">
  <div class="chapter-num">Part 5</div>
  <div class="chapter-title">What We Have Built</div>
  <div class="chapter-sub">The concrete Producer MVP and its proof boundary</div>
</div>

<!--
This section distinguishes delivered work from the complete architecture.
-->

---
layout: ppt
class: dense
---

# The Producer Surface Is Complete

<div class="eyebrow">DELIVERED IN THIS CHECKOUT · v0.2.0</div>

<div class="delivered-map">
  <div class="delivered-core">
    <span class="node-label">CLAUDE PLUGIN</span><h3>Seven Producer skills</h3>
    <div class="skill-list">
      <div><code>using-agent-teams</code><span>bootstrap, then route by seat</span></div>
      <div><code>intaking-requirement</code><span>Issue → Backlog → architect</span></div>
      <div><code>authoring-spec</code><span>specify · promote · decompose</span></div>
      <div><code>briefing-board</code><span>lanes · WIP · merge queue</span></div>
      <div><code>triaging-board</code><span>blocked work → responsible seat</span></div>
      <div><code>dispatching-work</code><span>Ready queue → kickoff prompts</span></div>
      <div><code>inspecting-queue</code><span>order QA work, issue no verdicts</span></div>
    </div>
  </div>
  <div class="delivered-plus">+</div>
  <div class="delivered-core">
    <span class="node-label">PYTHON STANDARD LIBRARY · SIX MODULES</span><h3>A layered adapter</h3>
    <div class="command-list"><code>model</code><code>policy</code><code>config</code><code>github</code><code>board</code><code>workflows</code></div>
    <p><code>policy</code> imports nothing that touches the network — which is why <strong>every</strong> transition edge and seat pair is asserted, not sampled.</p>
    <div class="command-list"><code>bootstrap</code><code>doctor</code><code>brief</code><code>triage</code><code>queue</code><code>dispatch</code><code>intake</code><code>promote</code><code>decompose</code><code>transition</code><code>handoff</code></div>
  </div>
</div>

<div class="delivered-foundation">
  <span><strong>Governance</strong> six-state machine · handoff cap · WIP · seat action policy</span>
  <span><strong>Recovery</strong> every partial mutation names its completed prefix</span>
  <span><strong>Hard floor</strong> no agent seat can merge — not overridable</span>
</div>

<!--
The branch deliberately excludes the earlier full framework: no service, database, virtualenv, hooks, setup engine, or dual backend.
Growth is 4 skills to 7 and 1 file to 6 modules; the CLI entry point producer_board.py stayed the stable public surface.
Layer discipline: model and policy are pure, github and board talk to gh, workflows composes transactions.
-->

---
layout: ppt
class: dense
---

# Writing the Rules Down Found Five Bugs

<div class="eyebrow">WHAT THE POLICY LAYER CAUGHT</div>

| Found | Why it mattered |
|---|---|
| `architect → analyst` was <span class="accent">missing</span> from the authority matrix | An architect could not return an under-specified card — only guess, or block |
| Board read capped at <code>--limit 100</code>, <span class="accent">no truncation check</span> | A card past page one was invisible to dispatch. <strong>Reported success while skipping real work</strong> |
| `doctor` validated <span class="accent">2 of 6</span> Statuses, stopped at the first defect | Six re-runs to learn six things |
| Generic `transition` could reach `Ready` | Bypassed the `promote_to_ready` refusal — <span class="accent">a hole around the seat policy</span> |
| Handoff free text could forge a second `**Handoff**` line | A parser would read the forged one |

- The first three contradicted documents we had already written; the last two <span class="accent">only appeared once the rules were executable</span>
- Both authority holes were caught by tests written expecting them to *pass*

<!--
This is the argument for extracting policy as a pure module, made concretely.
Prose can hold a contradiction indefinitely. A table with 36 asserted pairs cannot.
The pagination one is the serious bug: silent truncation is worse than a crash, because dispatch keeps reporting success.
Both authority holes were found by writing the test first and being surprised — not by review.
-->

---
layout: ppt
class: dense
---

# Local Checks Pass; Live Proof Is Next

<div class="scope-ledger">
  <div class="scope-column current">
    <div class="axis-label">VERIFIED</div><h3>What already passes</h3>
    <ul>
      <li><strong>123 / 123</strong> tests with an injected fake <code>gh</code> — up from 9</li>
      <li>All <strong>36</strong> Status pairs and all <strong>36</strong> Role pairs asserted individually</li>
      <li>Every partial-mutation boundary in intake, handoff, promote, and decompose</li>
      <li>Pagination: a 250-card board reads whole; a 10,000-card board <em>refuses</em> rather than truncating</li>
      <li>Six-state policy, handoff cap, WIP formula, and the non-overridable merge floor</li>
    </ul>
  </div>
  <div class="scope-divider">→</div>
  <div class="scope-column target">
    <div class="axis-label">NOT YET PROVEN / BUILT</div><h3>What closes Phase 1</h3>
    <ul>
      <li><strong>Live disposable GitHub Project contracts</strong> — the largest open risk</li>
      <li>Remote claim, isolated worktree, RD TDD, and governed Pull Request</li>
      <li>Independent QA verdict and the rejection loop</li>
      <li>Seat-aware audit and a reconstructable end-to-end trace</li>
      <li>Plugin manifest re-validation against the seven-skill layout</li>
    </ul>
  </div>
</div>

<div class="status-note"><strong>Honest status</strong><span>Every green test is hermetic: it proves the adapter behaves correctly <em>given response shapes that have never met a real</em> <code>gh</code>. That gap is M1.1–M1.3 and it is the next thing to close — not more features.</span></div>

<!--
The Producer half is done; M4/M5 are Consumer-shaped and M8 is the golden-path proof.
Say the quiet part out loud: 123 passing tests is a statement about internal consistency, not about GitHub.
If the installed gh caps --limit, the pagination escalation must become a documented ceiling instead. That is an assumption, not a fact.
-->
