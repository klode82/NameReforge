import errno
import json
import os
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from nameforge.core.plan import Entry, Status, can_execute
from nameforge.i18n import N_, tr

Pair = tuple[Path, Path]  # (da, a)

# Gli errori del sistema operativo arrivano in inglese (o nella lingua del sistema): i più comuni si traducono qui.
_ERRNO_TEXT = {
    errno.EACCES: N_("error.permission_denied"),
    errno.EPERM: N_("error.operation_not_permitted"),
    errno.ENOENT: N_("error.file_no_longer_exists"),
    errno.EEXIST: N_("error.destination_exists"),
    errno.EROFS: N_("error.read_only_filesystem"),
    errno.ENOSPC: N_("error.no_space_left"),
    errno.EBUSY: N_("error.file_in_use"),
    errno.ENAMETOOLONG: N_("error.name_too_long"),
}
_WINERROR_IN_USE = (32, 33)  # violazione di condivisione / blocco: il file è aperto in un altro programma


def os_error_text(exc: OSError) -> str:
    if getattr(exc, "winerror", None) in _WINERROR_IN_USE:
        return tr("error.file_in_use")
    text = _ERRNO_TEXT.get(exc.errno)
    return tr(text) if text else (exc.strerror or str(exc))


@dataclass
class Outcome:
    src: Path
    dst: Path
    ok: bool
    error: str | None = None


class PlanBlocked(Exception):
    """Il piano ha conflitti: niente viene toccato."""


def _key(p: Path, case_insensitive: bool) -> tuple[str, str]:
    name = p.name.casefold() if case_insensitive else p.name
    return os.path.dirname(p), name


def apply_renames(
    pairs: Sequence[Pair],
    case_insensitive: bool,
    progress: Callable[[int, int], None] | None = None,
    cancel: Callable[[], bool] | None = None,
) -> list[Outcome]:
    """Rinomina senza sovrascrivere nulla, anche con catene (a->b, b->c), scambi (a<->b) e cambi di solo maiuscole.

    Le coppie il cui bersaglio è oggi il nome di un altro file da rinominare passano da un nome temporaneo:
    1) quelle coppie -> temporaneo; 2) le altre direttamente; 3) temporaneo -> bersaglio.
    """
    sources = {_key(s, case_insensitive) for s, _ in pairs}
    blocked = [(s, d) for s, d in pairs if _key(d, case_insensitive) in sources]
    blocked_set = set(blocked)
    direct = [p for p in pairs if p not in blocked_set]
    total, done = len(pairs), 0
    outcomes: dict[Pair, Outcome] = {}
    temps: dict[Pair, Path] = {}

    def tick() -> bool:
        nonlocal done
        done += 1
        if progress:
            progress(done, total)
        return bool(cancel and cancel())

    def move(src: Path, dst: Path) -> str | None:
        # ponytail: lexists+rename non è atomico; link/RENAME_NOREPLACE chiuderebbe la finestra di corsa
        try:
            if os.path.lexists(dst):
                return tr("error.destination_exists")
            os.rename(src, dst)
        except OSError as exc:
            return os_error_text(exc)
        return None

    stopped = False
    for pair in blocked:
        tmp = pair[0].with_name(f".nameforge-{uuid.uuid4().hex}.tmp")
        err = move(pair[0], tmp)
        if err:
            outcomes[pair] = Outcome(*pair, False, err)
            stopped = tick()
        else:
            temps[pair] = tmp
        if stopped:
            break
    if not stopped:
        for pair in direct:
            err = move(*pair)
            outcomes[pair] = Outcome(*pair, err is None, err)
            if tick():
                stopped = True
                break
    # Fase 3 sempre eseguita: un file lasciato sotto nome temporaneo sarebbe perso per l'utente.
    for pair, tmp in temps.items():
        err = move(tmp, pair[1])
        if err:
            back = move(tmp, pair[0])  # ripristina il nome originale
            err += "" if back is None else tr("error.restore_failed", name=tmp.name)
        outcomes[pair] = Outcome(*pair, err is None, err)
        tick()
    for pair in pairs:
        outcomes.setdefault(pair, Outcome(*pair, False, tr("status.cancelled")))
    return [outcomes[p] for p in pairs]


def _write_atomic(path: Path, data: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def execute(
    plan: Sequence[Entry],
    case_insensitive: bool,
    manifest_dir: Path | None = None,
    progress: Callable[[int, int], None] | None = None,
    cancel: Callable[[], bool] | None = None,
) -> tuple[list[Outcome], Path | None]:
    """Esegue il piano. Il manifest è scritto PRIMA di toccare il disco: dopo un crash l'undo resta possibile."""
    if not can_execute(plan):
        raise PlanBlocked(tr("error.plan_has_conflicts"))
    pairs = [(e.path, e.target) for e in plan if e.status is Status.OK]
    if not pairs:
        return [], None
    manifest = None
    if manifest_dir:
        manifest_dir.mkdir(parents=True, exist_ok=True)
        manifest = manifest_dir / f"{datetime.now():%Y%m%d-%H%M%S-%f}.json"
        _write_atomic(manifest, {"version": 1, "created": datetime.now().isoformat(), "undone": False,
                                 "case_insensitive": case_insensitive,
                                 "renames": [[str(s), str(d)] for s, d in pairs]})
    return apply_renames(pairs, case_insensitive, progress, cancel), manifest


def pending_manifests(manifest_dir: Path) -> list[Path]:
    """Sessioni non ancora annullate, la più recente per ultima."""
    out = []
    for p in sorted(manifest_dir.glob("*.json")) if manifest_dir.is_dir() else []:
        try:
            if not json.loads(p.read_text(encoding="utf-8")).get("undone"):
                out.append(p)
        except (OSError, ValueError):
            continue
    return out


def undo(manifest: Path, progress=None) -> list[Outcome]:
    """Riporta i file ai nomi originali, guardando lo stato reale del disco e non solo il manifest.

    Salta (con motivo) i file spostati o cancellati dopo la rinomina e quelli il cui nome originale è stato rioccupato.
    """
    data = json.loads(manifest.read_text(encoding="utf-8"))
    ci = data.get("case_insensitive", False)
    back, skipped = [], []
    for s, d in data["renames"]:
        src, dst = Path(s), Path(d)
        if not os.path.lexists(dst):
            if os.path.lexists(src):  # già ripristinato (undo parziale ripetuto, o rinomina fallita all'origine)
                skipped.append(Outcome(dst, src, True, tr("status.already_original")))
            else:
                skipped.append(Outcome(dst, src, False, tr("error.file_not_at_new_name")))
        else:
            back.append((dst, src))
    # un originale oggi occupato da un file estraneo (non in lista) non va sovrascritto: lo segnala move()
    outcomes = apply_renames(back, ci, progress)
    data["undone"] = all(o.ok for o in skipped + outcomes)
    data["undone_at"] = datetime.now().isoformat()
    _write_atomic(manifest, data)  # parziale: resta in coda, i file già ripristinati sono saltati al giro dopo
    return skipped + outcomes
