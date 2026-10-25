from pathlib import Path

from nameforge.core.actions import FileContext, NameParts
from nameforge.core.builtins import (
    ChangeCase,
    ChangeExtension,
    DeleteChars,
    Enumerate,
    InsertChars,
    MoveChars,
    NamesFromFile,
    RandomName,
    Replace,
    load_names,
)


def run(action, name="Hello World.TXT", index=0, folder_index=0):
    ctx = FileContext(Path("/d") / name, index, folder_index)
    return action.process(NameParts.from_name(name), ctx).full


def test_replace():
    assert run(Replace("o", "0")) == "Hell0 W0rld.TXT"
    assert run(Replace("WORLD", "x", case_sensitive=False)) == "Hello x.TXT"
    assert run(Replace("WORLD", "x")) == "Hello World.TXT"
    assert run(Replace("", "x")) == "Hello World.TXT"
    assert run(Replace("o", r"\1"), "o.t") == r"\1.t"  # sostituzione letterale, non regex


def test_extension():
    assert run(ChangeExtension("replace", ".md")) == "Hello World.md"
    assert run(ChangeExtension("add", "bak")) == "Hello World.TXT.bak"
    assert run(ChangeExtension("remove")) == "Hello World"
    assert run(ChangeExtension("lower")) == "Hello World.txt"
    assert run(ChangeExtension("replace", "")) == "Hello World.TXT"


def test_case():
    assert run(ChangeCase("upper")) == "HELLO WORLD.TXT"
    assert run(ChangeCase("lower")) == "hello world.TXT"
    assert run(ChangeCase("title"), "don't_stop me.x") == "Don't_Stop Me.x"
    assert run(ChangeCase("sentence"), "hELLO wORLD.x") == "Hello world.x"


def test_enumerate():
    assert run(Enumerate(), "a.t", index=4, folder_index=1) == "002_a.t"
    assert run(Enumerate(per_folder=False), "a.t", index=4, folder_index=1) == "005_a.t"
    assert run(Enumerate(start=10, step=5, digits=0, position="suffix", separator="-"), "a.t", folder_index=2) == "a-20.t"
    assert run(Enumerate(position="replace"), "a.t") == "001.t"


def test_insert_delete_move():
    assert run(InsertChars("XX", 2), "abcd.t") == "abXXcd.t"
    assert run(InsertChars("XX", 1, from_end=True), "abcd.t") == "abcXXd.t"
    assert run(InsertChars("XX", 99), "abcd.t") == "abcdXX.t"
    assert run(DeleteChars(1, 2), "abcd.t") == "ad.t"
    assert run(DeleteChars(1, 2, from_end=True), "abcd.t") == "ad.t"
    assert run(DeleteChars(10, 2), "abcd.t") == "abcd.t"
    assert run(MoveChars(0, 2, 99), "abcd.t") == "cdab.t"
    assert run(MoveChars(2, 2, 0), "abcd.t") == "cdab.t"


def test_random_is_stable_and_seeded():
    a = RandomName(6, seed=7)
    assert run(a, index=3) == run(a, index=3) != run(a, index=4)
    assert len(NameParts.from_name(run(a)).stem) == 6
    assert run(a) != run(RandomName(6, seed=8))


def test_names_from_file(tmp_path):
    f = tmp_path / "n.csv"
    f.write_text("uno,x\ndue,y\n\n", encoding="utf-8-sig")
    names = load_names(str(f))
    assert names == ("uno", "due")
    a = NamesFromFile(names)
    assert run(a, "a.jpg", index=1) == "due.jpg"
    assert run(a, "a.jpg", index=5) == "a.jpg"  # oltre la lista: invariato
    assert run(NamesFromFile(("z.png",), with_extension=True), "a.jpg") == "z.png"
    assert a.warning(2) is None and "2 nomi" in a.warning(3)
