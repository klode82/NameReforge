from nameforge.actionpanels import SPECS
from nameforge.mainwindow import MainWindow


def test_every_panel_builds_default_action(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    for i, spec in enumerate(SPECS):
        win.actions_tab.list.setCurrentRow(i)
        action = win.actions_tab.current_actions()[0]
        assert action is not None, spec.title


def test_live_preview_debounced(qtbot, tmp_path):
    for n in ("a.txt", "b.txt"):
        (tmp_path / n).write_text("")
    win = MainWindow()
    qtbot.addWidget(win)
    win.files_tab.add_paths([tmp_path])
    tab = win.actions_tab
    find = tab.panels[0]._widgets["find"]
    with qtbot.waitSignal(tab.actionsChanged, timeout=2000):
        find.setText("a")  # una sola emissione dopo la pausa
    with qtbot.waitSignal(win.model.planReady, timeout=5000):
        tab.panels[0]._widgets["replace"].setText("z")
        tab.emit_now()
    assert [win.model.index(i, 1).data() for i in range(2)] == ["z.txt", "b.txt"]


def test_names_from_file_warning(qtbot, tmp_path):
    (tmp_path / "names.txt").write_text("x\ny\n")
    win = MainWindow()
    qtbot.addWidget(win)
    tab = win.actions_tab
    tab.list.setCurrentRow(len(SPECS) - 1)
    tab.panels[-1]._widgets["path"].edit.setText(str(tmp_path / "names.txt"))
    tab.current_actions()
    assert "2 nomi" in tab.warning.text()
    tab.panels[-1]._widgets["path"].edit.setText(str(tmp_path / "missing.txt"))
    tab.current_actions()
    assert tab.panels[-1].error


def test_invalid_regex_shows_error_and_keeps_names(qtbot, tmp_path):
    (tmp_path / "a.txt").write_text("")
    win = MainWindow()
    qtbot.addWidget(win)
    win.files_tab.add_paths([tmp_path])
    tab = win.actions_tab
    row = [s.key for s in SPECS].index("regex")
    tab.list.setCurrentRow(row)
    tab.panels[row]._widgets["pattern"].setText("(")
    with qtbot.waitSignal(win.model.planReady, timeout=5000):
        tab.emit_now()
    assert tab.panels[row].error
    assert tab.warning.text()
    assert win.model.index(0, 1).data() == "a.txt"


def test_preview_in_actions_tab_shares_model(qtbot, tmp_path):
    (tmp_path / "a.txt").write_text("")
    win = MainWindow()
    qtbot.addWidget(win)
    tab = win.actions_tab
    assert tab.preview.isHidden() and not tab.preview_hint.isHidden()  # senza file: invito
    win.files_tab.add_paths([tmp_path])
    assert not tab.preview.isHidden() and tab.preview_hint.isHidden()
    assert tab.preview.model() is win.model
    assert [tab.preview.isColumnHidden(c) for c in range(4)] == [False, False, True, True]
