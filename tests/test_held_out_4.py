import hashlib, inspect, json, re, subprocess, unittest
from pathlib import Path
from katie_coevobench import heldout4, judge
from katie_coevobench.erie import Erie
from katie_coevobench.heldout import sha
from katie_coevobench.judge import Judge

ROOT = Path(__file__).resolve().parent.parent
H = ROOT / "heldout4"
SEAL = json.loads((H / "SEAL.json").read_text(encoding="utf-8"))
TRUTH = json.loads((H / "ground_truth.json").read_text(encoding="utf-8"))
CHANGES = heldout4.load_changes()
RES = ROOT / "results" / "live-judge-held-out-4.json"


def git(*a, raw=False):
    r = subprocess.run(["git", *a], capture_output=True, cwd=ROOT)
    return r.returncode, (r.stdout if raw else r.stdout.decode("utf-8", "replace").strip())


class Turdys(unittest.TestCase):
    def test_set_shape(self):
        kinds = [t["kind"] for t in TRUTH["truth"].values()]
        self.assertEqual((kinds.count("noise"), kinds.count("logical"), kinds.count("ambiguous"), kinds.count("partial")), (3, 3, 2, 2))
        self.assertEqual(set(CHANGES), set(TRUTH["truth"]))
        self.assertEqual(heldout4.RUN_ORDER, TRUTH["run_order"])

    def test_written_by_turdy_not_the_builder(self):
        self.assertIn("Written by Turdy", (H / "README.md").read_text(encoding="utf-8"))
        self.assertEqual(TRUTH["written_by"][:5], "Turdy")
        code, authors = git("log", "--format=%an", "--", "heldout4/changes.json", "heldout4/ground_truth.json", "heldout4/README.md")
        first_batch = [a for a in authors.splitlines()]
        self.assertEqual(first_batch[-1], "Turdy")                       # the commit that added the files
        code, blob = git("cat-file", "blob", "0f4d231:heldout4/changes.json", raw=True)
        if code == 0:                                                    # sealed bytes are exactly Turdy's
            self.assertEqual(hashlib.sha256(blob.replace(b"\r\n", b"\n")).hexdigest(), SEAL["sealed"]["heldout4/changes.json"])
        code, blob = git("cat-file", "blob", "0f4d231:heldout4/ground_truth.json", raw=True)
        if code == 0:
            self.assertEqual(hashlib.sha256(blob.replace(b"\r\n", b"\n")).hexdigest(), SEAL["sealed"]["heldout4/ground_truth.json"])
        # a git author name is self-declared; the commit and the files are what is checked, not identity
        self.assertEqual(SEAL["turdy_commit"], "0f4d231")


class Sealed(unittest.TestCase):
    def test_hashes_match_the_seal(self):
        for f, h in SEAL["sealed"].items():
            self.assertEqual(sha(ROOT / f), h, f)

    def test_judge_code_never_reads_the_truth(self):
        for m in ("judge", "erie", "arms", "scenarios", "record", "sim"):
            src = (ROOT / "katie_coevobench" / f"{m}.py").read_text(encoding="utf-8")
            for bad in ("ground_truth", "heldout"):
                self.assertNotIn(bad, src, m)
        body = inspect.getsource(heldout4.run_calls).split('"""')[2]
        for bad in ("truth", "ground"):
            self.assertNotIn(bad, body)
        for fn in (heldout4.build_priors, heldout4.seed_record, heldout4.summarize, heldout4.derived_hurt):
            self.assertNotIn("ground_truth", inspect.getsource(fn))

    def test_truth_loaded_only_after_the_calls(self):
        src = inspect.getsource(heldout4.main)
        self.assertLess(src.index("run_calls(judge, calls)"), src.index("ground_truth.json"))

    def test_sealed_before_the_first_call(self):
        if not RES.exists():
            self.skipTest("live run not done yet")
        r = json.loads(RES.read_text(encoding="utf-8"))
        self.assertEqual(r["seal"], SEAL)
        code, seal = git("log", "--format=%H", "--grep=^SEAL4:")
        seal = seal.splitlines()[-1]
        self.assertEqual(git("merge-base", "--is-ancestor", seal, r["git_head_at_run"])[0], 0)
        _, added = git("log", "--diff-filter=A", "--format=%H", "--", "results/live-judge-held-out-4.json")
        self.assertEqual(git("merge-base", "--is-ancestor", seal, added.splitlines()[-1])[0], 0)
        self.assertNotEqual(seal, added.splitlines()[-1])


class Model(unittest.TestCase):
    def test_judge_was_k3(self):
        self.assertEqual(SEAL["judge_model"], "moonshotai/kimi-k3.1-pro")
        mc = json.loads((ROOT / "heldout3" / "model_check.json").read_text(encoding="utf-8"))
        self.assertIn(SEAL["judge_model"], mc["catalog_ids"])
        self.assertIn("timeout=900", inspect.getsource(heldout4.main))
        if RES.exists():
            self.assertEqual(json.loads(RES.read_text(encoding="utf-8"))["model"], SEAL["judge_model"])

    def test_sealed_code_is_the_code_that_ran(self):
        self.assertEqual(heldout4.frozen_hashes("bb1387a"), SEAL["frozen"])   # the code as it stood at the seal
        src = inspect.getsource(judge.NimJudge)
        self.assertIn('"temperature": 0', src)
        self.assertIn('"max_tokens": 8192', src)

    def test_prompt_changed_by_exactly_one_line_since_set_3(self):
        code, old = git("show", "7a65c44:katie_coevobench/judge.py")
        if code:
            self.skipTest("7a65c44 not available")
        old_p = old.replace("\r\n", "\n").split('\nPROMPT = """', 1)[1].split('"""', 1)[0].splitlines()
        j4 = git("show", "bb1387a:katie_coevobench/judge.py")[1].replace("\r\n", "\n")
        new_p = j4.split('\nPROMPT = """', 1)[1].split('"""', 1)[0].splitlines()
        self.assertEqual(len(new_p), len(old_p) + 1)
        added = [l for l in new_p if l not in old_p]
        self.assertEqual(added, ["5. If the coverage is partial, one touched example and one untouched example, say partial, not noise."])
        self.assertEqual([l for l in new_p if l not in added], old_p)

    def test_erie_unchanged_since_set_3(self):
        self.assertEqual(heldout4.frozen_hashes()["erie.py"], heldout4.frozen_hashes("7a65c44")["erie.py"])


class FakeJudge(Judge):
    """Says ambiguous for H4-N1 (the file says noise), noise elsewhere when it can; records what it was shown."""
    def __init__(self):
        self.seen = {}

    def raw(self, old, new, packet):
        cid = next(c["id"] for c in CHANGES.values() if c["new_text"] == new)
        self.seen[cid] = packet
        kind = "ambiguous" if cid == "H4-N1" else "logical" if any(e.shows == "changed" and e.type == "example" for e in packet.items) else "noise"
        cites = ", ".join(e.id for e in packet.items if e.type == "example")
        return json.dumps({"kind": kind, "reason": f"fake verdict for {cid}", "evidence": cites})


class Priors(unittest.TestCase):
    def test_at_least_four_changes_point_at_earlier_runs(self):
        order = heldout4.RUN_ORDER
        n = 0
        for cid, c in CHANGES.items():
            for p in c["priors"]:
                self.assertLess(order.index(p["source_run"]), order.index(cid))
                n += 1
        self.assertGreaterEqual(sum(bool(c["priors"]) for c in CHANGES.values()), 4)

    def test_priors_come_from_the_run_not_from_the_file(self):
        j = FakeJudge()
        rows, verdicts = heldout4.run_calls(j, 1)
        n3 = [r for r in rows if r["id"] == "H4-N3"][0]
        self.assertEqual(n3["prior_provenance"][0]["source_run"], "H4-N1")
        self.assertEqual(n3["prior_provenance"][0]["kind"], "ambiguous")       # the run said ambiguous
        self.assertEqual(n3["prior_provenance"][0]["file_said"]["kind"], "noise")  # the file said noise; unused
        prior = [e for e in j.seen["H4-N3"].items if e.type == "prior"]
        self.assertEqual(len(prior), 1)
        self.assertIn("judged ambiguous", prior[0].text)
        a2 = [e for e in j.seen["H4-A2"].items if e.type == "prior"]
        self.assertEqual(len(a2), 2)                                           # H4-N2 and H4-L2
        self.assertEqual(len([e for e in j.seen["H4-A4"].items if e.type == "prior"]), 1)
        self.assertEqual(sum(r["priors_in_packet"] > 0 for r in rows), 4)

    def test_next_job_hurt_derived_not_taken_from_the_file(self):
        self.assertEqual({k: heldout4.derived_hurt(c) for k, c in CHANGES.items() if k in ("H4-N1", "H4-N2", "H4-L1", "H4-L2")},
                         {"H4-N1": False, "H4-N2": False, "H4-L1": True, "H4-L2": True})

    def test_live_results_carry_real_priors(self):
        if not RES.exists():
            self.skipTest("live run not done yet")
        rows = json.loads(RES.read_text(encoding="utf-8"))["rows"]
        with_priors = {r["id"] for r in rows if r["priors_in_packet"] > 0 or r["prior_provenance"]}
        self.assertTrue({"H4-N3", "H4-L3", "H4-A2", "H4-A4"} <= with_priors)


if __name__ == "__main__":
    unittest.main()
