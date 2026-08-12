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

### Open Question 1 — which government dataset/API is the source of record

**Finding (research, not assumption):** no single structured, queryable
Taiwan government dataset covering cooking-oil safety/adulteration violations
exists. TFDA's only API-backed open dataset in this space
([data.gov.tw #6949](https://data.gov.tw/dataset/6949)) covers illegal
*advertising claims*, not product-safety violations. TFDA's border-inspection
query tool ([fda.gov.tw/UnsafeFood](https://www.fda.gov.tw/UnsafeFood/UnsafeFood.aspx))
only covers imported products, with no county field or penalty amount. Actual
domestic violations (e.g. the 2013 大統/福懋 adulteration cases, ongoing
cases disclosed under 食品安全衛生管理法) are published per-incident as
static PDFs and per-county health-bureau announcement pages — not one
downloadable feed.

**Decision:** v1 ingestion is a **curated import**, not a live API
integration. Data is a static, manually curated dataset shipped in the repo
(`data/oil-violations.json`). Each entry is transcribed from an identifiable
official government disclosure (a TFDA national announcement or a county
health-bureau announcement/PDF) and — critically — must carry a citation
(`source_url`, `source_agency`) back to that disclosure. This decision was
confirmed with the human requester after the research finding above.

**Rationale:** matches the repo's existing no-backend, no-build-step
constraint (see File Layout), and matches Issue #12's own acceptance
criterion 4, which only requires "a batch/periodic import process" and
explicitly accepts "a manually triggered one-time import" for v1. Requiring a
citable source per record is not optional: these are factual allegations
against real, named businesses, and an uncited or unverifiable entry is a
factual-accuracy and reputational-risk exposure this project should not ship.

**Flagged for human confirmation:** the dataset shipped with this Card is a
schema-only placeholder (see Open Risks) — real record content must be
supplied or reviewed by the human before this Card is promoted to
implementation, not sourced independently by `dev`.

### Open Question 2 — import automation mechanism and cadence

**Decision:** no automated scraper or scheduled job in v1. "Periodic import"
means a human re-runs the curation process (reviewing new official
disclosures and appending verified entries to `data/oil-violations.json`)
and commits the update — the same mechanism as the initial import, repeated
manually. This satisfies Issue #12 AC 4 ("a manually triggered one-time
import satisfies this acceptance criterion for v1").

**Rationale:** no backend/database exists in this repo (static site, no
server), and the source material itself (heterogeneous PDFs and per-county
web pages) is not amenable to a queryable API even if the site had one. An
automated scraping/NLP pipeline is a materially larger, separate Card if
disclosure volume later makes manual curation unsustainable — explicitly
deferred (see Open Risks), not part of this Card.

### Open Question 3 — search matching behavior

**Decision:** case-insensitive substring match, client-side (no backend),
run against two fields per record: `business_name` and `oil_product.brand`.
Search is independent of county selection — per Issue #12 AC 3, a user must
be able to find a record "without having to browse the map first." Matching
records render in the same results panel used for county drill-down (see Map
Rendering), replacing the county-scoped view while a query is active.

**Rationale:** substring match over two named fields is the smallest
mechanism that satisfies AC 3 without introducing a search index, fuzzy
matching, or a backend — none of which were requested and none of which fit
a static, dependency-light site.

### Open Question 4 — reuse of prior map-rendering work

**Decision:** reuse the *technical approach* chosen in the retired shop-
dashboard spec ([specs history, issue #7](https://github.com/Windmill10/agent-teams-test/issues/7)) —
[Leaflet](https://leafletjs.com/) with OpenStreetMap raster tiles, loaded
from public CDNs via plain `<script>`/`<link>` tags, no npm/bundler. Reuse
**no code, no files, no data** from that spec — it was never implemented (no
`dashboard.html`, `dashboard.js`, or `data/shops.json` exist in this repo),
and Issue #12 confirmed this feature is standalone.

**Rationale:** Leaflet+OSM was already evaluated as the right fit for this
repo's static/no-build constraints; re-litigating that choice from scratch
would not change the answer. Reusing the *decision* without reusing *assets*
keeps this Card independent, per Issue #12's non-goals.

## File Layout

```
/oil-map.html
/oil-map.css
/oil-map.js
/data/oil-violations.json
/data/taiwan-counties.geojson
```

No bundler, no `package.json`. `oil-map.js` is a single
`<script type="module" defer>` loaded from `oil-map.html`. This Card shares
no files with the Snake (#4) Card or the retired shop-dashboard spec.

## Data Model (`data/oil-violations.json`)

```json
[
  {
    "id": "string, unique, kebab-case",
    "county": "string, must exactly match a county/city name property in taiwan-counties.geojson",
    "business_name": "string",
    "violation_date": "string, ISO 8601 date (YYYY-MM-DD)",
    "description": "string, plain-language summary of the violation",
    "penalty_amount": "number in NTD, or null if the disclosure does not state one",
    "legal_basis": "string, e.g. 食品安全衛生管理法第XX條, or \"未公開\" if not stated",
    "oil_product": {
      "brand": "string or null",
      "type": "string, e.g. 食用油 | 沙拉油 | 芝麻油",
      "batch": "string or null"
    },
    "source_url": "string, URL of the official government disclosure this record was transcribed from — required, not nullable",
    "source_agency": "string, e.g. 衛生福利部食品藥物管理署 | 臺北市政府衛生局 — required, not nullable"
  }
]
```

- `source_url` and `source_agency` are mandatory on every record — see Open
  Question 1. `dev` validates this at load time and drops (with a
  `console.warn`) any entry missing either field, the same way `#7`'s spec
  handled invalid coordinates.
- `county` must exactly match a feature property in `taiwan-counties.geojson`
  (see Map Rendering). Entries with an unmatched county name are dropped
  with a `console.warn`, not silently ignored and not fatal to page load.

## Map Rendering

- Base map: Leaflet, centered on Taiwan (`lat: 23.6978, lng: 120.9605`), zoom
  level 7, default OSM tile layer (same parameters as the retired #7 spec).
- A `taiwan-counties.geojson` layer renders Taiwan's counties/cities as
  polygons. Each county's fill is a sequential color scale keyed to its
  violation count (`data/oil-violations.json` entries grouped by `county`):
  zero violations renders as a distinct, visible neutral fill (e.g. light
  gray, not white/transparent) — satisfying Issue #12 AC 1's requirement
  that zero-violation counties be "shown distinctly, not blank/broken."
- Clicking a county polygon populates a results panel (beside or below the
  map) listing every violation record for that county: `business_name`,
  `violation_date`, `description`, `penalty_amount` (or "未公開"),
  `legal_basis`, and `oil_product` (brand/type/batch) — satisfying AC 2.
- The same results panel is used for search results (see Open Question 3);
  an active search query overrides the county-scoped view until cleared.
- No marker clustering or heatmap view — county-level choropleth is the only
  map visualization in this Card (per Issue #12 non-goals: no address-level
  pins).

## Load Sequence

1. `oil-map.js` fetches `data/oil-violations.json` and
   `data/taiwan-counties.geojson` via `fetch()` on `DOMContentLoaded`.
2. On success: validate each violation entry (see Data Model), drop invalid
   entries, group remaining entries by `county`, render the choropleth layer,
   then wire up county-click and search-input handlers.
3. On fetch failure (e.g. opened via `file://` without a local server):
   render a visible on-page error message ("Could not load violation data.")
   in place of the map controls area — do not fail silently, consistent with
   the retired #7 spec's handling.

## Explicitly Out of Scope (non-goals)

Carried forward from Issue #12, plus implementation-level additions:

- Address-level pins or per-business geocoding (county/city aggregation
  only).
- Any automated or scheduled sync with a government data source — v1 import
  is a manual, human-curated commit (see Open Question 2).
- Regulator/internal analytics, trend, or enforcement-tracking views.
- Any code, file, or data reuse from the retired issue #7 shop dashboard.
- Authentication, accounts, or user-submitted/editable data — the dataset is
  read-only for site visitors.
- An automated scraping/NLP pipeline over county disclosure pages/PDFs — the
  curation step is a human editorial process for this Card.
- Mobile/touch-specific layout — desktop-viewport usability only, matching
  the retired #7 spec's assumption. **Flagged for human confirmation**: Issue
  #12 does not state a target viewport; if mobile support is actually
  required, this Card needs to be resized before promotion.

## Acceptance Criteria Traceability

Issue #12's acceptance criteria map to this spec as follows:

- AC 1 ("map renders all counties, zero-violation counties shown
  distinctly") → Map Rendering (choropleth layer, explicit neutral fill for
  zero-count counties).
- AC 2 ("selecting a county shows business name, date, description, penalty,
  legal basis, oil product detail") → Data Model (all six fields present per
  record) + Map Rendering (results panel on county click).
- AC 3 ("keyword search by business name/oil brand, independent of the map")
  → Open Question 3 (substring match over `business_name` and
  `oil_product.brand`, results panel usable without a prior county click).
- AC 4 ("data populated via batch/periodic import; manual one-time import
  acceptable for v1") → Open Question 1 and 2 (curated static JSON, manual
  re-curation cadence).

## Open Risks / Follow-ups

- **Placeholder dataset**: `data/oil-violations.json` ships with this spec
  as a schema example only — it must not be treated as real content. Real,
  citable violation records (each with a verifiable `source_url`) must be
  supplied or reviewed by the human before implementation proceeds. `dev`
  should treat dataset population as a Card-review question, not something
  to source independently — this is materially higher-stakes than the
  retired #7 spec's placeholder shop list, since these are factual
  allegations against real named businesses.
- **`taiwan-counties.geojson` source unresolved**: this spec assumes a
  license-clear, accurate Taiwan county/city boundary GeoJSON is available,
  but no specific source was verified during spec authoring. `dev` (or a
  follow-up spec review) must pin an exact source and license before
  implementation — do not select one silently mid-implementation.
- **CDN dependency** (Leaflet + OSM tiles): the map will not render without
  network access or if those CDNs are blocked. No offline fallback is in
  scope.
- **Manual curation does not scale indefinitely**: if disclosure volume
  grows, an automated scraping/NLP pipeline becomes its own Card — explicitly
  not this one (see non-goals).
- **Partial source data**: some official disclosures may omit penalty amount
  or precise legal basis. The data model allows `penalty_amount: null` and a
  `"未公開"` sentinel for `legal_basis` rather than forcing fabricated
  values — `dev` must never invent a number or citation to fill a gap.
