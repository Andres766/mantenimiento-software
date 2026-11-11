"""Si existe API_URL las pruebas golpean la API real (contenedor test-runner);
si no, usan TestClient en proceso (rápido y con medición de cobertura en CI)."""
import os

import pytest
import requests


class ClienteHttp:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def get(self, ruta, **kw):
        return requests.get(self.base_url + ruta, timeout=5, **kw)

    def post(self, ruta, **kw):
        return requests.post(self.base_url + ruta, timeout=5, **kw)


@pytest.fixture
def client():
    api_url = os.getenv("API_URL")
    if api_url:
        yield ClienteHttp(api_url)
        return
    from fastapi.testclient import TestClient

    from src.app.main import CALIFICACIONES, app

    CALIFICACIONES.clear()
    yield TestClient(app)
