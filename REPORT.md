# REPORT: Test 1, AppWorld harness flip

Date 2026-11-24. Branch `feat/appworld-harness-flip`. CoEvoBench commit referenced: `d39a924c8985806933c94777d8e969d6e756262c` (default branch head, read for split sizes and terms only; none of its code is run or copied).

## Read this first
This is a **simulation of the Figure 5 case, not a real AppWorld run and not real training.** No MiniCPM5-2B-Base was trained or served. The reference runner needs Docker, four GPUs and a teacher-model budget; this machine has one 8 GB GPU. Outcomes come from constants taken from the paper (+5 first training, -4 after revision, +4 after retraining on fresh data) in `katie_coevobench/sim.py`. So the result below proves the **record and the gate work as designed**. It does **not** show that KATIE improves a real researcher. The Control arm "reproduces the flip" because the simulator was built to.

## What was built
- `record.py`: append-only record. KID `T1-n` (own test record, nothing from KIDs 1-29), authority 0-9, source, what, when, why, optional `supersedes`. Entries are frozen; a change is a new entry.
- `sim.py`: AppWorld-easy stand-in. Splits 27 visible / 51 selection / 51 test. Rollouts use visible tasks only. Judging on visible raises. Test is readable only with `final=True`.
- `arms.py`: one scripted researcher for both arms: collect 40 rollouts, train on everything, revise harness, retrain on everything, if below Base collect more and retrain. Control appends raw untagged history. KATIE wraps the loop: KIDs for each harness, trajectory, training job and refusal; training data is filtered to the current harness KID; weights trained under another harness KID are not served (Base is served instead).
- `run.py`: 2 arms x 3 seeds. `python -m katie_coevobench.run`. Tests: `python -m unittest discover -s tests -t .` (15 pass; with the gate disabled 5 fail).

## Numbers (51-task selection set, Base = 14; identical in all 3 seeds)
| Stage | Control | KATIE |
|---|---|---|
| S0 Base, old harness | 14 | 14 |
| S1 trained, old harness | 19 (+5) | 19 (+5) |
| S2 harness revised, same weights | 10 (**-4**) | 14 (0) |
| S3 retrain attempt 1 | 13 (-1, hurt) | 14 (refused, 20 fresh < 40 needed, job skipped) |
| S4 retrain on fresh data | 18 (+4) | 18 (+4) |

| | Control | KATIE |
|---|---|---|
| Training jobs launched | 3 | 2 |
| Jobs that hurt | 1 | 0 |
| Jobs skipped by the gate | 0 | 1 |
| Dip at revision | -4 | 0 |
| Final test score (once) | 18 / 51 (Base 14) | 18 / 51 (Base 14) |
| Harness KID per trajectory used | n/a, untagged | every trajectory carries one (see `results/record-katie-*.jsonl`) |

Result: against the pass bar, KATIE avoids the -4 dip and skips the wasted job. Final score is equal; KATIE does not end higher, it gets there without the dip and with one fewer job.

## My own modelling choices (not from the paper)
Base = 14; a job needs 40 trajectories; the weights' effect is a linear mix of match (+5/+4) and stale (-4) by the share of stale trajectories; the researcher script and its rollout counts (40/20/20); "hurt" = below Base under the current harness. A different mix rule would change S3 for Control. The 3 seeds change which tasks are solved, not the counts, so they add no variance.

## Unproven
Everything about a real model. Whether a real researcher would behave like the script. Whether the gate helps when harness mismatch is partial. Test 2 and Test 3 are not built. Next step for a real result: run the actual CoEvoBench AppWorld pipeline with the KATIE wrapper on a machine with the required GPUs.
