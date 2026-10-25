import os

import pytest

from nameforge.core.actions import NameParts, RenameAction
from nameforge.core.executor import PlanBlocked, apply_renames, execute, pending_manifests, undo
from nameforge.core.plan import build_plan


def mk(tmp_path, **files):
    for name, text in files.items():
        (tmp_path / name).write_text(text)
    return tmp_path


def read(tmp_path):
    return {p.name: p.read_text() for p in sorted(tmp_path.iterdir()) if p.is_file()}


class Map(RenameAction):
    def __init__(self, mapping):
        self.mapping = mapping

    def process(self, parts, ctx):
        return NameParts.from_name(self.mapping.get(parts.full, parts.full))


def run(tmp_path, mapping, **kw):
    plan = build_plan([tmp_path / n for n in sorted(os.listdir(tmp_path)) if (tmp_path / n).is_file()], [Map(mapping)])
    return execute(plan, False, tmp_path / ".m", **kw)


def test_simple_and_unchanged_untouched(tmp_path):
    mk(tmp_path, a="A", b="B")
    out, manifest = run(tmp_path, {"a": "x"})
    assert [o.ok for o in out] == [True]
    assert read(tmp_path) == {"b": "B", "x": "A"}
    assert manifest and manifest.exists()


def test_swap_and_chain_and_cycle(tmp_path):
    mk(tmp_path, a="A", b="B", c="C", d="D")
    out, _ = run(tmp_path, {"a": "b", "b": "a", "c": "d", "d": "e"})  # scambio + catena c->d->e
    assert all(o.ok for o in out)
    assert read(tmp_path) == {"a": "B", "b": "A", "d": "C", "e": "D"}
    assert not [n for n in os.listdir(tmp_path) if n.endswith(".tmp")]

    mk(tmp_path, f="F", g="G", h="H")
    out, _ = run(tmp_path, {"f": "g", "g": "h", "h": "f"})  # ciclo a tre
    assert all(o.ok for o in out)
    assert (tmp_path / "g").read_text() == "F" and (tmp_path / "h").read_text() == "G" and (tmp_path / "f").read_text() == "H"


def test_case_only_rename_case_insensitive(tmp_path):
    mk(tmp_path, abc="1")
    outcomes = apply_renames([(tmp_path / "abc", tmp_path / "ABC")], case_insensitive=True)
    assert outcomes[0].ok
    assert "ABC" in os.listdir(tmp_path) and "abc" not in os.listdir(tmp_path)


def test_never_overwrites(tmp_path):
    mk(tmp_path, a="A", b="B")
    # il piano è calcolato, poi qualcuno crea il bersaglio prima dell'esecuzione
    plan = build_plan([tmp_path / "a"], [Map({"a": "z"})])
    (tmp_path / "z").write_text("INTRUSO")
    out, _ = execute(plan, False)
    assert not out[0].ok and "esiste" in out[0].error
    assert read(tmp_path) == {"a": "A", "b": "B", "z": "INTRUSO"}


def test_blocked_plan_touches_nothing(tmp_path):
    mk(tmp_path, a="A", b="B")
    plan = build_plan([tmp_path / "a", tmp_path / "b"], [Map({"a": "x", "b": "x"})])
    with pytest.raises(PlanBlocked):
        execute(plan, False)
    assert read(tmp_path) == {"a": "A", "b": "B"}


@pytest.mark.skipif(os.geteuid() == 0 if hasattr(os, "geteuid") else True, reason="serve un utente non root")
def test_permission_denied_reported(tmp_path):
    d = tmp_path / "ro"
    d.mkdir()
    (d / "a").write_text("A")
    ok = mk(tmp_path, b="B")
    plan = build_plan([d / "a", ok / "b"], [Map({"a": "x", "b": "y"})])
    d.chmod(0o500)
    try:
        out, _ = execute(plan, False)
    finally:
        d.chmod(0o700)
    assert [o.ok for o in out] == [False, True]
    assert "ermission" in out[0].error
    assert (d / "a").exists() and (tmp_path / "y").exists()


def test_undo_roundtrip(tmp_path):
    mk(tmp_path, a="A", b="B", c="C")
    _, m = run(tmp_path, {"a": "b", "b": "a", "c": "z"})
    assert read(tmp_path) == {"a": "B", "b": "A", "z": "C"}
    assert pending_manifests(tmp_path / ".m") == [m]
    out = undo(m)
    assert all(o.ok for o in out)
    assert read(tmp_path) == {"a": "A", "b": "B", "c": "C"}
    assert pending_manifests(tmp_path / ".m") == []


def test_undo_partial_when_file_gone_or_original_taken(tmp_path):
    mk(tmp_path, a="A", b="B")
    _, m = run(tmp_path, {"a": "x", "b": "y"})
    (tmp_path / "x").unlink()  # sparito
    (tmp_path / "b").write_text("ALTRO")  # l'originale di y è stato rioccupato
    out = undo(m)
    errs = [o.error for o in out if not o.ok]
    assert len(errs) == 2
    assert read(tmp_path) == {"b": "ALTRO", "y": "B"}
    assert pending_manifests(tmp_path / ".m") == [m]  # resta in coda
    (tmp_path / "b").unlink()
    out = undo(m)  # ripetibile: x sparito resta un errore, y ora torna
    assert (tmp_path / "b").read_text() == "B"


def test_cancel_still_finalizes_temp_files(tmp_path):
    mk(tmp_path, a="A", b="B", c="C", d="D")
    plan = build_plan([tmp_path / n for n in "abcd"], [Map({"a": "b", "b": "a", "c": "x", "d": "y"})])
    calls = []
    out, _ = execute(plan, False, cancel=lambda: calls.append(1) or True)
    assert not [n for n in os.listdir(tmp_path) if n.endswith(".tmp")]
    assert read(tmp_path)["a"] in ("A", "B")
    assert len(out) == 4
