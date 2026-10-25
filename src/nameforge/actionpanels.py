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
from nameforge.help import field_tip, rich
from nameforge.i18n import N_, tr


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
    ActionSpec("replace", N_("Sostituisci stringa"), (
        Field("find", N_("Cerca"), "text", ""),
        Field("replace", N_("Sostituisci con"), "text", ""),
        Field("case_sensitive", N_("Distingui maiuscole"), "bool", True),
    ), Replace),
    ActionSpec("extension", N_("Cambia estensione"), (
        Field("mode", N_("Modo"), "choice", "replace", (
            ("replace", N_("Sostituisci")), ("add", N_("Aggiungi in coda")), ("remove", N_("Rimuovi")),
            ("lower", N_("Minuscola")), ("upper", N_("Maiuscola")))),
        Field("value", N_("Estensione"), "text", ""),
    ), ChangeExtension),
    ActionSpec("case", N_("Maiuscole/minuscole"), (
        Field("mode", N_("Stile"), "choice", "lower", (
            ("lower", N_("tutto minuscolo")), ("upper", N_("TUTTO MAIUSCOLO")),
            ("title", N_("Iniziali Maiuscole")), ("sentence", N_("Prima lettera maiuscola")))),
    ), ChangeCase),
    ActionSpec("enumerate", N_("Enumerazione"), (
        Field("start", N_("Parti da"), "int", 1),
        Field("step", N_("Passo"), "int", 1),
        Field("digits", N_("Cifre (zeri a sinistra)"), "int", 3),
        Field("position", N_("Posizione"), "choice", "prefix", (
            ("prefix", N_("Prima del nome")), ("suffix", N_("Dopo il nome")), ("replace", N_("Al posto del nome")))),
        Field("separator", N_("Separatore"), "text", "_"),
        Field("per_folder", N_("Ricomincia in ogni cartella"), "bool", True),
    ), Enumerate),
    ActionSpec("insert", N_("Inserisci caratteri"), (
        Field("text", N_("Testo"), "text", ""),
        Field("position", N_("Posizione"), "int", 0),
        Field("from_end", N_("Conta dalla fine"), "bool", False),
    ), InsertChars),
    ActionSpec("move", N_("Sposta caratteri"), (
        Field("start", N_("Da posizione"), "int", 0),
        Field("count", N_("Quanti"), "int", 1),
        Field("to", N_("A posizione"), "int", 0),
    ), MoveChars),
    ActionSpec("delete", N_("Cancella caratteri"), (
        Field("start", N_("Da posizione"), "int", 0),
        Field("count", N_("Quanti"), "int", 1),
        Field("from_end", N_("Conta dalla fine"), "bool", False),
    ), DeleteChars),
    ActionSpec("random", N_("Nome casuale"), (
        Field("length", N_("Lunghezza"), "int", 8),
        Field("seed", N_("Seme (cambialo per nuovi nomi)"), "int", 1),
    ), RandomName),
    ActionSpec("regex", N_("Espressione regolare"), (
        Field("pattern", N_("Modello di ricerca"), "text", ""),
        Field("replacement", N_("Sostituzione (\\1 o $1)"), "text", ""),
        Field("ignore_case", N_("Ignora maiuscole"), "bool", False),
        Field("target", N_("Applica a"), "choice", "stem", (("stem", N_("Nome senza estensione")), ("full", N_("Nome con estensione")))),
    ), RegexReplace),
    ActionSpec("datetime", N_("Data e ora"), (
        Field("source", N_("Data"), "choice", "modified", (
            ("modified", N_("Ultima modifica")), ("created", N_("Creazione")), ("accessed", N_("Ultimo accesso")))),
        Field("fmt", N_("Formato (strftime)"), "text", "%Y-%m-%d"),
        Field("position", N_("Posizione"), "choice", "prefix", (
            ("prefix", N_("Prima del nome")), ("suffix", N_("Dopo il nome")), ("replace", N_("Al posto del nome")))),
        Field("separator", N_("Separatore"), "text", "_"),
    ), DateTime),
    ActionSpec("audio", N_("Tag audio"), (
        Field("template", N_("Modello ({artist} {title} {album} {albumartist} {genre} {track:02} {disc} {year})"), "text", "{artist} - {title}"),
        Field("position", N_("Posizione"), "choice", "replace", (
            ("prefix", N_("Prima del nome")), ("suffix", N_("Dopo il nome")), ("replace", N_("Al posto del nome")))),
        Field("separator", N_("Separatore"), "text", "_"),
        Field("skip_if_missing", N_("Se manca un dato lascia il nome com'è"), "bool", True),
        Field("missing", N_("Altrimenti scrivi"), "text", ""),
    ), AudioTags),
    ActionSpec("exif", N_("Metadati EXIF"), (
        Field("template", N_("Modello ({date:%Y-%m-%d_%H%M%S} {make} {model} {width} {height})"), "text", "{date:%Y-%m-%d_%H%M%S}"),
        Field("position", N_("Posizione"), "choice", "replace", (
            ("prefix", N_("Prima del nome")), ("suffix", N_("Dopo il nome")), ("replace", N_("Al posto del nome")))),
        Field("separator", N_("Separatore"), "text", "_"),
        Field("skip_if_missing", N_("Se manca un dato lascia il nome com'è"), "bool", True),
        Field("missing", N_("Altrimenti scrivi"), "text", ""),
    ), ExifTags),
    ActionSpec("names", N_("Nomi da file"), (
        Field("path", N_("File .txt o .csv"), "file", ""),
        Field("with_extension", N_("I nomi includono l'estensione"), "bool", False),
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
            tip = field_tip(spec.key, f.key)
            if f.kind == "bool":
                form.addRow("", w)
                targets = [w]
            else:
                label = QLabel(tr(f.label))
                form.addRow(label, w)
                targets = [label, w, *w.findChildren(QWidget)]  # il campo file contiene un QLineEdit e un pulsante
            if tip:
                for t in targets:
                    t.setToolTip(rich(tip))

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
            w = QCheckBox(tr(f.label))
            w.setChecked(f.default)
            w.toggled.connect(self.changed)
        elif f.kind == "choice":
            w = QComboBox()
            for value, label in f.options:
                w.addItem(tr(label), value)
            w.setCurrentIndex(w.findData(f.default))
            w.currentIndexChanged.connect(self.changed)
        else:  # file
            return self._make_file(f)
        return w

    def _make_file(self, f: Field) -> QWidget:
        box, edit, pick = QWidget(), QLineEdit(f.default), QPushButton(tr("Sfoglia…"))
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(edit)
        row.addWidget(pick)
        edit.textChanged.connect(self.changed)
        pick.clicked.connect(lambda: self._pick(edit))
        box.edit = edit  # type: ignore[attr-defined]
        return box

    def _pick(self, edit: QLineEdit) -> None:
        path, _ = QFileDialog.getOpenFileName(self, tr("Scegli il file"), "", tr("Nomi (*.txt *.csv);;Tutti i file (*)"))
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
            self.error = describe_error(exc)
            return Replace()  # azione neutra finché i parametri non sono validi


def describe_error(exc: Exception) -> str:
    """Errore per l'utente. I messaggi del modulo re sono in inglese: li introduce una frase tradotta."""
    return tr("Espressione regolare non valida: {err}", err=exc) if isinstance(exc, re.error) else str(exc)


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
