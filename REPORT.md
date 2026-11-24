# REPORT: OCME-007-evo, Kimi K3 as the judge, on held-out set 3 (Turdy)

Branch `feat/kimi-k3-judge`, from `feat/simple-judge-held-out-2` (`a9e1c2c`) plus Turdy's `feat/held-out-set-3` (`a81bb86`). Still a simulation: nothing trained, no AppWorld run. Key from env only, in no file or result.

## Headline
K3 (`moonshotai/kimi-k3.1-pro`): **27 of 30 model alone, 27 of 30 after the backstop.** The backstop changed nothing: K3 never needed it and the one change it missed slipped past it. **It does not catch the partial case: H3-A3 was called noise in all 3 calls.** It did catch the mixed-prior case H3-A4 on its own (3 of 3), which Ultra and Bolt both missed and left to the backstop.

Pass bar, model alone: Ultra 27/30 on set 1, Bolt 24/30 on set 2, K3 27/30 on set 3. Different sets, so not directly comparable. Sets 2 and 3 have the same shape (Turdy, same ten kinds of trap), and on that shape K3 beat Bolt by 3 calls: same miss on the partial case, but it got the mixed-prior case itself.

## Model and how it was verified
Read the live `/v1/models` list (32 ids), found `moonshotai/kimi-k3.1-pro` (same as the order), copied it into `heldout3/model_check.json`. One trivial call with the free key (not on the set) returned HTTP 200 in about 57 s, reasoning on by default. No paid plan seen. `judge.py` changed in one line, `MODEL`; a test checks the rest is byte-identical to `d21bf84`. Prompt, backstop, ERIE, `max_tokens` 8192, temperature 0 unchanged and hash-checked. Partial-coverage rule NOT added (test-checked: backstop hash equals set 2's). The only runner change: a 900 s HTTP timeout, because K3 is slow; it does not touch the prompt or the judgment. The set-2 runner now reads its sealed model so it still reproduces Bolt.

## Set and seal
Written by **Turdy** (`a81bb86`). Sealed in `7a65c44` ("SEAL3:"), pushed before the first call. Truth read only after the calls; no judge code reads it. One run, no retune. Tests: 90 (was 77).

## Priors from real runs
Built from this run's own verdicts, not the file. `next_job_hurt` derived from a Control-arm run of each earlier change. All four matched what Turdy typed: N3 from N1 (noise, no hurt), L3 from N2 (noise, no hurt), A2 from N2 noise and L2 logical (hurt), A4 from L1 logical (hurt).

## Results (3 live calls each; every call in `results/live-judge-held-out-3.json`)
| Change | Truth | Model alone | After backstop | Cited | Priors | KATIE (pipeline) |
|---|---|---|---|---|---|---|
| H3-N1 calendar colour | noise | noise x3 | noise x3 | E1,E2 | none | not run (noise) |
| H3-N2 underscores to spaces | noise | noise x3 | noise x3 | E1,E2 | none | not run (noise) |
| H3-L1 password 8 to 12 | logical | logical x3 | logical x3 | E1 | none | right |
| H3-L2 reminder before event | logical | logical x3 | logical x3 | E1 | none | right |
| H3-N3 relevance sort | noise | noise x3 | noise x3 | E1-E3 | N1 noise | not run (noise) |
| H3-L3 "clarification", title required | logical | logical x3 | logical x3 | E1 | N2 noise (misleading) | right |
| H3-A1 Spanish, count example | ambiguous | ambiguous x3 | ambiguous x3 | E1 | none | right |
| H3-A2 thumbnails, conflicting priors | ambiguous | ambiguous x3 | ambiguous x3 | E1,E2 | N2 noise, L2 logical | right |
| **H3-A3** only Spotify changes | ambiguous | **noise x3** | **noise x3** | E1 | none | **wrong** |
| H3-A4 stars for dots, prior L1 logical | ambiguous | ambiguous x3 | ambiguous x3 | E1-E3 | L1 logical | right |

## Where it failed
**H3-A3 (partial).** K3 cited E1, the touched Spotify example that did not change, and said noise, ignoring that the Venmo example is untouched. Same miss Bolt made on H2-A3. The backstop allows noise when a touched example is unchanged and the packet holds no changed answer, so it passed. Cost in the pipeline: where the change really mattered (H3-A3-matters) **KATIE ended below Control**, selection 14 vs 18 and test 14 vs 18, with the -4 dip and no job skipped. Harmless case: both ended at 19. The other 9 runs: KATIE ended equal to Control, skipped 1 job each, avoided the dip where answers moved.

**Two models, two sets, the same miss.** The partial case is not a model problem. The prompt's noise rule ("the examples touched by the change show the same answer") permits it, and the backstop agrees. The fix is the open partial-coverage call, which is Darren's.

## Unproven
Ultra and Bolt were not run on set 3, so there is no same-set comparison. One miss moves the score by 3 of 30. Outcomes are scripted. K3 is slow (about a minute per call), which matters if it judges live.
