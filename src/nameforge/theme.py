from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPalette
from PySide6.QtWidgets import QApplication, QStyle

ACCENT = "#4f6bed"

# palette(...) nel QSS segue i colori sotto: chiaro/scuro condividono lo stesso foglio di stile.
def _qss(dark: bool) -> str:
    muted = "#a3aab8" if dark else "#59606e"  # testo secondario: contrasto sufficiente su entrambi i temi
    return f"""
QPushButton {{ padding: 6px 14px; border: 1px solid palette(mid); border-radius: 6px; background: palette(button); }}
QPushButton:hover:enabled {{ border-color: palette(highlight); }}
QPushButton:disabled {{ color: {muted}; }}
QPushButton#primary {{ background: palette(highlight); color: palette(highlighted-text); border: none; font-weight: 600; padding: 6px 20px; }}
QPushButton#primary:disabled {{ background: palette(alternate-base); color: {muted}; border: 1px solid palette(mid); }}
QLineEdit {{ padding: 4px 8px; border: 1px solid palette(mid); border-radius: 5px; }}
QLineEdit:focus {{ border-color: palette(highlight); }}
QTabWidget::pane {{ border: 1px solid palette(mid); border-radius: 6px; top: -1px; }}
QTabBar::tab {{ padding: 9px 22px; margin-right: 2px; border: none; border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ font-weight: 600; border-bottom: 2px solid palette(highlight); }}
QTabBar::tab:hover:!selected {{ border-bottom: 2px solid palette(mid); }}
QTableView {{ border: 1px solid palette(mid); border-radius: 6px; gridline-color: transparent;
  alternate-background-color: palette(alternate-base); selection-background-color: palette(highlight);
  selection-color: palette(highlighted-text); }}
QTableView::item {{ padding: 3px 6px; }}
QHeaderView::section {{ padding: 7px 8px; border: none; border-bottom: 1px solid palette(mid); border-right: 1px solid palette(mid);
  background: palette(window); font-weight: 600; }}
QHeaderView::section:last {{ border-right: none; }}
QListWidget {{ border: 1px solid palette(mid); border-radius: 6px; padding: 4px; }}
QListWidget::item {{ padding: 0 8px; border-radius: 4px; }}
QListWidget::item:selected {{ background: palette(highlight); color: palette(highlighted-text); }}
QLabel#heading {{ font-size: 15px; font-weight: 600; padding-bottom: 4px; }}
QLabel#empty {{ border: 2px dashed palette(mid); border-radius: 10px; color: {muted}; font-size: 15px; }}
QLabel#hint {{ color: {muted}; }}
QStatusBar {{ border-top: 1px solid palette(mid); }}
"""


def _palette(dark: bool) -> QPalette:
    c = QColor
    colors = {
        QPalette.Window: "#1e2128" if dark else "#f4f5f7",
        QPalette.WindowText: "#e6e8ec" if dark else "#1f2430",
        QPalette.Base: "#252a33" if dark else "#ffffff",
        QPalette.AlternateBase: "#2b313b" if dark else "#f1f3f7",
        QPalette.Text: "#e6e8ec" if dark else "#1f2430",
        QPalette.Button: "#2f3541" if dark else "#ffffff",
        QPalette.ButtonText: "#e6e8ec" if dark else "#1f2430",
        QPalette.Mid: "#4a5160" if dark else "#c5cad3",
        QPalette.Highlight: ACCENT,
        QPalette.HighlightedText: "#ffffff",
        QPalette.ToolTipBase: "#2f3541" if dark else "#ffffff",
        QPalette.ToolTipText: "#e6e8ec" if dark else "#1f2430",
        QPalette.PlaceholderText: "#a3aab8" if dark else "#59606e",
    }
    p = QPalette()
    for role, value in colors.items():
        p.setColor(role, c(value))
    p.setColor(QPalette.Disabled, QPalette.Text, c("#8b93a3" if dark else "#6b7280"))
    p.setColor(QPalette.Disabled, QPalette.ButtonText, c("#8b93a3" if dark else "#6b7280"))
    return p


def apply_theme(app: QApplication) -> None:
    """Fusion come base; palette chiara o scura secondo il sistema (Qt >= 6.5), aggiornata al cambio."""
    app.setStyle("Fusion")

    def update() -> None:
        dark = getattr(app.styleHints(), "colorScheme", lambda: None)() == Qt.ColorScheme.Dark
        app.setPalette(_palette(dark))
        app.setStyleSheet(_qss(dark))

    hints = app.styleHints()
    if hasattr(hints, "colorSchemeChanged"):
        hints.colorSchemeChanged.connect(lambda *_: update())
    update()


def icon(theme_name: str, fallback: QStyle.StandardPixmap) -> QIcon:
    """Icona del tema di sistema (Linux); altrove quella standard dello stile."""
    return QIcon.fromTheme(theme_name, QApplication.style().standardIcon(fallback))
