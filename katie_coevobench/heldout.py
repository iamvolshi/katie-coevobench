"""Held-out judge test (OCME-004-evo). python -m katie_coevobench.heldout [calls]

Order of work, enforced here: (1) call the live judge for every change, with no access to the ground truth;
(2) only then load the sealed ground truth and score. Prompt, ERIE and the backstop are frozen (heldout/SEAL.json).
Needs NIM_API_KEY. Writes results/live-judge-held-out.json and results/pipeline-held-out.json (no key in either).
"""
from __future__ import annotations
import hashlib, json, subprocess, sys
from pathlib import Path
from .arms import run_arm
from .erie import Erie, Outcome
from .judge import NimJudge, parse_verdict, MODEL, cited_ids
from .record import Record
from .scenarios import Scenario

DIR = Path(__file__).resolve().parent.parent / "heldout"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def load_changes() -> list[dict]:
    return json.loads((DIR / "changes.json").read_text(encoding="utf-8"))


def outcomes(c) -> tuple[Outcome, ...]:
    return tuple(Outcome(o["task"], o["old_answer"], o["new_answer"], o["touched"]) for o in c["outcomes"])


def seed_record(rec: Record, priors) -> None:
    """History that already sits in the record before this change: each prior judgment and what its next job did."""
    for p in priors:
        rec.append("judgment", 6, "seed:held-out history", f"earlier harness change classified {p['kind']}", p["reason"],
                   judged_kind=p["kind"], failed=False, evidence="seeded")
        rec.append("training_job", 6, "seed:held-out history", "job after the earlier change", p["reason"],
                   hurt=p["next_job_hurt"])


def run_calls(calls: int) -> list[dict]:
    """Live judge calls only. This function never touches the ground truth."""
    judge, rows = NimJudge(), []
    for c in load_changes():
        rec = Record()
        seed_record(rec, c["priors"])
        packet = Erie().retrieve(rec, outcomes(c), c["id"])
        for n in range(1, calls + 1):
            try:
                raw = judge.raw(c["old_text"], c["new_text"], packet)
            except Exception as e:
                raw = None
                print(c["id"], "request failed:", type(e).__name__)
            model = parse_verdict(raw)                 # what the model said, before the backstop
            v = parse_verdict(raw, packet)             # what the judge returns after the backstop
            rows.append({"id": c["id"], "call": n, "model_kind": model.kind, "model_failed": model.failed,
                         "kind": v.kind, "failed": v.failed, "reason": v.reason, "evidence": v.evidence,
                         "cited": cited_ids(v.evidence), "backstop_changed_it": v.kind != model.kind or v.failed != model.failed,
                         "priors_in_packet": sum(e.type == "prior" for e in packet.items), "raw_reply": raw})
            print(c["id"], n, v.kind, "FAILED" if v.failed else "ok")
    return rows


def pipeline(truth: dict) -> list[dict]:
    """Full pipeline with the live judge on the logical and ambiguous changes. Ambiguous runs under both hidden truths."""
    judge, out = NimJudge(), []
    for c in load_changes():
        kind = truth[c["id"]]["kind"]
        if kind == "noise":
            continue
        variants = [("", True)] if kind == "logical" else [("-matters", True), ("-harmless", False)]
        for suffix, epoch in variants:
            sc = Scenario(c["id"] + suffix, c["new_text"], outcomes(c), kind, epoch, c["old_text"])
            seed = lambda rec, c=c: seed_record(rec, c["priors"])
            k = run_arm("katie", 1, None, sc, judge, record_seed=seed)
            ct = run_arm("control", 1, None, sc)
            out.append({"change": sc.name, "truth_kind": kind, "judge_kind": k["judge_kind"], "judge_failed": k["judge_failed"],
                        "katie_stages": [s["selection_solved"] for s in k["stages"]],
                        "control_stages": [s["selection_solved"] for s in ct["stages"]],
                        "katie_jobs_skipped": k["jobs_skipped"], "katie_jobs_hurt": k["jobs_hurt"],
                        "control_jobs_skipped": ct["jobs_skipped"], "control_jobs_hurt": ct["jobs_hurt"],
                        "katie_dip": k["dip_at_revision"], "control_dip": ct["dip_at_revision"],
                        "katie_final_test": k["final_test_solved"], "control_final_test": ct["final_test_solved"],
                        "ends_equal": k["final_selection"] == ct["final_selection"]})
            print(sc.name, "judge", k["judge_kind"], "katie", out[-1]["katie_stages"], "control", out[-1]["control_stages"])
    return out


def main(calls: int = 3):
    seal = json.loads((DIR / "SEAL.json").read_text(encoding="utf-8"))
    for f, h in seal["sealed"].items():
        assert sha(DIR.parent / f) == h, f"{f} changed after sealing"
    rows = run_calls(calls)                              # step 1: judge calls, truth unseen
    truth = json.loads((DIR / "ground_truth.json").read_text(encoding="utf-8"))["truth"]   # step 2: only now
    for r in rows:
        r["truth_kind"] = truth[r["id"]]["kind"]
        r["correct"] = r["kind"] == r["truth_kind"]
        r["model_correct"] = r["model_kind"] == r["truth_kind"]
    git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=DIR.parent).stdout.strip()
    Path("results").mkdir(exist_ok=True)
    Path("results/live-judge-held-out.json").write_text(json.dumps({
        "model": MODEL, "calls_per_change": calls, "git_head_at_run": git, "seal": seal,
        "correct": sum(r["correct"] for r in rows), "total": len(rows),
        "model_correct_before_backstop": sum(r["model_correct"] for r in rows), "rows": rows}, indent=1), encoding="utf-8")
    p = pipeline(truth)
    for r in p:
        r["judge_correct"] = r["judge_kind"] == r["truth_kind"]
    Path("results/pipeline-held-out.json").write_text(json.dumps(p, indent=1), encoding="utf-8")
    print("held-out:", sum(r["correct"] for r in rows), "/", len(rows), "after backstop;",
          sum(r["model_correct"] for r in rows), "/", len(rows), "model alone")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 3)
