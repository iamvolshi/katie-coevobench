"""OCME-008: partial is a kind, decided in code from the packet."""
import json, tempfile, unittest
from pathlib import Path
from katie_coevobench import heldout4
from katie_coevobench.arms import run_arm
from katie_coevobench.erie import Packet, Evidence, Erie
from katie_coevobench.judge import KINDS, StubJudge, parse_verdict, is_partial, PROMPT
from katie_coevobench.record import Record
from katie_coevobench.scenarios import Scenario

RAW = lambda **d: json.dumps(d)
CHANGES = heldout4.load_changes()


def pk(*shows, prior=None):
    items = [Evidence(f"E{i}", "example", "replay", 7, "t", s) for i, s in enumerate(shows, 1)]
    if prior:
        items.append(Evidence(f"E{len(items) + 1}", "prior", "T1-1", 6, "earlier change", prior))
    return Packet(tuple(items))


def packet_for(cid, priors=()):
    rec = Record()
    heldout4.seed_record(rec, list(priors))
    return Erie().retrieve(rec, heldout4.outcomes(CHANGES[cid]), cid)


class Rule(unittest.TestCase):
    def test_partial_is_a_kind(self):
        self.assertIn("partial", KINDS)
        self.assertIn("say partial, not noise", PROMPT)

    def test_noise_rejected_on_partial_packet_as_failed_partial(self):
        v = parse_verdict(RAW(kind="noise", reason="E1 unchanged", evidence="E1"), pk("unchanged", "nothing"))
        self.assertEqual((v.kind, v.failed), ("partial", True))
        self.assertIn("partial coverage", v.reason)

    def test_noise_still_allowed_when_every_example_touched_and_unchanged(self):
        v = parse_verdict(RAW(kind="noise", reason="E1, E2 unchanged", evidence="E1, E2"), pk("unchanged", "unchanged"))
        self.assertEqual((v.kind, v.failed), ("noise", False))
        v = parse_verdict(RAW(kind="noise", reason="r", evidence="E1, E2, E3"), pk("unchanged", "unchanged", "unchanged"))
        self.assertEqual((v.kind, v.failed), ("noise", False))

    def test_model_partial_accepted_and_ambiguous_named_partial(self):
        p = pk("unchanged", "nothing")
        self.assertEqual(parse_verdict(RAW(kind="partial", reason="r", evidence="E1, E2"), p).kind, "partial")
        v = parse_verdict(RAW(kind="ambiguous", reason="r", evidence="E1, E2"), p)
        self.assertEqual((v.kind, v.failed), ("partial", False))

    def test_partial_refused_where_coverage_is_not_partial(self):
        for p in (pk("unchanged", "unchanged"), pk("nothing", "nothing"), pk("nothing")):
            v = parse_verdict(RAW(kind="partial", reason="r", evidence="E1"), p)
            self.assertEqual((v.kind, v.failed), ("ambiguous", True))

    def test_failed_reply_on_partial_packet_is_partial(self):
        for raw in (None, "not json", '{"kind":"maybe","reason":"r","evidence":"E1"}'):
            v = parse_verdict(raw, pk("unchanged", "nothing"))
            self.assertEqual((v.kind, v.failed), ("partial", True))

    def test_noise_with_a_prior_that_moved_an_outcome_on_partial_packet(self):
        v = parse_verdict(RAW(kind="noise", reason="r", evidence="E1"), pk("unchanged", "nothing", prior="changed"))
        self.assertEqual((v.kind, v.failed), ("partial", True))

    def test_supported_logical_outranks_partial(self):
        v = parse_verdict(RAW(kind="logical", reason="E1 changed", evidence="E1"), pk("changed", "unchanged", "nothing"))
        self.assertEqual(v.kind, "logical")

    def test_priors_never_make_a_packet_partial(self):
        self.assertFalse(is_partial(pk("unchanged", "unchanged", prior="nothing")))
        self.assertTrue(is_partial(pk("unchanged", "nothing")))


class OnSetFour(unittest.TestCase):
    """The rule against Turdy's packets (truth file not read: kinds come from the packets alone)."""

    def test_partial_cases_are_partial_packets(self):
        self.assertTrue(is_partial(packet_for("H4-A3")))
        self.assertTrue(is_partial(packet_for("H4-A4", [{"source_run": "H4-L1", "kind": "logical", "reason": "r",
                                                         "failed": False, "next_job_hurt": True}])))

    def test_noise_cases_are_not_partial_and_noise_passes(self):
        for cid in ("H4-N1", "H4-N2", "H4-N3"):
            p = packet_for(cid)
            self.assertFalse(is_partial(p), cid)
            cites = ", ".join(e.id for e in p.items if e.type == "example")
            self.assertEqual(parse_verdict(RAW(kind="noise", reason="r", evidence=cites), p).kind, "noise", cid)

    def test_noise_on_set_four_partials_is_held_as_partial(self):
        for cid in ("H4-A3", "H4-A4"):
            v = parse_verdict(RAW(kind="noise", reason="r", evidence="E1"), packet_for(cid))
            self.assertEqual((v.kind, v.failed), ("partial", True), cid)

    def test_other_set_four_holds_are_not_partial(self):
        for cid in ("H4-A1", "H4-A2"):
            self.assertFalse(is_partial(packet_for(cid)), cid)


class InTheRecord(unittest.TestCase):
    def run_katie(self, cid, reply):
        c = CHANGES[cid]
        sc = Scenario(cid, c["new_text"], heldout4.outcomes(c), "", True, c["old_text"])
        d = tempfile.mkdtemp()
        r = run_arm("katie", 1, Path(d), sc, StubJudge(junk=json.dumps(reply)))
        rows = [json.loads(l) for l in (Path(d) / f"record-katie-{cid}-linear-1.jsonl").read_text().splitlines()]
        return r, rows

    def test_partial_kind_recorded_with_kid_and_it_holds(self):
        for cid in ("H4-A3", "H4-A4"):
            r, rows = self.run_katie(cid, {"kind": "noise", "reason": "r", "evidence": "E1"})
            j = [x for x in rows if x["kind"] == "judgment"][0]
            self.assertEqual((j["data"]["judged_kind"], j["data"]["failed"]), ("partial", True), cid)
            self.assertTrue(j["kid"].startswith("T1-"))
            hold = [x for x in rows if x["kind"] == "hold"]
            self.assertEqual(hold[0]["data"]["judgment_kid"], j["kid"])
            self.assertEqual((r["judge_kind"], r["jobs_skipped"], r["dip_at_revision"]), ("partial", 1, 0), cid)
            res = [x for x in rows if x["kind"] == "resolution"][0]
            self.assertEqual(res["supersedes"], hold[0]["kid"])          # the hold entry stays

    def test_noise_cases_record_noise_and_train(self):
        for cid in ("H4-N1", "H4-N2"):
            r, rows = self.run_katie(cid, {"kind": "noise", "reason": "r", "evidence": "E1, E2"})
            self.assertEqual([x["data"]["judged_kind"] for x in rows if x["kind"] == "judgment"], ["noise"], cid)
            self.assertFalse([x for x in rows if x["kind"] == "hold"], cid)
            self.assertEqual(r["jobs_skipped"], 0, cid)


if __name__ == "__main__":
    unittest.main()
