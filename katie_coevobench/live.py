"""python -m katie_coevobench.live -> one real round trip per script, printed and saved without the key."""
import json
from pathlib import Path
from .judge import NimJudge, build_prompt, parse_verdict, MODEL
from .scenarios import SCENARIOS, OLD


def main():
    j = NimJudge()   # raises if NIM_API_KEY is unset: nothing is invented
    rows = []
    for name in ("noise", "logical", "ambiguous_matters"):
        sc = SCENARIOS[name]
        try:
            raw = j.raw(OLD, sc.new_text, list(sc.examples))
        except Exception as e:
            raw = None
            print(name, "REQUEST FAILED", type(e).__name__)
        v = parse_verdict(raw)
        rows.append({"script": name, "expected": sc.true_kind, "kind": v.kind, "failed": v.failed,
                     "reason": v.reason, "evidence": v.evidence, "raw_reply": raw})
        print(name, "expected", sc.true_kind, "got", v.kind, "failed" if v.failed else "ok", "|", v.reason)
    Path("results").mkdir(exist_ok=True)
    Path("results/live-judge.json").write_text(json.dumps({"model": MODEL, "base_url": j.base_url, "rows": rows}, indent=1),
                                               encoding="utf-8")


if __name__ == "__main__":
    main()
