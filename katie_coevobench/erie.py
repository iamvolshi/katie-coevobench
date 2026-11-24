"""ERIE step: retrieve an evidence packet, read only. Ingredients and a recipe, not soup.

ERIE retrieves. The judge (judge.py) classifies from the packet. KATIE (arms.py) acts.
Nothing here classifies a change or writes to the record.
Every item carries its source and an authority grade 0-9, as in the K record.
"""
from __future__ import annotations
from dataclasses import dataclass
from .record import Record


@dataclass(frozen=True)
class Outcome:
    """One example task replayed under the old and new harness, with the actual answers."""
    task: str
    old_answer: str
    new_answer: str
    touched: bool      # does the change touch this task at all?


@dataclass(frozen=True)
class Evidence:
    id: str            # E1, E2, ...
    type: str          # example | prior
    source: str
    authority: int
    text: str
    shows: str         # changed | unchanged | nothing: a retrieval fact, not a classification


@dataclass(frozen=True)
class Packet:
    items: tuple[Evidence, ...]

    def get(self, eid: str) -> Evidence | None:
        return next((e for e in self.items if e.id == eid), None)

    def has_outcome(self) -> bool:
        """True if at least one item shows an outcome (changed or unchanged under a touched task)."""
        return any(e.shows in ("changed", "unchanged") for e in self.items)

    def render(self) -> str:
        return "\n".join(f"{e.id} [{e.type}; source={e.source}; authority={e.authority}] {e.text}" for e in self.items) \
            or "(no evidence retrieved)"

    def to_data(self) -> list[dict]:
        return [{"id": e.id, "type": e.type, "source": e.source, "authority": e.authority,
                 "shows": e.shows, "text": e.text} for e in self.items]


def example_item(i: int, o: Outcome) -> Evidence:
    changed = o.old_answer != o.new_answer
    if not o.touched:
        shows, note = "nothing", "task not touched by the change, so this proves nothing either way"
    elif changed:
        shows, note = "changed", "touched by the change; the answer CHANGED"
    else:
        shows, note = "unchanged", "touched by the change; the answer did NOT change"
    return Evidence(f"E{i}", "example", "replay:old+new-harness", 7,
                    f"task '{o.task}': old answer = {o.old_answer!r}; new answer = {o.new_answer!r}; {note}", shows)


class Erie:
    """Builds the packet from replayed example outcomes and from the test record's earlier judgments."""

    def __init__(self, max_prior: int = 3):
        self.max_prior = max_prior

    def retrieve(self, record: Record | None, outcomes, script: str | None = None) -> Packet:
        items = [example_item(i, o) for i, o in enumerate(outcomes, 1)]
        n = len(items)
        for e in (record.all("judgment") if record else [])[-self.max_prior:]:
            k = e.data.get("judged_kind")
            if e.data.get("failed"):
                continue
            n += 1
            shows = {"logical": "changed", "noise": "unchanged"}.get(k, "nothing")
            later = [x for x in record.all("training_job") if int(x.kid[3:]) > int(e.kid[3:])][:1]
            after = f"; next training job {later[0].kid} {'hurt' if later[0].data.get('hurt') else 'did not hurt'}" if later else ""
            items.append(Evidence(f"E{n}", "prior", e.kid, e.authority,
                                  f"earlier harness change {e.kid} was judged {k}{after}", shows))
        return Packet(tuple(items))


class StubErie:
    """Fixed packet per script. No record, no network. Tests prove the wiring, not the judgment."""

    def __init__(self, packets: dict[str, Packet]):
        self.packets = packets

    def retrieve(self, record, outcomes, script: str | None = None) -> Packet:
        return self.packets[script]
