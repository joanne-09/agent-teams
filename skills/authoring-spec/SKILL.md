---
name: authoring-spec
description: Turn one architect-owned Backlog Card into a durable specification through the configured direct or manual-PR route, then either wait for the specification merge or shape implementation Cards. Use for [role:architect], [routine:authoring-spec], "write the spec", "make this ready", "decompose this", "split into cards", architecture decisions, contracts, or implementation-facing plans.
---

<!-- The decomposition gates (INVEST, vertical slicing, SPIDR, sizing) are
     derived from board-superpowers `decomposing-into-milestones` (MIT,
     (c) 2026 PanQiWei, github.com/PanQiWei/board-superpowers), adapted to
     the agent-teams flow. See ATTRIBUTION.md. -->

# Specify work through the configured route

The architect removes implementation ambiguity, publishes the specification
through `publish-spec`, and shapes the implementation Cards. With the default
`spec_merge_mode: direct`, publication commits directly to the current branch
and the human only makes the later Card readiness decision. With
`spec_merge_mode: manual`, publication opens a specification Pull Request and
the human merges it before shaping resumes.

## 1. Bind and understand

Bootstrap as `architect`. Require the live pair `(Backlog, architect)`, then
read the Card, comments, related requirements, current repository structure,
and relevant architecture decisions.

Research resolvable unknowns instead of asking the human to transport context.
If a product answer genuinely cannot be inferred or researched, record the
specific question and hand the Card to `analyst`; do not invent it.

## 2. Write the specification

Create or update one Markdown file below `docs/`, normally:

```text
docs/specs/YYYY-MM-DD-card-N-short-name.md
```

It must state the problem, scope and non-goals, observable behavior, acceptance
criteria, dependencies, design decisions with rationale, risks, and verification
strategy. Keep it as small as possible while removing implementation ambiguity.

Do this in the current checkout, then publish only that file:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" publish-spec N \
  --path docs/specs/YYYY-MM-DD-card-N-short-name.md
```

`publish-spec` verifies `(Backlog, architect)`, refuses paths outside
`docs/**/*.md`, refuses unrelated checkout changes, publishes only the
requested file through the configured merge mode, and records its exact path
and commit on the Card. It owns branch and Pull Request creation when manual
mode requires them; do not create either yourself. Do not claim success without
`"ok": true`.

Inspect the returned specification:

- `mode: direct`: continue to shape the implementation.
- `mode: manual`: stop. Do not hand off or decompose yet. The coordinator
  exposes a `spec_merge` human gate for the exact Pull Request. After the user
  merges it, the coordinator runs `finalize-spec-merge`, records the durable
  base-branch commit, and starts a fresh architect stage to continue shaping.

## 3. Shape the implementation

Only enter this section after direct publication succeeds or a manual
specification merge has been finalized.

For a single independently shippable Card, hand it to the human readiness gate:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/producer_board.py" handoff N \
  --from-role architect --to-role human \
  --note "Specification is durable on the base branch and the Card is ready for the readiness decision." \
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

In direct mode, the human does not merge specification work. In manual mode,
the earlier `spec_merge` gate requires the user to merge the generated
specification Pull Request before this readiness gate can exist.

At the readiness gate, the human's only operation is:

Move the Card's Project Status from `Backlog` to `Ready`.

The coordinator then runs `finalize-readiness`: it retrieves the exact
specification path and commit from the Card, verifies Git still contains that
version, and hands the Ready Card to `dev`. If the specification changed after
its Card record, publish it again before asking for readiness.

## Boundaries

- Do not manually create or merge a specification branch or Pull Request;
  `publish-spec` and the user own those operations respectively.
- Do not modify production code.
- Do not make a Card Ready or act as `human`.
- Do not hand off or decompose while a manual specification PR is pending.
- Do not decompose vague or horizontally sliced work.
- Persist the specification and routing result before stopping; conversation
  text is not a handoff.
