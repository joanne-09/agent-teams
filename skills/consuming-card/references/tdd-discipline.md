# Test-driven development

<!-- Derived from superpowers `test-driven-development` and
     `verification-before-completion`. MIT. See ATTRIBUTION.md. -->

## The Iron Law

```
NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST
```

If you did not watch the test fail, you do not know it tests the right thing.

Wrote code before the test? Delete it. Not "keep it as reference" — you will
adapt it, and adapting is testing-after. Implement fresh from the tests.

## The cycle

### RED — write one failing test

One behaviour. A name that describes that behaviour. Real code rather than
mocks wherever mocking is avoidable.

Before writing it, answer: **what production change would make this test
fail?** If you cannot name one, the test asserts nothing.

### Verify RED — watch it fail

Mandatory. Run it and confirm three things:

- it **fails** rather than errors;
- the failure message is the one you expected;
- it fails because the behaviour is missing, not because of a typo or a bad
  import.

Test passes immediately? You are testing behaviour that already exists. Fix the
test.

### GREEN — minimal code

The simplest thing that passes. No extra parameters, no options nobody asked
for, no "while I'm here". Then run it and confirm it passes, that the rest of
the suite still passes, and that the output is clean — no new warnings.

Test still fails? Fix the code, not the test.

### REFACTOR — clean up, stay green

Remove duplication, improve names, extract helpers. No new behaviour.

## Rationalizations, and what is actually true

| Excuse | Reality |
|---|---|
| "Too simple to test" | Simple code breaks. The test takes half a minute. |
| "I'll test after" | Tests written after pass immediately, which proves nothing. They are biased by the code you already wrote: you verify the cases you remembered, not the ones you would have discovered. |
| "Tests-after achieve the same goal — spirit, not ritual" | Tests-after answer "what does this do?". Tests-first answer "what should this do?". Different questions. |
| "I already tested it manually" | No record of what you covered, no way to re-run it, easy to forget a case under pressure. |
| "Deleting hours of work is wasteful" | Sunk cost. The time is spent either way. The real choice is rewriting with confidence versus keeping code you cannot trust. |
| "Hard to test means the test is wrong" | Hard to test usually means hard to use. Listen to it. |
| "TDD will slow me down" | It catches the bug before the commit instead of in production. |

Any of these thoughts means stop and start over with a failing test.

## Evidence before claims

Separate from writing tests: **never state a result you have not just
observed.**

```
BEFORE claiming any status:
1. What command proves this?
2. Run it, in full, now.
3. Read the whole output. Check the exit code. Count the failures.
4. Does the output actually confirm the claim?
5. Only then say it -- with the evidence.
```

| Claim | Requires | Not sufficient |
|---|---|---|
| Tests pass | Test output, 0 failures | A previous run; "should pass" |
| Linter clean | Linter output, 0 errors | A partial check |
| Build succeeds | Build command, exit 0 | The linter passing |
| Bug fixed | The original symptom, re-tested | The code changed |
| Regression test works | Red-green verified: revert the fix, watch it fail, restore | It passes once |
| Agent finished | The diff, read by you | The agent said "done" |
| Requirements met | Each acceptance criterion, walked | The suite is green |

Words like "should", "probably", and "seems to" are the tell. So is expressing
satisfaction before running anything.

## Test strength

QA will judge the tests, not just their existence, and line coverage is not
evidence of behaviour. Deliveries hold up better when the tests carry:

- **branch outcomes**, not only executed lines;
- **negative paths** — the malformed input, the refused permission, the empty
  case;
- **scenario coverage** for the behaviour a user would describe;
- **integration or failure injection** at risky boundaries.

A test that would still pass if the implementation were wrong is coverage, not
a test.
