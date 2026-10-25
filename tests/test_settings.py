from nameforge.mainwindow import MainWindow


def test_settings_roundtrip(qtbot, tmp_path):
    w = MainWindow(data_dir=tmp_path)
    qtbot.addWidget(w)
    w.files_tab.recursive.setChecked(False)
    w.actions_tab.include_current.setChecked(False)
    w.resize(777, 444)
    w.close()
    assert (tmp_path / "settings.ini").is_file()

    w2 = MainWindow(data_dir=tmp_path)
    qtbot.addWidget(w2)
    assert not w2.files_tab.recursive.isChecked()
    assert not w2.actions_tab.include_current.isChecked()
    assert (w2.width(), w2.height()) == (777, 444)


def test_shortcuts_exist(qtbot, tmp_path):
    w = MainWindow(data_dir=tmp_path)
    qtbot.addWidget(w)
    keys = {a.text(): a.shortcut().toString() for m in w.menuBar().findChildren(type(w.menuBar().actions()[0].menu())) for a in m.actions()}
    assert keys["Reforge"] == "Ctrl+Return"
    assert keys["Annulla ultima rinomina"] == "Ctrl+Z"
    assert keys["Aggiungi file…"] == "Ctrl+O"
