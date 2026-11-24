"""Three harness-change scripts. The text is what the judge reads; epoch_changes is the simulator's hidden truth."""
from __future__ import annotations
from dataclasses import dataclass
from .erie import Outcome, Packet, example_item

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
    outcomes: tuple[Outcome, ...]   # replayed example tasks with actual answers (what ERIE retrieves)
    true_kind: str          # what a careful human would say; used only to mark the judge right or wrong
    epoch_changes: bool     # hidden simulator truth: does the correct answer actually move?


_DATE_FREE = (Outcome("list songs in the top playlist", "solved", "solved", False),
              Outcome("send $20 to a friend", "solved", "solved", False))   # no dates: the UTC rule does not touch them

SCENARIOS = {
    "noise": Scenario("noise", _NOISE, (
        Outcome("send $20 to a friend", "solved", "solved", True),
        Outcome("list songs in the top playlist", "solved", "solved", True)), "noise", False),
    "logical": Scenario("logical", _LOGICAL, (
        Outcome("find the cheapest order (agent also deletes a draft file)", "solved", "NOT solved", True),
        Outcome("send $20 to a friend, no extra writes", "solved", "solved", True)), "logical", True),
    # the same text and evidence, two hidden truths: with no settling example nobody can tell which one it is
    "ambiguous_matters": Scenario("ambiguous_matters", _AMBIG, _DATE_FREE, "ambiguous", True),
    "ambiguous_harmless": Scenario("ambiguous_harmless", _AMBIG, _DATE_FREE, "ambiguous", False),
}

# What a working judge should say, for the stub. Keyed by the new harness text; cites ERIE ids.
STUB_TABLE = {
    _NOISE: {"kind": "noise", "reason": "E1 and E2 are touched by the change and both answers are unchanged.",
             "evidence": "E1, E2"},
    _LOGICAL: {"kind": "logical", "reason": "E1 shows a solved task that is not solved under the new harness.",
               "evidence": "E1"},
    _AMBIG: {"kind": "ambiguous", "reason": "E1 and E2 are not touched by the date rule, so they prove nothing either way.",
             "evidence": "E1, E2"},
}

# Fixed packet per script for the stub ERIE: no record read, no network. Wiring tests only.
STUB_PACKETS = {name: Packet(tuple(example_item(i, o) for i, o in enumerate(sc.outcomes, 1)))
                for name, sc in SCENARIOS.items()}