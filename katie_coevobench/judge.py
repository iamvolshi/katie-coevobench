"""The judge classifies a harness change. It never acts, never edits the record, never rewrites answers.

KATIE (arms.py) decides what to do with the kind. Keep these two jobs apart.
Live judge: Nemotron 3 Ultra on NVIDIA's OpenAI-compatible endpoint. Key from env only.
"""
from __future__ import annotations
import json, os, re, urllib.request, urllib.error
from dataclasses import dataclass

KINDS = ("noise", "ambiguous", "logical")
MODEL = "moonshotai/kimi-k3.1-pro"   # OCME-007: was nemotron-3.5-bolt-e4b (OCME-006) and nemotron-3-ultra-550b-a55b (OCME-003/004); id copied from the live /v1/models list
DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"

PROMPT_V1 = """You judge a change to an AI agent's harness (its prompt, tools and scoring rules).
Classify the change as exactly one kind:
- noise: wording, formatting, order or labels only. The correct answer and what counts as a solved task are unchanged.
- logical: the change alters the correct answer, the scoring, or what counts as a solved task.
- ambiguous: it could alter outcomes, and you cannot tell from the harness text and the examples alone.
Never guess. If you cannot tell, answer ambiguous.
Reply with ONLY one JSON object, no prose, no code fence:
{"kind": "noise|ambiguous|logical", "reason": "one or two plain sentences", "evidence": "the exact part of the harness that changed"}

OLD HARNESS:
%s

NEW HARNESS:
%s

EXAMPLE TASKS BEFORE AND AFTER:
%s
"""  # the OCME-002-evo prompt, kept for the record; not used

PROMPT = """You judge a change to an AI agent's harness (its prompt, tools and scoring rules).
You are given an EVIDENCE PACKET retrieved from the record. Each item has an id (E1, E2, ...), a source and a trust grade
(authority 0-9, higher is more trusted). Decide ONLY from the packet. Do not infer beyond it.

Kinds:
- logical: at least one example item shows a task whose answer CHANGED under the new harness.
- noise: the example items touched by the change show answers that did NOT change, and no earlier change in the packet changed an outcome.
- ambiguous: the evidence is thin, mixed or missing. This includes: no example shows a changed answer and no example proves nothing changed
  (for instance, the examples are not touched by the change).

Rules:
1. If no example shows a changed answer, do not say logical. Do not infer logical from the harness text alone, however real the change looks.
   Then choose: if the examples touched by the change show the same answer under both harnesses, say noise; if the examples are untouched or the evidence is thin, say ambiguous.
2. A task the change does not touch proves nothing. Do not count it as proof of noise.
3. Cite the evidence you used by id in the "evidence" field, for example "E1, E3". Cite nothing you did not use.
4. If you cannot tell, answer ambiguous. Never guess.
Reply with ONLY one JSON object, no prose, no code fence:
{"kind": "noise|ambiguous|logical", "reason": "one or two plain sentences that name the evidence ids you used", "evidence": "the ids you cited, e.g. E1, E2"}

OLD HARNESS:
%s

NEW HARNESS:
%s

EVIDENCE PACKET:
%s
"""


@dataclass(frozen=True)
class Verdict:
    kind: str
    reason: str
    evidence: str
    failed: bool = False   # True when the response could not be used


def failed(why: str) -> Verdict:
    """A failed judgment is recorded as ambiguous. Never a guess."""
    return Verdict("ambiguous", f"judgment failed: {why}", "", True)


def cited_ids(evidence: str) -> list[str]:
    return re.findall(r"\bE\d+\b", evidence or "")


def check_against_packet(v: Verdict, packet) -> Verdict:
    """Backstop for the prompt rules. A kind the evidence does not support becomes a failed judgment (ambiguous)."""
    if v.failed or packet is None:
        return v
    items = {e.id: e for e in packet.items}
    cites = [items[c] for c in cited_ids(v.evidence) if c in items]
    if not packet.has_outcome():
        return failed(f"no evidence shows an outcome, so {v.kind!r} is unsupported") if v.kind != "ambiguous" else v
    if v.kind == "logical" and not any(e.type == "example" and e.shows == "changed" for e in cites):
        return failed("logical needs a cited example whose answer changed")
    if v.kind == "noise":
        if any(e.shows == "changed" for e in packet.items):
            return failed("noise contradicted: the packet holds a changed answer")
        if not any(e.type == "example" and e.shows == "unchanged" for e in cites):
            return failed("noise needs a cited touched example whose answer did not change")
    return v


def parse_verdict(raw, packet=None) -> Verdict:
    if not isinstance(raw, str):
        return failed("response was not text")
    s = raw.strip()
    m = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", s, re.S)   # tolerate a code fence, nothing else
    if m:
        s = m.group(1)
    try:
        d = json.loads(s)
    except ValueError:
        return failed("response was not valid JSON")
    if not isinstance(d, dict):
        return failed("response was not a JSON object")
    kind, reason, ev = d.get("kind"), d.get("reason"), d.get("evidence")
    if kind not in KINDS:
        return failed(f"kind {kind!r} is not one of {KINDS}")
    if not (isinstance(reason, str) and reason.strip() and isinstance(ev, str) and ev.strip()):
        return failed("reason and evidence must be non-empty text")
    return check_against_packet(Verdict(kind, reason.strip(), ev.strip()), packet)


def build_prompt(old: str, new: str, packet) -> str:
    return PROMPT % (old, new, packet.render())


class Judge:
    """Subclasses supply raw(); judge() parses it. Any error is a failed judgment."""

    def raw(self, old: str, new: str, packet) -> str:
        raise NotImplementedError

    def judge(self, old: str, new: str, packet) -> Verdict:
        if not packet.has_outcome():   # nothing to decide from: hold, no model call
            return Verdict("ambiguous", "the evidence packet shows no outcome, so the change cannot be classified", "none")
        try:
            return parse_verdict(self.raw(old, new, packet), packet)
        except Exception as e:  # network, auth, timeout: still a failed judgment
            return failed(type(e).__name__)


class StubJudge(Judge):
    """No key, no network. Answers from a table keyed by the new harness text; can be told to emit junk."""

    def __init__(self, table: dict[str, dict] | None = None, junk: str | None = None):
        self.table, self.junk = table or {}, junk
        self.calls = 0

    def raw(self, old, new, packet):
        self.calls += 1
        if self.junk is not None:
            return self.junk
        return json.dumps(self.table[new])


class NimJudge(Judge):
    def __init__(self, base_url: str | None = None, api_key: str | None = None, model: str = MODEL, timeout: int = 120):
        self.base_url = (base_url or os.environ.get("NIM_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self._key = api_key or os.environ.get("NIM_API_KEY")
        self.model, self.timeout = model, timeout
        if not self._key:
            raise RuntimeError("NIM_API_KEY is not set")

    def raw(self, old, new, packet):
        body = json.dumps({"model": self.model, "temperature": 0, "max_tokens": 8192,
                           "messages": [{"role": "user", "content": build_prompt(old, new, packet)}]}).encode()
        req = urllib.request.Request(self.base_url + "/chat/completions", body,
                                     {"Content-Type": "application/json", "Authorization": "Bearer " + self._key})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.load(r)["choices"][0]["message"]["content"]
