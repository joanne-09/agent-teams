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

## Reusable layouts and styles

- `layout: ppt` uses `layouts/ppt.vue` for title-bar content slides.
- `layout: center` plus the `chapter` classes creates section dividers.
- `styles/index.css` provides the shared editorial palette, typography, cards,
  grids, keyboard-key styling, and muted/accent utilities.
