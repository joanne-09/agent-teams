<!-- Derived near-verbatim from board-superpowers `intaking-requirement`
     references/scope-shape-judgment.md (MIT, (c) 2026 PanQiWei,
     github.com/PanQiWei/board-superpowers). Outcomes are adapted to the
     agent-teams flow: every shape produces at most ONE intake Card, and
     decomposition happens only after a merged specification. -->

# Shape judgment — intaking-requirement reference

Read this at workflow step 3 when the one-line shape table in SKILL.md is not
enough to make the call. Tables are applied in order: Table 1 decides shape,
Table 2 picks the cross-Card relationship mechanism when several Cards will
eventually exist, Table 3 decides whether decomposition should follow at all.

## Primary-source vocabulary

The hierarchy is anchored to four canonical primary sources, borrowed for
structural shape only. Cadence assumptions (sprints, iterations, fixed release
cycles) are NOT inherited — agent orchestration collapses time grain compared
to human team baselines.

| Source | What it gives this file |
|--------|------------------------|
| Cohn, *Agile Estimating and Planning* (2005) — § "Planning Onion" | Six concentric horizons (strategy / portfolio / product / release / iteration / day). |
| Patton, *User Story Mapping* (2014) — § "The Big Picture" | Backbone activities → tasks → stories hierarchy. |
| Cockburn, *Crystal Clear* (2004) + c2 wiki — § "Walking Skeleton" | Lower bound for vertical slicing on a brand-new feature surface. |
| Denne & Cleland-Huang, *Software by Numbers* (2003) — § "Minimum Marketable Features" | Criterion for a correct milestone: coherent Cards that deliver measurable value when shipped together. |

## Table 1 — Shape level for a fresh requirement

Rows are evaluated top-down; the first row whose triggers fire wins.

| Shape | Horizon | Triggers — fire any one | Outcome in agent-teams |
|-------|---------|------------------------|------------------------|
| **Cross-release roadmap** | portfolio | (a) Requirement crosses two or more release boundaries; (b) names a release-gate or cross-version umbrella; (c) bundles features that will not all ship in one cycle. | Stop. Surface: "This is roadmap-level — a positioning decision belongs before any Card." Do NOT create a Card yet. |
| **Milestone-grouped** | release | (a) Requirement names a coherent shipped-together unit; (b) the eventual Cards together deliver Denne-MMF-shaped value (shipping any subset alone delivers strictly less); (c) the work spans two or more distinct areas of the system. | Create ONE umbrella intake Card carrying the milestone intent and the expected member slices. The architect decomposes after the specification merges. |
| **Multi-card** | release sub-batch | (a) Requirement adds 2–N independent capabilities; (b) INVEST Independence holds across the candidate slices; (c) expected internal chunk count > 5 (empirical signal that single-Card scope will reactively chunk). | Create ONE intake Card stating the expected split for the architect. |
| **Single card** | iteration | (a) Single user-visible or developer-visible capability; (b) estimable as XS/S/M/L; (c) no cross-Card design A/B requiring shared rationale; (d) belongs in one area of the system. | Direct Card creation via the SKILL.md workflow. |

### The ">5 chunks" trigger rationale

This trigger is empirical. Cards that proceeded as "single card" and then
reactively chunked into 6–7 Pull Requests each paid a separate review tax and
kept work-in-progress opaque. When intake estimates more than 5 internal
chunks, upfront decomposition (after the spec) is cheaper.

### Walking-skeleton hint for brand-new surfaces

When the shape is milestone-grouped or multi-card AND the requirement targets
a brand-new feature surface (no prior Card, specification, or skill has
authored functionality at this surface), add an explicit note for the
architect: "the first child should be a walking skeleton — the smallest
end-to-end implementation that exercises every architectural layer."

## Table 2 — Cross-card relationship mechanism

Relevant once decomposition has happened; intake records the intent so the
architect picks the right mechanism.

| Mechanism | Use when | Anti-pattern |
|-----------|----------|--------------|
| **Umbrella Card + `depends-on (soft):`** | Cards form a coherent Denne-MMF group. The decomposition parent is the umbrella: it declares the milestone's intent in its body, and member Cards bind to it via `depends-on (soft): #<parent>`. | Using the GitHub Milestone field instead — it carries no body content and is invisible to the board protocol. |
| **`depends-on:` chain (hard)** | One Card cannot start until another finishes. Strict ordering. | Chains longer than 3 — that is a missed decomposition. |
| **`depends-on (soft):`** | One Card prefers another to land first but can ship in either order. | Treating soft-depends as schedule glue. |
| **Label** | Category or type tagging only (`type:feature`, `type:bug`, `size:M`). | Using labels to mean "v1 work" — that is the umbrella Card's job. |

## Table 3 — Whether decomposition should follow

The architect owns the split; intake records which row it expects to fire.

| Trigger | Expectation to record |
|---------|----------------------|
| Multi-capability requirement (Table 1 rows 2 or 3) | Decomposition after the spec merges. Attach the walking-skeleton hint if the surface is new. |
| Looks single-Card-sized but scope feels uncertain | The architect may sanity-check the slicing before promoting; say so in the body. |
| No clear capabilities yet (rambling design notes) | Not ready to file. Keep shaping in the intake conversation until at least one capability is stateable. |
| Single Card with clear acceptance criteria | No decomposition. Direct creation. |
| Pure refactor with no new capability | No INVEST value test applies; still one Card through the normal architect and readiness path. |
