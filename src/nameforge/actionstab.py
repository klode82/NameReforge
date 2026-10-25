from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QStyle,
    QTableView,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from nameforge.actionpanels import SPECS, ActionPanel, WarningLabel
from nameforge.core.actions import RenameAction
from nameforge.filemodel import FileTableModel
from nameforge.help import action_details, action_summary, rich, set_tip, show_help
from nameforge.i18n import tr
from nameforge.theme import icon

DEBOUNCE_MS = 280


class ActionsTab(QWidget):
    """Lista azioni a sinistra, parametri a destra. Emette l'azione scelta dopo una pausa nella digitazione."""

    actionsChanged = Signal(list)
    addToBatch = Signal(str, dict)  # chiave azione, valori

    def __init__(self, model: FileTableModel) -> None:
        super().__init__()
        self._n_files = model.rowCount
        self._runtime_error = ""
        self.list = QListWidget()
        self.stack = QStackedWidget()
        self.panels = [ActionPanel(s) for s in SPECS]
        for panel in self.panels:
            self.list.addItem(tr(panel.spec.title))
            item = self.list.item(self.list.count() - 1)
            item.setSizeHint(QSize(0, 34))  # il padding del QSS non conta nell'altezza
            if summary := action_summary(panel.spec.key):
                item.setToolTip(rich(summary))
            self.stack.addWidget(panel)
            panel.changed.connect(self._schedule)
        self.list.setMaximumWidth(220)
        self.list.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.list.currentRowChanged.connect(lambda i: self.heading.setText(tr(SPECS[i].title) if i >= 0 else ""))
        self.list.currentRowChanged.connect(self._schedule)

        self.warning = WarningLabel()
        add = QPushButton(tr("button.add_to_batch"))
        add.setIcon(icon("list-add", QStyle.SP_ArrowRight))
        self.heading = QLabel()
        self.heading.setObjectName("heading")
        self.help_button = QToolButton()
        self.help_button.setText("?")
        self.help_button.setAutoRaise(True)
        self.help_button.clicked.connect(self.show_action_help)
        set_tip(self.help_button, "actions.help")
        head = QHBoxLayout()
        head.addWidget(self.heading)
        head.addWidget(self.help_button)
        head.addStretch()
        add.clicked.connect(self._add_to_batch)
        self.include_current = QCheckBox(tr("checkbox.include_current_in_preview"))
        self.include_current.setChecked(True)
        self.include_current.toggled.connect(self._schedule)
        row = QHBoxLayout()
        row.addWidget(add)
        row.addWidget(self.include_current)
        row.addStretch()
        set_tip(add, "actions.add_to_batch")
        set_tip(self.include_current, "actions.include_current")
        set_tip(self.list, "actions.list")
        right = QWidget()
        col = QVBoxLayout(right)
        col.addLayout(head)
        col.addWidget(self.stack)
        col.addWidget(self.warning)
        col.addLayout(row)
        col.addWidget(self._make_preview(model), 1)

        split = QSplitter(Qt.Horizontal)
        split.addWidget(self.list)
        split.addWidget(right)
        split.setStretchFactor(1, 1)
        layout = QVBoxLayout(self)
        layout.addWidget(split)

        self._timer = QTimer(self, singleShot=True, interval=DEBOUNCE_MS)
        self._timer.timeout.connect(self.emit_now)
        self.list.setCurrentRow(0)

    def _make_preview(self, model: FileTableModel) -> QWidget:
        """Stesso modello della scheda Files: l'anteprima si aggiorna mentre si modificano i parametri."""
        box = QWidget()
        col = QVBoxLayout(box)
        col.setContentsMargins(0, 8, 0, 0)
        title = QLabel(tr("heading.preview"))
        title.setObjectName("heading")
        self.preview_hint = QLabel(tr("hint.preview_empty"))
        self.preview_hint.setObjectName("hint")
        self.preview = QTableView()
        self.preview.setModel(model)
        for column in (2, 3):  # percorso e dimensione restano nella scheda Files
            self.preview.setColumnHidden(column, True)
        self.preview.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.preview.verticalHeader().setVisible(False)
        self.preview.verticalHeader().setDefaultSectionSize(28)
        self.preview.setAlternatingRowColors(True)
        set_tip(self.preview, "actions.preview")
        self.preview.setShowGrid(False)
        self.preview.setTextElideMode(Qt.ElideMiddle)
        self.preview.setSelectionMode(QAbstractItemView.NoSelection)
        self.preview.setEditTriggers(QAbstractItemView.NoEditTriggers)
        col.addWidget(title)
        col.addWidget(self.preview_hint)
        col.addWidget(self.preview)
        model.modelReset.connect(self._update_preview_hint)
        self._update_preview_hint()
        return box

    def _update_preview_hint(self) -> None:
        empty = self._n_files() == 0
        self.preview_hint.setVisible(empty)
        self.preview.setVisible(not empty)

    def show_action_help(self) -> None:
        spec = self.panels[self.list.currentRow()].spec
        show_help(self, tr(spec.title), action_details(spec.key))

    def current_actions(self) -> list[RenameAction]:
        panel = self.panels[self.list.currentRow()]
        action = panel.build()
        self.warning.setText(panel.error or action.warning(self._n_files()) or self._runtime_error)
        return [action]

    def emit_now(self) -> None:
        self._timer.stop()
        self.actionsChanged.emit(self.current_actions())

    def refresh_warning(self) -> None:
        self.current_actions()

    def set_runtime_error(self, message: str | None) -> None:
        """Errore sollevato da un'azione durante il calcolo del piano (nel thread)."""
        self._runtime_error = message or ""
        self.current_actions()

    def _add_to_batch(self) -> None:
        panel = self.panels[self.list.currentRow()]
        if panel.build() is not None and not panel.error:
            self.addToBatch.emit(panel.spec.key, panel.values())
        else:
            self.warning.setText(panel.error or "")

    def _schedule(self) -> None:
        self._timer.start()
