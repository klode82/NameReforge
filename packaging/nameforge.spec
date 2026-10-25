# Uso (dalla radice del progetto): pyinstaller packaging/nameforge.spec --noconfirm
# Un unico spec per Linux, Windows e macOS; la cartella (onedir) si avvia più in fretta di un singolo file.
import sys

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None
icon = {"win32": "src/nameforge/assets/icon.ico", "darwin": "src/nameforge/assets/icon.icns"}.get(sys.platform)

a = Analysis(
    ["run.py"],
    pathex=["../src"],
    datas=[("../src/nameforge/assets", "nameforge/assets"), ("../LICENSE", ".")],
    hiddenimports=collect_submodules("mutagen"),
    excludes=["tkinter", "PySide6.QtNetwork", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtPdf", "PySide6.QtSvg"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="NameReforge", console=False,
          icon=("../" + icon) if icon else None)
coll = COLLECT(exe, a.binaries, a.datas, name="NameReforge")
if sys.platform == "darwin":
    app = BUNDLE(coll, name="NameReforge.app", icon="../src/nameforge/assets/icon.icns",
                 bundle_identifier="dev.aurigalab.nameforge")
