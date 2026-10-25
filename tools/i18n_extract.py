"""Trova le chiavi di traduzione nel codice e allinea tutti i cataloghi in assets/i18n/<lingua>.json.

    python tools/i18n_extract.py            # elenca chiavi mancanti, orfane o scritte male
    python tools/i18n_extract.py --write    # aggiunge le chiavi mancanti (valore vuoto) in ogni catalogo

Le chiavi sono i letterali passati a tr(), trn() e N_(). Hanno la forma gruppo.nome in minuscolo con underscore
(es. "action.replace_string"): un testo da leggere al posto di una chiave è un errore.
Le chiavi di trn() vogliono nel catalogo {"one": "...", "other": "..."}.
"""

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "nameforge"
CATALOGS = SRC / "assets" / "i18n"
KEY_FORMAT = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")


def collect(src: Path = SRC) -> dict[str, bool]:
    """{chiave: è plurale?} per ogni tr()/trn()/N_() con un letterale come primo argomento."""
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
    return sorted(CATALOGS.glob("*.json"))


def entries(data: dict) -> dict:
    return {k: v for k, v in data.items() if isinstance(v, (str, dict))}  # le liste sono commenti


def main() -> int:
    found = collect()
    status = 0
    bad = [k for k in found if not KEY_FORMAT.match(k)]
    if bad:
        status = 1
        print("chiavi nel codice che non sono chiavi (gruppo.nome):")
        for k in bad:
            print("  ", repr(k))
    for path in catalog_paths():
        data = json.loads(path.read_text(encoding="utf-8"))
        keys = entries(data)
        missing = [k for k in found if k not in keys or not (any(keys[k].values()) if isinstance(keys[k], dict) else keys[k])]
        stale = sorted(set(keys) - set(found))
        badly_named = [k for k in keys if not KEY_FORMAT.match(k)]
        print(f"{path.name}: {len(found)} chiavi nel codice, {len(missing)} da tradurre, {len(stale)} orfane")
        for label, items in (("da tradurre", missing), ("orfana", stale), ("chiave scritta male", badly_named)):
            for k in items:
                print(f"  {label}: {k!r}")
        status |= bool(missing or stale or badly_named)
        if "--write" in sys.argv:
            for k in missing:
                data[k] = {"one": "", "other": ""} if found[k] else ""
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
