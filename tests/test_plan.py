from pathlib import Path

from nameforge.core.actions import NameParts, RenameAction
from nameforge.core.plan import Status, build_plan, can_execute, invalid_reason


class Upper(RenameAction):
    def process(self, parts, ctx):
        return NameParts(parts.stem.upper(), parts.ext)


class Const(RenameAction):
    def process(self, parts, ctx):
        return NameParts("x", parts.ext)


class Index(RenameAction):
    def process(self, parts, ctx):
        return NameParts(f"{ctx.folder_index}", parts.ext)


def test_nameparts():
    assert NameParts.from_name("a.tar.gz") == NameParts("a.tar", "gz")
    assert NameParts.from_name(".bashrc") == NameParts(".bashrc", "")
    assert NameParts("a", "txt").full == "a.txt"


def test_pipeline_cascade_and_unchanged():
    plan = build_plan([Path("/d/a.txt"), Path("/d/B.TXT")], [Upper()], case_insensitive=False)
    assert [e.new_name for e in plan] == ["A.txt", "B.TXT"]
    assert [e.status for e in plan] == [Status.OK, Status.UNCHANGED]
    assert can_execute(plan)


def test_duplicate_blocks():
    plan = build_plan([Path("/d/a.txt"), Path("/d/b.txt")], [Const()])
    assert all(e.status is Status.DUPLICATE for e in plan)
    assert not can_execute(plan)


def test_same_name_other_folder_ok():
    plan = build_plan([Path("/d/a.txt"), Path("/e/b.txt")], [Const()])
    assert all(e.status is Status.OK for e in plan)


def test_case_insensitive_duplicate():
    class Lower(RenameAction):
        def process(self, parts, ctx):
            return NameParts("a" if ctx.index else "A", parts.ext)

    paths = [Path("/d/1.txt"), Path("/d/2.txt")]
    assert build_plan(paths, [Lower()], case_insensitive=True)[0].status is Status.DUPLICATE
    assert build_plan(paths, [Lower()], case_insensitive=False)[0].status is Status.OK


def test_exists_on_disk(tmp_path):
    (tmp_path / "a.txt").write_text("")
    (tmp_path / "x.txt").write_text("")
    plan = build_plan([tmp_path / "a.txt"], [Const()])
    assert plan[0].status is Status.EXISTS


def test_swap_inside_selection_is_not_exists(tmp_path):
    for n in ("1.txt", "0.txt"):
        (tmp_path / n).write_text("")
    # 1.txt -> 0.txt e 0.txt -> 1.txt: il bersaglio esiste ma fa parte della selezione
    plan = build_plan([tmp_path / "1.txt", tmp_path / "0.txt"], [Index()])
    assert [e.status for e in plan] == [Status.OK, Status.OK]


def test_folder_index_resets():
    plan = build_plan([Path("/a/1.t"), Path("/a/2.t"), Path("/b/3.t")], [Index()])
    assert [e.new_name for e in plan] == ["0.t", "1.t", "0.t"]


def test_invalid():
    assert invalid_reason("", windows=False)
    assert invalid_reason("a/b", windows=False)
    assert invalid_reason("é" * 200, windows=False)
    assert invalid_reason("a:b", windows=True) and not invalid_reason("a:b", windows=False)
    assert invalid_reason("con.txt", windows=True)
    assert invalid_reason("a.", windows=True)
    assert invalid_reason("ok.txt", windows=True) is None
