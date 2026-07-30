---
name: authoring-spec
description: |
  Use when an architect-seat session owns a Card whose deliverable is a
  durable specification, architecture decision, contract, or implementation-
  facing plan and must produce a docs-only PR. Trigger on `[role:architect]`
  with a spec Card, "author the spec", or "write the architecture". Do not
  use to implement production code or to clarify a requirement too thin to
  specify.
when_to_use: |
  Use after analyst intake hands a Backlog Card to architect, and before RD
  implementation Cards are made Ready.
user-invocable: true
---

# authoring-spec

Deliver one architect-owned Card as one reviewable docs PR. The routine is
Consumer-shaped for isolation, but the seat remains `architect` and the output
is specification, never production code.

Required skills:

- `board-superpowers:board-canon` for Card, Role, Status, claim, and handoff rules.
- `board-superpowers:operating-kanban` for reads, claim, transitions, PR link, and handoff.
- `board-superpowers:composing-siblings` before every design-discipline invocation.
- `board-superpowers:classifying-actions` and `board-superpowers:auditing-actions` at mutations.

## Hard boundary

Allowed deliverables include Markdown specs, ADRs, contract tables, diagrams
expressed in repository-native text, and implementation-facing plans. Tests
that validate documentation contracts may be changed only when the Card says
they are part of the spec surface.

Refuse application source, runtime scripts, migrations, UI components, and
production tests. Hand implementation to RD. If a docs decision requires a
small code proof, describe the proof as an acceptance criterion; do not write it.

## Enter the Card

1. Bind seat `architect` and read the full Card plus latest handoff.
2. Require Role `architect`. A different Role is a refusal unless a legal
   handoff first establishes ownership.
3. Require a resolvable Goal, evidence-backed Context, and acceptance criteria.
   If the requirement is underspecified, hand back to `analyst` with the exact
   missing decisions. Do not guess product intent.
4. Confirm the Card is claimable under the state machine.
5. Classify and invoke `claim_card`. Work only in the resulting worktree.

The root repository remains on its canonical branch. One Card produces one
claim branch and one docs PR.

## Route the artifact

Read the relevant nested repository contract before planning or editing. Then
choose exactly one durable destination:

- `docs/architecture/`: permanent English source of truth. Use for invariants,
  protocols, domain vocabulary, schemas, accepted design, and ADRs.
- `docs/plans/<feature>/`: temporary Producer scaffolding. It may be Chinese
  and span several Cards, is gitignored, and must not become a shadow spec.
- `docs/board-superpowers/plans/`: single-Card Consumer plan brief only.

A durable decision discovered in a plan moves into architecture docs in the
same PR that relies on it. CI and hooks never read temporary plans.

Read `references/artifact-routing.md` when placement is ambiguous.

## Compose design discipline

Consult `board-superpowers:composing-siblings`, then invoke only the discipline
needed by the Card:

1. `superpowers:brainstorming` when alternatives or intent remain open.
2. `gstack:/plan-ceo-review` when value, scope, or product shape is uncertain.
3. `superpowers:writing-plans` to make the accepted design executable.
4. `gstack:/plan-eng-review` for architecture, failure modes, and sequencing.

Sibling output is evidence, not authority. Reconcile contradictions against
repository contracts and record the chosen trade-off. Never depend on nested
agent depth or transient messages for correctness.

## Author the change

1. Read every existing document the Card will amend.
2. Trace each term and contract to its authoritative home.
3. Write the smallest coherent specification that closes the Card's criteria.
4. Update all coupled indices, cross-references, examples, and maintainer docs
   required by the repository change-impact matrix.
5. Keep normative words testable: name preconditions, postconditions, failure
   behavior, idempotency, and ownership.
6. Record rejected alternatives when they prevent a future reader from
   reopening the same ambiguity.
7. Keep temporary discussion out of durable spec prose.

Do not mark implementation complete. The spec defines what RD must prove.

## Verify

Run repository-native doc, link, schema, metadata, and formatting checks. For
rendered artifacts, inspect the render. Re-read the acceptance criteria and
show evidence for each. Search for stale terminology and outdated counts.

A passing test is not enough if a coupled contract remains stale. A clean docs
diff is not enough if it silently permits contradictory implementation.

## Submit the docs PR

Use the existing three-section PR contract. The PR body must identify:

- the user-visible or maintainer-visible outcome;
- the documents and contracts changed;
- exact verification commands and any unavailable live check;
- the Card close link.

Link the PR to the Card and transition to review only after verification. The
architect agent never self-merges.

## Complete the ownership handoff

After the docs PR merges and the design is implementation-ready:

1. Decompose into vertically sliced Cards when more than one independent
   delivery is required.
2. Create each implementation Card as Backlog with Role `rd`.
3. Promote to Ready only after the specification pointer and INVEST gate pass.
4. Invoke `handoff_card` from `architect` to `rd` with concrete artifacts and
   the receiving obligation.

If review reveals a missing requirement, hand to `analyst`. If it reveals an
architecture decision, keep Role `architect` and revise the same claim branch.
Status and Role mutations remain separate actions. Architect claim/worktree actions are Consumer-shaped; their audit writes set `actor_role: consumer` and `actor_seat: architect`. Producer-side decomposition and handoff writes use `actor_role: producer` with the same seat.

## Source-of-truth selection

Choose the authority before writing. Common destinations are:

| Decision type | Authoritative destination | Coupled updates |
|---|---|---|
| durable product premise or invariant | architecture overview or invariant doc | terminology, flows, affected ADRs |
| irreversible architectural choice | new ADR plus amended live contract | ADR index and superseded status header |
| runtime interface or schema | contract document | implementation reference and tests |
| domain term or ownership rule | ubiquitous language and aggregate docs | context map and protocol |
| implementation sequence only | temporary feature plan | none unless a durable decision emerges |
| one-Card execution brief | Consumer plan directory | delete after delivery |

A Card may require more than one authoritative file, but each fact has one
owner. Other files link to that owner and explain local implications; they do
not restate a second competing rule.

If the repository has a change-impact matrix, walk every matching row before
editing. Treat the matrix as a minimum, then search for textual consumers that
the matrix may not enumerate.

## ADR procedure

Create an ADR only for a choice with durable alternatives and meaningful
consequences. An ADR must state context, decision, consequences, rejected
alternatives, and coupled documents. Do not use an ADR as a changelog entry.

Accepted ADR bodies are immutable. To change an accepted decision:

1. author a successor ADR;
2. update the old ADR's status header only;
3. update the ADR index;
4. amend the live specification to cite the successor;
5. update implementations or acceptance criteria made stale by the decision.

A clarification that does not change the decision belongs in the live contract,
not a cosmetic successor ADR.

## Contract authoring checks

For each normative rule, answer all applicable questions:

- What actor owns the operation?
- What durable input is required?
- What precondition makes the operation legal?
- What changes on success?
- What remains unchanged?
- What failure kinds are distinguishable?
- Is retry idempotent?
- What is the audit boundary?
- Which platform or projection realizes it?
- Which test proves conformance?

Avoid "should handle" and "supports" without observable behavior. Prefer a
named input, result, refusal, and recovery path.

For a schema, pin field names, types, optionality, enum values, defaults,
precedence, unknown-field behavior, and migration. For a protocol action, pin
actor authority, required inputs, preconditions, postconditions, failures, and
projection responsibilities.

## Cross-directory procedure

When a change spans governed directories:

1. read every matching nested contract before planning that portion;
2. identify the upstream source of truth;
3. update the source before dependent artifacts when the repository requires
   that order;
4. edit coupled guides in the same PR;
5. run each directory's local verification gate;
6. search for stale counts, vocabulary, versions, and examples.

Do not assume a one-line downstream edit is exempt from its directory contract.
If an entry skill or authoring gate is mandatory, invoke it even for a small
frontmatter or table change.

## Claim and worktree transaction

Claim is complete only when the authoritative remote marker and isolated
worktree both exist. If either half fails, follow the claim primitive's rollback
contract. Never continue editing at the repository root after a partial claim.

Before the first edit, record:

- root repository branch and cleanliness;
- claim branch and worktree path;
- Card key, Status, and Role;
- starting specification revision;
- any user changes already present.

Preserve unrelated user modifications. If a required edit overlaps them and the
intent cannot be inferred safely, stop and ask rather than overwriting.

## Design-review reconciliation

Sibling design routines can disagree. Reconcile them in this order:

1. explicit user requirement;
2. repository contracts and accepted ADRs;
3. Card goal and acceptance criteria;
4. evidence from the current codebase;
5. sibling recommendations;
6. author preference.

Record a rejected recommendation only when the reason is durable. Temporary
review chatter stays in the PR discussion or feature plan.

Do not paste sibling output verbatim into the spec. Restate the accepted rule in
the repository's vocabulary and link the evidence that supports it.

## Implementation handoff payload

Every architect-to-RD handoff names:

- the implementation Card key;
- the authoritative specification or ADR paths;
- the exact acceptance criteria RD must prove;
- dependencies and their required states;
- compatibility or migration constraints;
- known risks and intentionally deferred scope;
- the next routine: `board-superpowers:consuming-card`.

Use the structured handoff marker. Role changes to `rd` do not replace Status
transition to Ready, and Ready does not imply Role. Perform and audit the two
mutations independently.

If the specification PR is not merged, do not make dependent RD Cards Ready
unless the Card explicitly points to a stable review revision and the project
policy permits it.

## Review and rework

A review request that changes wording without changing meaning stays on the same
claim branch. A review finding that reveals missing requirement intent hands to
analyst. A finding that reveals implementation work creates or amends an RD
Card; the architect does not absorb the code change into a docs PR.

When a contract change invalidates already-created implementation Cards, return
them to Backlog before editing their bodies. Re-run the spec-pointer and INVEST
gates before restoring Ready.

## Failure-mode table

| Failure | Result | Recovery |
|---|---|---|
| Card Role is not architect | refuse ownership | legal handoff to architect |
| requirement intent missing | hand back | analyst supplies named decision |
| spec authority ambiguous | stop placement | inspect repository contracts and indices |
| root branch not canonical | stop claim | restore root discipline without losing work |
| claim collision | no worktree edits | retry after remote state changes |
| accepted ADR contradicted | refuse in-place rewrite | successor ADR procedure |
| generated artifact cannot render | verification failure | fix source and re-render |
| coupled contract stale | verification failure | update it in the same PR |
| live external check unavailable | disclose gap | provide static evidence and exact follow-up |
| merge requested from same agent | refuse | human or authorized reviewer merges |

## Rationalization guards

Reject these shortcuts:

- "The implementation makes the behavior obvious" ? durable behavior still
  needs an authoritative contract when the Card requires one.
- "This is only documentation" ? documentation contracts can have runtime
  blast radius and require the same review discipline.
- "The ADR is old" ? age does not permit rewriting an accepted decision.
- "The code proof is tiny" ? production changes belong to RD.
- "Ready is close enough to ownership" ? Status and Role are orthogonal.
- "The plan already says it" ? temporary plans are not authoritative specs.
- "Only one file cites this" ? run the change-impact matrix and repository
  search before concluding that.
- "Tests pass" ? stale contracts and unsupported claims still fail delivery.
- "The architect can merge docs" ? self-merge remains prohibited.

## Terminal verification checklist

Before opening or updating the docs PR, confirm:

- only authorized docs and doc-contract test surfaces changed;
- every nested directory contract was read;
- durable decisions live in authoritative paths;
- temporary plans contain no unique normative rule;
- accepted ADR bodies were not rewritten;
- every changed term is consistent across vocabulary and consumers;
- every changed count and version is reconciled;
- every schema or protocol rule has a failure path;
- every acceptance criterion has evidence;
- repository-native checks pass or the unavailable check is disclosed;
- the PR body follows the repository contract;
- the Card and PR are bidirectionally linked;
- the architect-to-RD handoff is structured and within the cap;
- the agent did not merge its own PR.

## Refusals

Refuse and explain when asked to implement code, merge the PR, bypass the
architectural source of truth, set RD Ready without a specification pointer,
or hand directly from analyst to RD.

Read `references/spec-delivery.md` for the terminal checklist.
