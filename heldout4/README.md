# Held-out set 4, for OCME-008-evo

Written by Turdy, Nov 24, 2026. Not by Kiro. Kiro wrote the prompt, so this set is independent of the prompt builder.

Kiro: seal `changes.json` and `ground_truth.json` before the first judge call, as in OCME-004-evo. Do not run the judge before sealing. Do not retune on the failures. No rerun.

This set tests the partial coverage backstop rule. A partial change is one touched example unchanged plus at least one untouched example. That must hold, not be called noise.

## The set

10 changes, 3 noise, 3 logical, 4 ambiguous. None from set 1, 2, or 3.

- H4-N1 noise, note order, checker ignores order, every example touched
- H4-N2 noise, dates written format, checker reads both as same date, every example touched
- H4-L1 logical, extra spaces no longer ignored, Adele example flips
- H4-L2 logical, totals must be exact, no rounding, 12.50 example flips
- H4-N3 noise, times 24-hour, checker reads both formats, every example touched, prior from H4-N1 run
- H4-L3 logical, contact must be found by full name, first-name example flips, noise prior from H4-N2 is misleading
- H4-A1 ambiguous, messy thin, amounts may switch to euros, only example is a count, untouched
- H4-A2 ambiguous, messy conflicting priors, tasks may switch to French, examples are counts, untouched, priors are H4-N2 noise and H4-L2 logical
- H4-A3 ambiguous, messy partial, only calendar changes, email does not, calendar example touched and unchanged, email example untouched
- H4-A4 ambiguous, messy partial, only notes change, files do not, note example touched and unchanged, file example untouched, prior is H4-L1 logical

## Run order, and priors from real runs

Run in this order: H4-N1, H4-N2, H4-L1, H4-L2, H4-N3, H4-L3, H4-A1, H4-A2, H4-A3, H4-A4.

The priors in `changes.json` are not seeded by hand. They are the judgments from the earlier runs in this same test, in that order. Take the prior for H4-N3 from the H4-N1 run, for H4-L3 from the H4-N2 run, for H4-A2 from the H4-N2 and H4-L2 runs, and for H4-A4 from the H4-L1 run.

## Files

- `changes.json`, what the judge sees, in the same format as OCME-004-evo
- `ground_truth.json`, kind plus reason for each change, written before any call, judge code never reads it
