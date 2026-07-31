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
Our assignment's reference architecture; we studied it before designing our own.
Part 1 describes their system, so every slide in it carries a source line. Where we later diverge, the divergence is labelled as ours rather than folded into the description — the readiness gate on the lifecycle slide is the one to watch for.
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

<div class="citations">
<ul>
<li><b>board-superpowers</b> — github.com/PanQiWei/board-superpowers; doc paths below are from the repo root</li>
<li><b>scheduling layer + delegation</b> — AGENTS.md § "Architecture at a glance"; premise <code>P4b</code>, ADR-0004</li>
<li><b>board as truth</b> — <code>P4a</code> "the user's existing board is the truth. Period." — 0001-positioning.md</li>
<li><b>no server</b> — <code>C-PLUGIN-2</code> "no daemon, ever" — 0003-domain-model/03-aggregates-and-entities.md §3.3.4</li>
<li><b>100× thesis</b> — <code>P1</code> "throughput scales 100× while architect attention does not" — 0001-positioning.md</li>
</ul>
</div>

<!--
Not an app. Plugin = folders of instruction files + scripts, inert until a session starts.
State lives on the board and in git — kill every session, nothing is lost.
Sprint / story points deliberately removed: they assume implementation is the bottleneck.
-->

---
layout: ppt
class: dense
---

# Two Session Shapes

<div class="grid-2" style="max-width:100%;">
  <div class="card">
    <h3>Producer — Manager</h3>
    <p>Purpose: new items onto the board, and a board that stays ready to receive them.<br/>
    Long-lived, interactive, whole-board view.<br/>
    <span class="accent">Never writes code.</span></p>
  </div>
  <div class="card">
    <h3>Consumer — one item</h3>
    <p>Purpose: complete or resolve exactly one item.<br/>
    Claim one card, TDD, open one PR, terminate.<br/>
    <span class="accent">Never merges its own PR.</span></p>
  </div>
</div>

<br/>

- Core invariant: <span class="accent">one card = one Consumer session = one PR</span>
- Session: one cold-start execution — a launched CLI session, or a subagent the Producer spawns
- These two are their <span class="accent">only</span> kanban-relative roles — no SA / Architect / Dev / QA seats exist

<div class="citations">
<ul>
<li><b>purpose, not I/O</b> — "both roles read and write; what differs is what the session delivers" — 02-roles.md</li>
<li><b>Manager</b> — board orchestration; "long-lived, aggregate view" — 03-producer-surface.md §1.3.1</li>
<li><b>I-1 / I-2</b> — one card = one <b>Consumer</b> session = one PR; the two hard floors above — 07-cross-cutting-invariants.md</li>
<li><b>Mode-1 / Mode-2</b> — interactive CLI session, both platforms · Producer-spawned subagent, CC only — 04-consumer-surface.md</li>
<li><b>lifetime lock</b> their <b>original framing</b> · pull-system after Anderson, <i>Kanban</i> (2010) — 02-roles.md</li>
</ul>
</div>

<!--
Define the word before using it. The concrete version, if the room looks unsure: usually a session is one terminal running `claude` — not a container, not a daemon, not a bot with a name. When it exits it is gone, and the only reason the next one can continue the work is that this one wrote its result to GitHub. The one caveat is their Mode-2 Consumer, which is a subagent rather than its own terminal; it still cold-starts and still persists everything to GitHub, so nothing downstream changes. Everything else in the deck follows from that: no in-memory handoffs, no "ask the QA agent" — because there is nothing to ask.
Worth saying plainly: the seat names people expect to be agents (SA, Architect, Dev, QA) do not exist in their model at all. 02-roles.md allows other roles to be layered on top of the kanban-relative one, but declares them out of scope. Nobody is sitting in a chair waiting.
Their word, kept here on purpose: 02-roles.md defines "the role of the session's master agent with respect to the kanban", and states the invariant as "one session = one master agent = one kanban-relative role for the lifetime of the session". They flag that lifetime lock as an original framing — canonical Kanban names workers by station, not by purpose, and does not lock a worker's role over time.
In Part 2 we rename this to "shape", because our design needs the word Role for the durable field naming whose turn it is. Theirs has no seats, so it never had that second question to answer.
The real seam is purpose, and 02-roles.md is emphatic about it: "the distinction is purpose, not literal I/O direction — both roles read and write; what differs is what the session ultimately delivers." Producer's purpose is that new items land on the kanban and the kanban stays healthy enough to keep receiving them; Consumer's is that exactly one item ends up resolved. Do not sell it as interactive-vs-unattended — that is a consequence, and not even a reliable one.
Where the "unattended" instinct comes from, and why it is wrong: their Consumer has two modes. Mode-1 is architect-spawned and interactive — the architect pastes a card token into a fresh CLI session — and their spec calls it "the superset", the mode where every feature works, on both platforms. Mode-2 is the Producer-spawned subagent, and it is Claude Code only at v1. So the unattended shape is the narrower one, not the default. If asked "so is a Consumer a separate process?", the honest answer is: in Mode-1 yes, in Mode-2 it is a subagent inside the Producer's own session.
Note the invariant says one card = one *Consumer* session. It says nothing about Producer sessions, which are explicitly aggregate — one Manager session covers the whole project.
Part 2 has a slide devoted to what a session actually is, because this is the single most-confused word in the deck.
-->

---
layout: ppt
class: dense
---

# Card Lifecycle — Who Acts Where

<div class="rail">
  <div><span class="actor">AGENT</span><strong>Backlog</strong><span>analyst shapes the requirement, architect specs it</span></div>
  <div class="gate"><span class="actor">HUMAN · GATE 1</span><strong>→ Ready</strong><span>approve the work into the queue — <code>promote</code></span></div>
  <div><span class="actor">AGENT</span><strong>In Progress</strong><span>claim the card, TDD, open exactly one PR</span></div>
  <div><span class="actor">AGENT</span><strong>In Review</strong><span>independent verification, evidence, verdict</span></div>
  <div class="gate"><span class="actor">HUMAN · GATE 2</span><strong>Merge</strong><span>read the PR and accept the change — <code>gh pr merge</code></span></div>
  <div><span class="actor">SYSTEM</span><strong>Done</strong><span>the card reconciles once the PR lands</span></div>
</div>

- Card = GitHub Issue: Goal · Acceptance criteria · Out of scope · Dependencies · spec link
- `Blocked` is an <span class="accent">interrupt on any AGENT cell</span>, not a step in the line

<div class="citations">
<ul>
<li><b>six states + per-transition checklist</b> — skills/board-canon/references/state-machine.md</li>
<li><b>their <code>Backlog → Ready</code> gate is a checklist, not a person</b> — 5 mandatory body sections · INVEST · estimate set · no unmet hard <code>depends-on</code></li>
<li><b>ADR-0006 §3 autonomy matrix</b> — row 5 <code>Backlog → Ready = A</code> (auto, "forward state advance") · row 12 <code>merge = R</code> ("architect's reserved power") · <b>N = 0</b>, nothing permanently forbidden</li>
</ul>
</div>

<!--
Cards are thin pointers to specs — no spec, no card (anti-slop rule).
Say the attribution out loud, because it is easy to get backwards: only Gate 2 is theirs. Upstream, Backlog to Ready is class A — automatic, filed under "forward state advance" — gated by a checklist, not by a person. The only reserved power in their matrix is merge, and even that is class R, meaning the architect approves rather than the system refusing. Their matrix has N=0: nothing is permanently forbidden. Our Gate 1, and our two non-overridable hard floors, are additions.
Gates are cheap: read a one-screen card, read a PR. Minutes of attention govern hours of machine work.
Gate placement is not arbitrary — both sit where a decision is cheap to make and expensive to get wrong: committing the team to build a thing, and accepting a change into the repository.
"SYSTEM" on Done means no one decides it: GitHub closes the Issue on merge and the card reconciles.
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

<div class="citations">
<ul>
<li><b>claim = branch push</b> — ADR-0002 "Atomic claim via remote branch push"; created by <code>git push --force-with-lease=&lt;ref&gt;:</code></li>
<li><b>worktree isolation</b> — ADR-0003 "One worktree per Consumer session" + invariant <code>I-7</code> one-card-one-worktree</li>
<li><b>PR contract</b> — 0002-…/08-pr-contract.md · skills/enforcing-pr-contract/ · premise <code>P6</code> "human verification is a first-class output"</li>
<li><b>A / R / N + audit</b> — ADR-0006 §3 matrix, §5 audit log</li>
</ul>
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
| Manager intake conversation | <span class="accent">analyst</span> — requirement → spec |
| Decomposition into cards | <span class="accent">architect</span> — spec → INVEST cards |
| Consumer TDD loop | <span class="accent">dev</span> — card → tested PR |
| Verification chain + review queue | <span class="accent">qa</span> — evidence → verdict |
| Board briefing · dispatch · triage | <span class="accent">lead</span> — queue, WIP, dispatch |

- Keep: board as truth `P4a` · one card = one PR `I-1` · git as lock, worktree per Consumer `ADR-0002/3`
- Drop: multi-backend · dual-platform · runtime dependency on sibling plugins `P4b`

<div class="citations">
<ul>
<li><b>P4a</b> — "the user's existing board is the truth. Period." — 0001-positioning.md</li>
<li><b>I-1 / I-7</b> — one card = one <b>Consumer</b> session = one PR · one-card-one-worktree — 07-cross-cutting-invariants.md</li>
<li><b>ADR-0002 / ADR-0003</b> — "Atomic claim via remote branch push" · "One worktree per Consumer session" — adr/</li>
<li><b>P4b</b> — "Composition is permanent … hard runtime dependency is a feature, not a bug" — what our Drop line rejects</li>
<li><b>Add / Drop are ours</b> — hard-floor gates (inv. 5) · no sibling-plugin dependency (inv. 10) — docs/ARCHITECTURE.md</li>
</ul>
</div>

<!--
Cite the file, not the vibe: every tag on the three bullets points at a file we actually read — theirs for Keep, ours for Add and Drop — so a follow-up question has somewhere to land.
Read the table left-to-right, not as a one-to-one map: their single Manager role is the source of three of our seats (analyst, architect, lead), because they split sessions by purpose and we split them by capability.
The "Add" line is the correction worth making out loud, because it is easy to get backwards. We did NOT inherit two human gates. In their autonomy matrix, `Backlog -> Ready` is class A — automatic, filed under "forward state advance" — and the only reserved power is merge, class R, meaning the architect approves rather than the system refusing. Their matrix has N=0: nothing is permanently forbidden. Our readiness gate and our two hard floors are additions, and merge differs in kind as well as in owner — theirs is an approval, ours is a refusal no configuration can widen.
The Drop line's last item is the other deliberate divergence. P4b makes composition permanent for them, and a hard runtime dependency on superpowers and gstack an explicit feature. We reference the same disciplines by name and ship our own, so a missing sibling refuses loudly instead of silently downgrading governance.
Our other deviation: make the seats explicit named skills for demo legibility.
Scope honesty: happy path in days; reliability tuning is where real time goes.
-->

---
layout: center
---

<div class="chapter">
  <div class="chapter-num">Part 2</div>
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

# Overall Architecture

<div class="architecture-map">
  <div class="human-band">
    <div><strong>Human stakeholder</strong></div>
  </div>
  <div class="scope-architecture">
    <div class="scope-node board-scope">
      <div class="node-label">BOARD LEVEL · GITHUB PROJECT</div>
      <strong>Producer</strong>
      <span>lives with the board — shapes, routes, and dispatches</span>
      <div class="scope-seats">analyst · architect · lead · qa</div>
    </div>
    <div class="scope-flow">
      <span>dispatch →</span>
      <b>BOARD<br/>↕<br/>CARD</b>
      <span>← result</span>
    </div>
    <div class="scope-node card-scope">
      <div class="node-label">CARD LEVEL · ONE WORK ITEM</div>
      <strong>Consumer</strong>
      <span>lives with one Card — claims and resolves one stage</span>
      <div class="scope-seats">architect · dev · qa</div>
    </div>
  </div>
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

# Status And Role

<div class="axis-grid">
  <div class="axis-block">
    <div class="axis-label">LIFECYCLE AXIS</div><h3>Status</h3>
    <div class="token-line"><span>Backlog</span><b>→</b><span>Ready</span><b>→</b><span>In Progress</span><b>→</b><span>In Review</span><b>→</b><span>Done</span></div>
  </div>
  <div class="axis-block">
    <div class="axis-label">OWNERSHIP AXIS</div><h3>Role</h3>
    <div class="role-tokens"><span>analyst</span><span>architect</span><span>dev</span><span>qa</span><span>lead</span></div>
  </div>
</div>

<p class="takeaway">The routing state is the pair <code>(Status, Role)</code>.</p>

<!--
When both coordinates move, transition_card and handoff_card are separate semantic operations.
That separation makes a partial external mutation visible and recoverable.
-->

---
layout: center
---

<div class="chapter">
  <div class="chapter-num">Part 3</div>
  <div class="chapter-title">Work Flow & Mechanics</div>
  <div class="chapter-sub">How one request becomes one reviewable delivery</div>
</div>

---
layout: ppt
class: dense
---

# From Request to Delivery

<div class="journey">
  <div class="journey-step"><strong>Human</strong><span>request</span><small>no Card yet</small></div><div class="journey-arrow">→</div>
  <div class="journey-step"><strong>Analyst</strong><span>shape demand</span></div><div class="journey-arrow">→</div>
  <div class="journey-step"><strong>Architect</strong><span>spec + decompose</span></div><div class="journey-arrow">→</div>
  <div class="journey-step gate"><strong>Human</strong><span>approve ready</span></div><div class="journey-arrow">→</div>
  <div class="journey-step"><strong>Lead</strong><span>dispatch</span></div><div class="journey-arrow">→</div>
  <div class="journey-step"><strong>Dev</strong><span>claim + TDD + PR</span></div><div class="journey-arrow">→</div>
  <div class="journey-step"><strong>QA</strong><span>evidence + verdict</span></div><div class="journey-arrow">→</div>
  <div class="journey-step gate"><strong>Human</strong><span>verify + merge</span><small>Done</small></div>
</div>

<div class="rework-loop"><strong>QA fail path</strong><code>(In Review, qa) → (In Progress, dev)</code><span>Fix the same Card, branch, then Pull Request.</span></div>

---
layout: ppt
class: dense
---

# Consumer Mechanics

<div class="protocol">
  <div class="protocol-step"><span class="protocol-num">1</span><strong>Bind</strong><code>[role:dev] [board-card:#42]</code><p>Exactly one Card.</p></div><div class="protocol-arrow">→</div>
  <div class="protocol-step"><span class="protocol-num">2</span><strong>Preflight</strong><code>expected == live?</code><p>Validate configuration, credentials, authority, Status, Role, and required artifacts before touching anything.</p></div><div class="protocol-arrow">→</div>
  <div class="protocol-step"><span class="protocol-num">3</span><strong>Rehydrate</strong><code>Issue + PR</code><p>Rebuild the assignment from existing state.</p></div><div class="protocol-arrow">→</div>
  <div class="protocol-step"><span class="protocol-num">4</span><strong>Resolve one stage</strong><code>produce | deliver | verify</code><p>Implemention and testing.</p></div><div class="protocol-arrow">→</div>
  <div class="protocol-step"><span class="protocol-num">5</span><strong>Persist + stop</strong><code>transition + artifact</code><p>Verify the durable result, then terminate without merging.</p></div>
</div>

<!--
Producer sessions may inspect a bounded queue; Consumer sessions may mutate only one bound Card and its artifacts.
Step 4 runs our own skills. agent-teams does not invoke superpowers or gstack — it may reference them as recommended practice, but every skill and script in this plugin is its own.
The conversational summary helps the human, but GitHub remains authoritative.
Step 5 is deliberately last: a Consumer that cannot persist its result has not delivered, however good the code is.
-->

---
layout: ppt
class: dense
---

# Producer Mechanics

<div class="plugin-flow">
  <div class="plugin-node"><span class="node-label">1 · INPUT</span><strong>Requests</strong><code>[role:analyst] …</code></div><div class="plugin-arrow">→</div>
  <div class="plugin-node"><span class="node-label">2 · BOOTSTRAP</span><strong>Read-only orientation</strong><code>bootstrap</code></div><div class="plugin-arrow">→</div>
  <div class="plugin-node"><span class="node-label">3 · ORCHESTRATION</span><strong>Workflow skill</strong><code>intake · promote</code></div><div class="plugin-arrow">→</div>
  <div class="plugin-node"><span class="node-label">4 · ENFORCEMENT</span><strong>Policy, then adapter</strong><code>policy → board</code></div><div class="plugin-arrow">→</div>
  <div class="plugin-node"><span class="node-label">5 · DURABLE EFFECT</span><strong><code>gh</code> → GitHub</strong><code>Issue + comment</code></div>
</div>

<!--
The model chooses and follows a skill, but it never sets arbitrary Project fields: there is no set_card_field operation.
Step 4 is two things in order — policy decides legality with no network access, then board.py performs the mutation.
Dispatch is read-only: it renders a prompt. A human or another carrier must start the session.
-->

---
layout: ppt
class: dense
---

# Four Failure Modes

<div class="failclass wide">
  <div><span class="fc-num">1</span><div><strong>Refusal</strong> · <code>nothing changed</code><p>The seat lacks authority, or a precondition is unmet — caught before any GitHub call.</p></div></div>
  <div class="defect"><span class="fc-num">2</span><div><strong>Partial mutation</strong> · <code>ok=false · partial=true</code><p>A multi-step write broke midway: three calls, no transaction across them. <span class="accent">The only class we own.</span></p></div></div>
  <div><span class="fc-num">3</span><div><strong>Work failure</strong> · <code>same Card · same branch · same PR</code><p>The job itself did not succeed: tests will not go green, or the qa verdict is <code>fail</code>.</p></div></div>
  <div><span class="fc-num">4</span><div><strong>Blocked</strong> · <code>Status=Blocked · Role=owner</code><p>The answer is outside this session: a decision, a dependency, an unclear spec.</p></div></div>
</div>

<!--
Four things share the word "failed" and nothing else. Collapsing them is how a system retries a refusal, or rolls back a delivery that was fine.
When each one fires: refusal on any authority or precondition check; partial mutation only inside a multi-step write, and today that means intake, create-card and decompose; work failure is the ordinary one and by far the most common; blocked is a work failure nobody in this session can answer.
The marker on each row is what is left on the board afterwards, which is the thing the next session actually reads.
-->

---
layout: ppt
class: dense
---

# Failure Example

<div class="casegrid">
  <div>
    <div class="case-head"><span class="fc-num">1</span><strong>Refusal</strong></div>
    <p class="case-do">architect runs <code>promote 9 --spec PR#8 --acting-role architect</code></p>
    <p class="case-out">Refused before any write — <code>promote_to_ready</code> is closed to every agent seat.</p>
    <p class="case-board"><b>Board</b> — #9 unchanged at <code>(Backlog, architect)</code>. No comment, no audit entry.</p>
  </div>
  <div class="defect">
    <div class="case-head"><span class="fc-num">2</span><strong>Partial mutation</strong></div>
    <p class="case-do">analyst runs <code>intake --title "mini data dashboard"</code></p>
    <p class="case-out">Issue #11 created · added to the Project · then <code>status_set</code> fails on the third call.</p>
    <p class="case-board"><b>Board</b> — #11 is on the board with no Status, no Role, no handoff comment.</p>
  </div>
  <div>
    <div class="case-head"><span class="fc-num">3</span><strong>Work failure</strong></div>
    <p class="case-do">qa verifies card #9, delivered as PR #12</p>
    <p class="case-out">Verdict <code>fail</code> — AC-2 not met: an empty dataset renders <code>NaN</code>. Reproducible.</p>
    <p class="case-board"><b>Board</b> — #9 returns to <code>(In Progress, dev)</code>. PR #12 stays open.</p>
  </div>
  <div>
    <div class="case-head"><span class="fc-num">4</span><strong>Blocked</strong></div>
    <p class="case-do">dev, second failed attempt on card #10</p>
    <p class="case-out"><code>test_refresh_interval</code> still red — the specification never says what an interval of <code>0</code> means.</p>
    <p class="case-board"><b>Board</b> — #10 at <code>(Blocked, architect)</code>. Claim branch and worktree kept.</p>
  </div>
</div>

<!--
Read each card downwards: what was run, what came back, what is true on the board afterwards. The bottom line of each card is the one the next slide answers.
Cards 1 and 2 are the Producer half and run today. `promote` really is closed to every agent seat in policy.py, and intake really is three separate gh calls with no transaction — Issue, Project field, comment. Cards 3 and 4 are the designed Consumer path; the qa verdict and the dev seat are specified but not yet built, so present them as the contract rather than as a demo.
The numbers are deliberately the live-run cards from Part 5, so the room sees these as things that could happen to the run they are about to watch, not as invented incidents.
The bottom row of the grid is the real payload: nothing was written · a half-written card · a delivery that exists and is wrong · work parked with the branch intact. Four different states, which is exactly why one word for all four is useless.
Card 4's two attempts is the systematic-debugging rule: the same symptom failing twice means the diagnosis is wrong, not that the fix needs another try.
-->

---
layout: ppt
class: dense
---

# Recovering

<div class="casegrid">
  <div>
    <div class="case-head"><span class="fc-num">1</span><strong>Refusal</strong></div>
    <p class="case-step"><b>1</b> read the route the refusal names — <i>"hand the Card to human"</i></p>
    <p class="case-step"><b>2</b> <code>handoff 9</code> architect → human, with the spec link</p>
    <p class="case-step"><b>3</b> the human runs <code>promote 9 --spec PR#8</code></p>
    <p class="case-board"><b>After</b> — #9 at <code>(Ready, dev)</code>. Nothing needed undoing.</p>
  </div>
  <div class="defect">
    <div class="case-head"><span class="fc-num">2</span><strong>Partial mutation</strong></div>
    <p class="case-step"><b>1</b> read <code>completed</code> — the first two calls landed</p>
    <p class="case-step"><b>2</b> never re-run <code>intake</code>; it files a second Issue</p>
    <p class="case-step"><b>3</b> replay Status, then Role, then the comment</p>
    <p class="case-board"><b>After</b> — #11 at <code>(Backlog, architect)</code>, as a clean intake.</p>
  </div>
  <div>
    <div class="case-head"><span class="fc-num">3</span><strong>Work failure</strong></div>
    <p class="case-step"><b>1</b> a new dev session resumes the claim and worktree</p>
    <p class="case-step"><b>2</b> fix forward — PR #12 updates in place</p>
    <p class="case-step"><b>3</b> <code>handoff 9</code> dev → qa</p>
    <p class="case-board"><b>After</b> — #9 at <code>(In Review, qa)</code>. Still one Card, one PR.</p>
  </div>
  <div>
    <div class="case-head"><span class="fc-num">4</span><strong>Blocked</strong></div>
    <p class="case-step"><b>1</b> architect amends the spec to define interval <code>0</code></p>
    <p class="case-step"><b>2</b> <code>transition 10 --to "In Progress"</code></p>
    <p class="case-step"><b>3</b> <code>handoff 10</code> architect → dev</p>
    <p class="case-board"><b>After</b> — #10 at <code>(In Progress, dev)</code>, same worktree.</p>
  </div>
</div>

<p class="takeaway">Only <strong>partial mutation</strong> repairs the board. The other three move the Card forward — nothing is ever undone.</p>

<!--
Same four cells as the previous slide, so each card answers the incident that sat in that position. Walk them in the same order.
Refusal — the refusal text is written to teach the route, not just to say no. policy.py keeps a reason per closed action for exactly that purpose, which is why step 1 is "read it" rather than "try something else". Note what step 3 shows: the command that was refused is the same command that succeeds, run by the seat that holds the authority. Nothing about it was wrong except who called it.
Partial mutation — step 2 is the one that bites. Field writes are precondition-checked, so replaying one that already landed is refused harmlessly. Creations are not, so re-running the whole routine files the requirement twice. Never a rollback: a compensating write can fail too, and a false "rolled back" is worse than the error, because the reader then plans against a state that does not exist. The test suite asserts no result ever contains "rolled back", "rollback", "reverted" or "undone".
Work failure — say "a new session" deliberately. The old one is gone; what survives is the assignment on GitHub plus the branch and worktree on disk. Nothing is handed over in memory.
Blocked — the three things in step 2 are the contract. A blocker missing any of them is an abandonment, not a handoff.
Who runs these steps today: a human or the next session, from the result envelope. The `resolving-issues` skill would emit them as commands; it is designed, not built.
-->

---
layout: center
---

<div class="chapter">
  <div class="chapter-num">Part 4</div>
  <div class="chapter-title">What We Have Built</div>
  <div class="chapter-sub">The Producer MVP, and what comes after it</div>
</div>

<!--
This section distinguishes delivered work from the complete architecture, then names the next milestones in dependency order.
-->

---
layout: ppt
class: dense
---

# The Producer Surface Is Complete

<div class="eyebrow">SEVEN SKILLS · SIX MODULES</div>

<div class="skill-list" style="grid-template-columns: repeat(4, minmax(0, 1fr));">
  <div><code>using-agent-teams</code><span>bootstrap, then route</span></div>
  <div><code>intaking-requirement</code><span>analyst — shape one requirement</span></div>
  <div><code>authoring-spec</code><span>architect — specify and decompose</span></div>
  <div><code>briefing-board</code><span>lead — lanes, WIP, merge queue</span></div>
  <div><code>triaging-board</code><span>lead — blocked work → responsible seat</span></div>
  <div><code>dispatching-work</code><span>lead — Ready queue → kickoff prompts</span></div>
  <div><code>inspecting-queue</code><span>qa — order the queue, no verdicts</span></div>
  <div style="border-color: var(--accent); background: rgba(43,76,126,0.05);"><code>model · policy · config<br/>github · board · workflows</code><span>modules beneath</span></div>
</div>

<!--
The branch deliberately excludes the earlier full framework: no service, database, virtualenv, hooks, setup engine, or dual backend.
Growth is 4 skills to 7 and 1 file to 6 modules; producer_board.py stayed the stable public entry point.
The eighth cell is the deterministic layer: model and policy are pure, github and board talk to gh, workflows composes transactions.
Command names are in the README; what matters here is the shape, not the list.
-->

---
layout: ppt
class: dense
---

# Next Move

<div class="roadmap">
  <div>
    <div class="stage">NEXT</div>
    <div class="roadmap-copy"><strong>The <code>dev</code> Consumer seat</strong><span>Remote claim as the lock, isolated worktree, test-first work, one governed Pull Request.</span></div>
  </div>
  <div>
    <div class="stage">THEN</div>
    <div class="roadmap-copy"><strong>The <code>qa</code> verdict</strong><span>Independent verification with evidence, and the rejection loop back to the same Card.</span></div>
  </div>
  <div>
    <div class="stage">LATER</div>
    <div class="roadmap-copy"><strong>Audit, then OPS</strong><span>A reconstructable seat-by-seat trace for one Card; CI and merge machinery in phase 2.</span></div>
  </div>
</div>

<!--
The order is not preference, it is dependency: building a second seat on unverified response shapes doubles what must be re-checked when the first real gh call disagrees with a fixture.

Say the quiet part out loud: passing tests is a statement about internal consistency, not about GitHub.
-->

---
layout: center
---

<div class="chapter">
  <div class="chapter-num">Part 5</div>
  <div class="chapter-title">Demo</div>
  <div class="chapter-sub">Our agent team at work</div>
</div>

<!--
The demo workload lives in the sibling agent-teams-test repository; the plugin remains in agent-teams.
-->

---
layout: ppt
class: dense
---

# Our Seats

| Seat | Skill | Does |
|---|---|---|
| <span class="accent">analyst</span> | `intaking-requirement` | requirement → Backlog card → architect |
| <span class="accent">architect</span> | `authoring-spec` | spec PR · send to gate · decompose |
| <span class="accent">lead</span> | `briefing-board` · `triaging-board` · `dispatching-work` | brief · triage · dispatch kickoffs |
| <span class="accent">qa</span> | `inspecting-queue` | order the verification queue |
| dev | <span class="muted">not yet</span> | claim → TDD → code PR → qa |
| human | — | the two gates: <span class="accent">promote</span> + <span class="accent">merge</span> |

- Routing: plain language or a `[role:…]` token — skill descriptions match the request
- Authority: `policy.py` <span class="accent">refuses illegal actions before any GitHub call</span>

<!--
A seat = which skill the session loads, nothing more. Sessions are peers, not a call stack.
Two layers: routing is soft (prompt matching), authority is hard (Python raises before mutating).
Producer surface now complete across all four Producer seats; the dev Consumer slice is next.
qa's verdict is Consumer-shaped and not built yet; inspecting-queue only orders the queue.
-->

---
layout: ppt
class: dense
---

# One Requirement, End to End — Live Run

| # | Seat | We said / did | Durable result |
|---|---|---|---|
| 1 | analyst | "we need a mini data dashboard …" | Issue #7 · `(Backlog, architect)` |
| 2 | architect | "write the spec for card #7" | spec PR #8, docs-only — then <span class="accent">stop</span> |
| 3 | human | merge PR #8 | spec durable on `main` |
| 4 | architect | "split #7 into implementation cards" | cards #9 + #10 · `(Backlog, human)` |
| 5 | human | `promote 9 --spec PR#8` (and 10) | <span class="accent">the readiness gate</span> → `(Ready, dev)` |
| 6 | lead | "what's ready to work on?" | two `[role:dev] [board-card:#…]` kickoffs |
| 7 | dev | — | <span class="muted">future work</span> |

- No token needed: the plugin routed every plain-language request to the right seat
- Two human moments only: merge and promote — everything between ran itself

<!--
Update issue/PR numbers after the live run if they differ.
Steps 2 and 4 are separate architect sessions: one job per session (Consumer vs Producer shape).
Step 5 refuses every agent seat in policy.py, and refuses the human too until the spec PR is merged.
Step 6 renders prompts; rendering is not starting a session — a carrier starts the dev Consumer.
-->

---
layout: ppt
class: dense
---

# What Testing Taught Us

<div class="grid-2" style="max-width:100%;">
  <div class="card">
    <h3>Seats with a skill</h3>
    <p>Announced every mutation first, reported CLI JSON faithfully, refused out-of-authority
    actions..<br/>
    <span class="accent">Follows our rules.</span></p>
  </div>
  <div class="card">
    <h3>The seat without one (dev)</h3>
    <p>Kept the git habits — branch, one PR — but skipped the claim, skipped In&nbsp;Review,
    wrote no tests.<br/>
    <span class="accent">Tools alone don't make discipline.</span></p>
  </div>
</div>

<br/>

- Same model, same CLI available — the only variable was whether a skill defined the procedure


<!--
Evidence: Tetris (#1) and Snake (#4) both implemented by an unscripted dev seat.
Both runs produced honest handoffs and clean PRs, and both left the board wrong until a human repaired it.
This is the argument for building dev/qa as skills rather than trusting the protocol surface.
-->

---
layout: ppt
class: dense
---

# The Board in Action

<div class="figure">
  <img src="./images/board.png" />
</div>

<p class="takeaway">Card #1 after the live run — spec-derived acceptance criteria, <code>Status</code> and <code>Role</code>, linked Pull Request.</p>

<!--
One real artifact beats an illustrated one: an invented mini-board alongside a real screenshot said two different things about the same run.
The demo workload now belongs in the sibling agent-teams-test repository, while the plugin remains in agent-teams.
The current implementation plan still marks disposable-Project end-to-end proof as pending.
-->
