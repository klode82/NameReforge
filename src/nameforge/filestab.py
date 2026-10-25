from pathlib import Path

from PySide6.QtCore import QMimeData, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from nameforge.core.scan import collect_files
from nameforge.filemodel import FileTableModel


def paths_from_mime(mime: QMimeData) -> list[Path]:
    return [Path(u.toLocalFile()) for u in mime.urls() if u.isLocalFile()]


class FilesTab(QWidget):
    def __init__(self, model: FileTableModel) -> None:
        super().__init__()
        self.model = model
        self.setAcceptDrops(True)

        self.recursive = QCheckBox("Includi sottocartelle")
        self.recursive.setChecked(True)
        self.count = QLabel()
        add_files = QPushButton("Aggiungi file…")
        add_folder = QPushButton("Aggiungi cartella…")
        remove = QPushButton("Rimuovi selezionati")
        clear = QPushButton("Svuota")
        add_files.clicked.connect(self._pick_files)
        add_folder.clicked.connect(self._pick_folder)
        remove.clicked.connect(self.remove_selected)
        clear.clicked.connect(model.clear)

        bar = QHBoxLayout()
        for w in (add_files, add_folder, self.recursive, remove, clear):
            bar.addWidget(w)
        bar.addStretch()
        bar.addWidget(self.count)

        self.view = QTableView()
        self.view.setModel(model)
        self.view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.view.setSortingEnabled(True)  # il modello ordina da solo (sort), niente proxy
        self.view.setAcceptDrops(False)  # il drop sale al widget padre
        self.view.setWordWrap(False)
        self.view.verticalHeader().setVisible(False)
        self.view.horizontalHeader().setStretchLastSection(False)
        self.view.horizontalHeader().setSectionResizeMode(0, self.view.horizontalHeader().ResizeMode.Interactive)
        for col, w in enumerate((260, 260, 320, 90)):
            self.view.setColumnWidth(col, w)

        layout = QVBoxLayout(self)
        layout.addLayout(bar)
        layout.addWidget(self.view)

        model.modelReset.connect(self._update_count)
        self._update_count()

    def add_paths(self, paths) -> int:
        n = self.model.add_paths(collect_files(paths, self.recursive.isChecked()))
        self._update_count()
        return n

    def remove_selected(self) -> None:
        self.model.remove_rows(i.row() for i in self.view.selectionModel().selectedRows())

    def _update_count(self) -> None:
        self.count.setText(f"{self.model.rowCount()} file")

    def _pick_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "Aggiungi file")
        self.add_paths(map(Path, files))

    def _pick_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Aggiungi cartella")
        if folder:
            self.add_paths([Path(folder)])

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:
        event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        self.add_paths(paths_from_mime(event.mimeData()))
        event.setDropAction(Qt.CopyAction)
        event.accept()
