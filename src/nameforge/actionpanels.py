import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QWidget,
)

from nameforge.core.actions import RenameAction
from nameforge.core.builtins import (
    ChangeCase,
    ChangeExtension,
    DeleteChars,
    Enumerate,
    InsertChars,
    MoveChars,
    NamesFromFile,
    RandomName,
    Replace,
    load_names,
)
from nameforge.core.metadata import AudioTags, DateTime, ExifTags, RegexReplace


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    kind: str  # text | int | bool | choice | file
    default: Any = None
    options: tuple[tuple[str, str], ...] = ()  # (valore, etichetta) per choice


@dataclass(frozen=True)
class ActionSpec:
    key: str  # identificatore stabile nei profili JSON
    title: str
    fields: tuple[Field, ...]
    factory: Callable[..., RenameAction]


def _names_from_file(path: str, with_extension: bool) -> RenameAction:
    return NamesFromFile(load_names(path) if path else (), with_extension)


SPECS = (
    ActionSpec("replace", "Sostituisci stringa", (
        Field("find", "Cerca", "text", ""),
        Field("replace", "Sostituisci con", "text", ""),
        Field("case_sensitive", "Distingui maiuscole", "bool", True),
    ), Replace),
    ActionSpec("extension", "Cambia estensione", (
        Field("mode", "Modo", "choice", "replace", (
            ("replace", "Sostituisci"), ("add", "Aggiungi in coda"), ("remove", "Rimuovi"),
            ("lower", "Minuscola"), ("upper", "Maiuscola"))),
        Field("value", "Estensione", "text", ""),
    ), ChangeExtension),
    ActionSpec("case", "Maiuscole/minuscole", (
        Field("mode", "Stile", "choice", "lower", (
            ("lower", "tutto minuscolo"), ("upper", "TUTTO MAIUSCOLO"),
            ("title", "Iniziali Maiuscole"), ("sentence", "Prima lettera maiuscola"))),
    ), ChangeCase),
    ActionSpec("enumerate", "Enumerazione", (
        Field("start", "Parti da", "int", 1),
        Field("step", "Passo", "int", 1),
        Field("digits", "Cifre (zeri a sinistra)", "int", 3),
        Field("position", "Posizione", "choice", "prefix", (
            ("prefix", "Prima del nome"), ("suffix", "Dopo il nome"), ("replace", "Al posto del nome"))),
        Field("separator", "Separatore", "text", "_"),
        Field("per_folder", "Ricomincia in ogni cartella", "bool", True),
    ), Enumerate),
    ActionSpec("insert", "Inserisci caratteri", (
        Field("text", "Testo", "text", ""),
        Field("position", "Posizione", "int", 0),
        Field("from_end", "Conta dalla fine", "bool", False),
    ), InsertChars),
    ActionSpec("move", "Sposta caratteri", (
        Field("start", "Da posizione", "int", 0),
        Field("count", "Quanti", "int", 1),
        Field("to", "A posizione", "int", 0),
    ), MoveChars),
    ActionSpec("delete", "Cancella caratteri", (
        Field("start", "Da posizione", "int", 0),
        Field("count", "Quanti", "int", 1),
        Field("from_end", "Conta dalla fine", "bool", False),
    ), DeleteChars),
    ActionSpec("random", "Nome casuale", (
        Field("length", "Lunghezza", "int", 8),
        Field("seed", "Seme (cambialo per nuovi nomi)", "int", 1),
    ), RandomName),
    ActionSpec("regex", "Espressione regolare", (
        Field("pattern", "Pattern", "text", ""),
        Field("replacement", "Sostituzione (\\1, \\g<nome>)", "text", ""),
        Field("ignore_case", "Ignora maiuscole", "bool", False),
        Field("target", "Applica a", "choice", "stem", (("stem", "Nome senza estensione"), ("full", "Nome con estensione"))),
    ), RegexReplace),
    ActionSpec("datetime", "Data e ora", (
        Field("source", "Data", "choice", "modified", (
            ("modified", "Ultima modifica"), ("created", "Creazione"), ("accessed", "Ultimo accesso"))),
        Field("fmt", "Formato (strftime)", "text", "%Y-%m-%d"),
        Field("position", "Posizione", "choice", "prefix", (
            ("prefix", "Prima del nome"), ("suffix", "Dopo il nome"), ("replace", "Al posto del nome"))),
        Field("separator", "Separatore", "text", "_"),
    ), DateTime),
    ActionSpec("audio", "Tag audio", (
        Field("template", "Modello ({artist} {title} {album} {albumartist} {genre} {track:02} {disc} {year})", "text", "{artist} - {title}"),
        Field("position", "Posizione", "choice", "replace", (
            ("prefix", "Prima del nome"), ("suffix", "Dopo il nome"), ("replace", "Al posto del nome"))),
        Field("separator", "Separatore", "text", "_"),
        Field("skip_if_missing", "Se manca un dato lascia il nome com'è", "bool", True),
        Field("missing", "Altrimenti scrivi", "text", ""),
    ), AudioTags),
    ActionSpec("exif", "Metadati EXIF", (
        Field("template", "Modello ({date:%Y-%m-%d_%H%M%S} {make} {model} {width} {height})", "text", "{date:%Y-%m-%d_%H%M%S}"),
        Field("position", "Posizione", "choice", "replace", (
            ("prefix", "Prima del nome"), ("suffix", "Dopo il nome"), ("replace", "Al posto del nome"))),
        Field("separator", "Separatore", "text", "_"),
        Field("skip_if_missing", "Se manca un dato lascia il nome com'è", "bool", True),
        Field("missing", "Altrimenti scrivi", "text", ""),
    ), ExifTags),
    ActionSpec("names", "Nomi da file", (
        Field("path", "File .txt o .csv", "file", ""),
        Field("with_extension", "I nomi includono l'estensione", "bool", False),
    ), _names_from_file),
)


class ActionPanel(QWidget):
    """Pannello generato da una ActionSpec: nessuna classe per azione."""

    changed = Signal()

    def __init__(self, spec: ActionSpec) -> None:
        super().__init__()
        self.spec = spec
        self.error: str | None = None
        self._widgets: dict[str, QWidget] = {}
        form = QFormLayout(self)
        for f in spec.fields:
            w = self._make(f)
            self._widgets[f.key] = w
            form.addRow(f.label if f.kind != "bool" else "", w)

    def _make(self, f: Field) -> QWidget:
        if f.kind == "text":
            w = QLineEdit(f.default)
            w.textChanged.connect(self.changed)
        elif f.kind == "int":
            w = QSpinBox()
            w.setRange(-1_000_000, 1_000_000)
            w.setValue(f.default)
            w.valueChanged.connect(self.changed)
        elif f.kind == "bool":
            w = QCheckBox(f.label)
            w.setChecked(f.default)
            w.toggled.connect(self.changed)
        elif f.kind == "choice":
            w = QComboBox()
            for value, label in f.options:
                w.addItem(label, value)
            w.setCurrentIndex(w.findData(f.default))
            w.currentIndexChanged.connect(self.changed)
        else:  # file
            return self._make_file(f)
        return w

    def _make_file(self, f: Field) -> QWidget:
        box, edit, pick = QWidget(), QLineEdit(f.default), QPushButton("Sfoglia…")
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(edit)
        row.addWidget(pick)
        edit.textChanged.connect(self.changed)
        pick.clicked.connect(lambda: self._pick(edit))
        box.edit = edit  # type: ignore[attr-defined]
        return box

    def _pick(self, edit: QLineEdit) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Scegli il file", "", "Nomi (*.txt *.csv);;Tutti i file (*)")
        if path:
            edit.setText(path)

    def values(self) -> dict[str, Any]:
        out = {}
        for f in self.spec.fields:
            w = self._widgets[f.key]
            out[f.key] = (
                w.text() if f.kind == "text"
                else w.value() if f.kind == "int"
                else w.isChecked() if f.kind == "bool"
                else w.currentData() if f.kind == "choice"
                else w.edit.text()
            )
        return out

    def build(self) -> RenameAction:
        """Azione dai valori correnti. Se i parametri non sono validi (es. file illeggibile) lascia `error`."""
        self.error = None
        try:
            return self.spec.factory(**self.values())
        except (OSError, UnicodeDecodeError, ValueError, re.error) as exc:
            self.error = str(exc)
            return Replace()  # azione neutra finché i parametri non sono validi


class WarningLabel(QLabel):
    def __init__(self) -> None:
        super().__init__()
        self.setWordWrap(True)
        self.setStyleSheet("color: #b45309;")


SPEC_BY_KEY = {s.key: s for s in SPECS}


def build_action(key: str, values: dict[str, Any]) -> RenameAction:
    """Costruisce un'azione da chiave e valori (profili, batch). I campi mancanti prendono il default."""
    spec = SPEC_BY_KEY[key]
    full = {f.key: values.get(f.key, f.default) for f in spec.fields}
    return spec.factory(**full)
