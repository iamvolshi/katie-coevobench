# REPORT: OCME-003-evo, fix the judge prompt with ERIE evidence

Branch `feat/erie-judge-evidence`, on `feat/change-kinds` at `99c17b8`. CoEvoBench commit referenced: `d39a924c8985806933c94777d8e969d6e756262c` (read only).

## Read this first
Still a simulation: nothing trained, no model served, no AppWorld run. **The live judge is not proven here.** No `NIM_API_KEY` was in the build environment and I do not take keys in chat. Everything below marked "stub" is a lookup table that is right by construction: it proves the wiring, not the judgment. The pass bar to beat is the live run Darren reported (2 of 3 right, ambiguous-that-matters called logical, and ambiguous-harmless also logical). I did not see that run's output, so I cannot quote it. Whether the new prompt fixes the miss is **unknown until the live run is done**.

## What changed
Three jobs, kept apart:
- **ERIE retrieves** (`erie.py`, read only). Builds an evidence packet: for each example task the old and new answers and whether the change touches that task; plus up to 3 earlier judgments from the test record, each with its KID, kind and what the next training job did. Every item has an id (E1..), source, and authority 0-9, plus a retrieval fact `shows`: `changed`, `unchanged` (touched, same answer), or `nothing` (untouched task, proves nothing). `StubErie` returns a fixed packet per script.
- **The judge classifies** (`judge.py`) from the packet only, and cites ids. Typed JSON `{kind, reason, evidence}` as before. Unparseable means failed means ambiguous, as before. New backstop in code that mirrors the prompt rule: `logical` must cite an example that shows a changed answer; `noise` must cite a touched unchanged example and the packet must hold no changed answer; a packet with no outcome never yields logical, and the judge is not even called. A claim the evidence does not support becomes a failed judgment, recorded ambiguous.
- **KATIE acts** (`arms.py`), unchanged. It now also records an `evidence` entry (full packet, own KID) before the `judgment` entry, which carries `evidence_kid` and the cited ids. Nothing is overwritten.

## Prompts
Old (OCME-002): old text, new text, "example tasks before and after" (outcome words only), "if you cannot tell, answer ambiguous". Evidence field = the changed part of the harness. Kept in code as `PROMPT_V1`, unused.
New: same kinds, plus the EVIDENCE PACKET and rules: *1. If no example shows a changed answer, say ambiguous. Do not infer logical from the harness text alone, however real the change looks. 2. A task the change does not touch proves nothing. 3. Cite the evidence you used by id. 4. If you cannot tell, answer ambiguous.* Full text: `PROMPT` in `katie_coevobench/judge.py`.

## Numbers (selection set, Base 14, identical across 3 seeds)
| Script | Packet shows | Stub judge | Live judge | KATIE S2 / S4 | Skipped | Control S2 / S4 |
|---|---|---|---|---|---|---|
| noise | 2 touched, unchanged | noise | not run | 19 / 19 | 0 | 19 / 19 |
| logical | 1 changed, 1 unchanged | logical | not run | 14 / 18 | 1 | 10 / 18 |
| ambiguous, matters | 2 untouched | ambiguous | not run | 14 / 18 | 1 | 10 / 18 |
| ambiguous, harmless | 2 untouched | ambiguous | not run | 14 / 19 | 1 | 19 / 19 |

Real ERIE retrieval (not the stub packet) feeds the same packets and the stub judge gets all four right. The harmless case still costs KATIE +5 during the hold, as before.

Tests: 48 (was 33). New ones cover each kind from evidence, no or no-outcome evidence never gives logical (including a model that says logical anyway), logical and noise citation rules, the prompt text, evidence and citations recorded with KIDs and priors read from the record with their KID, read-only retrieval. With the backstop disabled 4 tests fail.

## Right and wrong
Stub: right on all four, meaning nothing. Live: no result. By design the new prompt should stop the UTC-dates case from becoming logical, because both example tasks are untouched by the date rule and the packet says so. A real model may still ignore the rule, and the backstop would then downgrade it to ambiguous.

## Unproven
Live judge accuracy with the new prompt (run `python -m katie_coevobench.live` with `NIM_API_KEY` set; it now covers all four scripts and saves `results/live-judge.json`). Prior-change similarity is not computed: ERIE returns the last 3 judgments, similar or not. Example outcomes are scripted, not replayed from real AppWorld. The backstop makes a wrong live answer of "noise" or "logical" harder, but it cannot catch a correct-looking citation of the wrong item.
