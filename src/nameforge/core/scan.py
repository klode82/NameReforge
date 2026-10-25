import os
from collections.abc import Iterable
from pathlib import Path


def collect_files(paths: Iterable[Path], recursive: bool = True) -> list[Path]:
    """Espande cartelle in file; i file passati direttamente restano. Ordine stabile, senza duplicati."""
    out: dict[Path, None] = {}
    for p in map(Path, paths):
        if p.is_dir():
            for f in _walk(p, recursive):
                out[f] = None
        elif p.is_file():
            out[p] = None
    return list(out)


def _walk(folder: Path, recursive: bool):
    try:
        with os.scandir(folder) as it:
            entries = sorted(it, key=lambda e: e.name.casefold())
    except OSError:
        return  # ponytail: cartelle illeggibili saltate in silenzio; segnalarle nel Log in fase 7
    for e in entries:
        if e.is_file():  # segue i symlink a file
            yield Path(e.path)
        elif recursive and e.is_dir(follow_symlinks=False):
            yield from _walk(Path(e.path), recursive)
