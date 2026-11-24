# Held-out set 2, for OCME-005-evo

Written by Turdy, Nov 24, 2026. Not by Kiro. Kiro wrote the prompt, so this set is independent of the prompt builder.

Kiro: seal `changes.json` and `ground_truth.json` before the first judge call, as in OCME-004-evo. Do not run the judge before sealing. Do not retune on the failures. No rerun.

## The set

10 changes, 3 noise, 3 logical, 4 ambiguous. None from OCME-002, OCME-003, or OCME-004-evo.

- H2-N1 noise, playlist order, checker ignores order
- H2-N2 noise, Venmo dollar sign, checker strips it
- H2-L1 logical, times local to UTC, 9am example flips
- H2-L2 logical, duplicate contacts must all be listed, Alex example flips
- H2-N3 noise, email subjects lower cased, checker lower cases both sides, prior from H2-N1 run
- H2-L3 logical, money answer must include currency symbol, $80 example flips, noise prior from H2-N2 is misleading
- H2-A1 ambiguous, messy thin, weights may switch to pounds, only example is a count, untouched
- H2-A2 ambiguous, messy conflicting priors, phone formatting may change, examples are names and email, untouched, priors are H2-N2 noise and H2-L2 logical
- H2-A3 ambiguous, messy partial, only Venmo changes, Amazon does not, Venmo example touched and unchanged, Amazon example untouched
- H2-A4 ambiguous, messy mixed, touched examples unchanged, prior is H2-L1 logical on a similar time rule

## Run order, and priors from real runs

Run in this order: H2-N1, H2-N2, H2-L1, H2-L2, H2-N3, H2-L3, H2-A1, H2-A2, H2-A3, H2-A4.

The priors in `changes.json` are not seeded by hand. They are the judgments from the earlier runs in this same test, in that order. Take the prior for H2-N3 from the H2-N1 run, for H2-L3 from the H2-N2 run, for H2-A2 from the H2-N2 and H2-L2 runs, and for H2-A4 from the H2-L1 run.

## Files

- `changes.json`, what the judge sees, in the same format as OCME-004-evo
- `ground_truth.json`, kind plus reason for each change, written before any call, judge code never reads it
