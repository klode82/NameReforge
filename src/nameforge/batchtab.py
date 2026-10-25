import re
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from nameforge.actionpanels import SPEC_BY_KEY, build_action
from nameforge.core.actions import RenameAction
from nameforge.profiles import ProfileError, dump_profile, parse_profile

BAD = QBrush(QColor("#b91c1c"))


def summarize(key: str, values: dict) -> str:
    spec = SPEC_BY_KEY[key]
    changed = [f"{f.key}={values[f.key]!r}" for f in spec.fields if f.key in values and values[f.key] != f.default]
    return f"{spec.title}" + (f" — {', '.join(changed)}" if changed else "")


class BatchTab(QWidget):
    """Sequenza ordinata di azioni, eseguite a cascata. Riordino con il trascinamento."""

    changed = Signal()

    def __init__(self, profiles_dir: Callable[[], Path]) -> None:
        super().__init__()
        self._profiles_dir = profiles_dir
        self.list = QListWidget()
        self.list.setDragDropMode(QAbstractItemView.InternalMove)
        self.list.setDefaultDropAction(Qt.MoveAction)
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list.itemChanged.connect(lambda _: self.changed.emit())
        self.list.model().rowsMoved.connect(lambda *_: self.changed.emit())
        self.hint = QLabel("Aggiungi azioni dalla scheda Actions. L'ordine conta: ognuna lavora sul risultato della precedente.")
        self.hint.setWordWrap(True)
        self.errors = QLabel()
        self.errors.setStyleSheet("color: #b91c1c;")
        self.errors.setWordWrap(True)

        buttons = []
        for text, slot in (
            ("Rimuovi selezionate", self.remove_selected),
            ("Svuota", self.clear),
            ("Salva profilo…", self._save_dialog),
            ("Carica profilo…", self._load_dialog),
        ):
            b = QPushButton(text)
            b.clicked.connect(slot)
            buttons.append(b)
        bar = QHBoxLayout()
        for b in buttons:
            bar.addWidget(b)
        bar.addStretch()

        layout = QVBoxLayout(self)
        layout.addWidget(self.hint)
        layout.addWidget(self.list)
        layout.addWidget(self.errors)
        layout.addLayout(bar)

    def add(self, key: str, values: dict, enabled: bool = True) -> None:
        item = QListWidgetItem(summarize(key, values))
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled)
        item.setCheckState(Qt.Checked if enabled else Qt.Unchecked)
        item.setSizeHint(QSize(0, 34))
        item.setData(Qt.UserRole, {"key": key, "values": dict(values)})
        self.list.addItem(item)
        self.changed.emit()

    def items(self) -> list[dict]:
        out = []
        for i in range(self.list.count()):
            it = self.list.item(i)
            out.append({**it.data(Qt.UserRole), "enabled": it.checkState() == Qt.Checked})
        return out

    def set_items(self, items: list[dict]) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        self.list.blockSignals(False)
        for it in items:
            self.add(it["key"], it["values"], it["enabled"])
        if not items:
            self.changed.emit()

    def actions(self) -> list[RenameAction]:
        """Azioni attive in ordine. Quelle con parametri non validi sono saltate e segnate in rosso."""
        out, problems = [], []
        self.list.blockSignals(True)  # setForeground emette itemChanged: senza blocco, ricorsione infinita
        for i in range(self.list.count()):
            it = self.list.item(i)
            data = it.data(Qt.UserRole)
            it.setForeground(QBrush())
            if it.checkState() != Qt.Checked:
                continue
            try:
                out.append(build_action(data["key"], data["values"]))
            except (OSError, UnicodeDecodeError, ValueError, re.error) as exc:
                it.setForeground(BAD)
                problems.append(f"{SPEC_BY_KEY[data['key']].title}: {exc}")
        self.list.blockSignals(False)
        self.errors.setText("\n".join(problems))
        return out

    def remove_selected(self) -> None:
        for it in self.list.selectedItems():
            self.list.takeItem(self.list.row(it))
        self.changed.emit()

    def clear(self) -> None:
        self.list.clear()
        self.changed.emit()

    def save_profile(self, path: Path) -> None:
        path.write_text(dump_profile(self.items()), encoding="utf-8")

    def load_profile(self, path: Path) -> None:
        self.set_items(parse_profile(path.read_text(encoding="utf-8")))

    def _save_dialog(self) -> None:
        folder = self._profiles_dir()
        folder.mkdir(parents=True, exist_ok=True)
        name, _ = QFileDialog.getSaveFileName(self, "Salva profilo", str(folder / "profilo.json"), "Profili (*.json)")
        if name:
            try:
                self.save_profile(Path(name))
            except OSError as exc:
                QMessageBox.warning(self, "Salva profilo", str(exc))

    def _load_dialog(self) -> None:
        folder = self._profiles_dir()
        name, _ = QFileDialog.getOpenFileName(self, "Carica profilo", str(folder), "Profili (*.json)")
        if name:
            try:
                self.load_profile(Path(name))
            except (OSError, ProfileError) as exc:
                QMessageBox.warning(self, "Carica profilo", str(exc))
