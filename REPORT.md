# REPORT: OCME-009-evo, a quicker judge (Bolt) on held-out set 5 (Turdy)

Branch `feat/quick-judge-set-5`, from `feat/partial-backstop` (`84ae523`) plus Turdy's `feat/held-out-set-5` (`f2d6b7e`). Still a simulation: nothing trained, no AppWorld run. Key from env only.

## Headline: the proof bar is met, and the hypermodel is not necessary here
Bolt (`nvidia/nemotron-3.5-bolt-e4b`): **30 of 30 after the backstop, 24 of 30 model alone.** H5-A3 and H5-A4 came back `partial`, 3 of 3 each. H5-N1, H5-N2 and H5-N3 came back `noise`, 3 of 3 each. **The 30 calls took 33.7 s in total, 1.1 s per call on average (0.8 to 3.6 s).** K3 on set 4 took about 1,770 s for its 30 calls, about 59 s per call. That is roughly 50 times faster. The whole run, calls plus the 11-run pipeline, took 43 s.

Same pattern as K3 on set 4: the model said `ambiguous` on all 6 partial calls, never `noise`, and the code named them `partial`. Those 6 are the only model-alone misses. On this set, Bolt and K3 behave the same (the scores match exactly). The backstop does the part that needs doing.

## The swap
One line in `judge.py`, the `MODEL` line. The id was read from the live `/v1/models` list (32 ids) and saved in `heldout5/model_check.json`. The timeout stays 900 s; Bolt needed nothing more. Prompt, ERIE and backstop, including the OCME-008 partial rule, are unchanged from the set 4 seal `bb1387a`. A test hashes all of it against that commit and checks that the only changed line in `judge.py` is `MODEL`. Older tests now read each earlier set's judge from its own seal commit, because the live `MODEL` moved again. The set 5 runner adds per-call timing; nothing else in it differs from set 4's.

## Set, seal, run
Written by **Turdy** (`f2d6b7e`). The swap went in first, then the set was sealed in `0cb726e` ("SEAL5:") and pushed before any call. One run, in the ordered sequence, no retune. The results record `git_head_at_run = 0cb726e`. Priors came from this run's own verdicts, and `next_job_hurt` was derived from the run; all four matched Turdy's file. Tests: 132 (was 118).

## Results (3 live calls each, every call in `results/live-judge-held-out-5.json`)
| Change | Truth | Model alone | After backstop | Cited | Priors | KATIE (pipeline) |
|---|---|---|---|---|---|---|
| H5-N1 | noise | noise x3 | **noise x3** | E1,E2 | none | not run (noise) |
| H5-N2 | noise | noise x3 | **noise x3** | E1,E2 | none | not run (noise) |
| H5-L1 | logical | logical x3 | logical x3 | E1 | none | right |
| H5-L2 | logical | logical x3 | logical x3 | E1 | none | right |
| H5-N3 | noise | noise x3 | **noise x3** | E1,E2 | N1 noise | not run (noise) |
| H5-L3 | logical | logical x3 | logical x3 | E1 | N2 noise (misleading) | right |
| H5-A1 | ambiguous | ambiguous x3 | ambiguous x3 | E1 | none | right |
| H5-A2 | ambiguous | ambiguous x3 | ambiguous x3 | E1,E2 | N2 noise, L2 logical | right |
| H5-A3 | partial | ambiguous x3 | **partial x3** | E1,E2 | none | right |
| H5-A4 | partial | ambiguous x3 | **partial x3** | E1 | L1 logical | right |

**Pipeline, live judge, 11 runs:** KATIE ended equal to Control on selection and test in all 11, skipped 1 job each, and had no job that hurt. It avoided the -4 dip wherever the change really moved answers. Where the change was harmless, it paid for the hold during the window and ended equal.

## Timing
| Judge | Set | 30 calls | Per call |
|---|---|---|---|
| K3 `kimi-k3.1-pro` | 4 | about 1,770 s | about 59 s |
| Bolt `nemotron-3.5-bolt-e4b` | 5 | 33.7 s | 1.1 s mean |

K3's time is wall clock from process start to the results file (it was not timed per call). Bolt's is the sum of per-call times. They are different sets of the same shape.

## Unproven
Bolt was not run on set 4, and K3 not on set 5, so there is no same-set head to head. Bolt's model-alone score was 24 of 30 here and also 24 of 30 on set 2, where it missed the partial case and the backstop had no partial rule. So the rule, not the model, is what moved it to 30. Outcomes are scripted, not replayed from AppWorld.
