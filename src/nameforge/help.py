"""Testi di aiuto: un file per lingua in assets/i18n/help/<lingua>.json, così si riscrivono senza toccare il codice."""

import html
import json
from functools import cache
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTextBrowser, QVBoxLayout, QWidget

from nameforge import i18n
from nameforge.i18n import tr

HELP_DIR = Path(__file__).parent / "assets" / "i18n" / "help"

# Chiavi dei tooltip dell'interfaccia: il contratto tra codice e file di aiuto (verificato da tests/test_help.py).
UI_KEYS = (
    "files.add_files", "files.add_folder", "files.recursive", "files.remove", "files.clear",
    "files.reforge", "files.table", "files.empty",
    "actions.list", "actions.help", "actions.add_to_batch", "actions.include_current", "actions.preview",
    "batch.list", "batch.remove", "batch.clear", "batch.save", "batch.load",
    "log.table", "log.export", "log.clear",
)


def help_path(language: str) -> Path:
    """<lingua>.json nella cartella dell'aiuto; se la lingua non ha il suo file, quello inglese (predefinito)."""
    path = HELP_DIR / f"{language}.json"
    return path if path.exists() else HELP_DIR / f"{i18n.DEFAULT_LANGUAGE}.json"


@cache
def _load(language: str) -> tuple[dict, str | None]:
    path = help_path(language)
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (OSError, ValueError) as exc:
        # L'app funziona lo stesso (senza tooltip), ma l'errore va mostrato: un file modificato a mano si rompe facilmente.
        return {}, f"help/{path.name}: {exc}"


def _data() -> dict:
    return _load(i18n.language())[0]


def load_error() -> str | None:
    """Motivo per cui il file di aiuto non è stato letto (con riga e colonna), oppure None."""
    return _load(i18n.language())[1]


def clear_cache() -> None:
    _load.cache_clear()


def rich(text: str) -> str:
    """Testo semplice -> HTML minimo: Qt manda a capo da solo solo i tooltip in rich text."""
    return "<p>" + html.escape(text).replace("\n", "<br>") + "</p>"


def ui_text(key: str) -> str:
    if key not in UI_KEYS:
        raise KeyError(f"chiave di aiuto sconosciuta: {key}")  # un refuso nel codice si vede subito
    return _data().get("ui", {}).get(key, "")


def set_tip(widget: QWidget, key: str) -> None:
    if text := ui_text(key):
        widget.setToolTip(rich(text))


def action_summary(action_key: str) -> str:
    return _data().get("actions", {}).get(action_key, {}).get("summary", "")


def action_details(action_key: str) -> str:
    return _data().get("actions", {}).get(action_key, {}).get("details", "")


def field_tip(action_key: str, field_key: str) -> str:
    return _data().get("actions", {}).get(action_key, {}).get("fields", {}).get(field_key, "")


def guide() -> tuple[str, str]:
    g = _data().get("guide", {})
    return g.get("title", "Guida"), g.get("body", "")


def build_dialog(parent: QWidget | None, title: str, markdown: str) -> QDialog:
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.resize(640, 560)
    dlg.setAttribute(Qt.WA_DeleteOnClose)
    view = QTextBrowser()
    error = load_error()
    if not markdown and error:
        markdown = tr(
            "help.unavailable",
            error=error,
        )
    view.setMarkdown(markdown or tr("help.no_text"))
    buttons = QDialogButtonBox(QDialogButtonBox.Close)
    buttons.button(QDialogButtonBox.Close).setText(tr("button.close"))
    buttons.rejected.connect(dlg.close)
    layout = QVBoxLayout(dlg)
    layout.addWidget(view)
    layout.addWidget(buttons)
    dlg.view = view  # type: ignore[attr-defined]
    return dlg


def show_help(parent: QWidget | None, title: str, markdown: str) -> QDialog:
    dlg = build_dialog(parent, title, markdown)
    dlg.show()  # non modale: si legge la guida mentre si lavora
    return dlg
