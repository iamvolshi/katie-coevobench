# REPORT: OCME-006-evo, a simpler judge on the held-out set Turdy wrote

Branch `feat/simple-judge-held-out-2`, built on Turdy's `feat/held-out-set-2` (`093c31c`) and OCME-004 (`b3369b7`). Still a simulation: nothing trained, no AppWorld run. Key from env only, in no file or result.

## Headline
New judge **`nvidia/nemotron-3.5-bolt-e4b`**: **27 of 30 after the backstop, 24 of 30 model alone.** Two changes missed: H2-A3 (model and backstop both wrong, 3 of 3 calls) and H2-A4 (model wrong, backstop right, 3 of 3). Best prior held-out score was 30 of 30 and 27 of 30 on set 1 with Ultra, **but that was my set and a different judge, so the scores are not comparable.** I did not run Ultra on this set, so I cannot say whether Bolt is better or worse than Ultra on the model-alone score. Only the model-alone result for Bolt is real: 24 of 30.

## Model and how it was verified
First pick was Bolt. I read the live `/v1/models` list (32 ids), copied `nvidia/nemotron-3.5-bolt-e4b` from it, and recorded the list in `heldout2/model_check.json`. One trivial chat call with the free key (not on the set) returned HTTP 200 with no reasoning tokens, so thinking is off by default. "Free tier" is shown only by that the call worked with this free key; I saw no billing. The fallback, Nano 9B v2, is not in the catalog, so it was not needed. `judge.py` changed in one line, the `MODEL` constant; a test checks the rest of the file is byte-identical to `d21bf84`. Prompt, backstop, ERIE, `max_tokens` 8192 and temperature 0 are unchanged, and hash-checked.

## The set and the seal
10 changes written by **Turdy** (commit `093c31c`, author Turdy). A git author name is self-declared, so the test checks the commit and bytes, not identity. I wrote none of it. Sealed in `cbab25c` ("SEAL2:"), pushed before the first call; tests check hashes, that the truth is read only after the calls, and that no judge code reads it. No retune, one run.

## Priors from real runs
The priors in `changes.json` were **not used**. Each prior is the judgment this run produced for the named earlier change, and `next_job_hurt` comes from a Control-arm simulation of that change's own examples. All four matched what Turdy typed (N3 from N1: noise; L3 from N2: noise; A2 from N2 noise and L2 logical; A4 from L1 logical). A test with a fake judge proves a different earlier verdict changes the prior.

## Results (3 live calls each, every call in `results/live-judge-held-out-2.json`)
| Change | Truth | After backstop | Model alone | Cited | Priors | KATIE (pipeline) |
|---|---|---|---|---|---|---|
| H2-N1 playlist order | noise | noise x3 | noise x3 | E1,E2 | none | not run (noise) |
| H2-N2 Venmo $ stripped | noise | noise x3 | noise x3 | E1,E2 | none | not run (noise) |
| H2-L1 local to UTC | logical | logical x3 | logical x3 | E1 | none | right |
| H2-L2 all duplicate contacts | logical | logical x3 | logical x3 | E1 | none | right |
| H2-N3 lower-cased subjects | noise | noise x3 | noise x3 | E1,E2 | N1 noise | not run (noise) |
| H2-L3 "wording cleanup", symbol required | logical | logical x3 | logical x3 | E1 | N2 noise (misleading) | right |
| H2-A1 kg to lb, count example | ambiguous | ambiguous x3 | ambiguous x3 | E1 | none | right |
| H2-A2 phone dashes, conflicting priors | ambiguous | ambiguous x3 | ambiguous x3 | E1-E4 | N2 noise, L2 logical | right |
| **H2-A3** only Venmo changes | ambiguous | **noise x3** | **noise x3** | E1 | none | **wrong** |
| **H2-A4** 24-hour times, prior L1 logical | ambiguous | ambiguous x3 (backstop) | **noise x3** | none | L1 logical | right |

## Where it failed
- **H2-A3 (partial).** The model said noise citing E1, the touched Venmo example that did not change; it ignored that the Amazon example proves nothing. The backstop accepts noise when a touched example is unchanged and nothing changed, so it passed. Under the sealed truth this is wrong. Note the prompt's own noise rule ("touched examples show the same answer") arguably allows it; the truth says partial coverage should hold. A failure is a result, so I did not change either.
- **H2-A4 (mixed).** Same as set 1: the model said noise three times and ignored the prior logical change. The code caught it ("noise contradicted: the packet holds a changed answer"), recorded a failed judgment, and held.
- **What the miss cost.** Pipeline, live judge: where the change really mattered (H2-A3-matters) **KATIE ended below Control**: selection 14 vs 18, test 14 vs 18, with a -4 dip and no job skipped. Where it did not matter (H2-A3-harmless) both ended at 19. In the other 9 runs KATIE ended equal to Control, skipped 1 job each, and avoided the dip where answers really moved. A wrong "noise" is the one error that makes KATIE worse than doing nothing.

## Unproven
Whether Bolt beats Ultra here (not run on this set). Sets are still small: one miss moves the score by 3 of 30. Outcomes are scripted. Priors were from the judge's own earlier verdicts, so a wrong earlier verdict would have fed forward (none was wrong). Whether a backstop rule for partial coverage (a touched example plus an untouched one) is wanted is Darren's call; I did not add one.
