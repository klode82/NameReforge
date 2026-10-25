import pytest


@pytest.fixture(autouse=True)
def isolated_app_data(tmp_path, monkeypatch):
    """Nessun test deve scrivere impostazioni, profili o manifest nella cartella dati reale dell'utente."""
    monkeypatch.setattr("nameforge.mainwindow._app_data", lambda: tmp_path / "appdata")
