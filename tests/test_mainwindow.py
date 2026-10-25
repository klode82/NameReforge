from nameforge.mainwindow import TABS, MainWindow


def test_four_tabs(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    assert [win.tabs.tabText(i) for i in range(win.tabs.count())] == list(TABS)
