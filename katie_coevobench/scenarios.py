"""Three harness-change scripts. The text is what the judge reads; epoch_changes is the simulator's hidden truth."""
from __future__ import annotations
from dataclasses import dataclass

OLD = """You are an AppWorld assistant. Use the apps' APIs to complete the task.
Tools are listed alphabetically: amazon, file_system, phone, spotify, venmo.
A task is solved when the final answer equals the expected value exactly and the task's required state changes are present.
Dates are compared as written."""

_NOISE = """You are an assistant working inside AppWorld. Complete the task by calling the apps' APIs.
Tools are listed in order of use: venmo, phone, amazon, spotify, file_system.
A task counts as solved when the final answer matches the expected value exactly and the required state changes are present.
Dates are compared as written."""

_LOGICAL = """You are an AppWorld assistant. Use the apps' APIs to complete the task.
Tools are listed alphabetically: amazon, file_system, phone, spotify, venmo.
A task is solved only when the final answer equals the expected value exactly, the required state changes are present, and NO other state changed (any extra write or delete fails the task).
Dates are compared as written."""

_AMBIG = """You are an AppWorld assistant. Use the apps' APIs to complete the task.
Tools are listed alphabetically: amazon, file_system, phone, spotify, venmo.
A task is solved when the final answer equals the expected value exactly and the task's required state changes are present.
Dates are normalized to UTC before they are compared."""


@dataclass(frozen=True)
class Scenario:
    name: str
    new_text: str
    examples: tuple[str, ...]
    true_kind: str          # what a careful human would say; used only to mark the judge right or wrong
    epoch_changes: bool     # hidden simulator truth: does the correct answer actually move?


SCENARIOS = {
    "noise": Scenario("noise", _NOISE, (
        "Task: send $20 to a friend. Before: solved. After: solved.",
        "Task: list songs in the top playlist. Before: solved. After: solved."), "noise", False),
    "logical": Scenario("logical", _LOGICAL, (
        "Task: find the cheapest order. Agent answers correctly but also deletes a draft file. Before: solved. After: NOT solved.",
        "Task: send $20 to a friend, no extra writes. Before: solved. After: solved."), "logical", True),
    # the same text, two hidden truths: with no settling example the judge cannot tell which one it is
    "ambiguous_matters": Scenario("ambiguous_matters", _AMBIG, (
        "Task: list songs in the top playlist (no dates). Before: solved. After: solved.",
        "Task: send $20 to a friend (no dates). Before: solved. After: solved."), "ambiguous", True),
    "ambiguous_harmless": Scenario("ambiguous_harmless", _AMBIG, (
        "Task: list songs in the top playlist (no dates). Before: solved. After: solved.",
        "Task: send $20 to a friend (no dates). Before: solved. After: solved."), "ambiguous", False),
}

# What a working judge should say, for the stub. Texts are shared, so the stub keys by new text.
STUB_TABLE = {
    _NOISE: {"kind": "noise", "reason": "Only wording and tool order changed; the scoring rule is the same.",
             "evidence": "Tools are listed in order of use / reworded prompt"},
    _LOGICAL: {"kind": "logical", "reason": "A task now fails on any extra state change, so some solved tasks become unsolved.",
               "evidence": "and NO other state changed (any extra write or delete fails the task)"},
    _AMBIG: {"kind": "ambiguous", "reason": "UTC normalization could change date answers, but no example involves dates.",
             "evidence": "Dates are normalized to UTC before they are compared."},
}
