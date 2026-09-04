# Naming the smell

<!-- Vocabulary from Martin Fowler & Kent Beck, "Refactoring" ch. 3 (the "Bad
     Smells in Code" catalogue), plus the resource/performance categories in
     alibaba/open-code-review's default ruleset (Apache-2.0). Introduced
     2026-09-04 after the team lead's code-smell aside in the 2026-08-28
     review. Which entries are catalogue and which are ours: ATTRIBUTION.md.

     The entries below are not prose. `model.CODE_SMELLS` holds the same list,
     `policy._findings_problems` refuses a `smell` outside it, and
     tests/test_findings.py compares this file against that tuple in both
     directions. Adding an entry here without adding it there fails the suite,
     which is the point: a vocabulary documented in one place and enforced
     from another is exactly the shape of the merge-mode rename that sat
     half-applied for a week. -->

A `structure`-bundle finding that says "this feels wrong" cannot be challenged,
cannot be deduplicated against another reviewer's finding, and cannot be
compared to the same problem on the next Card. A finding that says
**Shotgun Surgery** can do all three.

So: **where a finding matches a named smell, name it.** Not every finding has
one — a plain logic bug does not — and inventing a label for something that has
none is worse than leaving it unlabelled.

## Why this vocabulary and not a fresh one

A code smell is not a bug. It is a *surface indication* that usually
corresponds to a deeper problem — the phrase is Fowler's, and the point of it
is that the code runs today. That is exactly the class of finding this seat is
otherwise worst at reporting: a reviewer with no vocabulary for "correct but
rotting" either says nothing or says something unfalsifiable.

The catalogue is thirty years old, widely taught, and stable, which is what
makes it usable as a shared closed set rather than as one reviewer's taste.

## The catalogue, by the dimension that finds it

The grouping says which dimension is most likely to *notice* a smell, not the
only one permitted to report it. A `design` pass that sees Duplicated Code
files Duplicated Code; policy checks that the name is in this catalogue and
deliberately does not check that it matches the finding's dimension.

Four of the nine dimensions have no section here, and that is not an omission.
`correctness`, `edge-cases`, `security` and `compatibility` find defects — the
code is wrong now. Smells are the opposite class: the code is right now.

### `design` — this unit is the wrong size or shape

| Smell | What you are seeing |
|---|---|
| **Mysterious Name** | A name that does not say what the thing is. The cheapest smell to fix and the most expensive to leave: every later reader pays. This repository has already paid once: a merge setting whose name never said *which* Pull Request it governed, renamed for that reason — and the rename is what got lost |
| **Long Function** | One function doing several things, usually announced by a comment before each section |
| **Long Parameter List** | Callers must know more than they should to make one call |
| **Large Class** | Too many fields, too many responsibilities, no single reason to change |
| **Primitive Obsession** | Strings and ints standing in for a concept the domain has a name for. In this repository the counter-example is `Role` and `Status`: both were strings once |
| **Data Clumps** | The same three parameters travelling together everywhere, wanting to be one object |
| **Temporary Field** | A field set only in some circumstances, so readers must know which. An optional field on a frozen record that half the code assumes is present |
| **Lazy Element** | A class, function, or module that no longer earns its own name — a one-line wrapper, a module holding one constant |
| **Speculative Generality** | Abstraction for a case nobody has. In this repository: hooks, adapters, and "backends" nobody asked for |

### `architecture` — this belongs somewhere else

| Smell | What you are seeing |
|---|---|
| **Feature Envy** | A function more interested in another module's data than its own |
| **Inappropriate Intimacy** | Two modules reaching into each other's internals. The lead's second example: state that should be private breaking out until it becomes a security hole |
| **Message Chains** | `a.b().c().d()` — the caller is coupled to the whole path, and any link may change. The pair to Middle Man: removing one often creates the other, which is why both are here |
| **Middle Man** | A class that only delegates |
| **Divergent Change** | One module changed for several unrelated reasons |
| **Global Data** | State reachable and writable from anywhere, so nothing can say who changed it. Module-level mutable containers are the usual form |
| **Mutable Data** | A value changed in place where a new value would do. This codebase's records are frozen dataclasses on purpose; a mutable one is a finding, not a style preference |

### `cross-file` — the change had to be smeared

| Smell | What you are seeing |
|---|---|
| **Shotgun Surgery** | One conceptual change requiring small edits in many files. *This is the merge-mode rename's own smell*: one setting, five consumers, three of them missed |
| **Duplicated Code** | Same logic in two places, so a fix lands in one |
| **Repeated Switches** | The same conditional over the same set of cases, in several places. Adding a case means finding them all — Shotgun Surgery with a schedule |
| **Parallel Inheritance Hierarchies** | Adding a type here forces a type there |

### `resource-safety` — it works, until volume

| Smell | What you are seeing |
|---|---|
| **Unreleased Resource** | Acquire with no release on the failing path. The lead's first example: connections opened and never released, fine in test, buffer exhausted under load |
| **N+1** | A query inside a loop over the results of a query |
| **Unbounded Growth** | A cache, queue, buffer, or retry with no ceiling |
| **Whole-payload Read** | A file or response loaded entirely into memory because the test fixture was small |

These four are not in Fowler's catalogue; they are the operational categories
OpenCodeReview's default ruleset asks about, kept here because they belong to
the same "correct today" family and the same dimension.

### `test-strength` — the tests smell too

| Smell | What you are seeing |
|---|---|
| **Assertion-free Test** | Executes the code, asserts nothing meaningful. Caught by the `falsified_by` rule |
| **Mystery Guest** | The test depends on external state — a real file, a live service, an ambient date |
| **Test Mirrors Implementation** | Rewriting the same expression in the assertion, so it passes for any implementation of that shape |

## Deliberately not in this catalogue

A closed set is defined as much by what it excludes. These are Fowler entries
left out on purpose, so that nobody adds them back by reflex:

- **Comments** — Fowler's smell is comments used as deodorant for code that
  should have been clearer. This codebase deliberately writes long comments
  explaining *why* a rule exists, and several of them are the only record of a
  decision. Reporting that as a smell would attack the house style. Report the
  unclear code; never the comment that explains it.
- **Data Class** — a class that is only fields. Here that is the intended
  design: `Card`, `Verdict`, and `Acceptance` are frozen records precisely so
  that behaviour lives in `policy`. Reporting it would fight the architecture.
- **Refused Bequest** and **Alternative Classes with Different Interfaces** —
  inheritance smells. There is almost no inheritance in this codebase; an
  entry that can never legitimately fire trains reviewers to force matches.
- **Loops** — Fowler's second-edition entry, arguing for pipelines. In Python
  that is a comprehension-versus-loop preference, not a defect, and the
  `resource-safety` entries already cover the loops that actually cost
  something.

If you meet one of these and it genuinely is the finding, describe it plainly
and say why the exclusion does not apply. Do not smuggle it in under a
neighbouring name.

## Rules

**A smell is a name, not an argument.** It still needs quoted code, a
confidence score, and a challenge, exactly like any other finding. Naming
*Feature Envy* and stopping is a label, not a review.

**A smell is not automatically a defect.** Most are `low` or `medium` severity
and belong in a `pass` with findings. Escalate only when you can say what
breaks: *Shotgun Surgery* becomes `high` when you can point at the consumer the
last such change actually missed — and note that `high` now makes the verdict
`fail`, so the escalation is a real decision, not an adjective.

**Do not smell-hunt code the Card did not touch.** The delivery under review is
the diff. A smell in surrounding code is at most a `limitations` note or a
follow-up Card, never a reason to fail this one.

**Do not invent entries.** If a finding does not match a name here, describe it
plainly. A private vocabulary is worse than none, because it looks shared.
This one is enforced: `accept` refuses a verdict whose `smell` is not in the
list above, and names the value it rejected.

## Suggested reading, for the record

The team lead's aside in the 2026-08-28 review — that neither intern had met
the term — is what prompted this file, and the two sources he named:

- Martin Fowler with Kent Beck, *Refactoring: Improving the Design of Existing
  Code*, chapter 3, "Bad Smells in Code" — the catalogue above.
- Robert C. Martin, *Clean Architecture* — the boundary and dependency-direction
  arguments behind `architecture`.
