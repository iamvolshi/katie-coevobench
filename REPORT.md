# REPORT: OCME-008-evo, the partial-coverage backstop, proven on held-out set 4 (Turdy)

Branch `feat/partial-backstop`, from `feat/kimi-k3-judge` (`00839bc`) plus Turdy's `feat/held-out-set-4` at `0f4d231`. Still a simulation: nothing trained, no AppWorld run. Judge unchanged: K3, `moonshotai/kimi-k3.1-pro`, timeout 900 s, `max_tokens` 8192, temperature 0. Key from env only.

## Headline: the proof bar is met
**H4-A3 and H4-A4 came back `partial`, 3 of 3 each. H4-N1, H4-N2, H4-N3 came back `noise`, 3 of 3 each.** No partial case came back noise, so the rule worked. No full-coverage noise case came back partial, so the rule is not too broad. Score: **30 of 30 after the backstop, 24 of 30 model alone.** The model said `ambiguous` on all 6 partial calls, never `noise` and never `partial`. The code named them `partial`. The 6 model-alone misses are exactly those calls.

## The rule
**In code** (`judge.py`, `is_partial` and `check_partial`, run after the old checks): a packet is partial when it holds at least one touched example whose answer did not change AND at least one untouched example. Priors never count. On a partial packet:
- `noise` is rejected and recorded as a failed judgment with kind `partial`;
- `ambiguous`, or a failed reply, becomes `partial`;
- a supported `logical` (a cited changed example) still stands.

On a packet that is not partial, a `partial` answer is rejected (failed, ambiguous). That is what keeps the rule off full-coverage noise. `partial` is now a fourth kind. KATIE treats it like ambiguous: a hold entry with its own KID, no training on the mixed set, Base served, then a probe. It is recorded as `judged_kind: partial` in the test record.
**In the prompt**, one added line, rule 5: *"If the coverage is partial, one touched example and one untouched example, say partial, not noise."* Nothing else in the prompt changed (test-checked line by line against the set 3 seal). The reply template still lists three kinds, because changing it would have been a second prompt change. That may be why K3 said ambiguous and not partial.
**Steering note:** the first version of the order made partial a true/false flag. The second made it a kind. I built the flag first, then switched to the kind before the seal. Only the kind version was sealed and run.

## Set, seal, run
Written by **Turdy** (`ae6a709`, `eb9b203`, `0f4d231`). The rule went in first, then the set was sealed in `bb1387a` ("SEAL4:") and pushed before any call. One run, in the ordered sequence, no retune. The results commit (`7ab8b55`) records `git_head_at_run = bb1387a`. Priors came from this run's own verdicts. `next_job_hurt` was derived from the run, and all four matched Turdy's file. ERIE is unchanged. Tests: 118 (was 90). With the rule disabled, 6 partial tests fail. The set 1-3 freeze checks now read the code as it stood at each seal commit, because the judge has changed since.

## Results (3 live calls each, every call in `results/live-judge-held-out-4.json`)
| Change | Truth | Model alone | After backstop | Cited | Priors | KATIE (pipeline) |
|---|---|---|---|---|---|---|
| H4-N1 note order | noise | noise x3 | **noise x3** | E1,E2 | none | not run (noise) |
| H4-N2 written dates | noise | noise x3 | **noise x3** | E1,E2 | none | not run (noise) |
| H4-L1 spaces count | logical | logical x3 | logical x3 | E1 | none | right |
| H4-L2 exact totals | logical | logical x3 | logical x3 | E1 | none | right |
| H4-N3 24-hour times | noise | noise x3 | **noise x3** | E1-E3 | N1 noise | not run (noise) |
| H4-L3 "cleanup", full name required | logical | logical x3 | logical x3 | E1 | N2 noise (misleading) | right |
| H4-A1 euros, count example | ambiguous | ambiguous x3 | ambiguous x3 | E1 | none | right |
| H4-A2 French, conflicting priors | ambiguous | ambiguous x3 | ambiguous x3 | E1,E2 | N2 noise, L2 logical | right |
| H4-A3 only calendar changes | partial | ambiguous x3 | **partial x3** | E1,E2 | none | right |
| H4-A4 only notes change | partial | ambiguous x3 | **partial x3** | E1-E3 | L1 logical | right |

**Pipeline, live judge, 11 runs:** KATIE ended equal to Control on selection and test in all 11, skipped 1 job each, and had no job that hurt. Where the change really mattered, KATIE avoided the -4 dip (logical, ambiguous-matters and partial-matters). On H4-A3-matters it now ends at 18 against Control's 18. The same case on set 3 (H3-A3) ended 14 against 18. Where the change was harmless, KATIE paid for the hold (14 against 19 during the window) and ended equal at 19.

## Unproven
K3 never itself said `partial`. The model-alone score on partial cases is 0 of 6, so the catch is the code's. The rule is about coverage only: a partial packet where the untouched example is the one that matters is held, and the probe settles it. Other models were not run on set 4. Outcomes are scripted, not replayed from AppWorld.
