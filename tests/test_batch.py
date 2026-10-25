import json

import pytest
from PySide6.QtCore import Qt

from nameforge.mainwindow import MainWindow
from nameforge.profiles import ProfileError, dump_profile, parse_profile


@pytest.fixture
def win(qtbot, tmp_path):
    for n in ("Foo Bar.TXT", "baz.txt"):
        (tmp_path / n).write_text("")
    w = MainWindow()
    qtbot.addWidget(w)
    w.files_tab.add_paths([tmp_path])
    w.actions_tab.include_current.setChecked(False)
    return w


def names(w):
    return [w.model.index(i, 1).data() for i in range(w.model.rowCount())]


def settle(qtbot, w):
    with qtbot.waitSignal(w.model.planReady, timeout=5000):
        w.batch_tab.changed.emit()


def test_batch_cascade_and_toggle(qtbot, win):
    b = win.batch_tab
    b.add("replace", {"find": " ", "replace": "_"})
    b.add("case", {"mode": "lower"})
    b.add("enumerate", {"position": "prefix", "digits": 2})
    settle(qtbot, win)
    assert names(win) == ["01_baz.txt", "02_foo_bar.TXT"]

    b.list.item(1).setCheckState(Qt.Unchecked)
    settle(qtbot, win)
    assert names(win) == ["01_baz.txt", "02_Foo_Bar.TXT"]


def test_batch_invalid_item_is_skipped_and_reported(qtbot, win):
    b = win.batch_tab
    b.add("regex", {"pattern": "("})
    b.add("case", {"mode": "upper"})
    settle(qtbot, win)
    assert "Espressione regolare" in b.errors.text()
    assert names(win) == ["BAZ.txt", "FOO BAR.TXT"]


def test_include_current_after_batch(qtbot, win):
    win.batch_tab.add("case", {"mode": "upper"})
    win.actions_tab.include_current.setChecked(True)
    row = 0  # Sostituisci stringa
    win.actions_tab.list.setCurrentRow(row)
    win.actions_tab.panels[row]._widgets["find"].setText("BAZ")
    win.actions_tab.panels[row]._widgets["replace"].setText("X")
    with qtbot.waitSignal(win.model.planReady, timeout=5000):
        win.actions_tab.emit_now()
    assert names(win) == ["X.txt", "FOO BAR.TXT"]  # prima il batch (upper), poi l'azione corrente


def test_profile_roundtrip(tmp_path, win):
    win.batch_tab.add("replace", {"find": "a", "replace": "b"})
    win.batch_tab.add("case", {"mode": "upper"}, enabled=False)
    f = tmp_path / "p.json"
    win.batch_tab.save_profile(f)
    assert json.loads(f.read_text())["version"] == 1
    win.batch_tab.clear()
    assert win.batch_tab.items() == []
    win.batch_tab.load_profile(f)
    assert [(i["key"], i["enabled"]) for i in win.batch_tab.items()] == [("replace", True), ("case", False)]
    assert win.batch_tab.items()[0]["values"] == {"find": "a", "replace": "b"}


def test_profile_errors():
    for bad in ("not json", "[]", '{"actions": [{"key": "boh"}]}', '{"version": 99, "actions": []}'):
        with pytest.raises(ProfileError):
            parse_profile(bad)
    assert parse_profile(dump_profile([])) == []
    # campi mancanti: default; chiavi in più ignorate da build_action
    assert parse_profile('{"actions": [{"key": "case"}]}') == [{"key": "case", "values": {}, "enabled": True}]
