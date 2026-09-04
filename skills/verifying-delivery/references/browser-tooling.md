# Which browser suite the Browser reviewer uses

<!-- Written 2026-09-04 at the team lead's request (2026-08-28 review, todo 6):
     there are many browser-automation suites with different characteristics,
     and which one this seat drives has to be written down rather than left to
     whatever the model reaches for. INVENTED by agent-teams; see
     ATTRIBUTION.md. -->

**Playwright, driving headless Chromium, invoked from `Bash`.**

That is the answer. The rest of this file is why, what it does not cover, and
what to write in the evidence block.

## What is actually running

| | |
|---|---|
| Suite | [Playwright](https://playwright.dev) (Node) |
| Engine | Chromium, headless |
| Invoked by | the `qa-browser-worker`, through its `Bash` tool |
| Installed by | **not this plugin** — see "It is not installed for you" |
| Last observed live | `playwright (chromium headless) 1.62.1`, Card #28, head `5f8aac4`, 2026-08-28 |

The seat has no browser tool in its frontmatter. Its `tools:` list is `Read,
Bash, Grep, Glob, WebFetch, Skill, SendMessage` — the browser is reached by
running a script, not by calling a tool the harness provides. That is
deliberate (see "Why not the agent's own browser tooling") and it is the reason
this file exists: nothing in the agent definition names the suite, so the
answer had to be written somewhere.

## It is not installed for you

agent-teams installs no browser and declares no Node dependency. The consuming
repository supplies it, and the usual line inside the detached review worktree
is:

```bash
npm install --no-save playwright
npx playwright install chromium     # first run only; downloads the browser
```

If neither is available, **that is a `blocked` outcome with the reason
recorded** — not a pass with a note, and not a substitution for reading the
source instead. The blindness rule in `browser-pass.md` is not suspended
because the browser was inconvenient.

## Why Playwright, and what the alternatives would have bought

The deciding property is not ergonomics. `browser_evidence.console` is a
**validated required field**: `policy.validate_verdict` refuses a user-facing
pass whose console block is absent, because the one bug that got past QA before
was an ES-module error sitting silently behind a green suite. So the suite has
to make console and page errors trivially capturable, per interaction, in the
same process that drove the interaction.

| Suite | What it is good at | Why not here |
|---|---|---|
| **Playwright** | Three engines (Chromium / Firefox / WebKit), auto-waiting on actionability, `page.on('console')` and `page.on('pageerror')` as first-class events, network interception, screenshots and tracing built in, headless by default, one `npx` away with no daemon | **Chosen.** Console and page-error capture are events rather than a log scrape, which is exactly the shape `browser_evidence.console` needs |
| **Puppeteer** | Mature, small API, same CDP foundation, slightly lighter install | Chromium-only in practice, no auto-waiting, no bundled runner. It would work and buys nothing Playwright does not already have |
| **Selenium / WebDriver** | The cross-browser, cross-language standard; real grid and device-farm support; the right answer for a browser/OS matrix | Heaviest setup (per-browser drivers), and console capture on Chrome still drops to CDP anyway. We have no matrix to run — see "What this does not cover" |
| **Cypress** | Outstanding debugging, time-travel UI, retry-ability, strong for a suite that lives in the repository | Runs inside the browser's own event loop with the same-origin constraints that implies, and is built around a committed `cypress/` spec suite. This seat **publishes nothing** and deletes its worktree; a tool that wants to own a directory is a poor fit for a reviewer that must not write to the repository |
| **WebdriverIO** | Flexible, good mobile/Appium story | Same trade as Selenium, with more configuration than a one-Card pass justifies |
| **browser-use** and agentic wrappers | Natural-language driving, very little script to write | The `expected` / `actual` per input case would then be produced by a second model rather than *observed*. `browser_evidence` is already attested rather than proven; adding a model between the browser and the record makes that strictly worse |

### Why not the agent's own browser tooling

Claude's in-browser tooling (the Chrome extension, or any browser MCP server)
drives the **operator's real browser session**, with their cookies, extensions,
and logins. Three reasons that is wrong for this seat, in order of severity:

1. **A garbage-input pass must never run inside a logged-in identity.** Step 2
   of `browser-pass.md` deliberately submits injection-shaped strings to every
   field. Doing that in a session carrying real credentials is not a test.
2. **Evidence must be reproducible from a detached worktree at an exact SHA.**
   A shared browser session carries state from whatever was open before it, and
   `browser_evidence` claims to describe one commit.
3. **A subagent cannot rely on it.** MCP availability is a property of the
   operator's configuration, not of the Card. A dispatched worker that assumes
   it would be unrunnable on a machine where it is absent.

## Record the engine, not just the suite

Whatever ran goes in `browser_evidence.tool` **verbatim, with the engine and
the version**:

```json
"tool": "playwright (chromium headless) 1.62.1"
```

`"tool": "playwright"` alone is not enough. Headless Chromium, headed Chromium,
and WebKit differ in exactly the places this evidence is used to argue from —
console formatting, font and layout metrics, autoplay and permission defaults,
and CORS behaviour over `file://`, which is the failure that started this whole
line of work. A reader who cannot tell which engine produced a console listing
cannot check the finding.

Any suite that produces the same evidence is acceptable. Naming it is not
optional.

## What this does not cover

Stated plainly so nobody reads "we use Playwright" as broader coverage than it
is:

- **One engine.** Chromium only. No Firefox, no WebKit, so no Safari-class
  finding is reachable — and the original blank-page defect was a Chrome *and*
  Safari behaviour.
- **One viewport, headless.** No device emulation matrix, no real mobile.
- **One OS**, whatever the run happens to be on.
- **Nothing accumulates.** The worktree is removed when the pass ends and the
  flows are re-derived from the specification for every Card. There is no
  regression suite here; see the open decision on whether QA should accumulate
  test assets (`HANDOFF.md`).

A browser/OS matrix is the standard reason to reach for Selenium or a device
cloud. If that becomes a requirement, this choice should be revisited — the
suite is not the constraint, the absence of a matrix requirement is.
