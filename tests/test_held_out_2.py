import hashlib, inspect, json, re, subprocess, unittest
from pathlib import Path
from katie_coevobench import heldout2, judge
from katie_coevobench.erie import Erie
from katie_coevobench.heldout import sha
from katie_coevobench.judge import Judge

ROOT = Path(__file__).resolve().parent.parent
H = ROOT / "heldout2"
SEAL = json.loads((H / "SEAL.json").read_text(encoding="utf-8"))
TRUTH = json.loads((H / "ground_truth.json").read_text(encoding="utf-8"))
CHANGES = heldout2.load_changes()
RES = ROOT / "results" / "live-judge-held-out-2.json"


def git(*a, raw=False):
    r = subprocess.run(["git", *a], capture_output=True, cwd=ROOT)
    return r.returncode, (r.stdout if raw else r.stdout.decode("utf-8", "replace").strip())


class Turdys(unittest.TestCase):
    def test_set_shape(self):
        kinds = [t["kind"] for t in TRUTH["truth"].values()]
        self.assertEqual((kinds.count("noise"), kinds.count("logical"), kinds.count("ambiguous")), (3, 3, 4))
        self.assertEqual(set(CHANGES), set(TRUTH["truth"]))
        self.assertEqual(heldout2.RUN_ORDER, TRUTH["run_order"])

    def test_written_by_turdy_not_the_builder(self):
        self.assertIn("Written by Turdy", (H / "README.md").read_text(encoding="utf-8"))
        self.assertEqual(TRUTH["written_by"][:5], "Turdy")
        code, authors = git("log", "--format=%an", "--", "heldout2/changes.json", "heldout2/ground_truth.json", "heldout2/README.md")
        first_batch = [a for a in authors.splitlines()]
        self.assertEqual(first_batch[-1], "Turdy")                       # the commit that added the files
        code, blob = git("cat-file", "blob", "093c31c:heldout2/changes.json", raw=True)
        if code == 0:                                                    # sealed bytes are exactly Turdy's
            self.assertEqual(hashlib.sha256(blob.replace(b"\r\n", b"\n")).hexdigest(), SEAL["sealed"]["heldout2/changes.json"])
        code, blob = git("cat-file", "blob", "093c31c:heldout2/ground_truth.json", raw=True)
        if code == 0:
            self.assertEqual(hashlib.sha256(blob.replace(b"\r\n", b"\n")).hexdigest(), SEAL["sealed"]["heldout2/ground_truth.json"])
        # a git author name is self-declared; the commit and the files are what is checked, not identity
        self.assertEqual(SEAL["turdy_commit"], "093c31c")


class Sealed(unittest.TestCase):
    def test_hashes_match_the_seal(self):
        for f, h in SEAL["sealed"].items():
            self.assertEqual(sha(ROOT / f), h, f)

    def test_judge_code_never_reads_the_truth(self):
        for m in ("judge", "erie", "arms", "scenarios", "record", "sim"):
            src = (ROOT / "katie_coevobench" / f"{m}.py").read_text(encoding="utf-8")
            for bad in ("ground_truth", "heldout"):
                self.assertNotIn(bad, src, m)
        body = inspect.getsource(heldout2.run_calls).split('"""')[2]
        for bad in ("truth", "ground"):
            self.assertNotIn(bad, body)
        for fn in (heldout2.build_priors, heldout2.seed_record, heldout2.summarize, heldout2.derived_hurt):
            self.assertNotIn("ground_truth", inspect.getsource(fn))

    def test_truth_loaded_only_after_the_calls(self):
        src = inspect.getsource(heldout2.main)
        self.assertLess(src.index("run_calls(judge, calls)"), src.index("ground_truth.json"))

    def test_sealed_before_the_first_call(self):
        if not RES.exists():
            self.skipTest("live run not done yet")
        r = json.loads(RES.read_text(encoding="utf-8"))
        self.assertEqual(r["seal"], SEAL)
        code, seal = git("log", "--format=%H", "--grep=^SEAL2:")
        seal = seal.splitlines()[-1]
        self.assertEqual(git("merge-base", "--is-ancestor", seal, r["git_head_at_run"])[0], 0)
        _, added = git("log", "--diff-filter=A", "--format=%H", "--", "results/live-judge-held-out-2.json")
        self.assertEqual(git("merge-base", "--is-ancestor", seal, added.splitlines()[-1])[0], 0)
        self.assertNotEqual(seal, added.splitlines()[-1])


class Model(unittest.TestCase):
    def test_id_matches_the_live_catalog_record(self):
        mc = json.loads((H / "model_check.json").read_text(encoding="utf-8"))
        self.assertEqual(SEAL["judge_model"], mc["chosen"])
        self.assertIn(mc["chosen"], mc["catalog_ids"])
        self.assertTrue(mc["chosen_in_catalog"])
        self.assertEqual(mc["chosen"], "nvidia/nemotron-3.5-bolt-e4b")

    def test_this_run_used_its_sealed_model_not_ultra(self):
        self.assertNotIn("ultra", SEAL["judge_model"])
        if RES.exists():
            self.assertEqual(json.loads(RES.read_text(encoding="utf-8"))["model"], SEAL["judge_model"])

    def test_everything_else_frozen(self):
        self.assertEqual(heldout2.frozen_hashes(), SEAL["frozen"])
        src = inspect.getsource(judge.NimJudge)
        self.assertIn('"temperature": 0', src)
        self.assertIn('"max_tokens": 8192', src)


class FakeJudge(Judge):
    """Says ambiguous for H2-N1 (the file says noise), noise elsewhere when it can; records what it was shown."""
    def __init__(self):
        self.seen = {}

    def raw(self, old, new, packet):
        cid = next(c["id"] for c in CHANGES.values() if c["new_text"] == new)
        self.seen[cid] = packet
        kind = "ambiguous" if cid == "H2-N1" else "logical" if any(e.shows == "changed" and e.type == "example" for e in packet.items) else "noise"
        cites = ", ".join(e.id for e in packet.items if e.type == "example")
        return json.dumps({"kind": kind, "reason": f"fake verdict for {cid}", "evidence": cites})


class Priors(unittest.TestCase):
    def test_at_least_four_changes_point_at_earlier_runs(self):
        order = heldout2.RUN_ORDER
        n = 0
        for cid, c in CHANGES.items():
            for p in c["priors"]:
                self.assertLess(order.index(p["source_run"]), order.index(cid))
                n += 1
        self.assertGreaterEqual(sum(bool(c["priors"]) for c in CHANGES.values()), 4)

    def test_priors_come_from_the_run_not_from_the_file(self):
        j = FakeJudge()
        rows, verdicts = heldout2.run_calls(j, 1)
        n3 = [r for r in rows if r["id"] == "H2-N3"][0]
        self.assertEqual(n3["prior_provenance"][0]["source_run"], "H2-N1")
        self.assertEqual(n3["prior_provenance"][0]["kind"], "ambiguous")       # the run said ambiguous
        self.assertEqual(n3["prior_provenance"][0]["file_said"]["kind"], "noise")  # the file said noise; unused
        prior = [e for e in j.seen["H2-N3"].items if e.type == "prior"]
        self.assertEqual(len(prior), 1)
        self.assertIn("judged ambiguous", prior[0].text)
        a2 = [e for e in j.seen["H2-A2"].items if e.type == "prior"]
        self.assertEqual(len(a2), 2)                                           # H2-N2 and H2-L2
        self.assertEqual(len([e for e in j.seen["H2-A4"].items if e.type == "prior"]), 1)
        self.assertEqual(sum(r["priors_in_packet"] > 0 for r in rows), 4)

    def test_next_job_hurt_derived_not_taken_from_the_file(self):
        self.assertEqual({k: heldout2.derived_hurt(c) for k, c in CHANGES.items() if k in ("H2-N1", "H2-N2", "H2-L1", "H2-L2")},
                         {"H2-N1": False, "H2-N2": False, "H2-L1": True, "H2-L2": True})

    def test_live_results_carry_real_priors(self):
        if not RES.exists():
            self.skipTest("live run not done yet")
        rows = json.loads(RES.read_text(encoding="utf-8"))["rows"]
        with_priors = {r["id"] for r in rows if r["priors_in_packet"] > 0 or r["prior_provenance"]}
        self.assertTrue({"H2-N3", "H2-L3", "H2-A2", "H2-A4"} <= with_priors)


if __name__ == "__main__":
    unittest.main()
