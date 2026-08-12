# Transcript: 02-decompose-and-promote

- Session: `5b64bb2a-404b-40e0-aabe-f75a72327907` (cc_team, CLAUDE_CONFIG_DIR=~/.claude-team)
- Covers: Steps 4-5 - architect decompose (#14 walking skeleton + #15 + #16), then the human promote of #14 (typed CLI command)
- Full raw record: the JSONL file of the same session id; this export omits thinking blocks and truncates long tool output.

## Human (slash command: /clear) - 15:49:00

<command-name>/clear</command-name>
            <command-message>clear</command-message>
            <command-args></command-args>

## Human (typed) - 15:49:04

split card #12 into implementation cards

**Tool call: Skill**

```json
{
  "skill": "agent-teams:authoring-spec",
  "args": "split card #12 into implementation cards"
}
```

**Tool result:**

```
Launching skill: agent-teams:authoring-spec
```

**Tool call: Bash**

```json
{
  "command": "gh repo view --json nameWithOwner -q .nameWithOwner 2>&1",
  "description": "Get configured repo name"
}
```

**Tool result:**

```
Windmill10/agent-teams-test
```

**Tool call: Bash**

```json
{
  "command": "gh issue view 12 --repo Windmill10/agent-teams-test --comments 2>&1",
  "description": "View card #12 with comments"
}
```

**Tool result:**

```
author:	Windmill10
association:	owner
edited:	false
status:	none
--
<!-- agent-teams:handoff -->
**Handoff**: `analyst` -> `architect`
**Reason**: Requirement intake is complete and the Card is shaped.
**Needs from you**: Shape the durable specification and decide whether this is one implementation Card or needs decomposition.
**Artifacts**: https://github.com/Windmill10/agent-teams-test/issues/12
--
```

**Tool call: Bash**

```json
{
  "command": "gh issue view 12 --repo Windmill10/agent-teams-test --json title,body,labels,state,url 2>&1",
  "description": "Get card #12 full details as JSON"
}
```

**Tool result:**

```
{"body":"## Outcome\n\nThe general public can look up cooking-oil (油品) food-safety violations across\nTaiwan on a map — see which counties/cities have recorded violations, drill\ninto a county to see the individual records, and search directly by business\nname without having to browse the map.\n\n## Context\n\n\"毒油地圖\" (Poison-Oil Map) — a public-facing, map-based view of Taiwan\nfood-safety violations specifically related to cooking oil. Modeled loosely\non the idea of prior county-level Taiwan map dashboard work (issue #7,\nretired), but this is explicitly a **standalone feature** — no assumed reuse\nof or dependency on that retired spec.\n\nSource data is Taiwan government open data (e.g. TFDA-published violation\nrecords). A one-time/periodic batch import is sufficient for v1 — no\nreal-time sync requirement.\n\n## Acceptance Criteria\n\n1. A Taiwan map renders all counties/cities, and each one visually indicates\n   whether it has one or more recorded cooking-oil violations (e.g. via\n   color/shading), including counties with zero violations shown distinctly\n   (not blank/broken/uncolored).\n2. Selecting a county displays the list of oil-safety violation records for\n   that county. Each record shows at minimum: business/vendor name, violation\n   date, a description of the violation, the penalty/fine amount, the legal\n   basis (適用法規), and the oil product detail involved (brand/type/batch).\n3. A keyword search lets a user find violation records by business name (or\n   oil brand) directly, without needing to browse via the map first.\n4. Violation data is populated from a Taiwan government food-safety open\n   dataset via a batch/periodic import process. A manually triggered one-time\n   import satisfies this acceptance criterion for v1 — no automated live sync\n   is required.\n\n## Non-goals\n\n- Address-level pins / per-business geocoding. V1 is county/city-level\n  aggregation only.\n- Near-real-time or automated live sync with the government data source.\n- Any regulator/internal analytics, trend, or enforcement-tracking view. V1\n  is public browse/search only.\n- Reuse of, or dependency on, the retired \"Taiwan popular-shops map\n  dashboard\" (issue #7) — confirmed standalone by the requester.\n\n## Dependencies\n\nNone on the current board.\n\n## Expected split (for architect decomposition, not decided here)\n\nThis requirement bundles at least two largely independent capabilities:\n- Data ingestion: sourcing, parsing, and normalizing government violation\n  records into county-aggregated storage.\n- Public map/search UI: the Taiwan county map, county drill-down list, and\n  business/keyword search.\n\nThis is a brand-new feature surface (new data domain, new UI). The first\nchild Card after decomposition should be a walking skeleton — the smallest\nend-to-end slice through every layer (import a small sample of real\nviolation data → render the Taiwan map with county coloring → click a county\n→ show a minimal record list) — be
... [truncated, 922 more chars]
```

**Tool call: Bash**

```json
{
  "command": "find /Users/lee_eason/itri/ai_agents/agent-teams-scratch -maxdepth 2 -iname \"*.py\" 2>&1; echo \"---\"; ls /Users/lee_eason/itri/ai_agents/agent-teams-scratch/scripts 2>&1",
  "description": "Locate producer_board.py script"
}
```

**Tool result:**

```
/Users/lee_eason/itri/ai_agents/agent-teams-scratch/tests/test_workflows.py
/Users/lee_eason/itri/ai_agents/agent-teams-scratch/tests/fake_gh.py
/Users/lee_eason/itri/ai_agents/agent-teams-scratch/tests/test_producer_board.py
/Users/lee_eason/itri/ai_agents/agent-teams-scratch/tests/test_partial_failures.py
/Users/lee_eason/itri/ai_agents/agent-teams-scratch/tests/test_policy.py
/Users/lee_eason/itri/ai_agents/agent-teams-scratch/scripts/producer_board.py
---
__pycache__
agent_teams
producer_board.py
```

**Tool call: Bash**

```json
{
  "command": "python \"/Users/lee_eason/itri/ai_agents/agent-teams-scratch/scripts/producer_board.py\" seat_view --role architect --repo Windmill10/agent-teams-test 2>&1 | head -100",
  "description": "Check architect seat view of board"
}
```

**Tool result:**

```
usage: producer_board.py [-h] [--config CONFIG]
                         {init,doctor,bootstrap,list,brief,triage,queue,dispatch,intake,create-card,promote,decompose,release-claim,transition,handoff} ...
producer_board.py: error: argument command: invalid choice: 'seat_view' (choose from 'init', 'doctor', 'bootstrap', 'list', 'brief', 'triage', 'queue', 'dispatch', 'intake', 'create-card', 'promote', 'decompose', 'release-claim', 'transition', 'handoff')
```

**Tool call: Bash**

```json
{
  "command": "python \"/Users/lee_eason/itri/ai_agents/agent-teams-scratch/scripts/producer_board.py\" list --role architect 2>&1 | head -100",
  "description": "List cards for architect role"
}
```

**Tool result:**

```
[
  {
    "item_id": "PVTI_lAHOB5EpG84Be5UAzg1jXhg",
    "number": 12,
    "repo": "Windmill10/agent-teams-test",
    "title": "Build 毒油地圖 (Poison-Oil Map): Taiwan cooking-oil food-safety violation map",
    "url": "https://github.com/Windmill10/agent-teams-test/issues/12",
    "status": "Backlog",
    "role": "architect"
  }
]
```

**Tool call: Bash**

```json
{
  "command": "gh pr list --repo Windmill10/agent-teams-test --state all --search \"12\" --json number,title,url,state,body 2>&1\necho \"---branches---\"\ngit ls-remote --heads origin 2>&1 | grep -i \"12\\|oil\\|poison\" \necho \"---local docs---\"\nfind /Users/lee_eason/itri/ai_agents/agent-teams-test -iname \"*poison*\" -o -iname \"*oil*\" 2>&1 | grep -v node_modules",
  "description": "Check for existing spec PR or docs for issue 12"
}
```

**Tool result:**

```
[{"body":"## Summary\n- Resolves Issue #12's four open questions as explicit decisions: curated static-JSON import (no clean government API exists for oil-safety violations specifically — see spec for research findings), manual periodic re-curation cadence, client-side substring search independent of the map, and reuse of the Leaflet+OSM technical approach from the retired issue #7 spec without reusing any of its assets.\n- Follows this repo's existing static-site, no-backend, no-build-step pattern (Snake game, and the same shape as the retired `0003-taiwan-shop-dashboard.md`).\n- Flags the shipped dataset (`data/oil-violations.json` schema) as a placeholder only — real, citable violation records against real businesses must be human-supplied/reviewed before implementation, not sourced independently by `dev`.\n\nSpec for #12 (spec, not implementation — decomposition/promotion is a separate step).\n\n## Test plan\n- [ ] Human review of the four resolved decisions (data source, import cadence, search behavior, prior-work reuse)\n- [ ] Confirm/override the two explicitly flagged risks: placeholder dataset content, and the unresolved `taiwan-counties.geojson` source\n- [ ] Confirm desktop-only viewport assumption (Issue #12 did not state a target viewport)\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)\n","number":13,"state":"MERGED","title":"Spec: Taiwan cooking-oil violation map (毒油地圖)","url":"https://github.com/Windmill10/agent-teams-test/pull/13"}]
---branches---
---local docs---
/Users/lee_eason/itri/ai_agents/agent-teams-test/.git/refs/heads/spec/issue-12-oil-violation-map
/Users/lee_eason/itri/ai_agents/agent-teams-test/.git/logs/refs/heads/spec/issue-12-oil-violation-map
/Users/lee_eason/itri/ai_agents/agent-teams-test/.git/refs/remotes/origin/spec/issue-12-oil-violation-map
/Users/lee_eason/itri/ai_agents/agent-teams-test/.git/logs/refs/remotes/origin/spec/issue-12-oil-violation-map
```

## Agent - 15:49:56

There's already a merged spec PR (#13) for issue #12. Let me read the full spec doc before decomposing.

**Tool call: Bash**

```json
{
  "command": "gh pr view 13 --repo Windmill10/agent-teams-test --json files -q '.files[].path' 2>&1",
  "description": "List files changed in spec PR #13"
}
```

**Tool result:**

```
specs/0004-taiwan-oil-violation-map.md
```

**Tool call: Bash**

```json
{
  "command": "git -C /Users/lee_eason/itri/ai_agents/agent-teams-test show origin/main:specs/0004-taiwan-oil-violation-map.md 2>&1 || git -C /Users/lee_eason/itri/ai_agents/agent-teams-test show main:specs/0004-taiwan-oil-violation-map.md 2>&1",
  "description": "Read the merged spec document content"
}
```

**Tool result:**

```
Exit code 128
fatal: path 'specs/0004-taiwan-oil-violation-map.md' does not exist in 'origin/main'
fatal: path 'specs/0004-taiwan-oil-violation-map.md' does not exist in 'main'
```

**Tool call: Bash**

```json
{
  "command": "git fetch origin main 2>&1 && git show origin/main:specs/0004-taiwan-oil-violation-map.md 2>&1 | head -20\necho \"---find local---\"\nfind . -name \"0004*\" 2>&1",
  "description": "Fetch and read spec doc"
}
```

**Tool result:**

```
From https://github.com/Windmill10/agent-teams-test
 * branch            main       -> FETCH_HEAD
   a5bdee8..eb79ac7  main       -> origin/main
# Spec: 毒油地圖 — Taiwan Cooking-Oil Food-Safety Violation Map

- Issue: [#12](https://github.com/Windmill10/agent-teams-test/issues/12)
- Status: Draft
- Owner (spec): architect
- Owner (implementation, after handoff): dev

## Summary

A single standalone page (`oil-map.html` + one CSS file + one JS module),
framework-free like the existing Snake Card, that renders a county/city-level
choropleth map of Taiwan showing recorded cooking-oil food-safety violations,
plus a keyword search over the same records. This document resolves Issue
#12's four open questions (data source, import cadence, search behavior, and
reuse of prior work) as explicit decisions so `dev` can build without
re-deriving them, and flags each as a decision the human reviewer should
confirm or override before this Card is promoted.

## Decisions Resolving Issue #12's Open Questions

---find local---
```

**Tool call: Bash**

```json
{
  "command": "git -C /Users/lee_eason/itri/ai_agents/agent-teams-test show origin/main:specs/0004-taiwan-oil-violation-map.md 2>&1 > /private/tmp/claude-501/-Users-lee-eason-itri-ai-agents-agent-teams-test/5b64bb2a-404b-40e0-aabe-f75a72327907/scratchpad/spec-0004.md\nwc -l /private/tmp/claude-501/-Users-lee-eason-itri-ai-agents-agent-teams-test/5b64bb2a-404b-40e0-aabe-f75a72327907/scratchpad/spec-0004.md",
  "description": "Save spec doc to scratchpad and get line count"
}
```

**Tool result:**

```
238 /private/tmp/claude-501/-Users-lee-eason-itri-ai-agents-agent-teams-test/5b64bb2a-404b-40e0-aabe-f75a72327907/scratchpad/spec-0004.md
```

**Tool call: Read**

```json
{
  "file_path": "/private/tmp/claude-501/-Users-lee-eason-itri-ai-agents-agent-teams-test/5b64bb2a-404b-40e0-aabe-f75a72327907/scratchpad/spec-0004.md"
}
```

**Tool result:**

```
1	# Spec: 毒油地圖 — Taiwan Cooking-Oil Food-Safety Violation Map
2	
3	- Issue: [#12](https://github.com/Windmill10/agent-teams-test/issues/12)
4	- Status: Draft
5	- Owner (spec): architect
6	- Owner (implementation, after handoff): dev
7	
8	## Summary
9	
10	A single standalone page (`oil-map.html` + one CSS file + one JS module),
11	framework-free like the existing Snake Card, that renders a county/city-level
12	choropleth map of Taiwan showing recorded cooking-oil food-safety violations,
13	plus a keyword search over the same records. This document resolves Issue
14	#12's four open questions (data source, import cadence, search behavior, and
15	reuse of prior work) as explicit decisions so `dev` can build without
16	re-deriving them, and flags each as a decision the human reviewer should
17	confirm or override before this Card is promoted.
18	
19	## Decisions Resolving Issue #12's Open Questions
20	
21	### Open Question 1 — which government dataset/API is the source of record
22	
23	**Finding (research, not assumption):** no single structured, queryable
24	Taiwan government dataset covering cooking-oil safety/adulteration violations
25	exists. TFDA's only API-backed open dataset in this space
26	([data.gov.tw #6949](https://data.gov.tw/dataset/6949)) covers illegal
27	*advertising claims*, not product-safety violations. TFDA's border-inspection
28	query tool ([fda.gov.tw/UnsafeFood](https://www.fda.gov.tw/UnsafeFood/UnsafeFood.aspx))
29	only covers imported products, with no county field or penalty amount. Actual
30	domestic violations (e.g. the 2013 大統/福懋 adulteration cases, ongoing
31	cases disclosed under 食品安全衛生管理法) are published per-incident as
32	static PDFs and per-county health-bureau announcement pages — not one
33	downloadable feed.
34	
35	**Decision:** v1 ingestion is a **curated import**, not a live API
36	integration. Data is a static, manually curated dataset shipped in the repo
37	(`data/oil-violations.json`). Each entry is transcribed from an identifiable
38	official government disclosure (a TFDA national announcement or a county
39	health-bureau announcement/PDF) and — critically — must carry a citation
40	(`source_url`, `source_agency`) back to that disclosure. This decision was
41	confirmed with the human requester after the research finding above.
42	
43	**Rationale:** matches the repo's existing no-backend, no-build-step
44	constraint (see File Layout), and matches Issue #12's own acceptance
45	criterion 4, which only requires "a batch/periodic import process" and
46	explicitly accepts "a manually triggered one-time import" for v1. Requiring a
47	citable source per record is not optional: these are factual allegations
48	against real, named businesses, and an uncited or unverifiable entry is a
49	factual-accuracy and reputational-risk exposure this project should not ship.
50	
51	**Flagged for human confirmation:** the dataset shipped with this Card is a
52	schema-only placeholder (see Open Risks) — real record content must be
5
... [truncated, 10276 more chars]
```

## Agent - 15:50:18

Now let me read the decomposition gates reference before drafting children.

**Tool call: Read**

```json
{
  "file_path": "/Users/lee_eason/itri/ai_agents/agent-teams-scratch/skills/authoring-spec/references/decomposition-gates.md"
}
```

**Tool result:**

```
1	# Decomposition gates — INVEST, vertical slicing, sizing
2	
3	<!-- Derived from board-superpowers `decomposing-into-milestones` and its
4	     references (MIT, (c) 2026 PanQiWei,
5	     github.com/PanQiWei/board-superpowers), adapted to the agent-teams flow:
6	     children land at (Backlog, human), never Ready; creation runs through
7	     `producer_board.py decompose`. See ATTRIBUTION.md. -->
8	
9	Read this file during Job 3, before writing the children JSON. The gates are
10	**refusal conditions**, not steps: a child that fails one is not created —
11	reframe, reslice, or split until it passes, or leave the work as one Card.
12	
13	Primary sources: Wake, "INVEST in Good Stories, and SMART Tasks" (2003,
14	xp123.com); Cohn, "Five Simple But Powerful Ways to Split User Stories" and
15	"Five Story-Splitting Mistakes" (mountaingoatsoftware.com); sizing informed by
16	Reinertsen (2009) and Fowler's StoryCounting.
17	
18	## The Iron Law
19	
20	> Every child Card MUST pass the INVEST 6-letter gate AND clear all four
21	> vertical-slicing anti-patterns. Failing either is a refusal — the Card does
22	> not get created. Reframe, reslice, or split until it passes; never wave it
23	> through. A card that limps through the gate creates downstream pain that
24	> costs more than reframing the story up front would have.
25	
26	## INVEST — six refusal conditions (Wake 2003)
27	
28	- **I — Independent.** Refuses when two children overlap conceptually or
29	  cannot be claimed in any order, AND no `depends-on` declares the coupling.
30	  Independence is an ideal, not absolute: declared coupling is the escape
31	  valve — *silent* coupling is what is refused.
32	- **N — Negotiable.** Refuses when the body reads as an explicit contract —
33	  paragraphs of implementation prose, a procedural recipe. A Card is "a token
34	  promising a future conversation": acceptance criteria are post-conditions
35	  on the finished world ("login persists the session token"), never steps to
36	  type. Scope is fixed; details are negotiable.
37	- **V — Valuable.** Refuses when merging the child alone improves no
38	  user-visible or developer-visible state. Layer-only slices typically fail
39	  here. "Customer" includes the architect — internal tooling counts when it
40	  improves the loop.
41	- **E — Estimable.** Refuses when the body contains "TBD", "figure out",
42	  "we'll see", "depends on what we find". A knowledge gap gets a **spike** —
43	  a small research Card whose acceptance criterion is "we have a written
44	  answer to question X". Spikes are legitimate; "TBD" Cards are not.
45	- **S — Small.** Refuses past the L ceiling (below). E and S are one gate in
46	  practice: bigness itself causes inestimability.
47	- **T — Testable.** Refuses when acceptance criteria contain feeling-words —
48	  "feels good", "works well", "is reasonable", "looks correct" — or a bare
49	  "tests pass" without naming which tests check which behavior. Each
50	  criterion is checkable by a scr
... [truncated, 6971 more chars]
```

**Tool call: Bash**

```json
{
  "command": "python \"/Users/lee_eason/itri/ai_agents/agent-teams-scratch/scripts/producer_board.py\" decompose --help 2>&1",
  "description": "Check decompose command help for expected schema"
}
```

**Tool result:**

```
usage: producer_board.py decompose [-h] --spec SPEC --children CHILDREN
                                   [--acting-role {analyst,architect,dev,qa,lead,human}]
                                   parent

positional arguments:
  parent

options:
  -h, --help            show this help message and exit
  --spec SPEC
  --children CHILDREN   JSON file: [{"title": "...", "body": "..."}, ...]
  --acting-role {analyst,architect,dev,qa,lead,human}
```

## Agent - 15:52:03

Now I'll draft the three children, gated against INVEST and vertical-slicing per the spec's own walking-skeleton guidance (Paths + Rules axes, matching the "new feature" shape catalog).

**Tool call: Write**

```json
{
  "file_path": "/private/tmp/claude-501/-Users-lee-eason-itri-ai-agents-agent-teams-test/5b64bb2a-404b-40e0-aabe-f75a72327907/scratchpad/issue-12-children.json",
  "content": "[\n  {\n    \"title\": \"Oil-map walking skeleton: choropleth map + county drill-down (minimal fields)\",\n    \"body\": \"Goal: ship the smallest end-to-end slice of the oil-violation map so the technical approach (Leaflet+OSM, county choropleth, click-to-drill-down) is proven working in the browser before any field-completeness or search polish is added.\\n\\nSpec: docs/../specs/0004-taiwan-oil-violation-map.md (PR #13, merged) — Summary, File Layout, Map Rendering, Load Sequence sections.\\n\\ndepends-on: none (first card)\\n\\nPrerequisite (blocking, supplied by the human at Card review/promotion time, not sourced independently by dev): a small initial dataset (at least 3 real, citable violation records, each with `source_url` and `source_agency` pointing to an identifiable official government disclosure) must be attached to this Card before it is promoted. This Card must NOT ship with fabricated or unverified record content — see spec Open Risks (\\\"Placeholder dataset\\\").\\n\\nAcceptance:\\n- [ ] `oil-map.html` + `oil-map.css` + `oil-map.js` render a Leaflet map centered on Taiwan (lat 23.6978, lng 120.9605, zoom 7) with OSM tiles loaded via CDN `<script>`/`<link>` tags — no bundler, no npm, no framework.\\n- [ ] `data/taiwan-counties.geojson` is sourced from one specific, identified open dataset; its source URL and license are documented in a code comment or short note next to the file (not silently chosen without record — resolves spec's \\\"taiwan-counties.geojson source unresolved\\\" risk).\\n- [ ] The map renders every county/city polygon from the geojson layer; each county's fill color reflects its violation count from `data/oil-violations.json` grouped by `county`.\\n- [ ] Counties with zero recorded violations render with a distinct, visible neutral fill (e.g. light gray) —
... [truncated, 4167 more chars]
```

**Tool result:**

```
File created successfully at: /private/tmp/claude-501/-Users-lee-eason-itri-ai-agents-agent-teams-test/5b64bb2a-404b-40e0-aabe-f75a72327907/scratchpad/issue-12-children.json (file state is current in your context — no need to Read it back)
```

**Tool call: Bash**

```json
{
  "command": "python \"/Users/lee_eason/itri/ai_agents/agent-teams-scratch/scripts/producer_board.py\" decompose 12 \\\n  --spec https://github.com/Windmill10/agent-teams-test/pull/13 \\\n  --children \"/private/tmp/claude-501/-Users-lee-eason-itri-ai-agents-agent-teams-test/5b64bb2a-404b-40e0-aabe-f75a72327907/scratchpad/issue-12-children.json\" \\\n  --acting-role architect 2>&1",
  "description": "Decompose card #12 into three implementation children"
}
```

**Tool result:**

```
{
  "ok": true,
  "partial": false,
  "parent": 12,
  "spec": "https://github.com/Windmill10/agent-teams-test/pull/13",
  "created": [
    {
      "ok": true,
      "issue": 14,
      "url": "https://github.com/Windmill10/agent-teams-test/issues/14",
      "status": "Backlog",
      "role": "human",
      "completed": [
        "issue_created",
        "project_item_added",
        "status_set",
        "role_set"
      ]
    },
    {
      "ok": true,
      "issue": 15,
      "url": "https://github.com/Windmill10/agent-teams-test/issues/15",
      "status": "Backlog",
      "role": "human",
      "completed": [
        "issue_created",
        "project_item_added",
        "status_set",
        "role_set"
      ]
    },
    {
      "ok": true,
      "issue": 16,
      "url": "https://github.com/Windmill10/agent-teams-test/issues/16",
      "status": "Backlog",
      "role": "human",
      "completed": [
        "issue_created",
        "project_item_added",
        "status_set",
        "role_set"
      ]
    }
  ],
  "failed": [],
  "summary_comment_posted": true,
  "recovery": []
}
```

## Agent - 15:53:16

All three children were created successfully at `(Backlog, human)`, each carrying the provenance pointer to spec PR #13, and a summary comment was posted on the parent.

Card #12 split into three implementation Cards, gated against INVEST and vertical-slicing per the spec's own walking-skeleton-first guidance:

1. **[#14](https://github.com/Windmill10/agent-teams-test/issues/14) — Walking skeleton**: choropleth map + county drill-down with minimal fields. Blocking prerequisite: the human must attach ≥3 real, citable violation records (with `source_url`/`source_agency`) before promotion — the spec explicitly forbids `dev` sourcing that content independently.
2. **[#15](https://github.com/Windmill10/agent-teams-test/issues/15) — Full record fields + validation**: penalty/legal-basis/oil-product fields, dropping uncited or county-mismatched records on load. `depends-on` #14.
3. **[#16](https://github.com/Windmill10/agent-teams-test/issues/16) — Keyword search**: business-name/oil-brand substring search, independent of map browsing. `depends-on` #14 only, independent of #15.

Each stands alone as a shippable, testable slice — no layer-only or "wire-it-up" cards. Next step is yours: `promote` each one individually (with #14's dataset prerequisite resolved first) to send it to `dev`.

## Human (typed) - 17:12:47

cd ~/itri/ai_agents/agent-teams-test
python3 ../agent-teams-scratch/scripts/producer_board.py promote 14 \
  --spec https://github.com/Windmill10/agent-teams-test/pull/13
