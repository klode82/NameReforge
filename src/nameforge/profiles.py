import json

from nameforge.actionpanels import SPEC_BY_KEY

VERSION = 1


class ProfileError(ValueError):
    pass


def dump_profile(items: list[dict]) -> str:
    """items: [{"key", "values", "enabled"}] nell'ordine del batch."""
    return json.dumps({"version": VERSION, "actions": items}, indent=2, ensure_ascii=False)


def parse_profile(text: str) -> list[dict]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProfileError(f"File non valido: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("actions"), list):
        raise ProfileError("Non è un profilo di NameReforge")
    if data.get("version", 0) > VERSION:
        raise ProfileError("Profilo creato da una versione più recente di NameReforge")
    items = []
    for a in data["actions"]:
        if not isinstance(a, dict) or a.get("key") not in SPEC_BY_KEY or not isinstance(a.get("values", {}), dict):
            raise ProfileError(f"Azione non riconosciuta: {a.get('key') if isinstance(a, dict) else a!r}")
        items.append({"key": a["key"], "values": a.get("values", {}), "enabled": bool(a.get("enabled", True))})
    return items
