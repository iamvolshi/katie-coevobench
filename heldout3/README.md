# Held-out set 3, for OCME-007-evo

Written by Turdy, Nov 24, 2026. Not by Kiro. Kiro wrote the prompt, so this set is independent of the prompt builder.

Kiro: seal `changes.json` and `ground_truth.json` before the first judge call, as in OCME-004-evo. Do not run the judge before sealing. Do not retune on the failures. No rerun.

## The set

10 changes, 3 noise, 3 logical, 4 ambiguous. None from set 1 or set 2.

- H3-N1 noise, calendar colour, checker ignores colour
- H3-N2 noise, file names underscores to spaces, checker treats them the same
- H3-L1 logical, password length 8 to 12, 10-character example flips
- H3-L2 logical, reminders must be before the event, after example flips
- H3-N3 noise, search results sorted by relevance, checker ignores order, prior from H3-N1 run
- H3-L3 logical, note must have a title, no-title example flips, noise prior from H3-N2 is misleading
- H3-A1 ambiguous, messy thin, text may switch to Spanish, only example is a count, untouched
- H3-A2 ambiguous, messy conflicting priors, images may switch to thumbnails, examples are names and titles, untouched, priors are H3-N2 noise and H3-L2 logical
- H3-A3 ambiguous, messy partial, only Spotify changes, Venmo does not, Spotify example touched and unchanged, Venmo example untouched
- H3-A4 ambiguous, messy mixed, touched examples unchanged, prior is H3-L1 logical on a similar password rule

## Run order, and priors from real runs

Run in this order: H3-N1, H3-N2, H3-L1, H3-L2, H3-N3, H3-L3, H3-A1, H3-A2, H3-A3, H3-A4.

The priors in `changes.json` are not seeded by hand. They are the judgments from the earlier runs in this same test, in that order. Take the prior for H3-N3 from the H3-N1 run, for H3-L3 from the H3-N2 run, for H3-A2 from the H3-N2 and H3-L2 runs, and for H3-A4 from the H3-L1 run.

## Files

- `changes.json`, what the judge sees, in the same format as OCME-004-evo
- `ground_truth.json`, kind plus reason for each change, written before any call, judge code never reads it
