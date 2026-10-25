import sys
from pathlib import Path

from PySide6.QtCore import QLibraryInfo, QLocale, QSettings, QTranslator
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from nameforge import i18n
from nameforge.mainwindow import MainWindow, _app_data
from nameforge.theme import apply_theme

ICON = Path(__file__).parent / "assets" / "icon.png"


def selftest() -> int:
    """Verifica che dipendenze e risorse ci siano (serve a provare il pacchetto PyInstaller)."""
    import importlib
    import tempfile

    from PIL import Image

    from nameforge.core.metadata import ExifTags

    assert ICON.is_file(), f"icona mancante: {ICON}"
    for lang in i18n.LANGUAGES:  # ogni catalogo si deve leggere dal pacchetto
        i18n.set_language(lang)
        assert i18n.catalog_error() is None, i18n.catalog_error()
    i18n.set_language(i18n.DEFAULT_LANGUAGE)
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


def install_qt_translations(app: QApplication, language: str) -> None:
    """Traduzioni di Qt stesso (pulsanti Sì/No, dialoghi dei file...), se la lingua le ha."""
    translator = QTranslator(app)  # figlio di app: vive quanto l'applicazione
    if translator.load(f"qtbase_{language}", QLibraryInfo.path(QLibraryInfo.TranslationsPath)):
        app.installTranslator(translator)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("NameReforge")
    setting = QSettings(str(_app_data() / "settings.ini"), QSettings.IniFormat).value("ui/language", i18n.DEFAULT_LANGUAGE)
    system = QLocale.system()
    preferred = (system.uiLanguages() or [system.name()])[0]  # la prima lingua preferita, come per le traduzioni di Qt
    i18n.set_language(i18n.resolve_language(setting, preferred))
    install_qt_translations(app, i18n.language())
    app.setDesktopFileName("nameforge")  # Wayland: abbina la finestra a nameforge.desktop (icona, raggruppamento)
    app.setWindowIcon(QIcon(str(ICON)))
    apply_theme(app)
    if "--selftest" in sys.argv:
        return selftest()
    window = MainWindow()
    window.show()
    return app.exec()
