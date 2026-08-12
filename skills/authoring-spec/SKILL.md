---
name: authoring-spec
description: Turn one architect-owned Backlog Card into a specification committed directly to the current Git branch, then either hand the Card to the human readiness gate or decompose it into flat implementation Cards. Use for [role:architect], [routine:authoring-spec], "write the spec", "make this ready", "decompose this", "split into cards", architecture decisions, contracts, or implementation-facing plans. Never creates a specification branch or Pull Request.
---

<!-- The decomposition gates (INVEST, vertical slicing, SPIDR, sizing) are
     derived from board-superpowers `decomposing-into-milestones` (MIT,
     (c) 2026 PanQiWei, github.com/PanQiWei/board-superpowers), adapted to
     the agent-teams flow. See ATTRIBUTION.md. -->

# Specify work directly in Git

The architect removes implementation ambiguity, publishes the specification
directly on the repository's current branch, and shapes the implementation
Cards. There is no specification branch, Pull Request, or human merge step.

## 1. Bind and understand

Bootstrap as `architect`. Require the live pair `(Backlog, architect)`, then
read the Card, comments, related requirements, current repository structure,
and relevant architecture decisions.

Research resolvable unknowns instead of asking the human to transport context.
If a product answer genuinely cannot be inferred or researched, record the
specific question and hand the Card to `analyst`; do not invent it.

## 2. Write the direct specification

Create or update one Markdown file below `docs/`, normally:

```text
docs/specs/YYYY-MM-DD-card-N-short-name.md
```

It must state the problem, scope and non-goals, observable behavior, acceptance
criteria, dependencies, design decisions with rationale, risks, and verification
strategy. Keep it as small as possible while removing implementation ambiguity.

Do this in the current checkout. **Do not create a branch, worktree, or Pull
Request.** Then publish only that file:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" publish-spec N \
  --path docs/specs/YYYY-MM-DD-card-N-short-name.md
```

`publish-spec` verifies `(Backlog, architect)`, refuses paths outside
`docs/**/*.md`, refuses unrelated checkout changes, commits only the requested
file on the current branch, pushes that branch, and records the exact path and
commit on the Card. Do not claim success without `"ok": true`.

## 3. Shape the implementation

For a single independently shippable Card, hand it to the human readiness gate:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" handoff N \
  --from-role architect --to-role human \
  --note "Specification is published directly in Git and the Card is ready for the readiness decision." \
  --needs "Approve into Ready, or return it with the missing decision." \
  --artifacts "docs/specs/...md @ <commit>"
```

For multiple independently shippable slices, read
`references/decomposition-gates.md`, then run:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" decompose N \
  --children children.json
```

Every child must pass INVEST, be a vertical slice, fit the size ceiling, and
remain independently testable. Reslice failures with SPIDR. Children land at
`(Backlog, human)` with the recorded specification path and provenance. The
human decides readiness for each Card; the architect never promotes them.

## 4. Stop at the gate

The human does not merge specification work. Their only readiness operation is:

Move the Card's Project Status from `Backlog` to `Ready`.

The coordinator then runs `finalize-readiness`: it retrieves the exact
specification path and commit from the Card, verifies Git still contains that
version, and hands the Ready Card to `dev`. If the specification changed after
its Card record, publish it again before asking for readiness.

## Boundaries

- Do not create or merge a specification Pull Request.
- Do not create a specification branch or worktree.
- Do not modify production code.
- Do not make a Card Ready or act as `human`.
- Do not decompose vague or horizontally sliced work.
- Persist the specification and routing result before stopping; conversation
  text is not a handoff.
