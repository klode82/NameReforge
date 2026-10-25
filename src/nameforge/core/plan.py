import os
import sys
from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from nameforge.core.actions import FileContext, NameParts, RenameAction
from nameforge.i18n import tr

CASE_INSENSITIVE = sys.platform != "linux"  # macOS/Windows: Foo e foo sono lo stesso file
_WIN_BAD = set('<>:"/\\|?*') | {chr(c) for c in range(32)}
_WIN_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                 *(f"LPT{i}" for i in range(1, 10))}


class Cancelled(Exception):
    """Il piano è obsoleto: l'elenco o le azioni sono cambiati durante il calcolo."""


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
        return tr("error.name_empty_or_reserved")
    if "/" in name or "\0" in name:
        return tr("error.character_not_allowed")
    if len(name.encode()) > 255:
        return tr("error.name_too_long")
    if windows:
        if set(name) & _WIN_BAD:
            return tr("error.character_not_allowed_windows")
        if name[-1] in ". ":
            return tr("error.trailing_dot_space_windows")
        if name.split(".")[0].upper() in _WIN_RESERVED:
            return tr("error.reserved_name_windows")
    return None


def _names_in(cache: dict[str, set[str]], folder: str, key) -> set[str]:
    if folder not in cache:
        try:
            cache[folder] = {key(n) for n in os.listdir(folder)}
        except OSError:
            cache[folder] = set()
    return cache[folder]


def build_plan(
    paths: Iterable[Path],
    actions: Sequence[RenameAction],
    case_insensitive: bool = CASE_INSENSITIVE,
    windows: bool = sys.platform == "win32",
    cancel: Callable[[], bool] | None = None,
) -> list[Entry]:
    """Dry-run: calcola i nuovi nomi e segnala i conflitti; nessuna scrittura su disco."""
    key = str.casefold if case_insensitive else str
    counters: dict[str, int] = defaultdict(int)
    entries, parents, names = [], [], []
    for i, p in enumerate(map(Path, paths)):
        if cancel and i % 1024 == 0 and cancel():
            raise Cancelled
        parent = os.path.dirname(p) or "."  # str: hash e confronto di Path sono lenti con 50.000 file
        entries.append(Entry(p, apply_actions(actions, p, i, counters[parent])))
        parents.append(parent)
        names.append(os.path.basename(p))
        counters[parent] += 1

    sources = {(par, key(n)) for par, n in zip(parents, names)}
    seen: dict[tuple[str, str], int] = defaultdict(int)
    keys = [(par, key(e.new_name)) for e, par in zip(entries, parents)]
    for k in keys:
        seen[k] += 1
    on_disk: dict[str, set[str]] = {}  # un listdir per cartella invece di uno stat per file
    for i, (e, k) in enumerate(zip(entries, keys)):
        if invalid_reason(e.new_name, windows):
            e.status = Status.INVALID
        elif e.new_name == names[i]:
            e.status = Status.UNCHANGED
        elif seen[k] > 1:
            e.status = Status.DUPLICATE
        elif k not in sources and k[1] in _names_in(on_disk, k[0], key):
            e.status = Status.EXISTS
    return entries


def can_execute(plan: Sequence[Entry]) -> bool:
    return not any(e.status.blocking for e in plan)
