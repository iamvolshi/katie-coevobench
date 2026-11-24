# REPORT: Test 1 follow-up, three change kinds (OCME-002-evo)

Branch `feat/change-kinds`, on top of `feat/appworld-harness-flip` at `4d40fe1`. CoEvoBench commit referenced: `d39a924c8985806933c94777d8e969d6e756262c` (read only, no code run or copied).

## Read this first
Still a **simulation**. Nothing is trained, no model is served, no AppWorld run. The simulator's outcomes come from the paper's constants (+5, -4, +4) and a hidden truth per script. **The live judge is unproven: no `NIM_API_KEY` was available on the build machine** (a key needs a sign-up at build.nvidia.com that I cannot do). Every judge result below is from a **stub**, which is a lookup table and so is "right" by construction. That proves the wiring, not the judgment.

## What changed
- `judge.py`: the judge only classifies. Returns `{kind, reason, evidence}`. Anything that does not parse, is not one of the three kinds, has empty reason or evidence, or errors/times out becomes a **failed judgment recorded as ambiguous**. `NimJudge` calls `nvidia/nemotron-3-ultra-550b-a55b` at `NIM_BASE_URL` (default `https://integrate.api.nvidia.com/v1`) with `NIM_API_KEY` from env only. `StubJudge` needs no key.
- `arms.py` (KATIE wrapper) decides what a kind means. Each judgment gets its own KID with reason and evidence. **Noise**: same epoch, old trajectories and weights stay usable. **Logical**: new epoch, stale data blocked, stale weights not served (Base served). **Ambiguous**: a `hold` KID is recorded, old weights not served, mixed sets refused. A probe (run the held weights on the selection set under both harnesses) then resolves it with a `resolution` entry that supersedes the hold; the hold stays in the record. The probe is my addition: the order says hold "until probed" but does not say how.
- `scenarios.py`: `noise`, `logical`, `ambiguous` (one text, two hidden truths: `ambiguous_matters`, `ambiguous_harmless`, because "might matter, might not" needs both).
- `sim.py`: mix rules `linear`, `stale_wins`, `majority`. Control arm is unchanged: raw history, no tags, no gate, no judge.
- `live.py`: `python -m katie_coevobench.live` makes one real call per script and saves `results/live-judge.json` (no key in it). Not run yet.
- Tests: 33 (was 15), `python -m unittest discover -s tests -t .`. They cover each kind, failed judgments never guessing, KID with reason recorded and old entries untouched, the mix rules. With the hold logic disabled 4 tests fail.

## Numbers (selection set, Base 14; stub judge; counts identical across 3 seeds)
| Script | Arm | S0 | S1 | S2 revised | S3 | S4 | Jobs / hurt / skipped | Test |
|---|---|---|---|---|---|---|---|---|
| noise | Control | 14 | 19 | 19 | 19 | 19 | 2 / 0 / 0 | 19 |
| noise | KATIE (noise) | 14 | 19 | 19 | 19 | 19 | 2 / 0 / 0 | 19 |
| logical | Control | 14 | 19 | 10 | 13 | 18 | 3 / 1 / 0 | 18 |
| logical | KATIE (logical) | 14 | 19 | 14 | 14 | 18 | 2 / 0 / 1 | 18 |
| ambiguous, truly matters | Control | 14 | 19 | 10 | 13 | 18 | 3 / 1 / 0 | 18 |
| ambiguous, truly matters | KATIE (hold, probe: logical) | 14 | 19 | 14 | 14 | 18 | 2 / 0 / 1 | 18 |
| ambiguous, harmless | Control | 14 | 19 | 19 | 19 | 19 | 2 / 0 / 0 | 19 |
| ambiguous, harmless | KATIE (hold, probe: noise) | 14 | 19 | **14** | 14 | 19 | 2 / 0 / 1 | 19 |

Plain reading: on **noise** KATIE and Control are identical; KATIE adds nothing but the record. On **logical** and **ambiguous-matters** KATIE avoids the -4 dip and one bad job, same end score. On **ambiguous-harmless** KATIE **loses**: the hold throws away +5 for the revision window and skips a job Control ran fine; it ends equal only because it recovers after the probe. That is the price of not guessing.

## Mix-rule sensitivity (logical script, Control S3 = score at first retrain)
| Rule | Control S3 | KATIE dip | KATIE skips bad job | Ends equal to Control |
|---|---|---|---|---|
| linear (Test 1) | 13 (-1) | 0 | yes | yes (18) |
| stale wins | **10 (-4)** | 0 | yes | yes (18) |
| majority wins | **10 (-4)** | 0 | yes | yes (18) |

The rule changes Control's S3: under `stale wins` and `majority wins` the mixed job (40 stale + 20 fresh) scores -4, not -1. Under majority, a tie counts as stale (my choice). The KATIE conclusion holds under all three; it never depended on S3.

## Judge: right and wrong
Stub: right on all four scripts, meaning nothing. Failed-judgment path tested with junk replies: it becomes ambiguous and holds, even on a noise change (a cost, not a bug). Live judge: **not run, no result to report**. To prove it: set `NIM_API_KEY` (and optionally `NIM_BASE_URL`), run `python -m katie_coevobench.live`, then `python -m katie_coevobench.run --live`.

## Unproven
Live judge accuracy, especially on the ambiguous text (a real model may call it logical or noise). Any real model or AppWorld behavior. The probe is an oracle on the simulator's truth. The 3 seeds add no variance. Test 2 and 3 not built.
