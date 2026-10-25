from pathlib import Path

from PySide6.QtCore import QMimeData, Qt, QUrl

from nameforge.core.actions import NameParts, RenameAction
from nameforge.core.scan import collect_files
from nameforge.filemodel import FileTableModel, human_size
from nameforge.filestab import paths_from_mime


class Const(RenameAction):
    def process(self, parts, ctx):
        return NameParts("x", parts.ext)


def make(tmp_path, names):
    out = []
    for n in names:
        p = tmp_path / n
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("ab")
        out.append(p)
    return out


def test_collect_recursive_and_flat(tmp_path):
    make(tmp_path, ["b.txt", "A.txt", "sub/c.txt"])
    names = lambda r: [p.name for p in collect_files([tmp_path], r)]
    assert names(True) == ["A.txt", "b.txt", "c.txt"]
    assert names(False) == ["A.txt", "b.txt"]
    assert collect_files([tmp_path / "A.txt", tmp_path / "A.txt"]) == [tmp_path / "A.txt"]


def test_model_add_dedupe_remove(tmp_path):
    ps = make(tmp_path, ["a.txt", "b.txt", "c.txt"])
    m = FileTableModel()
    assert m.add_paths(ps) == 3
    assert m.add_paths(ps) == 0
    assert m.index(0, 3).data() == "2 B"
    m.remove_rows([1])
    assert [m.index(i, 0).data() for i in range(m.rowCount())] == ["a.txt", "c.txt"]
    m.clear()
    assert m.rowCount() == 0


def test_conflict_is_flagged(tmp_path):
    m = FileTableModel()
    m.add_paths(make(tmp_path, ["a.txt", "b.txt"]))
    m.set_actions([Const()])
    assert m.has_conflicts
    assert m.index(0, 1).data() == "x.txt"
    assert m.index(0, 0).data(role=8) is not None  # Qt.BackgroundRole
    assert m.index(0, 0).data(role=3)  # Qt.ToolTipRole


def test_sort_by_size_desc(tmp_path):
    ps = make(tmp_path, ["a.txt", "b.txt"])
    ps[1].write_text("abcdef")
    m = FileTableModel()
    m.add_paths(ps)
    m.sort(3, order=Qt.DescendingOrder)
    assert m.index(0, 0).data() == "b.txt"


def test_mime_urls(tmp_path):
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(tmp_path)), QUrl("http://x/y")])
    assert paths_from_mime(mime) == [Path(tmp_path)]


def test_tab_add_paths(qtbot, tmp_path):
    from nameforge.mainwindow import MainWindow

    make(tmp_path, ["a.txt", "sub/b.txt"])
    win = MainWindow()
    qtbot.addWidget(win)
    assert win.files_tab.add_paths([tmp_path]) == 2
    assert win.files_tab.count.text() == "2 file"
    win.files_tab.view.selectRow(0)
    win.files_tab.remove_selected()
    assert win.model.rowCount() == 1


def test_human_size():
    assert human_size(0) == "0 B"
    assert human_size(1536) == "1.5 KB"
