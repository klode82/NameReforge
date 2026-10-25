import ast
import json
import re
import sys
from pathlib import Path

import pytest
from PySide6.QtCore import Qt

from nameforge import help as h
from nameforge import i18n
from nameforge.actionpanels import SPECS
from nameforge.core.plan import invalid_reason
from nameforge.mainwindow import MainWindow

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import i18n_extract

FOREIGN = sorted(set(i18n.LANGUAGES) - {i18n.SOURCE_LANGUAGE})
PLACEHOLDER = re.compile(r"\{[^{}]*\}")


def catalog(language):
    data = json.loads((i18n.CATALOG_DIR / f"{language}.json").read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if isinstance(v, (str, dict))}


def texts(value):
    return list(value.values()) if isinstance(value, dict) else [value]


@pytest.mark.parametrize("language", FOREIGN)
def test_catalog_is_complete_and_has_no_orphans(language):
    found, cat = i18n_extract.collect(), catalog(language)
    missing = [k for k in found if not all(texts(cat.get(k, "")))]
    assert not missing, f"{language}: da tradurre (python tools/i18n_extract.py --write): {missing[:5]}"
    assert not set(cat) - set(found), f"{language}: voci orfane {sorted(set(cat) - set(found))[:5]}"


@pytest.mark.parametrize("language", FOREIGN)
def test_plural_entries_have_both_forms(language):
    cat = catalog(language)
    for key, plural in i18n_extract.collect().items():
        if plural:
            assert isinstance(cat[key], dict) and cat[key].get("one") and cat[key].get("other"), key
        else:
            assert isinstance(cat[key], str), key


@pytest.mark.parametrize("language", FOREIGN)
def test_placeholders_survive_translation(language):
    """Un {segnaposto} cambiato o perso in traduzione manderebbe in errore la format() a runtime."""
    for key, value in catalog(language).items():
        for text in texts(value):
            src = set(PLACEHOLDER.findall(key))
            assert set(PLACEHOLDER.findall(text)) <= src | {"{n}"}, (key, text)
            if "{n}" not in key and not isinstance(value, dict):
                assert set(PLACEHOLDER.findall(text)) == src, (key, text)


def test_translatable_calls_take_plain_literals():
    """tr(f"...") non si può estrarre né tradurre: i valori vanno passati come segnaposto."""
    for path in (ROOT / "src" / "nameforge").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            is_call = isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.args
            if is_call and node.func.id in ("tr", "trn", "N_") and isinstance(node.args[0], ast.JoinedStr | ast.BinOp):
                pytest.fail(f"{path.name}:{node.lineno}: {node.func.id}() con f-string o concatenazione")


def test_every_spec_text_is_in_the_catalog():
    cat = catalog("en")
    for spec in SPECS:
        assert cat[spec.title], spec.title
        for f in spec.fields:
            assert cat[f.label], f.label
            for _value, label in f.options:
                assert cat[label], label


def test_tr_trn_and_fallbacks():
    assert i18n.tr("Rinomina") == "Rinomina"  # lingua sorgente: invariato
    i18n.set_language("en")
    assert i18n.tr("Rinomina") == "Rename"
    assert i18n.tr("Rinominati: {n}", n=3) == "Renamed: 3"
    assert i18n.trn("{n} file", 1) == "1 file" and i18n.trn("{n} file", 5) == "5 files"
    assert i18n.tr("Testo mai tradotto") == "Testo mai tradotto"  # senza voce: il sorgente
    i18n.set_language("xx")  # lingua sconosciuta: italiano
    assert i18n.language() == "it" and i18n.tr("Rinomina") == "Rinomina"


def test_resolve_language():
    assert i18n.resolve_language("en", "it_IT") == "en"
    assert i18n.resolve_language("it", "en_US") == "it"
    assert i18n.resolve_language("auto", "it_IT") == "it"
    assert i18n.resolve_language(None, "de_DE") == "en"  # lingue senza traduzione: inglese
    assert i18n.resolve_language("klingon", "it_CH") == "it"


def test_unreadable_catalog_keeps_italian_and_reports(tmp_path, monkeypatch):
    (tmp_path / "en.json").write_text('{"Rinomina": "Rename"}\nroba incollata', encoding="utf-8")
    monkeypatch.setattr(i18n, "CATALOG_DIR", tmp_path)
    i18n.set_language("en")
    assert "Extra data" in i18n.catalog_error() and "line 2" in i18n.catalog_error()
    assert i18n.tr("Rinomina") == "Rinomina"


def test_core_messages_follow_the_language():
    assert invalid_reason("", windows=False) == "nome vuoto o riservato"
    i18n.set_language("en")
    assert invalid_reason("", windows=False) == "empty or reserved name"
    assert invalid_reason("a:b", windows=True) == "character not allowed on Windows"


def test_interface_in_english(qtbot, tmp_path):
    i18n.set_language("en")
    win = MainWindow(data_dir=tmp_path)
    qtbot.addWidget(win)
    assert win.model.headerData(1, Qt.Horizontal) == "New name"
    assert win.files_tab.count.text() == "0 files"
    assert win.files_tab.recursive.text() == "Include subfolders"
    assert [a.text() for a in win.menuBar().actions()] == ["&File", "&Edit", "&Help"]
    assert win.actions_tab.list.item(0).text() == "Replace text"
    assert win.actions_tab.heading.text() == "Replace text"
    assert win.statusBar().currentMessage() == "Ready"
    # i campi di ogni azione sono tradotti e ogni scheda ha il suo aiuto inglese
    panel = win.actions_tab.panels[0]
    assert panel.findChildren(type(win.files_tab.count))[0].text() == "Find"
    assert "Replace text" in h.action_details("replace")
    assert win.files_tab.reforge.toolTip().startswith("<p>Applies the changes")


def test_help_dialog_in_english(qtbot):
    i18n.set_language("en")
    win = MainWindow()
    qtbot.addWidget(win)
    assert h.guide()[0] == "How to use NameReforge"
    dlg = h.build_dialog(win, "x", h.action_details("regex"))
    assert "Regular expression" in dlg.view.toPlainText() and "Show - S02E01" in dlg.view.toPlainText()


def test_language_setting_is_saved_and_shown(qtbot, tmp_path):
    win = MainWindow(data_dir=tmp_path)
    qtbot.addWidget(win)
    win.set_language_setting("en", notify=False)
    assert "language=en" in (tmp_path / "settings.ini").read_text()
    win2 = MainWindow(data_dir=tmp_path)
    qtbot.addWidget(win2)
    language_menu = next(a for a in win2.menuBar().actions()[2].menu().actions() if a.menu()).menu()
    assert {a.text(): a.isChecked() for a in language_menu.actions()} == {"Automatica": False, "Italiano": False, "English": True}


def test_shipped_catalogs_load_without_errors():
    for language in i18n.LANGUAGES:
        i18n.set_language(language)
        assert i18n.catalog_error() is None, language


# Testi che restano uguali nelle due lingue di proposito: marchio, nome della lingua nel suo idioma,
# il comando "Reforge" (nome dell'operazione), "Batch" (termine in uso anche in italiano), "&File", "?".
SAME_ON_PURPOSE = {"&File", "English", "Italiano", "Reforge", "?", "NameReforge", "Batch"}


def visible_texts(language, tmp_path):
    from PySide6.QtWidgets import (
        QAbstractButton,
        QComboBox,
        QLabel,
        QListWidget,
        QTableWidget,
        QWidget,
    )

    i18n.set_language(language)
    win = MainWindow(data_dir=tmp_path / language)
    win.show()
    out = {}
    for i, act in enumerate(win.findChildren(type(win.undo_action))):
        out[("action", i)] = act.text()
    for i in range(win.tabs.tabBar().count()):
        out[("tab", i)] = win.tabs.tabBar().tabText(i)
    for i, w in enumerate(win.findChildren(QWidget)):
        if isinstance(w, QAbstractButton | QLabel):
            out[("text", i)] = w.text()
        if isinstance(w, QComboBox):
            out.update({("combo", i, j): w.itemText(j) for j in range(w.count())})
        if isinstance(w, QListWidget):
            out.update({("list", i, j): w.item(j).text() for j in range(w.count())})
        if isinstance(w, QTableWidget):
            out.update({("header", i, j): w.horizontalHeaderItem(j).text() for j in range(w.columnCount())})
        if w.toolTip():
            out[("tooltip", i)] = w.toolTip()
    out.update({("model-header", j): str(win.model.headerData(j, Qt.Horizontal)) for j in range(4)})
    out[("status",)] = win.statusBar().currentMessage()
    win.close()
    return out


def test_whole_interface_is_translated(tmp_path):
    """Nessun testo visibile resta uguale nelle due lingue, salvo quelli dichiarati in SAME_ON_PURPOSE."""
    it, en = visible_texts("it", tmp_path), visible_texts("en", tmp_path)
    untranslated = {it[k] for k in it if k in en and it[k] == en[k] and it[k].strip()} - SAME_ON_PURPOSE
    assert not untranslated, f"testi non tradotti: {sorted(untranslated)}"


def test_tab_names_follow_the_language(qtbot, tmp_path):
    names = {}
    for language in ("it", "en"):
        i18n.set_language(language)
        win = MainWindow(data_dir=tmp_path / language)
        qtbot.addWidget(win)
        names[language] = [win.tabs.tabText(i) for i in range(4)]
    assert names["it"] == ["File", "Azioni", "Batch", "Registro"]
    assert names["en"] == ["Files", "Actions", "Batch", "Log"]


def test_regex_errors_get_a_translated_introduction():
    import re

    from nameforge.actionpanels import describe_error

    assert describe_error(re.error("missing )")) == "Espressione regolare non valida: missing )"
    i18n.set_language("en")
    assert describe_error(re.error("missing )")) == "Invalid regular expression: missing )"
    assert describe_error(ValueError("altro")) == "altro"
