from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths, QThread, Signal
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import QMainWindow, QMessageBox, QProgressBar, QTabWidget

from nameforge import i18n
from nameforge.actionstab import ActionsTab
from nameforge.batchtab import BatchTab
from nameforge.core.executor import PlanBlocked, execute, pending_manifests, undo
from nameforge.core.plan import CASE_INSENSITIVE
from nameforge.filemodel import FileTableModel
from nameforge.filestab import FilesTab
from nameforge.help import guide, load_error, show_help
from nameforge.i18n import LANGUAGES, N_, tr, trn
from nameforge.logtab import LogTab

TABS = (N_("tab.files"), N_("tab.actions"), N_("tab.batch"), N_("tab.log"))


class _Task(QThread):
    """Esegue fn(progress) fuori dal thread UI; i segnali tornano nel thread UI."""

    progressed = Signal(int, int)
    result = Signal(object)
    failed = Signal(str)

    def __init__(self, fn: Callable) -> None:
        super().__init__()
        self._fn = fn

    def run(self) -> None:
        try:
            self.result.emit(self._fn(self.progressed.emit))
        except PlanBlocked as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001 - qualunque errore va mostrato, non perso nel thread
            self.failed.emit(f"{type(exc).__name__}: {exc}")


def _app_data() -> Path:
    return Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation))


class MainWindow(QMainWindow):
    def __init__(self, data_dir: Path | None = None) -> None:
        super().__init__()
        self.data_dir = data_dir or _app_data()
        self.setWindowTitle("NameReforge")
        self.resize(1000, 650)
        self.model = FileTableModel()
        self.files_tab = FilesTab(self.model)
        self.files_tab.reforgeRequested.connect(self.reforge)
        self.actions_tab = ActionsTab(self.model)
        self.batch_tab = BatchTab(lambda: self.data_dir / "profiles")
        self.log_tab = LogTab()
        self.actions_tab.actionsChanged.connect(self._update_actions)
        self.actions_tab.addToBatch.connect(self.batch_tab.add)
        self.batch_tab.changed.connect(self._update_actions)
        self.model.modelReset.connect(self.actions_tab.refresh_warning)
        self.model.planReady.connect(lambda: self.actions_tab.set_runtime_error(self.model.error))

        self.tabs = QTabWidget()
        for widget, name in zip((self.files_tab, self.actions_tab, self.batch_tab, self.log_tab), TABS):
            self.tabs.addTab(widget, tr(name))
        self.setCentralWidget(self.tabs)

        self._build_menus()
        self.progress = QProgressBar()
        self.progress.setMaximumWidth(220)
        self.progress.hide()
        self.statusBar().addPermanentWidget(self.progress)
        err = load_error()
        self.statusBar().showMessage(tr("status.help_not_loaded", err=err) if err else tr("status.ready"))
        self._task: _Task | None = None
        self._refresh_undo()
        self._restore_settings()
        self.actions_tab.emit_now()

    # --- menu, scorciatoie, impostazioni -------------------------------------------------------

    def _action(self, menu, text: str, slot, shortcut=None) -> QAction:
        act = QAction(text, self)
        if shortcut:
            act.setShortcut(shortcut)
        act.triggered.connect(lambda _checked=False: slot())
        menu.addAction(act)
        return act

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu(tr("menu.file"))
        self._action(file_menu, tr("button.add_files"), self.files_tab.pick_files, QKeySequence.Open)
        self._action(file_menu, tr("button.add_folder"), self.files_tab.pick_folder, "Ctrl+Shift+O")
        file_menu.addSeparator()
        self._action(file_menu, "Reforge", self.reforge, "Ctrl+Return")  # reforge() ignora se non applicabile
        file_menu.addSeparator()
        self._action(file_menu, tr("menu.quit"), self.close, QKeySequence.Quit)
        edit_menu = self.menuBar().addMenu(tr("menu.edit"))
        self.undo_action = self._action(edit_menu, tr("menu.undo"), self.undo_last, QKeySequence.Undo)
        self._action(edit_menu, tr("menu.remove_selected_files"), self.files_tab.remove_selected, QKeySequence.Delete)
        help_menu = self.menuBar().addMenu(tr("menu.help"))
        self._action(help_menu, tr("menu.how_to_use"), self.show_guide)
        self._action(help_menu, tr("menu.tab_help"), self.show_context_help, QKeySequence.HelpContents)
        help_menu.addSeparator()
        self._build_language_menu(help_menu.addMenu(tr("menu.language")))

    def _build_language_menu(self, menu) -> None:
        group = QActionGroup(self)
        current = self.settings.value("ui/language", i18n.DEFAULT_LANGUAGE)
        if current not in ("auto", *LANGUAGES):
            current = i18n.DEFAULT_LANGUAGE
        for code, name in (*LANGUAGES.items(), ("auto", tr("menu.language_auto"))):
            act = QAction(name, self)
            act.setCheckable(True)
            act.setChecked(code == current)
            act.triggered.connect(lambda _checked=False, c=code: self.set_language_setting(c))
            group.addAction(act)
            menu.addAction(act)

    def set_language_setting(self, code: str, notify: bool = True) -> None:
        """Salva la lingua scelta ("auto" = quella del sistema). Si applica al prossimo avvio."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        s = self.settings
        s.setValue("ui/language", code)
        s.sync()
        if notify:  # messaggio fisso nelle due lingue: chi cambia lingua deve poterlo leggere comunque
            QMessageBox.information(
                self, "NameReforge", "Riavvia NameReforge per applicare la lingua.\nRestart NameReforge to apply the language."
            )

    def show_guide(self) -> None:
        show_help(self, *guide())

    def show_context_help(self) -> None:
        """F1: nella scheda Actions la guida dell'azione scelta, altrove la guida generale."""
        if self.tabs.currentWidget() is self.actions_tab:
            self.actions_tab.show_action_help()
        else:
            self.show_guide()

    @property
    def settings(self) -> QSettings:
        # file .ini nella cartella dei dati: uguale su ogni sistema e isolato nei test
        return QSettings(str(self.data_dir / "settings.ini"), QSettings.IniFormat)

    def _restore_settings(self) -> None:
        s = self.settings
        if geometry := s.value("window/geometry"):
            self.restoreGeometry(geometry)
        self.files_tab.recursive.setChecked(s.value("files/recursive", True, type=bool))
        self.actions_tab.include_current.setChecked(s.value("actions/include_current", True, type=bool))

    def _save_settings(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        s = self.settings
        s.setValue("window/geometry", self.saveGeometry())
        s.setValue("files/recursive", self.files_tab.recursive.isChecked())
        s.setValue("actions/include_current", self.actions_tab.include_current.isChecked())
        s.sync()

    # --- anteprima ---------------------------------------------------------------------------

    def _update_actions(self, current=None) -> None:
        """Anteprima = batch attivo, seguito dall'azione in modifica se richiesto."""
        actions = self.batch_tab.actions()
        if self.actions_tab.include_current.isChecked():
            actions += current if isinstance(current, list) else self.actions_tab.current_actions()
        self.model.set_actions(actions)

    # --- scrittura sul disco ---------------------------------------------------------------------

    @property
    def _manifest_dir(self) -> Path:
        return self.data_dir / "sessions"

    def _refresh_undo(self) -> None:
        self.undo_action.setEnabled(self._task is None and bool(pending_manifests(self._manifest_dir)))

    def _start(self, fn: Callable, done: Callable, text: str) -> None:
        self._task = _Task(fn)
        self.files_tab.set_locked(True)
        self.undo_action.setEnabled(False)
        self.progress.setRange(0, 0)
        self.progress.show()
        self.statusBar().showMessage(text)
        self._task.progressed.connect(self._on_progress)
        self._task.result.connect(done)
        self._task.failed.connect(self._on_failed)
        self._task.finished.connect(self._on_finished)
        self._task.start()

    def _on_progress(self, done: int, total: int) -> None:
        self.progress.setRange(0, total)
        self.progress.setValue(done)

    def _on_finished(self) -> None:
        self._task = None
        self.progress.hide()
        self.files_tab.set_locked(False)
        self._refresh_undo()

    def _on_failed(self, message: str) -> None:
        self.statusBar().showMessage(tr("status.operation_failed"))
        QMessageBox.warning(self, "NameReforge", message)

    def reforge(self, confirm: bool = True) -> None:
        m = self.model
        if self._task or m.busy or m.conflicts or not m.changes:
            return
        if confirm and QMessageBox.question(
            self, "Reforge", trn("dialog.confirm_rename", m.changes) + "\n" + tr("dialog.undo_hint")
        ) != QMessageBox.Yes:
            return
        plan = list(m.entries)  # fotografia: il piano mostrato è quello eseguito
        self._start(
            lambda progress: execute(plan, CASE_INSENSITIVE, self._manifest_dir, progress),
            self._on_reforged,
            trn("status.renaming", m.changes),
        )

    def _on_reforged(self, result) -> None:
        outcomes, _ = result
        self.log_tab.add(tr("log.operation_rename"), outcomes)
        self.model.apply_renames({o.src: o.dst for o in outcomes if o.ok})
        failed = sum(not o.ok for o in outcomes)
        self.statusBar().showMessage(
            tr("status.renamed", n=len(outcomes) - failed)
            + (tr("status.errors_suffix", n=failed) if failed else "")
        )
        if failed:
            self.tabs.setCurrentWidget(self.log_tab)

    def undo_last(self) -> None:
        pending = pending_manifests(self._manifest_dir)
        if self._task or not pending:
            return
        manifest = pending[-1]
        self._start(lambda progress: undo(manifest, progress), self._on_undone, tr("status.restoring"))

    def _on_undone(self, outcomes) -> None:
        self.log_tab.add(tr("log.operation_undo"), outcomes)
        self.model.apply_renames({o.src: o.dst for o in outcomes if o.ok})
        failed = sum(not o.ok for o in outcomes)
        self.statusBar().showMessage(
            tr("status.restored", n=len(outcomes) - failed)
            + (tr("status.not_restorable_suffix", n=failed) if failed else "")
        )
        if failed:
            self.tabs.setCurrentWidget(self.log_tab)

    def closeEvent(self, event) -> None:
        if self._task:
            self._task.wait()  # una rinomina a metà non va interrotta chiudendo la finestra
        self._save_settings()
        self.model.shutdown()
        super().closeEvent(event)
