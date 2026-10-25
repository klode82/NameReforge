import csv
from datetime import datetime
from pathlib import Path

from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from nameforge.core.executor import Outcome
from nameforge.help import set_tip
from nameforge.i18n import N_, tr

HEADERS = (N_("log.column.time"), N_("log.column.operation"), N_("log.column.result"), N_("log.column.from"), N_("log.column.to"), N_("log.column.detail"))
BAD = QBrush(QColor("#b91c1c"))


class LogTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.summary = QLabel(tr("log.empty"))
        self.table = QTableWidget(0, len(HEADERS))
        self.table.setHorizontalHeaderLabels([tr(h) for h in HEADERS])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        export, clear = QPushButton(tr("button.export_csv")), QPushButton(tr("button.clear"))
        set_tip(self.table, "log.table")
        set_tip(export, "log.export")
        set_tip(clear, "log.clear")
        export.clicked.connect(self._export_dialog)
        clear.clicked.connect(self.clear)
        bar = QHBoxLayout()
        bar.addWidget(export)
        bar.addWidget(clear)
        bar.addStretch()
        layout = QVBoxLayout(self)
        layout.addWidget(self.summary)
        layout.addWidget(self.table)
        layout.addLayout(bar)

    def add(self, operation: str, outcomes: list[Outcome]) -> None:
        now = datetime.now().strftime("%H:%M:%S")
        for o in outcomes:
            row = self.table.rowCount()
            self.table.insertRow(row)
            cells = (now, operation, "OK" if o.ok else tr("log.result_error"), str(o.src), str(o.dst), o.error or "")
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if not o.ok:
                    item.setForeground(BAD)
                self.table.setItem(row, col, item)
        ok = sum(o.ok for o in outcomes)
        self.summary.setText(tr("log.summary", operation=operation, ok=ok, failed=len(outcomes) - ok))
        self.table.scrollToBottom()

    def rows(self) -> list[list[str]]:
        return [[self.table.item(r, c).text() for c in range(len(HEADERS))] for r in range(self.table.rowCount())]

    def clear(self) -> None:
        self.table.setRowCount(0)
        self.summary.setText(tr("log.empty"))

    def export_csv(self, path: Path) -> None:
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow([tr(h) for h in HEADERS])
            w.writerows(self.rows())

    def _export_dialog(self) -> None:
        name, _ = QFileDialog.getSaveFileName(self, tr("dialog.export_log_title"), "nameforge-log.csv", "CSV (*.csv)")
        if name:
            try:
                self.export_csv(Path(name))
            except OSError as exc:
                QMessageBox.warning(self, tr("dialog.export_log_title"), str(exc))
