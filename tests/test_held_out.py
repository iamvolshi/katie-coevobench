import hashlib, inspect, json, re, subprocess, unittest
from pathlib import Path
from katie_coevobench import heldout, judge, erie
from katie_coevobench.erie import Erie
from katie_coevobench.record import Record
from katie_coevobench.arms import run_arm
from katie_coevobench.scenarios import SCENARIOS, Scenario
from katie_coevobench.judge import StubJudge

ROOT = Path(__file__).resolve().parent.parent
H = ROOT / "heldout"
SEAL = json.loads((H / "SEAL.json").read_text(encoding="utf-8"))
TRUTH = json.loads((H / "ground_truth.json").read_text(encoding="utf-8"))["truth"]
CHANGES = json.loads((H / "changes.json").read_text(encoding="utf-8"))


def git(*a):
    r = subprocess.run(["git", *a], capture_output=True, text=True, cwd=ROOT)
    return r.returncode, r.stdout.strip()


class Set(unittest.TestCase):
    def test_size_and_balance(self):
        kinds = [t["kind"] for t in TRUTH.values()]
        self.assertGreaterEqual(len(kinds), 8)
        for k in ("noise", "logical", "ambiguous"):
            self.assertGreaterEqual(kinds.count(k), 2, k)
        self.assertEqual({c["id"] for c in CHANGES}, set(TRUTH))
        self.assertTrue(all(t["why"] for t in TRUTH.values()))

    def test_changes_file_has_no_answer_key(self):
        text = (H / "changes.json").read_text(encoding="utf-8")
        for bad in ("ground_truth", '"kind": "noise"', '"kind": "logical"', '"kind": "ambiguous"', "true_kind"):
            self.assertNotIn(bad, text.replace('"kind": "noise", "reason"', "").replace('"kind": "logical", "reason"', ""), bad)

    def test_new_not_reused(self):
        used = {s.new_text for s in SCENARIOS.values()}
        for c in CHANGES:
            self.assertNotIn(c["new_text"], used)
            self.assertNotIn("UTC", c["new_text"])
            self.assertNotIn("alphabetically", c["new_text"])

    def test_priors_exist_for_at_least_two_changes(self):
        self.assertGreaterEqual(sum(bool(c["priors"]) for c in CHANGES), 2)

    def test_priors_reach_the_packet_with_their_kid(self):
        c = next(c for c in CHANGES if c["id"] == "HO-A4")
        rec = Record()
        heldout.seed_record(rec, c["priors"])
        p = Erie().retrieve(rec, heldout.outcomes(c), c["id"])
        prior = [e for e in p.items if e.type == "prior"]
        self.assertEqual(len(prior), 1)
        self.assertEqual((prior[0].source, prior[0].shows), ("T1-1", "changed"))
        self.assertIn("hurt", prior[0].text)

    def test_truth_follows_the_written_rule_given_the_evidence(self):
        # consistency of the sealed set with its own rule; reads the truth in a test, never in judge code
        for c in CHANGES:
            rec = Record()
            heldout.seed_record(rec, c["priors"])
            items = Erie().retrieve(rec, heldout.outcomes(c), c["id"]).items
            ex = [e for e in items if e.type == "example"]
            changed_ex = any(e.shows == "changed" for e in ex)
            changed_any = any(e.shows == "changed" for e in items)
            unchanged_ex = any(e.shows == "unchanged" for e in ex)
            want = "logical" if changed_ex else "noise" if unchanged_ex and not changed_any else "ambiguous"
            self.assertEqual(TRUTH[c["id"]]["kind"], want, c["id"])


class Sealed(unittest.TestCase):
    def test_hashes_match_the_seal(self):
        for f, h in SEAL["sealed"].items():
            self.assertEqual(heldout.sha(ROOT / f), h, f)

    def test_judge_code_never_reads_the_truth(self):
        for m in ("judge", "erie", "arms", "scenarios", "record", "sim"):
            src = (ROOT / "katie_coevobench" / f"{m}.py").read_text(encoding="utf-8")
            self.assertNotIn("ground_truth", src, m)
            self.assertNotIn("heldout", src, m)
        body = inspect.getsource(heldout.run_calls).split('"""')[2]     # code after the docstring
        self.assertNotIn("truth", body)
        self.assertNotIn("ground", body)

    def test_truth_is_loaded_only_after_the_calls(self):
        src = inspect.getsource(heldout.main)
        self.assertLess(src.index("run_calls(calls)"), src.index("ground_truth.json"))

    def test_sealed_before_the_live_run(self):
        res = ROOT / "results" / "live-judge-held-out.json"
        if not res.exists():
            self.skipTest("live run not done yet")
        code, seal = git("log", "--format=%H", "--grep=^SEAL:")
        self.assertEqual(code, 0)
        seal = seal.splitlines()[-1]
        r = json.loads(res.read_text(encoding="utf-8"))
        self.assertEqual(r["seal"], SEAL)                                    # the run saw this exact seal
        self.assertEqual(git("merge-base", "--is-ancestor", seal, r["git_head_at_run"])[0], 0)
        _, added = git("log", "--diff-filter=A", "--format=%H", "--", "results/live-judge-held-out.json")
        self.assertEqual(git("merge-base", "--is-ancestor", seal, added.splitlines()[-1])[0], 0)
        self.assertNotEqual(seal, added.splitlines()[-1])


class Frozen(unittest.TestCase):
    def test_judge_and_erie_files_unchanged_since_ocme_003(self):
        # OCME-006 changed exactly one thing in judge.py: the MODEL line
        strip = lambda s: re.sub(r"(?m)^MODEL = .*$", "MODEL = <id>", s.replace("\r\n", "\n"))
        self.assertEqual(heldout.sha(ROOT / "katie_coevobench/erie.py"), SEAL["frozen"]["katie_coevobench/erie.py"])
        code, old = git("show", "d21bf84:katie_coevobench/judge.py")
        if code != 0:
            self.skipTest("d21bf84 not available")
        self.assertEqual(strip(old).strip(), strip((ROOT / "katie_coevobench/judge.py").read_text(encoding="utf-8")).strip())

    def test_prompt_frozen(self):
        self.assertEqual(hashlib.sha256(judge.PROMPT.encode()).hexdigest(), SEAL["frozen"]["PROMPT"])
        self.assertIn("If no example shows a changed answer, do not say logical", judge.PROMPT)

    def test_prompt_and_backstop_match_ocme_003_commit(self):
        code, old = git("show", "d21bf84:katie_coevobench/judge.py")
        if code != 0:
            self.skipTest("d21bf84 not available")
        old = old.replace("\r\n", "\n")
        old_prompt = old.split("\nPROMPT = \"\"\"", 1)[1].split("\"\"\"", 1)[0]
        self.assertEqual(old_prompt, judge.PROMPT)
        old_backstop = re.search(r"def check_against_packet.*?\n\n\ndef parse_verdict", old.replace("\r\n", "\n"), re.S).group(0)
        new_backstop = re.search(r"def check_against_packet.*?\n\n\ndef parse_verdict",
                                 inspect.getsource(judge).replace("\r\n", "\n"), re.S).group(0)
        self.assertEqual(old_backstop, new_backstop)

    def test_live_settings_frozen(self):
        src = inspect.getsource(judge.NimJudge)
        self.assertIn('"temperature": 0', src)
        self.assertIn('"max_tokens": 8192', src)


class Plumbing(unittest.TestCase):
    def test_held_out_change_runs_through_the_pipeline_with_stub(self):
        c = next(c for c in CHANGES if c["id"] == "HO-L1")
        sc = Scenario(c["id"], c["new_text"], heldout.outcomes(c), "logical", True, c["old_text"])
        table = {c["new_text"]: {"kind": "logical", "reason": "E1 changed", "evidence": "E1"}}
        r = run_arm("katie", 1, None, sc, StubJudge(table))
        self.assertEqual((r["judge_kind"], r["jobs_skipped"], r["dip_at_revision"]), ("logical", 1, 0))

    def test_seeded_priors_appear_in_a_pipeline_record(self):
        c = next(c for c in CHANGES if c["id"] == "HO-A3")
        sc = Scenario(c["id"], c["new_text"], heldout.outcomes(c), "ambiguous", False, c["old_text"])
        seen = {}

        class Spy(StubJudge):
            def raw(self, old, new, packet):
                seen["priors"] = [e for e in packet.items if e.type == "prior"]
                return json.dumps({"kind": "ambiguous", "reason": "r", "evidence": "E1"})
        run_arm("katie", 1, None, sc, Spy(), record_seed=lambda rec: heldout.seed_record(rec, c["priors"]))
        self.assertEqual(len(seen["priors"]), 1)


if __name__ == "__main__":
    unittest.main()
