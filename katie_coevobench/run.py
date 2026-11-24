"""python -m katie_coevobench.run  -> runs both arms, 3 seeds each, writes results/results.json"""
import json
from pathlib import Path
from .arms import run_arm

SEEDS = (1, 2, 3)


def main(out: Path = Path("results")):
    out.mkdir(exist_ok=True)
    res = [run_arm(a, s, out) for a in ("control", "katie") for s in SEEDS]
    (out / "results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    for r in res:
        print(r["arm"], r["seed"], [x["selection_solved"] for x in r["stages"]],
              "launched", r["jobs_launched"], "hurt", r["jobs_hurt"], "skipped", r["jobs_skipped"],
              "dip", r["dip_at_revision"], "test", r["final_test_solved"], "/ base", r["base_test_solved"])
    return res


if __name__ == "__main__":
    main()
