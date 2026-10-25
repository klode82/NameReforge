import os
from collections.abc import Iterable, Sequence
from pathlib import Path

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    QRunnable,
    Qt,
    QThreadPool,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPalette

from nameforge.core.actions import RenameAction
from nameforge.core.plan import Cancelled, Entry, Status, build_plan
from nameforge.i18n import N_, tr

HEADERS = (N_("Nome attuale"), N_("Nuovo nome"), N_("Percorso"), N_("Dimensione"))
MESSAGES = {
    Status.DUPLICATE: N_("Più file avrebbero lo stesso nome"),
    Status.EXISTS: N_("Esiste già un file con questo nome"),
    Status.INVALID: N_("Nome non valido"),
}
_ROOT = QModelIndex()
CONFLICT_COLOR = QColor(255, 120, 120, 110)


def human_size(n: int) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{int(size)} B" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024


class _Signals(QObject):
    done = Signal(int, object)  # (generazione, piano | eccezione)


class _Job(QRunnable):
    def __init__(self, gen, paths, actions, model, signals):
        super().__init__()
        self.gen, self.paths, self.actions, self.model, self.signals = gen, paths, actions, model, signals

    def run(self):
        try:
            result = build_plan(self.paths, self.actions, cancel=lambda: self.gen != self.model._gen)
        except Cancelled:
            return
        except Exception as exc:  # noqa: BLE001 azione difettosa: il modello tiene il piano precedente
            result = exc
        self.signals.done.emit(self.gen, result)


class FileTableModel(QAbstractTableModel):
    """Elenco file + piano di rinomina. Ogni modifica ricalcola il piano: l'ordine conta (enumerazione)."""

    planStarted = Signal()
    planReady = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._gen = 0
        self._busy = False
        self.error: str | None = None
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)  # ponytail: thread + GIL; processo separato se la UI rallenta ancora a 50.000 file
        self._signals = _Signals()
        self._signals.done.connect(self._on_done)
        self._entries: list[Entry] = []
        self._sizes: dict[Path, int] = {}
        self._actions: Sequence[RenameAction] = ()

    @property
    def entries(self) -> list[Entry]:
        return self._entries

    @property
    def busy(self) -> bool:
        """True mentre il piano è in calcolo: i nomi mostrati possono essere obsoleti."""
        return self._busy

    def shutdown(self) -> None:
        self._gen += 1
        self._pool.waitForDone()

    @property
    def has_conflicts(self) -> bool:
        return any(e.status.blocking for e in self._entries)

    def rowCount(self, parent=_ROOT) -> int:
        return 0 if parent.isValid() else len(self._entries)

    def columnCount(self, parent=_ROOT) -> int:
        return 0 if parent.isValid() else len(HEADERS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return tr(HEADERS[section])

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
        if col == 1 and e.status is Status.OK:  # nome che cambierà: in evidenza
            if role == Qt.FontRole:
                f = QFont()
                f.setBold(True)
                return f
            if role == Qt.ForegroundRole:
                pal = QGuiApplication.palette()
                accent = pal.color(QPalette.Highlight)
                # contrasto: più scuro su sfondo chiaro, più chiaro su sfondo scuro
                return accent.darker(125) if pal.color(QPalette.Base).lightness() > 128 else accent.lighter(135)
        if role == Qt.BackgroundRole and e.status.blocking:
            return CONFLICT_COLOR
        if role == Qt.ToolTipRole and e.status in MESSAGES:
            return tr(MESSAGES[e.status])
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

    def apply_renames(self, mapping: dict[Path, Path]) -> None:
        """Dopo una rinomina (o un undo) sul disco: aggiorna i percorsi in elenco, mantenendo l'ordine."""
        for old, new in mapping.items():
            if old in self._sizes:
                self._sizes[new] = self._sizes.pop(old)
        self._rebuild([mapping.get(e.path, e.path) for e in self._entries])

    @property
    def conflicts(self) -> int:
        return sum(e.status.blocking for e in self._entries)

    @property
    def changes(self) -> int:
        return sum(e.status is Status.OK for e in self._entries)

    def clear(self) -> None:
        self._sizes.clear()
        self._rebuild([])

    def set_actions(self, actions: Sequence[RenameAction]) -> None:
        self._actions = actions
        self._replan()

    def sort(self, column, order=Qt.AscendingOrder):
        keys = (
            lambda e: e.path.name.casefold(),
            lambda e: e.new_name.casefold(),
            lambda e: (str(e.path.parent).casefold(), e.path.name.casefold()),
            lambda e: self._sizes.get(e.path, 0),
        )
        ordered = sorted(self._entries, key=keys[column], reverse=order == Qt.DescendingOrder)
        self._rebuild([e.path for e in ordered])

    def _rebuild(self, paths: list[Path]) -> None:
        """Elenco subito, con nomi provvisori; il piano arriva dal thread."""
        self.beginResetModel()
        self._entries = [Entry(p, p.name, Status.UNCHANGED) for p in paths]
        keep = set(paths)
        self._sizes = {p: s for p, s in self._sizes.items() if p in keep}
        self.endResetModel()
        self._replan()

    def _replan(self) -> None:
        self._gen += 1
        if not self._entries:
            self._busy = False
            self.planReady.emit()
            return
        self._busy = True
        self.planStarted.emit()
        paths = [e.path for e in self._entries]
        self._pool.start(_Job(self._gen, paths, self._actions, self, self._signals))

    def _on_done(self, gen: int, result) -> None:
        if gen != self._gen:
            return
        self._busy = False
        if isinstance(result, Exception):
            self.error = f"{type(result).__name__}: {result}"
        else:
            self.error = None
            self._entries = result
            if result:
                self.dataChanged.emit(self.index(0, 0), self.index(len(result) - 1, len(HEADERS) - 1))
        self.planReady.emit()
