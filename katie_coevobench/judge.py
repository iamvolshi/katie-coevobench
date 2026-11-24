"""The judge classifies a harness change. It never acts, never edits the record, never rewrites answers.

KATIE (arms.py) decides what to do with the kind. Keep these two jobs apart.
Live judge: Nemotron 3 Ultra on NVIDIA's OpenAI-compatible endpoint. Key from env only.
"""
from __future__ import annotations
import json, os, re, urllib.request, urllib.error
from dataclasses import dataclass

KINDS = ("noise", "ambiguous", "logical")
MODEL = "nvidia/nemotron-3-ultra-550b-a55b"
DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"

PROMPT = """You judge a change to an AI agent's harness (its prompt, tools and scoring rules).
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


def parse_verdict(raw) -> Verdict:
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
    return Verdict(kind, reason.strip(), ev.strip())


def build_prompt(old: str, new: str, examples: list[str]) -> str:
    return PROMPT % (old, new, "\n".join(examples) or "(none)")


class Judge:
    """Subclasses supply raw(); judge() parses it. Any error is a failed judgment."""

    def raw(self, old: str, new: str, examples: list[str]) -> str:
        raise NotImplementedError

    def judge(self, old: str, new: str, examples: list[str]) -> Verdict:
        try:
            return parse_verdict(self.raw(old, new, examples))
        except Exception as e:  # network, auth, timeout: still a failed judgment
            return failed(type(e).__name__)


class StubJudge(Judge):
    """No key, no network. Answers from a table keyed by the new harness text; can be told to emit junk."""

    def __init__(self, table: dict[str, dict] | None = None, junk: str | None = None):
        self.table, self.junk = table or {}, junk
        self.calls = 0

    def raw(self, old, new, examples):
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

    def raw(self, old, new, examples):
        body = json.dumps({"model": self.model, "temperature": 0, "max_tokens": 2048,
                           "messages": [{"role": "user", "content": build_prompt(old, new, examples)}]}).encode()
        req = urllib.request.Request(self.base_url + "/chat/completions", body,
                                     {"Content-Type": "application/json", "Authorization": "Bearer " + self._key})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.load(r)["choices"][0]["message"]["content"]
