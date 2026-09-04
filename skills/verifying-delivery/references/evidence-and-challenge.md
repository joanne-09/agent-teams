# Evidence, calibration, and challenge

<!-- Derived from gstack `/review` (the pre-emit verification gate, confidence
     calibration, the red-team pass) and superpowers
     `verification-before-completion` and `requesting-code-review`. MIT.
     See ATTRIBUTION.md. -->

## The pre-emit gate

**Before a finding is promoted, quote the code lines that motivate it.**

Not paraphrase the file. Not name the function. Quote the lines, with the path
and line numbers, and say what about them is wrong.

A finding that cannot pass this gate is **suppressed**, not softened. Move it
to `limitations` as an unverified suspicion, or drop it.

This is the single highest-value rule in this skill. Most bad review is not
wrong analysis, it is confident analysis of code nobody re-read.

```
Finding: parse() crashes on an empty header.

  src/parser.py:41-43
      header = lines[0].split(",")
      if not header[0]:
          raise ValueError(...)

  lines[0] raises IndexError before the guard runs, so an empty file
  produces IndexError rather than the documented ValueError.

  Reproduced: python -c "import parser; parser.parse('')" -> IndexError
```

Path, lines, the actual code, what is wrong, and how it was observed.

## Confidence calibration

Score every finding 1-10.

| Score | Meaning | What to do |
|---|---|---|
| 8-10 | Verified against the code, reproduced or clearly traced | State it plainly |
| 7 | Confident, not reproduced | State it, note it was not reproduced |
| 5-6 | Plausible, evidence incomplete | State the caveat inside the finding |
| 3-4 | Suspicion only | `limitations`, not `findings` |
| 1-2 | Speculation | Drop it |

Uncalibrated findings make a report unusable: the reader cannot tell what to
act on first, so they either act on everything or on nothing.

## Challenging a finding

Every material finding gets an explicit attempt to falsify it. Record the
attempt and its outcome — **including for findings that survive**, because "we
tried to break this and could not" is much stronger evidence than the finding
alone.

Work through:

- **Callers.** Does any real caller reach this state? A crash on input nothing
  produces is a different severity.
- **Related files.** Is it already handled upstream or downstream?
- **Existing mitigations.** A validator, a schema, a type, a guard elsewhere.
- **Intended behaviour.** Is this actually the specified behaviour, and the
  specification is what you disagree with? That is an architecture finding for
  the Architect, not a defect for the Developer.
- **Contrary evidence.** Is there a passing test that asserts the behaviour you
  are calling broken? Read it before proceeding.

Outcomes worth recording verbatim:

```
challenge: checked all 3 callers of parse(); read_file() passes file
contents which can be empty when the upload is zero-length.
outcome: survives -- reachable in production.

challenge: looked for upstream validation; ingest.py:88 rejects empty
uploads before parse() is reached.
outcome: refuted -- not reachable. Lowered to limitations.
```

A refuted finding is a success of this process, not a wasted pass.

## When you are unsure, keep it

<!-- The asymmetry below is derived from alibaba/open-code-review's
     review-filter prompt (Apache-2.0), which states it for a separate
     fact-checking model. Applied here to the reviewer reconciling its own
     helper passes. See ATTRIBUTION.md. -->

Challenge exists to refute findings **with evidence**, and the two mistakes
available to you are not equally bad:

- Keeping a finding that turns out to be wrong costs the Developer a few
  seconds of attention and leaves a visible record that it was raised.
- Dropping a finding that was right destroys it silently. It reaches nobody,
  and nobody ever learns it was dropped.

So the bar for dropping is **proof, not doubt.** "I could not verify this",
"it looks fine to me", "probably a false positive", and "not worth their time"
all mean **keep it** — as a lower-confidence finding, or in `limitations` with
the reason. Only a specific, quotable refutation removes one, and the refutation
goes in `challenges` where the next reader can check it.

This matters most exactly where you are least likely to notice it: reconciling
what three review passes sent back. A finding you did not personally derive is
the easiest one to quietly not carry forward, and deduplication is not the same
operation as dismissal.

## The blind-spot loop

Before writing the verdict, ask what you have not actually looked at:

- a file you only saw as a diff hunk, never in context;
- a dimension you moved through quickly because the first two looked clean;
- a behaviour with no test either proving or disproving it;
- a caller you assumed rather than opened.

Anything you find here means **re-run that dimension**, then ask again.

`blind_spots` must be empty for a pass, and `accept` enforces it. That
constraint is the point: an unresolved blind spot is a `blocked` verdict, which
policy routes to a human. Converting it into a qualified pass is exactly the
failure this whole design exists to prevent.

## Evidence before claims

The same rule the Developer works under applies to the reviewer. Do not write
"tests pass" into a verdict without running them in this session and reading
the output. Do not write "no security issues" for a dimension you sampled.

`limitations` exists precisely so you can say what you did not check. Using it
honestly costs nothing; a pass that quietly omits a dimension costs the whole
gate its credibility.
