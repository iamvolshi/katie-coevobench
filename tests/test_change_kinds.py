import json, os, tempfile, unittest
from pathlib import Path
from katie_coevobench.arms import run_arm
from katie_coevobench.judge import StubJudge, parse_verdict, NimJudge, Judge
from katie_coevobench.scenarios import SCENARIOS, STUB_TABLE, OLD
from katie_coevobench.erie import Erie, Packet
from katie_coevobench.sim import BASE_SOLVED, MIX_RULES


def kat(sc, **kw):
    return run_arm("katie", 1, scenario=sc, **kw)


def con(sc, **kw):
    return run_arm("control", 1, scenario=sc, **kw)


class Kinds(unittest.TestCase):
    def test_noise_classified_and_training_goes_ahead(self):
        r = kat("noise")
        self.assertEqual(r["judge_kind"], "noise")
        self.assertEqual((r["dip_at_revision"], r["jobs_skipped"], r["jobs_launched"]), (5, 0, 2))  # +5 kept, no dip, no skip
        self.assertEqual(r["final_selection"], BASE_SOLVED + 5)
        self.assertEqual(con("noise")["final_selection"], r["final_selection"])  # nothing to save: same as Control

    def test_ambiguous_classified_and_mixed_job_held(self):
        for sc in ("ambiguous_matters", "ambiguous_harmless"):
            r = kat(sc)
            self.assertEqual(r["judge_kind"], "ambiguous")
            self.assertEqual(r["jobs_skipped"], 1)
            self.assertEqual(r["jobs_hurt"], 0)
            self.assertEqual(r["dip_at_revision"], 0)
            self.assertEqual(r["stages"][2]["selection_solved"], BASE_SOLVED)  # Base served while unsure

    def test_ambiguous_probe_resolves_both_truths(self):
        self.assertEqual(kat("ambiguous_matters")["probe"], "logical")
        self.assertEqual(kat("ambiguous_harmless")["probe"], "noise")
        self.assertEqual(kat("ambiguous_matters")["final_selection"], BASE_SOLVED + 4)
        self.assertEqual(kat("ambiguous_harmless")["final_selection"], BASE_SOLVED + 5)

    def test_ambiguous_hold_costs_when_change_was_harmless(self):
        # honest cost: Control never held, so it keeps the +5 that KATIE gives up while unsure
        self.assertEqual(con("ambiguous_harmless")["stages"][2]["selection_solved"], BASE_SOLVED + 5)
        self.assertEqual(kat("ambiguous_harmless")["stages"][2]["selection_solved"], BASE_SOLVED)
        self.assertEqual(kat("ambiguous_harmless")["jobs_skipped"], 1)

    def test_logical_blocks_stale_and_retrains(self):
        r = kat("logical")
        self.assertEqual(r["judge_kind"], "logical")
        self.assertEqual((r["dip_at_revision"], r["jobs_skipped"], r["jobs_hurt"]), (0, 1, 0))
        self.assertEqual(r["final_selection"], BASE_SOLVED + 4)
        self.assertEqual(con("logical")["dip_at_revision"], -4)

    def test_judge_correct_flag(self):
        for sc, s in SCENARIOS.items():
            self.assertEqual(kat(sc)["judge_correct"], True, sc)


class FailedJudgment(unittest.TestCase):
    JUNK = ["not json at all", "", "{}", '{"kind":"noise"}', '{"kind":"maybe","reason":"r","evidence":"e"}',
            '{"kind":"noise","reason":"","evidence":"e"}', "[1,2]", None]

    def test_unparseable_is_ambiguous_failed(self):
        for raw in self.JUNK:
            v = parse_verdict(raw)
            self.assertEqual((v.kind, v.failed), ("ambiguous", True), raw)

    def test_failed_judgment_holds_on_a_logical_change(self):
        r = kat("logical", judge=StubJudge(junk="the model rambled"))
        self.assertTrue(r["judge_failed"])
        self.assertEqual(r["judge_kind"], "ambiguous")
        self.assertEqual(r["jobs_skipped"], 1)
        self.assertEqual(r["dip_at_revision"], 0)      # held, not guessed noise

    def test_failed_judgment_never_guesses_noise_on_a_noise_change(self):
        r = kat("noise", judge=StubJudge(junk="{"))
        self.assertEqual(r["judge_kind"], "ambiguous")
        self.assertEqual(r["jobs_skipped"], 1)         # it held; a guess of noise would have trained

    def test_judge_exception_is_failed_judgment(self):
        class Boom(Judge):
            def raw(self, *a):
                raise TimeoutError()
        v = Boom().judge(OLD, "x", Erie().retrieve(None, SCENARIOS["noise"].outcomes))
        self.assertEqual((v.kind, v.failed), ("ambiguous", True))

    def test_fenced_json_is_accepted_nothing_else(self):
        v = parse_verdict('```json\n{"kind":"noise","reason":"r","evidence":"e"}\n```')
        self.assertEqual((v.kind, v.failed), ("noise", False))
        self.assertTrue(parse_verdict('Sure! {"kind":"noise","reason":"r","evidence":"e"}').failed)


class Recording(unittest.TestCase):
    def test_kind_reason_recorded_with_kid_and_old_entries_intact(self):
        with tempfile.TemporaryDirectory() as d:
            run_arm("katie", 1, Path(d), "ambiguous_matters")
            rows = [json.loads(l) for l in (Path(d) / "record-katie-ambiguous_matters-linear-1.jsonl").read_text().splitlines()]
            by = {r["kid"]: r for r in rows}
            self.assertEqual(len(by), len(rows))                       # unique KIDs
            j = [r for r in rows if r["kind"] == "judgment"][0]
            self.assertEqual(j["data"]["judged_kind"], "ambiguous")
            self.assertTrue(j["why"] and j["data"]["evidence"])
            hold = [r for r in rows if r["kind"] == "hold"][0]
            self.assertEqual(hold["data"]["judgment_kid"], j["kid"])
            self.assertTrue(hold["why"])
            res = [r for r in rows if r["kind"] == "resolution"][0]
            self.assertEqual(res["supersedes"], hold["kid"])
            self.assertEqual(by[hold["kid"]]["what"], "change marked unsure; old trajectories held")  # not overwritten
            h = [r for r in rows if r["kind"] == "harness"]
            self.assertEqual(h[1]["supersedes"], h[0]["kid"])

    def test_noise_has_judgment_kid_and_no_hold(self):
        with tempfile.TemporaryDirectory() as d:
            run_arm("katie", 1, Path(d), "noise")
            rows = [json.loads(l) for l in (Path(d) / "record-katie-noise-linear-1.jsonl").read_text().splitlines()]
            self.assertEqual([r["data"]["judged_kind"] for r in rows if r["kind"] == "judgment"], ["noise"])
            self.assertFalse([r for r in rows if r["kind"] in ("hold", "refusal")])

    def test_judge_cannot_write_the_record(self):
        # the judge returns a Verdict and holds no reference to the record
        v = StubJudge(STUB_TABLE).judge(OLD, SCENARIOS["noise"].new_text, Erie().retrieve(None, SCENARIOS["noise"].outcomes))
        self.assertEqual(set(v.__dataclass_fields__), {"kind", "reason", "evidence", "failed"})


class MixRules(unittest.TestCase):
    def test_control_s3_per_rule(self):
        self.assertEqual({m: con("logical", mix=m)["s3"] - BASE_SOLVED for m in MIX_RULES},
                         {"linear": -1, "stale_wins": -4, "majority": -4})

    def test_katie_conclusion_holds_under_every_rule(self):
        for m in MIX_RULES:
            k, c = kat("logical", mix=m), con("logical", mix=m)
            self.assertEqual(k["dip_at_revision"], 0, m)
            self.assertEqual((k["jobs_skipped"], k["jobs_hurt"]), (1, 0), m)
            self.assertEqual(k["final_selection"], c["final_selection"], m)
            self.assertEqual(k["final_test_solved"], c["final_test_solved"], m)

    def test_bad_rule_rejected(self):
        with self.assertRaises(ValueError):
            run_arm("control", 1, mix="nonsense")


class Live(unittest.TestCase):
    def test_live_judge_needs_a_key_and_never_invents(self):
        old = os.environ.pop("NIM_API_KEY", None)
        try:
            with self.assertRaises(RuntimeError):
                NimJudge()
        finally:
            if old:
                os.environ["NIM_API_KEY"] = old


if __name__ == "__main__":
    unittest.main()
