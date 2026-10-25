"""Trova le stringhe da tradurre nel codice e allinea assets/i18n/<lingua>.json.

    python tools/i18n_extract.py            # elenca voci mancanti e voci orfane
    python tools/i18n_extract.py --write    # aggiunge le mancanti (valore vuoto) in tutti i cataloghi

Le stringhe sono i letterali passati a tr(), trn() e N_(); i letterali con più forme (trn) vogliono
nel catalogo {"one": "...", "other": "..."}.
"""

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "nameforge"
CATALOGS = SRC / "assets" / "i18n"
SOURCE_LANGUAGE = "it"


def collect(src: Path = SRC) -> dict[str, bool]:
    """{testo sorgente: è plurale?} per ogni tr()/trn()/N_() con un letterale come primo argomento."""
    found: dict[str, bool] = {}
    for path in sorted(src.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.args):
                continue
            first = node.args[0]
            if node.func.id in ("tr", "trn", "N_") and isinstance(first, ast.Constant) and isinstance(first.value, str):
                found[first.value] = found.get(first.value, False) or node.func.id == "trn"
    return found


def catalog_paths() -> list[Path]:
    return sorted(p for p in CATALOGS.glob("*.json") if p.stem != SOURCE_LANGUAGE)


def main() -> int:
    found = collect()
    status = 0
    for path in catalog_paths():
        data = json.loads(path.read_text(encoding="utf-8"))
        keys = {k for k, v in data.items() if isinstance(v, (str, dict))}  # le liste sono commenti
        missing = [k for k in found if k not in keys or not data[k]]
        stale = sorted(keys - set(found))
        print(f"{path.name}: {len(found)} stringhe, {len(missing)} da tradurre, {len(stale)} orfane")
        for k in missing:
            print("  da tradurre:", repr(k))
        for k in stale:
            print("  orfana:     ", repr(k))
        status |= bool(missing or stale)
        if "--write" in sys.argv:
            for k in missing:
                data.setdefault(k, {"one": "", "other": ""} if found[k] else "")
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
