from PySide6.QtWidgets import QLabel, QMainWindow, QTabWidget

from nameforge.filemodel import FileTableModel
from nameforge.filestab import FilesTab

TABS = ("Files", "Actions", "Batch", "Log")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("NameReforge")
        self.resize(1000, 650)
        self.model = FileTableModel()
        self.files_tab = FilesTab(self.model)
        self.tabs = QTabWidget()
        self.tabs.addTab(self.files_tab, TABS[0])
        for name in TABS[1:]:
            self.tabs.addTab(QLabel(name), name)  # ponytail: segnaposto, ogni scheda ha il suo widget nelle fasi 4-7
        self.setCentralWidget(self.tabs)
