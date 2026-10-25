import csv
import random
import re
import string
from dataclasses import dataclass
from pathlib import Path

from nameforge.core.actions import FileContext, NameParts, RenameAction
from nameforge.i18n import tr


@dataclass
class Replace(RenameAction):
    find: str = ""
    replace: str = ""
    case_sensitive: bool = True

    def process(self, parts: NameParts, ctx: FileContext) -> NameParts:
        if not self.find:
            return parts
        if self.case_sensitive:
            stem = parts.stem.replace(self.find, self.replace)
        else:
            stem = re.sub(re.escape(self.find), lambda _: self.replace, parts.stem, flags=re.IGNORECASE)
        return NameParts(stem, parts.ext)


@dataclass
class ChangeExtension(RenameAction):
    mode: str = "replace"  # replace | add | remove | lower | upper
    value: str = ""

    def process(self, parts: NameParts, ctx: FileContext) -> NameParts:
        value = self.value.lstrip(".")
        match self.mode:
            case "replace" if value:
                return NameParts(parts.stem, value)
            case "add" if value:
                return NameParts(parts.full, value)  # a.txt -> a.txt.bak
            case "remove":
                return NameParts(parts.stem, "")
            case "lower":
                return NameParts(parts.stem, parts.ext.lower())
            case "upper":
                return NameParts(parts.stem, parts.ext.upper())
        return parts


_WORD = re.compile(r"[^\W_]+(?:'[^\W_]+)*")  # "don't" resta una parola; "_" separa


@dataclass
class ChangeCase(RenameAction):
    mode: str = "lower"  # lower | upper | title | sentence

    def process(self, parts: NameParts, ctx: FileContext) -> NameParts:
        s = parts.stem
        match self.mode:
            case "lower":
                s = s.lower()
            case "upper":
                s = s.upper()
            case "title":
                s = _WORD.sub(lambda m: m[0].capitalize(), s)
            case "sentence":
                s = s[:1].upper() + s[1:].lower()
        return NameParts(s, parts.ext)


@dataclass
class Enumerate(RenameAction):
    start: int = 1
    step: int = 1
    digits: int = 3
    position: str = "prefix"  # prefix | suffix | replace
    separator: str = "_"
    per_folder: bool = True

    def process(self, parts: NameParts, ctx: FileContext) -> NameParts:
        i = ctx.folder_index if self.per_folder else ctx.index
        n = str(self.start + self.step * i).zfill(self.digits)
        match self.position:
            case "suffix":
                return NameParts(parts.stem + self.separator + n, parts.ext)
            case "replace":
                return NameParts(n, parts.ext)
        return NameParts(n + self.separator + parts.stem, parts.ext)


def _from_end(n: int, pos: int, from_end: bool) -> int:
    return max(0, n - pos) if from_end else min(pos, n)


@dataclass
class InsertChars(RenameAction):
    text: str = ""
    position: int = 0
    from_end: bool = False

    def process(self, parts: NameParts, ctx: FileContext) -> NameParts:
        s = parts.stem
        i = _from_end(len(s), self.position, self.from_end)
        return NameParts(s[:i] + self.text + s[i:], parts.ext)


@dataclass
class DeleteChars(RenameAction):
    start: int = 0
    count: int = 1
    from_end: bool = False  # start contato dalla fine del nome

    def process(self, parts: NameParts, ctx: FileContext) -> NameParts:
        s = parts.stem
        if self.from_end:
            end = len(s) - self.start
            begin = max(0, end - self.count)
            end = max(0, end)
        else:
            begin, end = self.start, self.start + self.count
        return NameParts(s[:begin] + s[end:], parts.ext)


@dataclass
class MoveChars(RenameAction):
    start: int = 0
    count: int = 1
    to: int = 0  # posizione nel nome rimasto dopo l'estrazione del blocco

    def process(self, parts: NameParts, ctx: FileContext) -> NameParts:
        s = parts.stem
        block, rest = s[self.start : self.start + self.count], s[: self.start] + s[self.start + self.count :]
        i = min(self.to, len(rest))
        return NameParts(rest[:i] + block + rest[i:], parts.ext)


@dataclass
class RandomName(RenameAction):
    length: int = 8
    seed: int = 1  # stesso seme, stessi nomi: l'anteprima non cambia a ogni ricalcolo

    def process(self, parts: NameParts, ctx: FileContext) -> NameParts:
        rng = random.Random(self.seed * 1_000_003 + ctx.index)
        return NameParts("".join(rng.choices(string.ascii_lowercase + string.digits, k=self.length)), parts.ext)


def load_names(path: str) -> tuple[str, ...]:
    """Una riga per nome; per i .csv la prima colonna. Righe vuote finali ignorate."""
    p = Path(path)
    with p.open(encoding="utf-8-sig", newline="") as f:
        rows = [r[0] if r else "" for r in csv.reader(f)] if p.suffix.lower() == ".csv" else f.read().splitlines()
    names = [r.strip() for r in rows]
    while names and not names[-1]:
        names.pop()
    return tuple(names)


@dataclass
class NamesFromFile(RenameAction):
    names: tuple[str, ...] = ()
    with_extension: bool = False

    def process(self, parts: NameParts, ctx: FileContext) -> NameParts:
        if ctx.index >= len(self.names):
            return parts
        new = self.names[ctx.index]
        return NameParts.from_name(new) if self.with_extension else NameParts(new, parts.ext)

    def warning(self, n_files: int) -> str | None:
        if len(self.names) != n_files:
            return tr("Il file contiene {names} nomi, la lista {files} file.", names=len(self.names), files=n_files)
        return None
