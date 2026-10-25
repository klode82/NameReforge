import json

import pytest
from PySide6.QtWidgets import QWidget

from nameforge import help as h
from nameforge import i18n
from nameforge.actionpanels import SPECS
from nameforge.mainwindow import MainWindow


def data(language):
    return json.loads(h.help_path(language).read_text(encoding="utf-8"))


@pytest.mark.parametrize("language", sorted(i18n.LANGUAGES))
def test_every_action_and_field_has_help(language):
    d = data(language)
    for spec in SPECS:
        entry = d["actions"][spec.key]
        assert entry["summary"].strip(), spec.key
        assert entry["details"].strip().startswith("#"), spec.key  # Markdown con titolo
        for f in spec.fields:
            assert entry["fields"].get(f.key, "").strip(), f"{language}: {spec.key}.{f.key}"


@pytest.mark.parametrize("language", sorted(i18n.LANGUAGES))
def test_no_orphan_keys_in_help_file(language):
    d = data(language)
    assert set(d["actions"]) == {s.key for s in SPECS}
    for spec in SPECS:
        assert set(d["actions"][spec.key]["fields"]) == {f.key for f in spec.fields}, f"{language}: {spec.key}"
    assert set(d["ui"]) == set(h.UI_KEYS), language
    assert d["guide"]["title"] and d["guide"]["body"]


def test_help_files_exist_for_every_language():
    for language in i18n.LANGUAGES:
        assert h.help_path(language).name == f"{language}.json", language
        assert h.help_path(language).parent.name == "help", language


def test_missing_help_file_falls_back_to_english(tmp_path, monkeypatch):
    (tmp_path / "en.json").write_text('{"ui": {}}', encoding="utf-8")
    monkeypatch.setattr(h, "HELP_DIR", tmp_path)
    assert h.help_path("it").name == "en.json" and h.help_path("xx").name == "en.json"


def test_unknown_ui_key_is_a_loud_error():
    with pytest.raises(KeyError):
        h.ui_text("files.refrog")


def test_tooltips_are_applied(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    assert "Ctrl+Z" in win.files_tab.reforge.toolTip()
    assert win.batch_tab.list.toolTip() and win.log_tab.table.toolTip()
    tab = win.actions_tab
    for i, panel in enumerate(tab.panels):
        assert tab.list.item(i).toolTip(), panel.spec.key
        for f in panel.spec.fields:
            assert panel._widgets[f.key].toolTip(), f"{panel.spec.key}.{f.key}"
        for child in panel.findChildren(QWidget):
            if child.toolTip():
                assert child.toolTip().startswith("<p>")  # rich text: Qt manda a capo da solo


def test_shipped_help_file_is_valid():
    h.clear_cache()
    assert h.load_error() is None


def test_trailing_chat_text_is_reported_with_position(tmp_path, monkeypatch):
    """Caso reale: la risposta di un assistente incollata col suo commento finale."""
    (tmp_path / "it.json").write_text('{"ui": {}}\n```eof\n\nEcco i testi migliorati!', encoding="utf-8")
    monkeypatch.setattr(h, "HELP_DIR", tmp_path)
    h.clear_cache()
    try:
        assert "Extra data" in h.load_error() and "line 2" in h.load_error()
    finally:
        h.clear_cache()


def test_help_dialogs(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.tabs.setCurrentWidget(win.actions_tab)
    row = [s.key for s in SPECS].index("regex")
    win.actions_tab.list.setCurrentRow(row)
    win.actions_tab.show_action_help()
    dlg = [w for w in win.findChildren(type(h.build_dialog(None, "", "")))][-1]
    assert "Espressione regolare" in dlg.view.toPlainText()
    assert "$1" in dlg.view.toPlainText()  # avvisa sulla differenza \1 / $1
    dlg.close()
    win.tabs.setCurrentWidget(win.files_tab)
    win.show_context_help()
    dlg = [w for w in win.findChildren(type(dlg)) if w.isVisible()][-1]
    assert "Come si usa NameReforge" in dlg.view.toPlainText()


def test_unreadable_help_file_does_not_break_app(qtbot, tmp_path, monkeypatch):
    (tmp_path / "it.json").write_text("{non json")
    monkeypatch.setattr(h, "HELP_DIR", tmp_path)
    h.clear_cache()
    try:
        assert h.load_error() and "help/it.json" in h.load_error()
        win = MainWindow()
        qtbot.addWidget(win)
        assert win.files_tab.reforge.toolTip() == ""
        assert win.actions_tab.list.item(0).toolTip() == ""
        assert "Testi di aiuto non caricati" in win.statusBar().currentMessage()  # non resta un errore muto
        dlg = h.build_dialog(win, "x", h.action_details("regex"))
        assert "non si può leggere" in dlg.view.toPlainText() and "help/it.json" in dlg.view.toPlainText()
    finally:
        h.clear_cache()
