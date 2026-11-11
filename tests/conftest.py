"""Fixtures compartidas.

- Sin API_URL: TestClient en proceso, BD limpia por prueba (SQLite en memoria, o PostgreSQL
  si se define TEST_DATABASE_URL). Rápido y con medición de cobertura.
- Con API_URL: las mismas pruebas golpean la API real (contenedor test-runner).
Las claves de prueba se leen del entorno; los valores por defecto solo existen para correr en local.
"""
import os

os.environ.setdefault("JWT_SECRET", "solo-para-pruebas-locales-no-usar-en-produccion")
os.environ.setdefault("DOCENTE_CLAVE", "docente-pruebas")
os.environ.setdefault("ESTUDIANTE_CLAVE", "estudiante-pruebas")
os.environ.setdefault("ESTUDIANTE_ID", "1001")
os.environ.setdefault("DATABASE_URL", os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:"))

import pytest  # noqa: E402
import requests  # noqa: E402

REMOTO = bool(os.getenv("API_URL"))


class ClienteHttp:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def get(self, ruta, **kw):
        return requests.get(self.base_url + ruta, timeout=5, **kw)

    def post(self, ruta, **kw):
        return requests.post(self.base_url + ruta, timeout=5, **kw)


@pytest.fixture
def client():
    if REMOTO:
        yield ClienteHttp(os.environ["API_URL"])
        return
    from fastapi.testclient import TestClient

    from src.app import db
    from src.app.main import app

    db.Base.metadata.drop_all(db.motor)          # BD limpia: el lifespan la recrea y siembra
    with TestClient(app) as cliente:
        yield cliente


def _cabecera(cliente, usuario: str, clave: str) -> dict:
    respuesta = cliente.post("/api/v1/auth/token", json={"usuario": usuario, "clave": clave})
    assert respuesta.status_code == 200, respuesta.text
    return {"Authorization": f"Bearer {respuesta.json()['access_token']}"}


@pytest.fixture
def docente(client) -> dict:
    return _cabecera(client, "docente", os.environ["DOCENTE_CLAVE"])


@pytest.fixture
def estudiante(client) -> dict:
    return _cabecera(client, "estudiante", os.environ["ESTUDIANTE_CLAVE"])


@pytest.fixture
def estudiante_id() -> int:
    return int(os.environ["ESTUDIANTE_ID"])
