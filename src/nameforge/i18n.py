"""Traduzioni: un catalogo JSON per lingua (assets/i18n/<lingua>.json) con chiavi stabili (gruppo.nome).

    tr("button.add_files")              -> testo nella lingua attiva
    tr("status.renamed", n=3)           -> con segnaposto (str.format)
    trn("status.file_count", n)         -> forma singolare/plurale: nel catalogo {"one": "...", "other": "..."}
    N_("action.replace_string")         -> segna una chiave da tradurre più tardi (dati a livello di modulo)

La lingua predefinita è l'inglese. Una chiave mancante (o vuota) nella lingua attiva si cerca in inglese; se manca
anche lì si mostra la chiave stessa, così un buco nella traduzione si vede ma non rompe nulla.
Nessuna dipendenza da Qt: ci si appoggia anche il motore (core/).
"""

import json
from pathlib import Path

CATALOG_DIR = Path(__file__).parent / "assets" / "i18n"
DEFAULT_LANGUAGE = "en"  # lingua predefinita e di ripiego
LANGUAGES = {"en": "English", "it": "Italiano"}  # ogni lingua col proprio nome

_language = DEFAULT_LANGUAGE
_catalog: dict = {}
_fallback: dict = {}
_error: str | None = None


def N_(key: str) -> str:
    """Non traduce: marca la chiave perché lo strumento di estrazione la trovi."""
    return key


def _load(language: str) -> tuple[dict, str | None]:
    path = CATALOG_DIR / f"{language}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {}, f"{path.name}: {exc}"  # l'errore si mostra; l'interfaccia resta usabile
    return {k: v for k, v in data.items() if isinstance(v, (str, dict))}, None  # le liste sono commenti


def set_language(language: str) -> None:
    global _language, _catalog, _fallback, _error
    _language = language if language in LANGUAGES else DEFAULT_LANGUAGE
    _fallback, fallback_error = _load(DEFAULT_LANGUAGE)
    if _language == DEFAULT_LANGUAGE:
        _catalog, _error = _fallback, fallback_error
    else:
        _catalog, _error = _load(_language)


def language() -> str:
    return _language


def catalog_error() -> str | None:
    """Motivo per cui il catalogo della lingua attiva non è stato letto (con riga e colonna), oppure None."""
    return _error


def _entry(key: str):
    for catalog in (_catalog, _fallback):
        value = catalog.get(key)
        if isinstance(value, dict) and any(value.values()) or isinstance(value, str) and value:
            return value
    return key


def tr(key: str, /, **values) -> str:
    out = _entry(key)
    out = out if isinstance(out, str) else key
    return out.format(**values) if values else out


def trn(key: str, n: int, /, **values) -> str:
    out = _entry(key)
    if isinstance(out, dict):
        out = out.get("one" if n == 1 else "other") or out.get("other") or key
    return out.format(n=n, **values)


def resolve_language(setting: str | None, system_locale: str) -> str:
    """Scelta esplicita se valida; "auto" = lingua del sistema; nessuna scelta = inglese (predefinita)."""
    if setting in LANGUAGES:
        return setting
    if setting == "auto":
        return "it" if system_locale.lower().startswith("it") else DEFAULT_LANGUAGE
    return DEFAULT_LANGUAGE


set_language(DEFAULT_LANGUAGE)
