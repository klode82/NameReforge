"""Traduzioni: un catalogo JSON per lingua (assets/i18n/<lingua>.json), con il testo sorgente in italiano come chiave.

    tr("Testo")                      -> testo tradotto
    tr("Rinominati: {n}", n=3)       -> con segnaposto (str.format)
    trn("{n} file", n)               -> forma singolare/plurale: nel catalogo {"one": "...", "other": "..."}
    N_("Testo")                      -> segna una stringa da tradurre più tardi (dati a livello di modulo)

Senza voce nel catalogo (o con voce vuota) vale il testo sorgente: una traduzione mancante non rompe nulla.
Nessuna dipendenza da Qt: ci si appoggia anche il motore (core/).
"""

import json
from pathlib import Path

CATALOG_DIR = Path(__file__).parent / "assets" / "i18n"
SOURCE_LANGUAGE = "it"
LANGUAGES = {"it": "Italiano", "en": "English"}  # ogni lingua col proprio nome

_language = SOURCE_LANGUAGE
_catalog: dict = {}
_error: str | None = None


def N_(text: str) -> str:
    """Non traduce: marca il testo perché lo strumento di estrazione lo trovi."""
    return text


def set_language(language: str) -> None:
    global _language, _catalog, _error
    _language = language if language in LANGUAGES else SOURCE_LANGUAGE
    _catalog, _error = {}, None
    if _language == SOURCE_LANGUAGE:
        return
    path = CATALOG_DIR / f"{_language}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        _catalog = {k: v for k, v in data.items() if isinstance(v, (str, dict))}  # le liste sono commenti
    except (OSError, ValueError) as exc:
        _error = f"{path.name}: {exc}"  # l'interfaccia resta in italiano, ma l'errore si mostra


def language() -> str:
    return _language


def catalog_error() -> str | None:
    """Motivo per cui il catalogo non è stato letto (con riga e colonna), oppure None."""
    return _error


def tr(text: str, **values) -> str:
    out = _catalog.get(text)
    out = out if isinstance(out, str) and out else text
    return out.format(**values) if values else out


def trn(text: str, n: int, **values) -> str:
    entry = _catalog.get(text)
    if isinstance(entry, dict):
        out = entry.get("one" if n == 1 else "other") or text
    else:
        out = entry if isinstance(entry, str) and entry else text
    return out.format(n=n, **values)


def resolve_language(setting: str | None, system_locale: str) -> str:
    """Scelta esplicita se valida; altrimenti la lingua del sistema (italiano solo se il sistema è italiano)."""
    if setting in LANGUAGES:
        return setting
    return "it" if system_locale.lower().startswith("it") else "en"
