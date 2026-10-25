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
    ActionSpec("replace", N_("action.replace_string"), (
        Field("find", N_("field.find"), "text", ""),
        Field("replace", N_("field.replace_with"), "text", ""),
        Field("case_sensitive", N_("field.match_case"), "bool", True),
    ), Replace),
    ActionSpec("extension", N_("action.change_extension"), (
        Field("mode", N_("field.mode"), "choice", "replace", (
            ("replace", N_("option.replace")), ("add", N_("option.add_at_end")), ("remove", N_("option.remove")),
            ("lower", N_("option.lowercase")), ("upper", N_("option.uppercase")))),
        Field("value", N_("field.extension"), "text", ""),
    ), ChangeExtension),
    ActionSpec("case", N_("action.change_case"), (
        Field("mode", N_("field.style"), "choice", "lower", (
            ("lower", N_("option.all_lowercase")), ("upper", N_("option.all_uppercase")),
            ("title", N_("option.title_case")), ("sentence", N_("option.first_letter_uppercase")))),
    ), ChangeCase),
    ActionSpec("enumerate", N_("action.numbering"), (
        Field("start", N_("field.start_at"), "int", 1),
        Field("step", N_("field.step"), "int", 1),
        Field("digits", N_("field.digits"), "int", 3),
        Field("position", N_("field.position"), "choice", "prefix", (
            ("prefix", N_("option.before_name")), ("suffix", N_("option.after_name")), ("replace", N_("option.instead_of_name")))),
        Field("separator", N_("field.separator"), "text", "_"),
        Field("per_folder", N_("field.restart_per_folder"), "bool", True),
    ), Enumerate),
    ActionSpec("insert", N_("action.insert_characters"), (
        Field("text", N_("field.text"), "text", ""),
        Field("position", N_("field.position"), "int", 0),
        Field("from_end", N_("field.count_from_end"), "bool", False),
    ), InsertChars),
    ActionSpec("move", N_("action.move_characters"), (
        Field("start", N_("field.from_position"), "int", 0),
        Field("count", N_("field.how_many"), "int", 1),
        Field("to", N_("field.to_position"), "int", 0),
    ), MoveChars),
    ActionSpec("delete", N_("action.delete_characters"), (
        Field("start", N_("field.from_position"), "int", 0),
        Field("count", N_("field.how_many"), "int", 1),
        Field("from_end", N_("field.count_from_end"), "bool", False),
    ), DeleteChars),
    ActionSpec("random", N_("action.random_name"), (
        Field("length", N_("field.length"), "int", 8),
        Field("seed", N_("field.seed"), "int", 1),
    ), RandomName),
    ActionSpec("regex", N_("action.regular_expression"), (
        Field("pattern", N_("field.pattern"), "text", ""),
        Field("replacement", N_("field.replacement"), "text", ""),
        Field("ignore_case", N_("field.ignore_case"), "bool", False),
        Field("target", N_("field.apply_to"), "choice", "stem", (("stem", N_("option.name_without_extension")), ("full", N_("option.name_with_extension")))),
    ), RegexReplace),
    ActionSpec("datetime", N_("action.date_time"), (
        Field("source", N_("field.date_source"), "choice", "modified", (
            ("modified", N_("option.last_modified")), ("created", N_("option.created")), ("accessed", N_("option.last_accessed")))),
        Field("fmt", N_("field.date_format"), "text", "%Y-%m-%d"),
        Field("position", N_("field.position"), "choice", "prefix", (
            ("prefix", N_("option.before_name")), ("suffix", N_("option.after_name")), ("replace", N_("option.instead_of_name")))),
        Field("separator", N_("field.separator"), "text", "_"),
    ), DateTime),
    ActionSpec("audio", N_("action.audio_tags"), (
        Field("template", N_("field.audio_template"), "text", "{artist} - {title}"),
        Field("position", N_("field.position"), "choice", "replace", (
            ("prefix", N_("option.before_name")), ("suffix", N_("option.after_name")), ("replace", N_("option.instead_of_name")))),
        Field("separator", N_("field.separator"), "text", "_"),
        Field("skip_if_missing", N_("field.keep_name_if_missing"), "bool", True),
        Field("missing", N_("field.otherwise_write"), "text", ""),
    ), AudioTags),
    ActionSpec("exif", N_("action.exif_metadata"), (
        Field("template", N_("field.exif_template"), "text", "{date:%Y-%m-%d_%H%M%S}"),
        Field("position", N_("field.position"), "choice", "replace", (
            ("prefix", N_("option.before_name")), ("suffix", N_("option.after_name")), ("replace", N_("option.instead_of_name")))),
        Field("separator", N_("field.separator"), "text", "_"),
        Field("skip_if_missing", N_("field.keep_name_if_missing"), "bool", True),
        Field("missing", N_("field.otherwise_write"), "text", ""),
    ), ExifTags),
    ActionSpec("names", N_("action.names_from_file"), (
        Field("path", N_("field.names_file"), "file", ""),
        Field("with_extension", N_("field.names_include_extension"), "bool", False),
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
        box, edit, pick = QWidget(), QLineEdit(f.default), QPushButton(tr("button.browse"))
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(edit)
        row.addWidget(pick)
        edit.textChanged.connect(self.changed)
        pick.clicked.connect(lambda: self._pick(edit))
        box.edit = edit  # type: ignore[attr-defined]
        return box

    def _pick(self, edit: QLineEdit) -> None:
        path, _ = QFileDialog.getOpenFileName(self, tr("dialog.choose_names_file"), "", tr("dialog.names_file_filter"))
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
    return tr("error.invalid_regex", err=exc) if isinstance(exc, re.error) else str(exc)


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
