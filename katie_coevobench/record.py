"""Append-only KATIE test record. Own KID space (T1-n); never touches the trifecta record."""
from __future__ import annotations
import json, datetime
from dataclasses import dataclass, asdict, field
from pathlib import Path


@dataclass(frozen=True)
class Entry:
    kid: str
    kind: str          # harness | trajectory | training_job | candidate | refusal
    authority: int     # 0-9
    source: str
    what: str
    when: str
    why: str
    supersedes: str | None = None
    data: dict = field(default_factory=dict)


class Record:
    """Entries can be added, never changed or removed. A change is a new entry that supersedes."""

    def __init__(self, path: Path | None = None):
        self._entries: list[Entry] = []
        self._path = Path(path) if path else None
        if self._path:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text("", encoding="utf-8")  # a run owns a fresh file

    def append(self, kind, authority, source, what, why, supersedes=None, **data) -> Entry:
        if not why or not what or not source:
            raise ValueError("an entry needs what, why and source")
        if not 0 <= authority <= 9:
            raise ValueError("authority is 0-9")
        if supersedes is not None and self.get(supersedes) is None:
            raise KeyError(f"cannot supersede unknown {supersedes}")
        e = Entry(f"T1-{len(self._entries) + 1}", kind, authority, source, what,
                  datetime.datetime.now(datetime.timezone.utc).isoformat(), why, supersedes, dict(data))
        self._entries.append(e)
        if self._path:
            with self._path.open("a", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(asdict(e), sort_keys=True) + "\n")
        return e

    def get(self, kid: str) -> Entry | None:
        return next((e for e in self._entries if e.kid == kid), None)

    def all(self, kind: str | None = None) -> list[Entry]:
        return [e for e in self._entries if kind is None or e.kind == kind]

    def __len__(self):
        return len(self._entries)
