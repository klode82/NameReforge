"""Benchmark: 50.000 file finti nel modello. Uso: QT_QPA_PLATFORM=offscreen python tools/bench_files.py"""
import time
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from nameforge.core.actions import NameParts, RenameAction
from nameforge.filemodel import FileTableModel

N = 50_000


class Upper(RenameAction):
    def process(self, parts, ctx):
        return NameParts(parts.stem.upper(), parts.ext)


def timed(label, fn):
    t = time.perf_counter()
    fn()
    print(f"{label}: {(time.perf_counter() - t) * 1000:.0f} ms")


app = QApplication([])
m = FileTableModel()
paths = [Path(f"/nonexistent/dir{i % 100}/file_{i:05d}.txt") for i in range(N)]
timed("add_paths (stat inclusa)", lambda: m.add_paths(paths))
timed("set_actions (replan)", lambda: m.set_actions([Upper()]))
timed("sort per nome", lambda: m.sort(0, Qt.DescendingOrder))
timed("lettura celle visibili (40 righe x 4)", lambda: [m.index(r, c).data() for r in range(40) for c in range(4)])
