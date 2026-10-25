import sys

from PySide6.QtWidgets import QApplication

from nameforge.mainwindow import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("NameReforge")
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    return app.exec()
