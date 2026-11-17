"""Las pruebas sin modelo (API y herramientas) usan los datos de prueba en JSON, aunque el .env tenga DATABASE_URL.
Las de Postgres (test_postgres.py) usan TEST_DATABASE_URL."""
import pytest


@pytest.fixture(autouse=True)
def sin_postgres(request, monkeypatch):
    if request.module.__name__.split(".")[-1] in {"test_api", "test_tools"}:
        monkeypatch.delenv("DATABASE_URL", raising=False)
