import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from nameforge.mainwindow import MainWindow
from nameforge.theme import apply_theme

ICON = Path(__file__).parent / "assets" / "icon.png"


def selftest() -> int:
    """Verifica che dipendenze e risorse ci siano (serve a provare il pacchetto PyInstaller)."""
    import importlib
    import tempfile

    from PIL import Image

    from nameforge.core.metadata import ExifTags

    assert ICON.is_file(), f"icona mancante: {ICON}"
    for mod in ("mp3", "flac", "oggvorbis", "oggopus", "mp4", "easyid3", "easymp4"):
        importlib.import_module(f"mutagen.{mod}")  # i formati dei tag audio devono stare nel pacchetto
    with tempfile.TemporaryDirectory() as d:
        jpg = Path(d) / "t.jpg"
        img = Image.new("RGB", (4, 3))
        exif = img.getexif()
        exif.get_ifd(0x8769)[0x9003] = "2021:05:04 10:20:30"
        img.save(jpg, exif=exif)
        assert ExifTags().read(jpg)["date"].year == 2021, "lettura EXIF non funzionante"
    window = MainWindow()
    QApplication.processEvents()
    window.close()
    print("nameforge selftest ok")
    return 0


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("NameReforge")
    app.setWindowIcon(QIcon(str(ICON)))
    apply_theme(app)
    if "--selftest" in sys.argv:
        return selftest()
    window = MainWindow()
    window.show()
    return app.exec()
