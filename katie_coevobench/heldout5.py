"""Held-out set 5 (OCME-009-evo), written by Turdy. python -m katie_coevobench.heldout5

The set is Turdy's: heldout5/changes.json and heldout5/ground_truth.json, sealed in heldout5/SEAL.json before any call.
Priors are NOT the ones typed in changes.json. Each prior is built from the real judgment this run produced for the
named earlier change (its `source_run`), and its `next_job_hurt` is derived from a Control-arm simulation of that change,
using only the change's own example outcomes. The judge code never reads the truth; the truth is loaded after the calls.
"""
from __future__ import annotations
import collections, json, subprocess, sys, time
from pathlib import Path
from .arms import run_arm
from .erie import Erie, Outcome
from .heldout import sha
from .judge import NimJudge, parse_verdict, cited_ids
from .record import Record
from .scenarios import Scenario

DIR = Path(__file__).resolve().parent.parent / "heldout5"
RUN_ORDER = ["H5-N1", "H5-N2", "H5-L1", "H5-L2", "H5-N3", "H5-L3", "H5-A1", "H5-A2", "H5-A3", "H5-A4"]   # from the order


def frozen_hashes(ref: str | None = None) -> dict[str, str]:
    """What must not change between OCME-004 and this run: the prompt, the backstop, ERIE, and judge.py except its MODEL line.
    ref=None reads the working tree (used when sealing); ref=<commit> reads the code as it stood at that commit,
    so the freeze stays checkable after later OCMEs change the judge."""
    import hashlib, re
    root = DIR.parent / "katie_coevobench"

    def read(name: str) -> str:
        if ref is None:
            return (root / name).read_bytes().decode("utf-8").replace("\r\n", "\n")
        out = subprocess.run(["git", "show", f"{ref}:katie_coevobench/{name}"], capture_output=True, cwd=DIR.parent)
        return out.stdout.decode("utf-8").replace("\r\n", "\n")
    j = read("judge.py")
    prompt = j.split('\nPROMPT = """', 1)[1].split('"""', 1)[0]
    backstop = re.search(r"def check_against_packet.*?\n\n\ndef parse_verdict", j, re.S).group(0)
    h = lambda s: hashlib.sha256(s.encode("utf-8")).hexdigest()
    return {"PROMPT": h(prompt), "backstop": h(backstop),
            "judge.py without MODEL line": h(re.sub(r"(?m)^MODEL = .*$", "MODEL = <id>", j)),
            "erie.py": h(read("erie.py"))}


def load_changes() -> dict[str, dict]:
    return {c["id"]: c for c in json.loads((DIR / "changes.json").read_text(encoding="utf-8"))}


def outcomes(c) -> tuple[Outcome, ...]:
    return tuple(Outcome(o["task"], o["old_answer"], o["new_answer"], o["touched"]) for o in c["outcomes"])


def any_answer_changed(c) -> bool:
    return any(o["old_answer"] != o["new_answer"] for o in c["outcomes"])


def derived_hurt(c) -> bool:
    """Did the next training job hurt after this change? Control arm in the sim; hidden epoch = did any example answer move."""
    sc = Scenario(c["id"] + "-prior", c["new_text"], outcomes(c), "", any_answer_changed(c), c["old_text"])
    return run_arm("control", 1, None, sc)["jobs_hurt"] > 0


def build_priors(c, verdicts: dict[str, dict]) -> list[dict]:
    """Real priors: the judgment from each named earlier run, as the system returned it. Nothing typed in the file is used."""
    out = []
    for p in c["priors"]:
        v = verdicts[p["source_run"]]            # earlier in RUN_ORDER, so it exists
        out.append({"source_run": p["source_run"], "kind": v["kind"], "reason": v["reason"], "failed": v["failed"],
                    "next_job_hurt": v["next_job_hurt"],
                    "file_said": {"kind": p["kind"], "next_job_hurt": p["next_job_hurt"]}})
    return out


def seed_record(rec: Record, priors: list[dict]) -> None:
    for p in priors:
        rec.append("judgment", 6, f"run:{p['source_run']}", f"earlier harness change {p['source_run']} classified {p['kind']}",
                   p["reason"], judged_kind=p["kind"], failed=p["failed"], evidence="from this test's earlier run")
        rec.append("training_job", 6, f"run:{p['source_run']}", f"job after {p['source_run']}", "derived from the Control-arm simulation",
                   hurt=p["next_job_hurt"])


def summarize(rows: list[dict], c) -> dict:
    """The system's judgment for one change: the most common post-backstop kind over its calls (a 3-way split is ambiguous)."""
    kinds = collections.Counter(r["kind"] for r in rows)
    top, n = kinds.most_common(1)[0]
    if sum(1 for k in kinds.values() if k == n) > 1:
        top = "ambiguous"
    first = next((r for r in rows if r["kind"] == top), rows[0])
    return {"kind": top, "reason": first["reason"], "failed": first["failed"], "next_job_hurt": derived_hurt(c)}


def run_calls(judge, calls: int, order=RUN_ORDER) -> tuple[list[dict], dict]:
    """Judge calls only. This function never touches the ground truth."""
    changes, rows, verdicts = load_changes(), [], {}
    for cid in order:
        c = changes[cid]
        priors = build_priors(c, verdicts)
        rec = Record()
        seed_record(rec, priors)
        packet = Erie().retrieve(rec, outcomes(c), cid)
        mine = []
        for n in range(1, calls + 1):
            t0 = time.monotonic()
            try:
                raw = judge.raw(c["old_text"], c["new_text"], packet)
            except Exception as e:
                raw = None
                print(cid, "request failed:", type(e).__name__)
            seconds = round(time.monotonic() - t0, 2)
            model = parse_verdict(raw)
            v = parse_verdict(raw, packet)
            row = {"id": cid, "call": n, "model_kind": model.kind, "model_failed": model.failed, "kind": v.kind,
                   "failed": v.failed, "reason": v.reason, "evidence": v.evidence, "cited": cited_ids(v.evidence),
                   "backstop_changed_it": v.kind != model.kind or v.failed != model.failed,
                   "priors_in_packet": sum(e.type == "prior" for e in packet.items), "prior_provenance": priors, "raw_reply": raw,
                   "seconds": seconds}
            mine.append(row)
            rows.append(row)
            print(cid, n, v.kind, "FAILED" if v.failed else "ok", "| model alone:", model.kind)
        verdicts[cid] = summarize(mine, c)
    return rows, verdicts


def pipeline(judge, truth: dict, verdicts: dict) -> list[dict]:
    """Full pipeline on the logical and ambiguous changes. Ambiguous runs under both hidden truths."""
    changes, out = load_changes(), []
    for cid in RUN_ORDER:
        c, kind = changes[cid], truth[cid]["kind"]
        if kind == "noise":
            continue
        priors = build_priors(c, verdicts)
        # ambiguous and partial both hold, so both run under both hidden truths
        variants = [("", True)] if kind == "logical" else [("-matters", True), ("-harmless", False)]
        for suffix, epoch in variants:
            sc = Scenario(cid + suffix, c["new_text"], outcomes(c), kind, epoch, c["old_text"])
            k = run_arm("katie", 1, None, sc, judge, record_seed=lambda rec, p=priors: seed_record(rec, p))
            ct = run_arm("control", 1, None, sc)
            out.append({"change": sc.name, "truth_kind": kind, "judge_kind": k["judge_kind"], "judge_failed": k["judge_failed"],
                        "judge_correct": k["judge_kind"] == kind,
                        "katie_stages": [s["selection_solved"] for s in k["stages"]],
                        "control_stages": [s["selection_solved"] for s in ct["stages"]],
                        "katie_jobs_skipped": k["jobs_skipped"], "katie_jobs_hurt": k["jobs_hurt"],
                        "control_jobs_hurt": ct["jobs_hurt"], "katie_dip": k["dip_at_revision"], "control_dip": ct["dip_at_revision"],
                        "katie_final_test": k["final_test_solved"], "control_final_test": ct["final_test_solved"],
                        "ends_equal": k["final_selection"] == ct["final_selection"]})
            print(sc.name, "judge", k["judge_kind"], "katie", out[-1]["katie_stages"], "control", out[-1]["control_stages"])
    return out


def main(calls: int = 3):
    seal = json.loads((DIR / "SEAL.json").read_text(encoding="utf-8"))
    for f, h in seal["sealed"].items():
        assert sha(DIR.parent / f) == h, f"{f} changed after sealing"
    judge = NimJudge(model=seal["judge_model"], timeout=900)           # model sealed for this run; long timeout so a slow reasoning reply is not a false failure
    rows, verdicts = run_calls(judge, calls)             # step 1: judge calls, truth unseen
    truth = json.loads((DIR / "ground_truth.json").read_text(encoding="utf-8"))["truth"]   # step 2: only now
    for r in rows:
        r["truth_kind"] = truth[r["id"]]["kind"]
        r["correct"] = r["kind"] == r["truth_kind"]
        r["model_correct"] = r["model_kind"] == r["truth_kind"] and not r["model_failed"]
    git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=DIR.parent).stdout.strip()
    Path("results").mkdir(exist_ok=True)
    Path("results/live-judge-held-out-5.json").write_text(json.dumps({
        "model": seal["judge_model"], "calls_per_change": calls, "git_head_at_run": git, "seal": seal, "run_order": RUN_ORDER,
        "correct_after_backstop": sum(r["correct"] for r in rows), "total": len(rows),
        "correct_model_alone": sum(r["model_correct"] for r in rows),
        "seconds_total_30_calls": round(sum(r["seconds"] for r in rows), 1),
        "seconds_per_call": {"min": min(r["seconds"] for r in rows), "max": max(r["seconds"] for r in rows),
                             "mean": round(sum(r["seconds"] for r in rows) / len(rows), 2)},
        "rows": rows}, indent=1), encoding="utf-8")
    p = pipeline(judge, truth, verdicts)
    Path("results/pipeline-held-out-5.json").write_text(json.dumps(p, indent=1), encoding="utf-8")
    print("held-out 5:", sum(r["correct"] for r in rows), "/", len(rows), "after backstop;",
          sum(r["model_correct"] for r in rows), "/", len(rows), "model alone;",
          round(sum(r["seconds"] for r in rows), 1), "s for the calls")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 3)
