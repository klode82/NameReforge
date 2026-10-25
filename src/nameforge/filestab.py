from pathlib import Path

from PySide6.QtCore import QEvent, QMimeData, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QStackedLayout,
    QStyle,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from nameforge.core.scan import collect_files
from nameforge.filemodel import FileTableModel
from nameforge.theme import icon


def paths_from_mime(mime: QMimeData) -> list[Path]:
    return [Path(u.toLocalFile()) for u in mime.urls() if u.isLocalFile()]


# Quota di larghezza di Nome attuale, Nuovo nome, Percorso; Dimensione si adatta al contenuto.
COLUMN_WEIGHTS = (0.37, 0.37, 0.26)


class FilesTab(QWidget):
    reforgeRequested = Signal()

    def __init__(self, model: FileTableModel) -> None:
        super().__init__()
        self.model = model
        self.setAcceptDrops(True)

        self.recursive = QCheckBox("Includi sottocartelle")
        self.recursive.setChecked(True)
        self.count = QLabel()
        self.reforge = QPushButton("Reforge")
        self.reforge.setToolTip("Applica le nuove denominazioni ai file sul disco")
        self.reforge.setObjectName("primary")
        self.reforge.setIcon(icon("system-run", QStyle.SP_MediaPlay))
        self.reforge.clicked.connect(self.reforgeRequested)
        self._locked = False
        add_files = QPushButton("Aggiungi file…")
        add_folder = QPushButton("Aggiungi cartella…")
        remove = QPushButton("Rimuovi selezionati")
        clear = QPushButton("Svuota")
        add_files.setIcon(icon("document-open", QStyle.SP_FileIcon))
        add_folder.setIcon(icon("folder-open", QStyle.SP_DirOpenIcon))
        remove.setIcon(icon("list-remove", QStyle.SP_DialogCancelButton))
        clear.setIcon(icon("edit-clear", QStyle.SP_DialogResetButton))
        add_files.clicked.connect(self.pick_files)
        add_folder.clicked.connect(self.pick_folder)
        remove.clicked.connect(self.remove_selected)
        clear.clicked.connect(model.clear)

        bar = QHBoxLayout()
        for w in (add_files, add_folder, self.recursive, remove, clear):
            bar.addWidget(w)
        bar.addStretch()
        bar.addWidget(self.count)
        bar.addWidget(self.reforge)

        self.view = QTableView()
        self.view.setModel(model)
        self.view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.view.setSortingEnabled(True)  # il modello ordina da solo (sort), niente proxy
        self.view.setAcceptDrops(False)  # il drop sale al widget padre
        self.view.setWordWrap(False)
        self.view.verticalHeader().setVisible(False)
        header = self.view.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setMinimumSectionSize(60)
        header.sectionResized.connect(self._on_section_resized)
        header.sectionHandleDoubleClicked.connect(self._refit)  # doppio clic su un separatore: ripartizione automatica
        self._viewport = self.view.viewport()  # riferimento Python: l'eventFilter può girare a oggetti Qt già distrutti
        self._viewport.installEventFilter(self)
        self.view.setTextElideMode(Qt.ElideMiddle)  # i nomi lunghi perdono il centro, non l'estensione
        self._user_sized = False  # dopo un ridimensionamento a mano non tocchiamo più le larghezze
        self._fitting = False

        self.empty = QLabel("Trascina qui file e cartelle\noppure usa «Aggiungi file…» e «Aggiungi cartella…»")
        self.empty.setObjectName("empty")
        self.empty.setAlignment(Qt.AlignCenter)
        self.stack = QStackedLayout()
        self.stack.addWidget(self.empty)
        self.stack.addWidget(self.view)
        self.view.setAlternatingRowColors(True)
        self.view.setShowGrid(False)
        self.view.verticalHeader().setDefaultSectionSize(28)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addLayout(bar)
        layout.addLayout(self.stack)

        model.modelReset.connect(self._update_count)
        model.planStarted.connect(self._update_count)
        model.planReady.connect(self._update_count)
        self._update_count()

    def add_paths(self, paths) -> int:
        n = self.model.add_paths(collect_files(paths, self.recursive.isChecked()))
        self._update_count()
        return n

    def remove_selected(self) -> None:
        self.model.remove_rows(i.row() for i in self.view.selectionModel().selectedRows())

    def eventFilter(self, obj, event) -> bool:
        if obj is self._viewport and event.type() == QEvent.Resize:
            self._fit_columns()
        return super().eventFilter(obj, event)

    def _fit_columns(self) -> None:
        if self._user_sized:
            return
        header = self.view.horizontalHeader()
        total = self.view.viewport().width() - header.sectionSize(3)
        self._fitting = True
        for col, weight in enumerate(COLUMN_WEIGHTS):
            self.view.setColumnWidth(col, max(60, int(total * weight)))
        self._fitting = False

    def _refit(self, _section: int = 0) -> None:
        self._user_sized = False
        self._fit_columns()

    def _on_section_resized(self, column: int, _old: int, _new: int) -> None:
        if not self._fitting and column < 3:
            self._user_sized = True

    def set_locked(self, locked: bool) -> None:
        """Durante una rinomina sul disco il pulsante resta spento."""
        self._locked = locked
        self._update_count()

    def _update_count(self) -> None:
        m = self.model
        extra = " — calcolo…" if m.busy else (f" — {m.conflicts} in conflitto" if m.conflicts else "")
        self.count.setText(f"{m.rowCount()} file{extra}")
        self.stack.setCurrentWidget(self.view if m.rowCount() else self.empty)
        self.reforge.setEnabled(not self._locked and not m.busy and not m.conflicts and m.changes > 0)

    def pick_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "Aggiungi file")
        self.add_paths(map(Path, files))

    def pick_folder(self) -> None:
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
