import os
import re
import string
import sys
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import ClassVar

from nameforge.core.actions import FileContext, NameParts, RenameAction


def _join(parts: NameParts, text: str, position: str, separator: str) -> NameParts:
    match position:
        case "suffix":
            return NameParts(parts.stem + separator + text, parts.ext)
        case "replace":
            return NameParts(text, parts.ext)
    return NameParts(text + separator + parts.stem, parts.ext)


@dataclass
class RegexReplace(RenameAction):
    pattern: str = ""
    replacement: str = ""  # \1, \g<nome>
    ignore_case: bool = False
    target: str = "stem"  # stem | full (nome con estensione)

    def __post_init__(self) -> None:
        self._rx = re.compile(self.pattern, re.IGNORECASE if self.ignore_case else 0) if self.pattern else None
        if self._rx:
            self._rx.sub(self.replacement, "")  # il template sbagliato (\9 inesistente) fallisce già qui

    def process(self, parts: NameParts, ctx: FileContext) -> NameParts:
        if not self._rx:
            return parts
        if self.target == "full":
            return NameParts.from_name(self._rx.sub(self.replacement, parts.full))
        return NameParts(self._rx.sub(self.replacement, parts.stem), parts.ext)


@dataclass
class DateTime(RenameAction):
    source: str = "modified"  # created | modified | accessed
    fmt: str = "%Y-%m-%d"
    position: str = "prefix"
    separator: str = "_"

    def __post_init__(self) -> None:
        datetime.now().strftime(self.fmt)  # formato non valido: ValueError subito

    def process(self, parts: NameParts, ctx: FileContext) -> NameParts:
        try:
            st = os.stat(ctx.path)
        except OSError:
            return parts
        ts = {
            "created": getattr(st, "st_birthtime", st.st_mtime),  # ponytail: Linux non espone la creazione via os.stat; statx se serve
            "accessed": st.st_atime,
        }.get(self.source, st.st_mtime)
        text = datetime.fromtimestamp(ts).strftime(self.fmt)
        return _join(parts, text, self.position, self.separator)

    def warning(self, n_files: int) -> str | None:
        if self.source == "created" and sys.platform.startswith("linux"):
            return "Su Linux la data di creazione non è disponibile: viene usata quella di modifica."
        return None


def _fields_in(template: str) -> list[str]:
    try:
        return [re.split(r"[.\[]", f)[0] for _, f, _, _ in string.Formatter().parse(template) if f is not None]
    except ValueError as exc:
        raise ValueError(f"Modello non valido: {exc}") from exc


@dataclass
class TemplateAction(RenameAction):
    """Inserisce nel nome un testo costruito da metadati del file, es. '{artist} - {title}'."""

    template: str = ""
    position: str = "replace"
    separator: str = "_"
    skip_if_missing: bool = True  # metadato assente: nome invariato
    missing: str = ""  # altrimenti: testo al suo posto

    FIELDS: ClassVar[tuple[str, ...]] = ()

    def __post_init__(self) -> None:
        unknown = [f for f in _fields_in(self.template) if f not in self.FIELDS]
        if unknown:
            raise ValueError(f"Campo sconosciuto: {unknown[0]}. Disponibili: {', '.join(self.FIELDS)}")

    def read(self, path: Path) -> dict:
        raise NotImplementedError

    def process(self, parts: NameParts, ctx: FileContext) -> NameParts:
        if not self.template:
            return parts
        values = self.read(ctx.path)
        used = _fields_in(self.template)
        if any(values.get(f) in (None, "") for f in used):
            if self.skip_if_missing:
                return parts
            values = {k: (v if v not in (None, "") else self.missing) for k, v in values.items()}
            for f in used:
                values.setdefault(f, self.missing)
        try:
            text = self.template.format_map(values)
        except (ValueError, TypeError):  # es. {date:%Y} con data sostituita dal segnaposto
            return parts
        return _join(parts, text, self.position, self.separator)


def _stamp(path: Path) -> tuple[int, int] | None:
    try:
        st = os.stat(path)
    except OSError:
        return None
    return st.st_mtime_ns, st.st_size


# La lettura dei tag è il costo dominante; la chiave include mtime/size così le modifiche sul disco invalidano.
@lru_cache(maxsize=200_000)
def _audio_tags(path: str, stamp: tuple[int, int]) -> dict:
    import mutagen

    try:
        f = mutagen.File(path, easy=True)
    except Exception:  # noqa: BLE001 - file corrotto o formato strano: nessun tag, non un errore
        return {}
    if f is None or not f.tags:
        return {}

    def first(key: str) -> str:
        v = f.tags.get(key)
        return str(v[0]).strip() if v else ""

    def number(key: str):
        m = re.match(r"\d+", first(key))  # "3/12" -> 3
        return int(m[0]) if m else ""

    year = re.match(r"\d{4}", first("date"))
    return {
        "artist": first("artist"), "title": first("title"), "album": first("album"),
        "albumartist": first("albumartist"), "genre": first("genre"),
        "track": number("tracknumber"), "disc": number("discnumber"),
        "year": int(year[0]) if year else "",
    }


@dataclass
class AudioTags(TemplateAction):
    template: str = "{artist} - {title}"
    FIELDS = ("artist", "title", "album", "albumartist", "genre", "track", "disc", "year")

    def read(self, path: Path) -> dict:
        stamp = _stamp(path)
        return _audio_tags(str(path), stamp) if stamp else {}


@lru_cache(maxsize=200_000)
def _exif(path: str, stamp: tuple[int, int]) -> dict:
    from PIL import Image

    try:
        with Image.open(path) as img:
            width, height = img.size
            exif = img.getexif()
            sub = exif.get_ifd(0x8769)  # Exif IFD: DateTimeOriginal sta qui
            raw = sub.get(0x9003) or sub.get(0x9004) or exif.get(0x0132)
            clean = lambda v: str(v).replace("\x00", "").strip() if v else ""
            date = None
            if raw:
                try:
                    date = datetime.strptime(str(raw).strip("\x00 "), "%Y:%m:%d %H:%M:%S")
                except ValueError:
                    pass
            return {"date": date, "make": clean(exif.get(0x010F)), "model": clean(exif.get(0x0110)),
                    "width": width, "height": height}
    except Exception:  # noqa: BLE001 - non è un'immagine leggibile
        return {}


@dataclass
class ExifTags(TemplateAction):
    template: str = "{date:%Y-%m-%d_%H%M%S}"
    FIELDS = ("date", "make", "model", "width", "height")

    def read(self, path: Path) -> dict:
        stamp = _stamp(path)
        return _exif(str(path), stamp) if stamp else {}
