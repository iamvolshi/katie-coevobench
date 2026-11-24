import json, tempfile, unittest
from pathlib import Path
from katie_coevobench.arms import run_arm
from katie_coevobench.erie import Erie, StubErie, Packet, Evidence
from katie_coevobench.judge import StubJudge, parse_verdict, build_prompt, PROMPT
from katie_coevobench.record import Record
from katie_coevobench.scenarios import SCENARIOS, STUB_TABLE, STUB_PACKETS, OLD
from katie_coevobench.sim import BASE_SOLVED

STUB = StubErie(STUB_PACKETS)
RAW = lambda **d: json.dumps(d)


def kat(sc, **kw):
    kw.setdefault("erie", STUB)
    return run_arm("katie", 1, scenario=sc, **kw)


def pk(*shows):
    return Packet(tuple(Evidence(f"E{i}", "example", "replay", 7, "t", s) for i, s in enumerate(shows, 1)))


class KindsFromEvidence(unittest.TestCase):
    def test_logical_when_evidence_shows_a_changed_answer(self):
        r = kat("logical")
        self.assertEqual(r["judge_kind"], "logical")
        self.assertEqual((r["dip_at_revision"], r["jobs_skipped"]), (0, 1))

    def test_noise_when_evidence_shows_no_changed_answer(self):
        r = kat("noise")
        self.assertEqual(r["judge_kind"], "noise")
        self.assertEqual((r["jobs_skipped"], r["jobs_launched"]), (0, 2))

    def test_ambiguous_when_evidence_is_thin(self):
        for sc in ("ambiguous_matters", "ambiguous_harmless"):
            r = kat(sc)
            self.assertEqual(r["judge_kind"], "ambiguous")
            self.assertEqual(r["jobs_skipped"], 1)

    def test_real_erie_retrieval_gives_same_kinds(self):
        for sc in SCENARIOS:
            self.assertTrue(run_arm("katie", 1, scenario=sc)["judge_correct"], sc)

    def test_packet_facts(self):
        shows = lambda s: [e.shows for e in Erie().retrieve(None, SCENARIOS[s].outcomes).items]
        self.assertEqual(shows("noise"), ["unchanged", "unchanged"])
        self.assertEqual(shows("logical"), ["changed", "unchanged"])
        self.assertEqual(shows("ambiguous_matters"), ["nothing", "nothing"])


class NoEvidenceNeverLogical(unittest.TestCase):
    LOGICAL = {"kind": "logical", "reason": "Dates changed, so answers must.", "evidence": "E1"}

    def test_no_evidence_at_all_is_ambiguous_without_a_model_call(self):
        j = StubJudge({"x": self.LOGICAL})
        v = j.judge(OLD, "x", Packet(()))
        self.assertEqual(v.kind, "ambiguous")
        self.assertEqual(j.calls, 0)

    def test_evidence_with_no_outcome_is_ambiguous(self):
        j = StubJudge({"x": self.LOGICAL})
        self.assertEqual(j.judge(OLD, "x", pk("nothing", "nothing")).kind, "ambiguous")
        self.assertEqual(j.calls, 0)

    def test_a_model_that_says_logical_anyway_is_downgraded(self):
        # the live failure: UTC dates "look" logical. The text alone must not be enough.
        for packet in (pk("nothing", "nothing"), pk("unchanged", "unchanged")):
            v = parse_verdict(RAW(**self.LOGICAL), packet)
            self.assertEqual((v.kind, v.failed), ("ambiguous", True))

    def test_logical_must_cite_an_example_that_changed(self):
        p = pk("changed", "unchanged")
        self.assertEqual(parse_verdict(RAW(kind="logical", reason="r", evidence="E1"), p).kind, "logical")
        self.assertTrue(parse_verdict(RAW(kind="logical", reason="r", evidence="E2"), p).failed)
        self.assertTrue(parse_verdict(RAW(kind="logical", reason="r", evidence="the date rule"), p).failed)

    def test_noise_blocked_by_a_changed_answer_or_no_proof(self):
        self.assertTrue(parse_verdict(RAW(kind="noise", reason="r", evidence="E2"), pk("changed", "unchanged")).failed)
        self.assertTrue(parse_verdict(RAW(kind="noise", reason="r", evidence="E1"), pk("nothing", "nothing")).failed)

    def test_run_with_no_evidence_holds_even_if_model_says_logical(self):
        empty = StubErie({s: Packet(()) for s in SCENARIOS})
        r = kat("ambiguous_matters", erie=empty, judge=StubJudge({SCENARIOS["ambiguous_matters"].new_text: self.LOGICAL}))
        self.assertEqual(r["judge_kind"], "ambiguous")
        self.assertEqual((r["jobs_skipped"], r["dip_at_revision"]), (1, 0))


class PromptHasTheRecipe(unittest.TestCase):
    def test_prompt_rules_and_packet(self):
        p = build_prompt(OLD, SCENARIOS["logical"].new_text, Erie().retrieve(None, SCENARIOS["logical"].outcomes))
        self.assertIn("If no example shows a changed answer, do not say logical", p)
        self.assertIn("say noise", p)
        self.assertIn("Do not infer logical from the harness text alone", p)
        self.assertIn("E1 [example; source=replay:old+new-harness; authority=7]", p)
        self.assertIn("Cite the evidence you used by id", PROMPT)


class EvidenceRecorded(unittest.TestCase):
    def rows(self, sc):
        d = tempfile.mkdtemp()
        run_arm("katie", 1, Path(d), sc)
        return [json.loads(l) for l in (Path(d) / f"record-katie-{sc}-linear-1.jsonl").read_text().splitlines()]

    def test_citations_recorded_with_kid_and_nothing_overwritten(self):
        rows = self.rows("logical")
        by = {r["kid"]: r for r in rows}
        ev = [r for r in rows if r["kind"] == "evidence"]
        j = [r for r in rows if r["kind"] == "judgment"]
        self.assertEqual((len(ev), len(j)), (1, 1))
        self.assertEqual(j[0]["data"]["evidence_kid"], ev[0]["kid"])
        self.assertEqual(j[0]["data"]["cited"], ["E1"])
        item = ev[0]["data"]["items"][0]
        self.assertTrue(item["source"] and 0 <= item["authority"] <= 9 and item["text"])
        self.assertEqual(len(by), len(rows))                         # KIDs unique
        self.assertEqual(int(ev[0]["kid"][3:]) < int(j[0]["kid"][3:]), True)   # retrieved before judged
        self.assertEqual(by[ev[0]["kid"]]["data"]["items"], ev[0]["data"]["items"])

    def test_prior_changes_come_from_the_record_with_their_kid(self):
        rec = Record()
        j = rec.append("judgment", 6, "judge", "classified logical", "E1 changed", judged_kind="logical", failed=False)
        p = Erie().retrieve(rec, SCENARIOS["noise"].outcomes)
        prior = [e for e in p.items if e.type == "prior"][0]
        self.assertEqual((prior.source, prior.authority, prior.shows), (j.kid, 6, "changed"))
        # a noise claim now meets a prior change that moved an outcome: not supported
        self.assertTrue(parse_verdict(RAW(kind="noise", reason="r", evidence="E1, E2"), p).failed)
        self.assertEqual(len(rec), 1)                                # retrieval is read only

    def test_failed_prior_judgments_are_not_evidence(self):
        rec = Record()
        rec.append("judgment", 6, "judge", "classified ambiguous", "failed", judged_kind="ambiguous", failed=True)
        self.assertEqual([e for e in Erie().retrieve(rec, ()).items if e.type == "prior"], [])


if __name__ == "__main__":
    unittest.main()
