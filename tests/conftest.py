import pytest

from nameforge import i18n


@pytest.fixture(autouse=True)
def isolated_app_data(tmp_path, monkeypatch):
    """Nessun test deve scrivere impostazioni, profili o manifest nella cartella dati reale dell'utente."""
    monkeypatch.setattr("nameforge.mainwindow._app_data", lambda: tmp_path / "appdata")


@pytest.fixture(autouse=True)
def italian():
    """I test confrontano testi italiani (lingua sorgente): ogni test parte e finisce in italiano."""
    i18n.set_language("it")
    yield
    i18n.set_language("it")
