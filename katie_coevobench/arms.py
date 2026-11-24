"""The researcher loop (one script, both arms) and the two arms' wrappers.

Both arms run the same scripted researcher: collect rollouts, train on everything it has, revise the
harness once, retrain if the result is below Base. The only difference is the wrapper.
Control: raw untagged history, no gate, no judge.
KATIE: wraps the loop. A judge (judge.py) classifies each harness change; KATIE decides what the kind means.
"""
from __future__ import annotations
from pathlib import Path
from .record import Record
from .sim import World, Weights, Traj
from .judge import Judge, StubJudge, Verdict, cited_ids
from .erie import Erie, Packet
from .scenarios import SCENARIOS, OLD, STUB_TABLE

MIN_TRAIN = 40   # ASSUMPTION: a training job needs at least 40 trajectories
N_FIRST, N_FRESH_1, N_FRESH_2 = 40, 20, 20


class ControlWrapper:
    """Paper's raw history: append everything, no tags, no gate."""
    name = "control"

    def __init__(self):
        self.history: list[Traj] = []
        self._post: list[Traj] = []
        self.hold = False

    def revise(self, version, why, verdict=None, packet=None):
        self._post = []

    def add(self, trajs):
        self.history += trajs
        self._post += trajs

    def train_data(self, since_revision=False):
        return list(self._post if since_revision else self.history)

    def filter_for_training(self, trajs, why):
        return list(trajs), None

    def log_job(self, w, trajs, hurt):
        pass

    def serve(self, w):
        return w


class KatieWrapper:
    """Every harness, judgment, hold, trajectory, job and refusal gets a KID in its own record.

    Epoch = a run of harness versions that share the same correct answers. Noise keeps the epoch,
    logical starts a new one, ambiguous holds until probed. Data and weights are usable only in the current epoch.
    """
    name = "katie"

    def __init__(self, record: Record):
        self.rec = record
        self.hkid: str | None = None
        self.epoch_of: dict[str, int] = {}      # harness KID -> epoch
        self.hold: str | None = None            # KID of the open hold entry
        self.history: list[Traj] = []
        self.wkid: dict[int, str | None] = {}   # id(weights) -> harness KID it was trained under
        self._hk: dict[str, str] = {}           # trajectory KID -> harness KID it was collected under

    @property
    def epoch(self) -> int:
        return self.epoch_of[self.hkid]

    def revise(self, version, why, verdict: Verdict | None = None, packet: Packet | None = None):
        prev = self.hkid
        e = self.rec.append("harness", 7, "researcher", f"harness {version}", why, supersedes=prev, version=version)
        self.hkid = e.kid
        if prev is None:
            self.epoch_of[e.kid] = 0
            return
        n = self.epoch_of[prev]
        if verdict is None or verdict.kind == "logical":    # no judgment = Test 1 behavior: every revision is a new epoch
            n += 1
        self.epoch_of[e.kid] = n
        if verdict is None:
            return
        ev_kid = None
        if packet is not None:   # the retrieved packet is recorded as retrieved, before the judge's verdict is
            ev_kid = self.rec.append("evidence", 6, "erie", f"evidence packet for the change to {version}",
                                     f"{len(packet.items)} items retrieved read-only for the judge",
                                     harness_kid=e.kid, items=packet.to_data()).kid
        j = self.rec.append("judgment", 6, "judge", f"harness change classified {verdict.kind}", verdict.reason,
                            harness_kid=e.kid, prior_harness_kid=prev, judged_kind=verdict.kind,
                            evidence=verdict.evidence, failed=verdict.failed, evidence_kid=ev_kid,
                            cited=cited_ids(verdict.evidence))
        if verdict.kind == "ambiguous":
            h = self.rec.append("hold", 8, "gate", "change marked unsure; old trajectories held",
                                verdict.reason, harness_kid=e.kid, judgment_kid=j.kid)
            self.hold = h.kid

    def resolve(self, kind: str, evidence: str):
        """A probe settled the open hold. The hold entry stays; a resolution entry supersedes it."""
        assert self.hold, "no open hold"
        self.rec.append("resolution", 8, "probe", f"hold resolved as {kind}", evidence,
                        supersedes=self.hold, harness_kid=self.hkid, resolved_kind=kind)
        if kind == "logical":
            self.epoch_of[self.hkid] += 1
        self.hold = None

    def add(self, trajs):
        for t in trajs:
            e = self.rec.append("trajectory", 5, "rollout", f"rollout {t.task}", "evidence for later training",
                                harness_kid=self.hkid, task=t.task)
            t.kid = e.kid
            self._hk[t.kid] = self.hkid
            self.history.append(t)

    def filter_for_training(self, trajs, why):
        ok = [t for t in trajs if self.epoch_of[self._hk[t.kid]] == self.epoch]
        stale = len(trajs) - len(ok)
        if self.hold and len({self._hk[t.kid] for t in trajs}) > 1:
            e = self.rec.append("refusal", 8, "gate", "training refused: mixed set under an open hold",
                                f"change is unsure ({self.hold}); {len(trajs)} trajectories span more than one harness; {why}",
                                hold_kid=self.hold, size=len(trajs))
            return [], e.kid
        if len(ok) < MIN_TRAIN:
            e = self.rec.append("refusal", 8, "gate",
                                f"training refused: {len(ok)} trajectories match harness {self.hkid}, need {MIN_TRAIN}",
                                f"{stale} stale-harness trajectories excluded; {why}",
                                current_harness_kid=self.hkid, stale=stale, matching=len(ok))
            return ok, e.kid
        return ok, None

    def log_job(self, w, trajs, hurt):
        e = self.rec.append("training_job", 6, "trainer", f"trained {w.name} on {len(trajs)} trajectories",
                            f"every trajectory is in the current epoch; harness KID {self.hkid}",
                            harness_kid=self.hkid, trajectory_kids=[t.kid for t in trajs], hurt=hurt)
        self.wkid[id(w)] = self.hkid
        return e

    def serve(self, w: Weights):
        """Weights from another epoch, or from before an open hold, are not served; Base is."""
        k = self.wkid.get(id(w))
        if not w.trained_on:
            return w
        if self.epoch_of[k] != self.epoch or (self.hold and k != self.hkid):
            why = "unsure change on hold" if self.hold else f"trained under harness KID {k}, a different epoch"
            self.rec.append("refusal", 8, "gate", f"weights {w.name} not served under harness {self.hkid}",
                            f"{why}; falling back to Base weights", weights_harness_kid=k, current_harness_kid=self.hkid)
            return Weights("base")
        return w


def run_arm(arm: str, seed: int, out: Path | None = None, scenario: str = "logical",
            judge: Judge | None = None, mix: str = "linear", erie=None) -> dict:
    sc = SCENARIOS[scenario]
    world = World(seed, mix)
    tag = f"{scenario}-{mix}-{seed}"
    rec = Record(out / f"record-{arm}-{tag}.jsonl") if out and arm == "katie" else Record()
    wrap = KatieWrapper(rec) if arm == "katie" else ControlWrapper()
    judge = judge or StubJudge(STUB_TABLE)
    erie = erie or Erie()
    stages, jobs, used = [], [], []
    base = Weights("base")
    cur = "H0"   # ground-truth epoch label the simulator scores against

    def sel(w):
        return len(world.solved(w, cur, "selection"))

    def stage(name, w, note):
        stages.append({"stage": name, "weights": w.name, "selection_solved": sel(w), "note": note})

    def train(name, trajs):
        w = Weights(name, [t.harness for t in trajs])
        hurt = sel(w) < sel(base)
        wrap.log_job(w, trajs, hurt)
        jobs.append({"job": len(jobs) + 1, "weights": name, "trajectories": len(trajs), "launched": True,
                     "hurt": hurt, "true_stale_in_data": sum(t.harness != cur for t in trajs)})
        used.extend(t.tid for t in trajs)
        return w

    wrap.revise("V0", "initial harness")
    stage("S0 base, old harness", base, "Base weights")
    wrap.add(world.collect("H0", N_FIRST))
    w1 = train("w1", list(wrap.history))
    stage("S1 trained, old harness", w1, "job 1")

    verdict = packet = None
    if arm == "katie":
        packet = erie.retrieve(rec, sc.outcomes, scenario)          # ERIE retrieves
        verdict = judge.judge(OLD, sc.new_text, packet)             # the judge classifies; KATIE acts below
    wrap.revise("V1", f"researcher revised the harness ({scenario})", verdict, packet)
    cur = "H1" if sc.epoch_changes else "H0"
    served = wrap.serve(w1)
    stage("S2 harness revised, same weights", served,
          "w1 served as is" if served is w1 else "KATIE did not serve w1; Base served")
    cands = {served.name + "@S2": served}

    fresh1 = world.collect(cur, N_FRESH_1)
    wrap.add(fresh1)
    ok, refusal = wrap.filter_for_training(list(wrap.history), "retrain request after revision")
    post_job = None
    if refusal:
        jobs.append({"job": len(jobs) + 1, "weights": "w2", "trajectories": len(ok), "launched": False,
                     "hurt": False, "refusal_kid": refusal})
        stage("S3 retrain attempt 1", served, f"refused ({refusal}), job skipped")
    else:
        post_job = train("w2", ok if arm == "katie" else wrap.train_data())
        cands["w2"] = post_job
        stage("S3 retrain attempt 1", post_job, "trained on whole history")

    probe = None
    if arm == "katie" and wrap.hold:
        # Probe: run the held weights on the selection set under both harnesses. Selection use only.
        before, after = len(world.solved(w1, "H0", "selection")), len(world.solved(w1, cur, "selection"))
        probe = "logical" if before != after else "noise"
        wrap.resolve(probe, f"w1 solves {before} before and {after} after the change on the selection set")

    wrap.add(world.collect(cur, N_FRESH_2))
    if arm == "control":
        data = wrap.train_data(since_revision=True) if post_job and sel(post_job) < sel(base) else []
    elif post_job is None or sel(post_job) < sel(base):
        data, refusal = wrap.filter_for_training(list(wrap.history), "retrain request, more fresh rollouts")
        data = [] if refusal else data
    else:
        data = []
    if data:
        w3 = train("w3", data)
        cands["w3"] = w3
        stage("S4 retrain on fresh data", w3, "post-revision trajectories only" if arm == "control" else "gated by epoch")
    else:
        stage("S4 no further job", post_job or served, "no retrain needed")

    best = cands[max(cands, key=lambda k: sel(cands[k]))]
    final = len(world.solved(best, cur, "test", final=True))
    base_test = len(world.solved(base, cur, "test", final=True))
    s = {x["stage"][:2]: x["selection_solved"] for x in stages}
    out_d = {"arm": arm, "seed": seed, "scenario": scenario, "mix": mix, "stages": stages, "jobs": jobs,
             "jobs_launched": sum(j["launched"] for j in jobs), "jobs_hurt": sum(j["hurt"] for j in jobs),
             "jobs_skipped": sum(not j["launched"] for j in jobs),
             "base_selection": s["S0"], "dip_at_revision": s["S2"] - s["S0"], "s3": s["S3"],
             "final_selection": s["S4"], "final_test_solved": final, "base_test_solved": base_test,
             "trajectories_used": len(used), "test_reads": world.test_reads,
             "record_entries": len(rec) if arm == "katie" else 0}
    if verdict:
        out_d.update(judge_kind=verdict.kind, judge_failed=verdict.failed, true_kind=sc.true_kind,
                     judge_correct=verdict.kind == sc.true_kind, probe=probe)
    return out_d
