"""Deterministic AppWorld-easy stand-in. NOT a real AppWorld run and NOT real training.

Outcomes are driven by the paper's Figure 5 case, kept as named constants below.
Everything else is this repo's own modelling choice, listed in REPORT.md.
"""
from __future__ import annotations
import random
from dataclasses import dataclass, field

SPLITS = {"visible": 27, "selection": 51, "test": 51}   # AppWorld easy split sizes (CoEvoBench README)
BASE_SOLVED = 14           # ASSUMPTION: Base solves 14 of 51; the paper case gives only deltas
GAIN = {"H0": 5, "H1": 4}  # Fig 5: first training +5 (old harness); retrain after revision +4
STALE_PENALTY = -4         # Fig 5: same weights after the harness revision fall 4 behind Base


MIX_RULES = ("linear", "stale_wins", "majority")


class SplitViolation(Exception):
    pass


@dataclass
class Traj:
    tid: int
    task: str
    harness: str             # ground truth: used only by the simulator and the audit
    kid: str | None = None   # set by the KATIE arm only


@dataclass
class Weights:
    name: str = "base"
    trained_on: list[str] = field(default_factory=list)   # ground-truth harness of each trajectory used


class World:
    def __init__(self, seed: int, mix: str = "linear"):
        if mix not in MIX_RULES:
            raise ValueError(f"mix rule must be one of {MIX_RULES}")
        self.mix = mix
        rng = random.Random(seed)
        self.tasks = {s: [f"{s}-{i:02d}" for i in range(n)] for s, n in SPLITS.items()}
        self._order = {s: rng.sample(t, len(t)) for s, t in self.tasks.items()}
        self._next = 0
        self.test_reads = 0

    def collect(self, harness: str, n: int) -> list[Traj]:
        """Roll out on VISIBLE tasks only."""
        vis = self.tasks["visible"]
        out = []
        for _ in range(n):
            out.append(Traj(self._next, vis[self._next % len(vis)], harness))
            self._next += 1
        return out

    def delta(self, w: Weights, harness: str) -> int:
        if not w.trained_on:
            return 0
        f = sum(h == harness for h in w.trained_on) / len(w.trained_on)   # matching share
        if self.mix == "stale_wins":    # any stale data poisons the job
            return GAIN[harness] if f == 1 else STALE_PENALTY
        if self.mix == "majority":      # whichever side holds more data; a tie counts as stale
            return GAIN[harness] if f > 0.5 else STALE_PENALTY
        return round(GAIN[harness] * f + STALE_PENALTY * (1 - f))

    def solved(self, w: Weights, harness: str, split: str, final: bool = False) -> set[str]:
        if split == "visible":
            raise SplitViolation("candidates are never judged on visible tasks")
        if split == "test":
            if not final:
                raise SplitViolation("test split is for the final score only")
            self.test_reads += 1
        n = max(0, BASE_SOLVED + self.delta(w, harness))
        return set(self._order[split][:n])
