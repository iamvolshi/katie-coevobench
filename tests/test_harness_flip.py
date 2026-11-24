import dataclasses, json, tempfile, unittest
from pathlib import Path
from katie_coevobench.record import Record
from katie_coevobench.sim import World, Weights, SplitViolation, BASE_SOLVED
from katie_coevobench.arms import KatieWrapper, run_arm, MIN_TRAIN


def katie_with_trajs(n_old, n_new):
    w = World(1)
    k = KatieWrapper(Record())
    k.revise("H0", "start")
    k.add(w.collect("H0", n_old))
    k.revise("H1", "revision")
    k.add(w.collect("H1", n_new))
    return k


class Gating(unittest.TestCase):
    def test_stale_harness_kid_refused(self):
        k = katie_with_trajs(40, 0)
        ok, refusal = k.filter_for_training(list(k.history), "t")
        self.assertEqual(ok, [])
        self.assertIsNotNone(refusal)
        self.assertEqual(k.rec.get(refusal).kind, "refusal")

    def test_current_harness_kid_accepted(self):
        k = katie_with_trajs(40, 40)
        ok, refusal = k.filter_for_training(list(k.history), "t")
        self.assertIsNone(refusal)
        self.assertEqual(len(ok), 40)
        self.assertTrue(all(k._hk[t.kid] == k.hkid for t in ok))

    def test_mixed_history_only_current_passes(self):
        k = katie_with_trajs(40, MIN_TRAIN)
        ok, _ = k.filter_for_training(list(k.history), "t")
        self.assertEqual(len(ok), MIN_TRAIN)
        self.assertTrue(all(t.harness == "H1" for t in ok))

    def test_stale_weights_not_served(self):
        k = KatieWrapper(Record())
        k.revise("H0", "start")
        w = Weights("w1", ["H0"] * 40)
        k.wkid[id(w)] = k.hkid           # trained under the first harness KID
        self.assertIs(k.serve(w), w)     # still current: served
        k.revise("H1", "revision")
        self.assertEqual(k.serve(w).name, "base")   # stale: refused


class RecordRules(unittest.TestCase):
    def test_every_change_mints_a_kid_and_never_overwrites(self):
        r = Record()
        a = r.append("harness", 7, "t", "H0", "start")
        b = r.append("harness", 7, "t", "H1", "revise", supersedes=a.kid)
        self.assertNotEqual(a.kid, b.kid)
        self.assertEqual(r.get(a.kid).what, "H0")           # old entry intact
        self.assertEqual(r.get(b.kid).supersedes, a.kid)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            a.what = "changed"
        self.assertEqual(len(r), 2)

    def test_kids_unique_and_file_only_grows(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "r.jsonl"
            r = Record(p)
            sizes = []
            for i in range(5):
                r.append("note", 1, "t", f"n{i}", "w")
                sizes.append(len(p.read_text().splitlines()))
            self.assertEqual(sizes, [1, 2, 3, 4, 5])
            kids = [json.loads(l)["kid"] for l in p.read_text().splitlines()]
            self.assertEqual(len(set(kids)), 5)

    def test_entry_needs_why(self):
        with self.assertRaises(ValueError):
            Record().append("note", 1, "t", "what", "")

    def test_run_mints_kid_for_every_change(self):
        with tempfile.TemporaryDirectory() as d:
            r = run_arm("katie", 1, Path(d))
            lines = [json.loads(l) for l in (Path(d) / "record-katie-1.jsonl").read_text().splitlines()]
            self.assertEqual(len(lines), r["record_entries"])
            kinds = {l["kind"] for l in lines}
            self.assertTrue({"harness", "trajectory", "training_job", "refusal"} <= kinds)
            h = [l for l in lines if l["kind"] == "harness"]
            self.assertEqual(h[1]["supersedes"], h[0]["kid"])
            self.assertEqual(len(h), 2)                       # both harness versions survive


class Splits(unittest.TestCase):
    def test_visible_never_judges(self):
        with self.assertRaises(SplitViolation):
            World(1).solved(Weights(), "H0", "visible")

    def test_test_only_when_final(self):
        with self.assertRaises(SplitViolation):
            World(1).solved(Weights(), "H0", "test")

    def test_sizes(self):
        w = World(1)
        self.assertEqual((len(w.tasks["visible"]), len(w.tasks["selection"]), len(w.tasks["test"])), (27, 51, 51))


class Flip(unittest.TestCase):
    def setUp(self):
        self.c = [run_arm("control", s) for s in (1, 2, 3)]
        self.k = [run_arm("katie", s) for s in (1, 2, 3)]

    def test_control_reproduces_flip(self):
        for r in self.c:
            s = [x["selection_solved"] for x in r["stages"]]
            self.assertEqual(s[1] - s[0], 5)       # training helps under old harness
            self.assertEqual(s[2] - s[0], -4)      # falls 4 behind Base after revision
            self.assertEqual(s[-1] - s[0], 4)      # retrain on fresh data restores +4

    def test_katie_avoids_dip_and_skips_job(self):
        for r in self.k:
            self.assertEqual(r["dip_at_revision"], 0)
            self.assertEqual(r["jobs_skipped"], 1)
            self.assertEqual(r["jobs_hurt"], 0)
            self.assertEqual(r["stages"][-1]["selection_solved"] - BASE_SOLVED, 4)

    def test_katie_trains_only_on_matching_harness(self):
        for r in self.k:
            for j in r["jobs"]:
                if j["launched"]:
                    self.assertEqual(j["true_stale_in_data"], 0)

    def test_test_set_read_once_per_candidate_pair(self):
        for r in self.c + self.k:
            self.assertEqual(r["test_reads"], 2)   # frozen candidate + Base reference


if __name__ == "__main__":
    unittest.main()
