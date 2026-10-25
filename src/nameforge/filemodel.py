import os
from collections.abc import Iterable, Sequence
from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor

from nameforge.core.actions import RenameAction
from nameforge.core.plan import Entry, Status, build_plan

HEADERS = ("Nome attuale", "Nuovo nome", "Percorso", "Dimensione")
MESSAGES = {
    Status.DUPLICATE: "Più file avrebbero lo stesso nome",
    Status.EXISTS: "Esiste già un file con questo nome",
    Status.INVALID: "Nome non valido",
}
_ROOT = QModelIndex()
CONFLICT_COLOR = QColor(255, 120, 120, 110)


def human_size(n: int) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{int(size)} B" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024


class FileTableModel(QAbstractTableModel):
    """Elenco file + piano di rinomina. Ogni modifica ricalcola il piano: l'ordine conta (enumerazione)."""

    def __init__(self) -> None:
        super().__init__()
        self._entries: list[Entry] = []
        self._sizes: dict[Path, int] = {}
        self._actions: Sequence[RenameAction] = ()

    @property
    def entries(self) -> list[Entry]:
        return self._entries

    @property
    def has_conflicts(self) -> bool:
        return any(e.status.blocking for e in self._entries)

    def rowCount(self, parent=_ROOT) -> int:
        return 0 if parent.isValid() else len(self._entries)

    def columnCount(self, parent=_ROOT) -> int:
        return 0 if parent.isValid() else len(HEADERS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return HEADERS[section]

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        e, col = self._entries[index.row()], index.column()
        if role == Qt.DisplayRole:
            if col == 0:
                return e.path.name
            if col == 1:
                return e.new_name
            if col == 2:
                return str(e.path.parent)
            return human_size(self._sizes.get(e.path, 0))
        if role == Qt.BackgroundRole and e.status.blocking:
            return CONFLICT_COLOR
        if role == Qt.ToolTipRole and e.status in MESSAGES:
            return MESSAGES[e.status]
        if role == Qt.TextAlignmentRole and col == 3:
            return int(Qt.AlignRight | Qt.AlignVCenter)

    def add_paths(self, paths: Iterable[Path]) -> int:
        have = {e.path for e in self._entries}
        new = [p for p in dict.fromkeys(paths) if p not in have]
        if not new:
            return 0
        for p in new:
            try:
                self._sizes[p] = os.stat(p).st_size
            except OSError:
                self._sizes[p] = 0
        self._rebuild([e.path for e in self._entries] + new)
        return len(new)

    def remove_rows(self, rows: Iterable[int]) -> None:
        drop = set(rows)
        self._rebuild([e.path for i, e in enumerate(self._entries) if i not in drop])

    def clear(self) -> None:
        self._sizes.clear()
        self._rebuild([])

    def set_actions(self, actions: Sequence[RenameAction]) -> None:
        self._actions = actions
        if self._entries:
            self._replan([e.path for e in self._entries])
            self.dataChanged.emit(self.index(0, 0), self.index(len(self._entries) - 1, len(HEADERS) - 1))

    def sort(self, column, order=Qt.AscendingOrder):
        keys = (
            lambda e: e.path.name.casefold(),
            lambda e: e.new_name.casefold(),
            lambda e: (str(e.path.parent).casefold(), e.path.name.casefold()),
            lambda e: self._sizes.get(e.path, 0),
        )
        ordered = sorted(self._entries, key=keys[column], reverse=order == Qt.DescendingOrder)
        self._rebuild([e.path for e in ordered])

    def _replan(self, paths: list[Path]) -> None:
        self._entries = build_plan(paths, self._actions)

    def _rebuild(self, paths: list[Path]) -> None:
        self.beginResetModel()
        self._replan(paths)
        keep = set(paths)
        self._sizes = {p: s for p, s in self._sizes.items() if p in keep}
        self.endResetModel()
