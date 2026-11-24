"""The researcher loop (one script, both arms) and the two arms' wrappers.

Both arms run the same scripted researcher policy: collect rollouts, train on everything it has,
revise the harness once, retrain if the result is below Base. The only difference is the wrapper:
Control appends raw history; KATIE records every step and gates training/serving by harness KID.
"""
from __future__ import annotations
from pathlib import Path
from .record import Record
from .sim import World, Weights, Traj

MIN_TRAIN = 40   # ASSUMPTION: a training job needs at least 40 trajectories
N_FIRST, N_FRESH_1, N_FRESH_2 = 40, 20, 20


class ControlWrapper:
    """Paper's raw history: append everything, no tags, no gate."""
    name = "control"

    def __init__(self):
        self.history: list[Traj] = []
        self.harness = "H0"

    def revise(self, harness, why):
        self.harness = harness

    def add(self, trajs):
        self.history += trajs

    def train_data(self, since_revision=False):
        # raw history has no tags, so "fresh" can only mean "collected after the revision"
        return list(self.history) if not since_revision else list(self._post)

    def mark_revision(self):
        self._post = []

    def add_post(self, trajs):
        self._post += trajs

    def filter_for_training(self, trajs, why):
        return trajs, None

    def log_job(self, w, trajs, hurt):  # nothing is recorded
        pass

    def serve(self, w: Weights):
        return w


class KatieWrapper:
    """Wraps the loop. Every harness, trajectory, job and refusal gets a KID in its own record."""
    name = "katie"

    def __init__(self, record: Record):
        self.rec = record
        self.harness = "H0"
        self.hkid: str | None = None
        self.history: list[Traj] = []
        self.wkid: dict[int, str | None] = {}   # id(weights) -> harness KID it was trained under
        self._hk: dict[str, str] = {}           # trajectory KID -> harness KID it was collected under

    def revise(self, harness, why):
        e = self.rec.append("harness", 7, "researcher", f"harness {harness}", why,
                            supersedes=self.hkid, harness=harness)
        self.harness, self.hkid = harness, e.kid

    def add(self, trajs):
        for t in trajs:
            e = self.rec.append("trajectory", 5, "rollout", f"rollout {t.task} under {self.harness}",
                                "evidence for later training", harness_kid=self.hkid, task=t.task)
            t.kid = e.kid
            self._hk[t.kid] = self.hkid
            self.history.append(t)

    def filter_for_training(self, trajs, why):
        ok = [t for t in trajs if self._hk[t.kid] == self.hkid]
        stale = len(trajs) - len(ok)
        if len(ok) < MIN_TRAIN:
            e = self.rec.append("refusal", 8, "gate",
                                f"training refused: {len(ok)} trajectories match harness {self.hkid}, need {MIN_TRAIN}",
                                f"{stale} stale-harness trajectories excluded; {why}",
                                current_harness_kid=self.hkid, stale=stale, matching=len(ok))
            return ok, e.kid
        return ok, None

    def log_job(self, w, trajs, hurt):
        e = self.rec.append("training_job", 6, "trainer", f"trained {w.name} on {len(trajs)} trajectories",
                            f"harness KID {self.hkid} matches every trajectory used",
                            harness_kid=self.hkid, trajectory_kids=[t.kid for t in trajs], hurt=hurt)
        self.wkid[id(w)] = self.hkid
        return e

    def serve(self, w: Weights):
        """Candidate gate: weights trained under a different harness KID are not served."""
        k = self.wkid.get(id(w))
        if w.trained_on and k != self.hkid:
            self.rec.append("refusal", 8, "gate", f"weights {w.name} not served under harness {self.hkid}",
                            f"trained under harness KID {k}; falling back to Base weights",
                            weights_harness_kid=k, current_harness_kid=self.hkid)
            return Weights("base")
        return w


def run_arm(arm: str, seed: int, out: Path | None = None) -> dict:
    world = World(seed)
    rec = Record(out / f"record-{arm}-{seed}.jsonl") if out and arm == "katie" else Record()
    wrap = KatieWrapper(rec) if arm == "katie" else ControlWrapper()
    stages, jobs, used = [], [], []
    base = Weights("base")

    def sel(w, h):
        return len(world.solved(w, h, "selection"))

    def stage(name, w, note):
        stages.append({"stage": name, "harness": wrap.harness, "weights": w.name,
                       "selection_solved": sel(w, wrap.harness), "note": note})

    def train(name, trajs):
        w = Weights(name, [t.harness for t in trajs])
        n = len(jobs) + 1
        solved = sel(w, wrap.harness)
        hurt = solved < sel(base, wrap.harness)
        wrap.log_job(w, trajs, hurt)
        jobs.append({"job": n, "weights": name, "trajectories": len(trajs), "launched": True, "hurt": hurt,
                     "true_stale_in_data": sum(t.harness != wrap.harness for t in trajs),
                     "harness_kids_used": sorted({getattr(t, "kid", None) and wrap._hk[t.kid] for t in trajs}) if arm == "katie" else "untagged"})
        used.extend(t.tid for t in trajs)
        return w

    wrap.revise("H0", "initial harness") if arm == "katie" else None
    stage("S0 base, old harness", base, "Base weights")
    wrap.add(world.collect("H0", N_FIRST))
    w1 = train("w1", list(wrap.history))
    stage("S1 trained, old harness", w1, "job 1")
    cands = {}

    # harness revision
    wrap.revise("H1", "researcher revised the harness")
    if arm == "control":
        wrap.mark_revision()
    served = wrap.serve(w1)
    stage("S2 harness revised, same weights", served, "control serves w1 as is; KATIE refuses stale weights" if arm == "katie" else "w1 served as is")
    cands[served.name + "@S2"] = served

    fresh1 = world.collect("H1", N_FRESH_1)
    wrap.add(fresh1)
    if arm == "control":
        wrap.add_post(fresh1)
    ok, refusal = wrap.filter_for_training(list(wrap.history), "retrain request after revision")
    if refusal:
        jobs.append({"job": len(jobs) + 1, "weights": "w2", "trajectories": len(ok), "launched": False,
                     "hurt": False, "refusal_kid": refusal})
        stage("S3 retrain attempt 1", served, f"refused ({refusal}), job skipped")
    else:
        w2 = train("w2", ok)
        stage("S3 retrain attempt 1", w2, "trained on whole history")
        cands["w2"] = w2

    fresh2 = world.collect("H1", N_FRESH_2)
    wrap.add(fresh2)
    if arm == "control":
        wrap.add_post(fresh2)
        data = wrap.train_data(since_revision=True)
        if sel(cands["w2"], wrap.harness) >= sel(base, wrap.harness):
            data = []
    else:
        data, refusal = wrap.filter_for_training(list(wrap.history), "retrain request, more fresh rollouts")
        if refusal:
            data = []
    if data:
        w3 = train("w3", data)
        cands["w3"] = w3
        stage("S4 retrain on fresh data", w3, "post-revision trajectories only" if arm == "control" else "gated by harness KID")

    best_name = max(cands, key=lambda k: sel(cands[k], wrap.harness))
    best = cands[best_name]
    final = len(world.solved(best, wrap.harness, "test", final=True))
    base_test = len(world.solved(base, wrap.harness, "test", final=True))
    s = {x["stage"][:2]: x["selection_solved"] for x in stages}
    return {"arm": arm, "seed": seed, "stages": stages, "jobs": jobs,
            "jobs_launched": sum(j["launched"] for j in jobs), "jobs_hurt": sum(j["hurt"] for j in jobs),
            "jobs_skipped": sum(not j["launched"] for j in jobs),
            "base_selection": s["S0"], "dip_at_revision": s["S2"] - s["S0"],
            "final_candidate": best_name, "final_test_solved": final, "base_test_solved": base_test,
            "trajectories_used": len(used), "test_reads": world.test_reads,
            "record_entries": len(rec) if arm == "katie" else 0}
