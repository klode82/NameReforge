import csv

import pytest

from nameforge.actionpanels import SPECS
from nameforge.mainwindow import MainWindow


@pytest.fixture
def setup(qtbot, tmp_path):
    files = tmp_path / "files"
    files.mkdir()
    for n in ("a.txt", "b.txt"):
        (files / n).write_text(n)
    win = MainWindow(data_dir=tmp_path / "data")
    qtbot.addWidget(win)
    win.files_tab.add_paths([files])
    return win, files


def choose(qtbot, win, key, **values):
    row = [s.key for s in SPECS].index(key)
    win.actions_tab.list.setCurrentRow(row)
    for k, v in values.items():
        w = win.actions_tab.panels[row]._widgets[k]
        w.setText(v) if hasattr(w, "setText") else w.setValue(v)
    with qtbot.waitSignal(win.model.planReady, timeout=5000):
        win.actions_tab.emit_now()


def idle(qtbot, win):
    qtbot.waitUntil(lambda: win._task is None and not win.model.busy, timeout=5000)


def names(win):
    return [win.model.index(i, 0).data() for i in range(win.model.rowCount())]


def test_reforge_then_undo(qtbot, setup):
    win, files = setup
    choose(qtbot, win, "extension", value="md")
    assert win.files_tab.reforge.isEnabled()
    win.reforge(confirm=False)
    idle(qtbot, win)
    assert sorted(p.name for p in files.iterdir()) == ["a.md", "b.md"]
    assert names(win) == ["a.md", "b.md"]  # elenco aggiornato ai nuovi percorsi
    assert [r[2] for r in win.log_tab.rows()] == ["OK", "OK"]
    assert win.undo_action.isEnabled()

    win.undo_last()
    idle(qtbot, win)
    assert sorted(p.name for p in files.iterdir()) == ["a.txt", "b.txt"]
    assert (files / "a.txt").read_text() == "a.txt"
    assert names(win) == ["a.txt", "b.txt"]
    assert not win.undo_action.isEnabled()


def test_reforge_blocked_without_changes_or_with_conflicts(qtbot, setup):
    win, files = setup
    choose(qtbot, win, "replace", find="zzz")
    assert not win.files_tab.reforge.isEnabled()  # nessuna modifica

    choose(qtbot, win, "regex", pattern=".*", replacement="x")  # a.txt e b.txt -> x.txt
    assert win.model.conflicts == 2
    assert not win.files_tab.reforge.isEnabled()
    assert "2 in conflitto" in win.files_tab.count.text()
    win.reforge(confirm=False)  # ignorato
    assert sorted(p.name for p in files.iterdir()) == ["a.txt", "b.txt"]


def test_log_export(qtbot, setup, tmp_path):
    win, _ = setup
    choose(qtbot, win, "extension", value="md")
    win.reforge(confirm=False)
    idle(qtbot, win)
    out = tmp_path / "log.csv"
    win.log_tab.export_csv(out)
    rows = list(csv.reader(out.open(encoding="utf-8")))
    assert rows[0][0] == "Ora" and len(rows) == 3


def test_failure_shows_in_log(qtbot, setup):
    win, files = setup
    choose(qtbot, win, "extension", value="md")
    (files / "a.md").write_text("INTRUSO")  # appare dopo il piano: non va sovrascritto
    win.reforge(confirm=False)
    idle(qtbot, win)
    assert (files / "a.md").read_text() == "INTRUSO"
    assert (files / "a.txt").read_text() == "a.txt"
    assert [r[2] for r in win.log_tab.rows()] == ["Errore", "OK"]
    assert win.tabs.currentWidget() is win.log_tab
