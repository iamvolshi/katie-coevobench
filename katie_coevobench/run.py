"""python -m katie_coevobench.run [--live]  -> both arms, all scripts, 3 seeds, three mix rules.

Default judge is the stub (no key). --live uses Nemotron through NIM_API_KEY / NIM_BASE_URL.
"""
import json, sys
from pathlib import Path
from .arms import run_arm
from .judge import NimJudge
from .scenarios import SCENARIOS
from .sim import MIX_RULES

SEEDS = (1, 2, 3)


def main(out: Path = Path("results"), live: bool = False):
    out.mkdir(exist_ok=True)
    judge = NimJudge() if live else None
    res = []
    for mix in MIX_RULES:
        for sc in (SCENARIOS if mix == "linear" else ("logical",)):   # other mix rules: the Test 1 case only
            for arm in ("control", "katie"):
                for s in SEEDS:
                    res.append(run_arm(arm, s, out, sc, judge, mix))
    name = "results-live.json" if live else "results.json"
    (out / name).write_text(json.dumps(res, indent=1), encoding="utf-8")
    for r in res:
        if r["seed"] == 1:
            print(r["scenario"], r["mix"], r["arm"], [x["selection_solved"] for x in r["stages"]],
                  "launched", r["jobs_launched"], "hurt", r["jobs_hurt"], "skipped", r["jobs_skipped"],
                  "dip", r["dip_at_revision"], "test", r["final_test_solved"], "/", r["base_test_solved"],
                  r.get("judge_kind", ""))
    return res


if __name__ == "__main__":
    main(live="--live" in sys.argv)
