# katie-coevobench

KATIE on CoEvoBench. A public test of a simple claim: recursive improvement cannot compound without a record.

CoEvoBench finds that current LLM researchers make a strong first improvement, then stall. The first candidate delivers about three quarters of the total gain. In 25 of 28 improving runs, the first rise was the largest step. Later rounds add little.

Our claim is that this is a record problem, not a model problem. Each harness revision changes what training is worth. Nothing in the run records what was believed when the first change was made, what evidence it rested on, and why it worked under that harness and not this one. So the second round starts blind.

KATIE is an append-only knowledge record. Every entry carries its own KID, its authority, its source, and the what, when, and why of the belief behind it. This repo tests whether giving the researcher that record lets the gains compound.

## The paper under test

CoEvoBench: Can LLMs Drive Recursive Co-Evolution of Agentic Systems?
Xiao, Wang, Fan, Du, Xu. Zhejiang University, Alibaba Group, Shanghai Jiao Tong University.
arXiv:2611.27116, 20 Nov 2026.
https://arxiv.org/abs/2611.27116
https://www.alphaxiv.org/abs/2611.27116
Code: https://github.com/AlibabaResearch/CoEvoBench

Five domains: SWE-bench Verified, TB-Lite, AppWorld easy, tau2-bench Telecom, BFCL-V4 multi-turn and memory.
Budget in the paper: 24 hours, four NVIDIA H20 GPUs, $100 teacher-model budget per run.

## Tests

### Test 1: AppWorld harness flip

Their Figure 5 case. Training first solves five more selection tasks than Base. After a harness revision, the same weights fall four tasks behind Base. Retraining on fresh data restores a gain of four tasks. Counts are on the same 51-task selection set.

Cross-checking all 35 trained systems: the reference harness lifts Instruct from 30.2 percent to 37.8 percent but drops the trained weights from 19.8 percent to 2.6 percent.

Test: replay AppWorld with KATIE tagging every trajectory with its harness version KID. Training is only allowed on trajectories whose harness KID matches the current harness.

Pass bar: avoid the minus 4 dip, and skip the wasted training job.

### Test 2: Second-round gain

Control arm: researcher gets a raw history that just appends each action and observation, as in the paper.
KATIE arm: researcher gets a K-record. Every candidate, failure, and lesson gets a KID, an authority, a source, and the what, when, and why. The researcher must cite the KID before its next action.

Run AppWorld and BFCL only, two rounds only, not the full 24 hours.

Pass bar: share of total gain from round 2 and later goes up, number of new bests in the second half goes up, training jobs wasted goes down. Baseline to beat: first candidate about 75 percent of gain, first rise largest in 25 of 28 runs, share of new bests falls by more than half from first half to second half.

### Test 3: BFCL memory

BFCL is scored 60 percent multi-turn and 40 percent memory. Training carries over 80 percent of the gain on BFCL, while the harness carries most of the gain on the other four tasks.

Test: run BFCL memory tasks with KATIE as the memory versus flat retrieval with no record.

Pass bar: memory accuracy up, and lessons survive a harness change. A flat memory cannot say where a fact came from or if it is still valid. KATIE can.

## What we will not do first

SWE-bench or TB-Lite. Long-horizon coding is where training fails for everyone in the paper. The harness carries the gain there. That is not where KATIE wins.

## Plan

- One domain first: AppWorld easy.
- One target model first: MiniCPM5-2B-Base, to keep it cheap, not Qwen3.5-9B-Base.
- Two arms, three runs each.
- KATIE sits as a wrapper around the researcher loop, not inside the model. It records every change and gates training data by harness KID.
- This repo is separate from trifecta. Trifecta is the Kiroween demo. This is a clean public test harness for a public paper.

## Status

Repo created 24 Nov 2026, public. Tests not yet run.
