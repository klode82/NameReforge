import sys
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from nameforge.core.actions import FileContext, NameParts, RenameAction

_WIN_BAD = set('<>:"/\\|?*') | {chr(c) for c in range(32)}
_WIN_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                 *(f"LPT{i}" for i in range(1, 10))}


class Status(Enum):
    OK = "ok"
    UNCHANGED = "unchanged"
    DUPLICATE = "duplicate"  # due file della selezione puntano allo stesso nome finale
    EXISTS = "exists"  # il nome finale è già occupato da un file fuori dalla selezione
    INVALID = "invalid"

    @property
    def blocking(self) -> bool:
        return self not in (Status.OK, Status.UNCHANGED)


@dataclass
class Entry:
    path: Path
    new_name: str
    status: Status = Status.OK

    @property
    def target(self) -> Path:
        return self.path.with_name(self.new_name)


def apply_actions(actions: Sequence[RenameAction], path: Path, index: int, folder_index: int) -> str:
    ctx = FileContext(path, index, folder_index)
    parts = NameParts.from_name(path.name)
    for a in actions:
        parts = a.process(parts, ctx)
    return parts.full


def invalid_reason(name: str, windows: bool = sys.platform == "win32") -> str | None:
    if not name or name in (".", ".."):
        return "nome vuoto o riservato"
    if "/" in name or "\0" in name:
        return "carattere non ammesso"
    if len(name.encode()) > 255:
        return "nome troppo lungo"
    if windows:
        if set(name) & _WIN_BAD:
            return "carattere non ammesso su Windows"
        if name[-1] in ". ":
            return "punto o spazio finale non ammesso su Windows"
        if name.split(".")[0].upper() in _WIN_RESERVED:
            return "nome riservato di Windows"
    return None


def build_plan(
    paths: Iterable[Path],
    actions: Sequence[RenameAction],
    case_insensitive: bool = sys.platform != "linux",
    windows: bool = sys.platform == "win32",
) -> list[Entry]:
    """Dry-run: calcola i nuovi nomi e segnala i conflitti; nessuna scrittura su disco."""
    key = str.casefold if case_insensitive else str
    counters: dict[Path, int] = defaultdict(int)
    entries = []
    for i, p in enumerate(map(Path, paths)):
        entries.append(Entry(p, apply_actions(actions, p, i, counters[p.parent])))
        counters[p.parent] += 1

    sources = {(e.path.parent, key(e.path.name)) for e in entries}
    seen: dict[tuple[Path, str], int] = defaultdict(int)
    for e in entries:
        seen[(e.path.parent, key(e.new_name))] += 1
    for e in entries:
        k = (e.path.parent, key(e.new_name))
        if invalid_reason(e.new_name, windows):
            e.status = Status.INVALID
        elif e.new_name == e.path.name:
            e.status = Status.UNCHANGED
        elif seen[k] > 1:
            e.status = Status.DUPLICATE
        elif k not in sources and e.target.exists():
            e.status = Status.EXISTS
    return entries


def can_execute(plan: Sequence[Entry]) -> bool:
    return not any(e.status.blocking for e in plan)
