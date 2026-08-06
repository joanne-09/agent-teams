# Attribution

agent-teams ships every skill it uses — nothing is invoked from another plugin
at runtime. Where a skill's text is substantially derived from an open-source
project, that derivation is recorded here and marked with a comment at the top
of the derived file. All three sources are MIT-licensed; the notices below
satisfy their license conditions.

| Source | License | Derived into |
|---|---|---|
| [board-superpowers](https://github.com/PanQiWei/board-superpowers) — MIT, (c) 2026 PanQiWei | MIT | `skills/intaking-requirement/` (shape judgment, spec awareness, decline policy), `skills/briefing-board/` (report template, recommendation ladder, stale-claim check), `skills/triaging-board/` (stale-claim sweep, blocker classes, evidence rules), `skills/using-agent-teams/` (state table, non-signals, router anti-pattern), `skills/inspecting-queue/` (observation guards), `skills/authoring-spec/` (decomposition gates: INVEST, vertical slicing, SPIDR, sizing); each including any `references/` files. Details: `docs/skill_migration.md` + `docs/skill_migration_audit.md` |
| [superpowers](https://github.com/obra/superpowers) — MIT, (c) 2025 Jesse Vincent | MIT | (planned: dev/qa Consumer skills) |
| [gstack](https://github.com/garrytan/gstack) — MIT, (c) 2026 Garry Tan | MIT | (planned: qa verification skill) |

Derived text is adapted, not vendored: board mutations are rewired to
`scripts/producer_board.py`, sibling-plugin routing is removed, and procedures
are adjusted to agent-teams' authority model (human-only readiness, policy
refusals in code). A grep for `superpowers:` or `gstack:/` across `skills/`
must return nothing — that absence is the proof that these are derivations,
not runtime dependencies.

MIT license text of the sources is available in each linked repository.
