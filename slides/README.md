# AI Agents Slidev deck

This Slidev project reuses the editorial theme and layout primitives from
`/Users/lee_eason/CS/SV_lecture` without copying that lecture's content or assets.

## Commands

```bash
npm install
npm run dev
npm run build
npm run export
npm run export:pptx
```

The editable presentation source is `slides.md`.

## Multiple decks

One deck per weekly presentation, as a sibling `.md` file named by date
(e.g. `2026-08-06-weekly.md`). All decks in this directory automatically share
`layouts/`, `styles/`, `global-bottom.vue`, `images/`, and one `node_modules`.
`slides.md` remains the main project-introduction deck.

Run a specific deck by passing its filename:

```bash
npm run dev -- 2026-08-06-weekly.md
npm run export -- 2026-08-06-weekly.md
```

To reuse slides from another deck without copying, use Slidev's `src` import
inside a slide's frontmatter, e.g. `src: ./pages/lifecycle.md` — shared
fragments belong in `pages/`.

## Reusable layouts and styles

- `layout: ppt` uses `layouts/ppt.vue` for title-bar content slides.
- `layout: center` plus the `chapter` classes creates section dividers.
- `styles/index.css` provides the shared editorial palette, typography, cards,
  grids, keyboard-key styling, and muted/accent utilities.
