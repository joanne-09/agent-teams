# Handoff authority

`Role` is a single-select Card field with exactly six values: `analyst`,
`architect`, `rd`, `qa`, `em`, `human`. It is orthogonal to Status and to
backend assignees. A handoff changes Role only.

| From / To | analyst | architect | rd | qa | em | human |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| analyst | - | shape | - | - | escalate | question |
| architect | return | - | dispatch | dispatch | escalate | question |
| rd | - | escalate | - | PR ready | escalate | - |
| qa | - | escalate | reject | - | escalate | merge gate |
| em | route | route | route | route | - | route |
| human | route | route | route | route | route | - |

Every non-dash cell is legal. Every dash is a refusal before mutation. In
particular, analyst cannot skip architect to reach RD, RD cannot reach human,
and only QA can open the human merge gate.

## Handoff cap

A Card may carry at most six structured handoff comments by default. The
seventh attempt is refused and should be escalated to EM. A repository may
set `BOARD_SP_HANDOFF_CAP` or pass `--handoff-cap`; the value must be a
positive integer. Handoff count is independent of Status transitions.

## Structured comment

```markdown
<!-- board-superpowers:handoff -->
**Handoff**: `<from>` -> `<to>`
**Reason**: <why ownership changes>
**Needs from you**: <specific receiving-seat obligation>
**Artifacts**: <card, PR, branch, spec, or evidence links>
```
