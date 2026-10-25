import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class NameParts:
    stem: str
    ext: str = ""  # senza punto iniziale

    @classmethod
    def from_name(cls, name: str) -> "NameParts":
        # come Path.suffix: ".bashrc" è senza estensione. splitext evita di creare un Path per ogni file
        stem, ext = os.path.splitext(name)
        return cls(name, "") if ext == "." else cls(stem, ext[1:])

    @property
    def full(self) -> str:
        return f"{self.stem}.{self.ext}" if self.ext else self.stem


@dataclass(frozen=True)
class FileContext:
    path: Path
    index: int  # posizione nell'elenco; serve a enumerazione e nomi da file esterno
    folder_index: int  # posizione dentro la propria cartella; reset per cartella


class RenameAction(ABC):
    @abstractmethod
    def process(self, parts: NameParts, ctx: FileContext) -> NameParts:
        """Restituisce le parti trasformate; non scrive mai sul disco."""
