# REPORT: OCME-004-evo, held-out test of the judge

Branch `feat/held-out-judge`. Follows `feat/erie-judge-evidence` at `d21bf84` (its report is on that branch). Still a simulation: nothing trained, no AppWorld run. Judge: `nvidia/nemotron-3-ultra-550b-a55b`, `https://integrate.api.nvidia.com/v1`, temperature 0, `max_tokens` 8192, key from env only (not in any file or result).

## Headline
**30 of 30 calls right after the backstop, 27 of 30 from the model alone.** That is 10 of 10 changes, 3 calls each. It is not lower than 12 of 12 on the face of it, but read the caveats: the model got one change (HO-A4) wrong all 3 times, and only the code backstop turned it into the right answer.

## How it was kept honest
- 10 new changes (3 noise, 3 logical, 4 ambiguous), different tools, scoring, number, text and paging rules. None reuses an earlier script (test-checked). Files: `heldout/changes.json` (what the judge sees), `heldout/ground_truth.json` (kind plus reason, written before any call).
- Sealed: `heldout/SEAL.json` holds sha256 of both files and of the frozen `judge.py`, `erie.py` and `PROMPT`. Sealed in commit `2762c74` ("SEAL:") and pushed **before** the first call. A test checks the hashes, that the truth is loaded only after the calls in `heldout.main`, that no judge code mentions the truth file, and that the live results commit comes after the seal.
- Frozen: `judge.py` equals the `d21bf84` file byte for byte (hash, and the prompt and backstop text compared to that commit). No prompt, ERIE or backstop change. No rerun. This is the only run.

## Results (3 live calls each; every call is in `results/live-judge-held-out.json`)
| Change | Truth | Judge (3 calls) | Model alone | Cited | Prior in packet | KATIE acted |
|---|---|---|---|---|---|---|
| HO-N1 tool rename | noise | noise x3 | noise x3 | E1,E2 | no | right |
| HO-N2 money commas, checker strips them | noise | noise x3 | noise x3 | E1,E2 | no | right |
| HO-N3 scoring as checklist | noise | noise x3 | noise x3 | E1-E3 | noise | right |
| HO-L1 tolerance 1.0 to 2 decimals | logical | logical x3 | logical x3 | E1 | no | right |
| HO-L2 case-insensitive to exact | logical | logical x3 | logical x3 | E1 | no | right |
| HO-L3 "no behavior change" but 2nd answer dropped | logical | logical x3 | logical x3 | E1 | noise | right |
| HO-A1 cent rounding, whole-dollar examples | ambiguous | ambiguous x3 | ambiguous x3 | E1,E2 | no | right |
| HO-A2 NFC text, ASCII examples | ambiguous | ambiguous x3 | ambiguous x3 | E1,E2 | no | right |
| HO-A3 paging at 20, small result sets | ambiguous | ambiguous x3 | ambiguous x3 | E1,E2 | logical | right |
| **HO-A4** percent text, prior change moved an outcome | ambiguous | ambiguous x3 (recorded as failed) | **noise x3** | none | logical | right, via backstop |

**Where the model was wrong:** HO-A4. Two touched examples were unchanged, so it said noise and cited nothing. The packet also held a prior logical change on percentages. The backstop rejected noise ("packet holds a changed answer") and recorded a failed judgment, which holds. Correct outcome, wrong model. The model ignored the prior item; the code did not.
**Traps it passed:** HO-L3's text says no behavior change and a misleading noise prior, yet it cited the changed example. HO-N2 and HO-A3 look like real changes and it read the evidence instead.

## Full pipeline, live judge, logical and ambiguous changes (seed 1; ambiguous run under both hidden truths)
KATIE ended **equal to Control** on selection and test in all 11 runs, and skipped 1 job each time. Where the change really moved answers (logical, ambiguous-matters), KATIE avoided the -4 dip (S2 14 vs Control 10). Where an ambiguous change was harmless (4 runs), KATIE paid for the hold: S2 14 vs Control 19, ending equal at 19. Same numbers as the OCME-002 and 003 scripts, because the simulator scores by kind, not by content. Details: `results/pipeline-held-out.json`.

## Caveats, plainly
- **I wrote the set, the prompt and the truth.** Sealing stops retuning after the fact; it does not make the set independent or adversarial. The truth follows the same written rule as the prompt (a test confirms that), so this mostly measures whether the model follows the rule given clean evidence.
- Only HO-A4 stressed the model; one change is thin evidence about priors. Priors were exercised live in 4 changes (N3, L3, A3, A4), seeded into the record as history, not produced by real earlier runs.
- Outcomes are scripted, not replayed from AppWorld. Temperature 0 did not give identical text between calls earlier, though here all 30 kinds were stable.
- Unproven: changes whose evidence is genuinely messy (partial changes, conflicting examples), and a judge that sees no ERIE packet at all.
