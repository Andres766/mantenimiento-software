"""Semana 9: la lógica de promoción/rollback también se prueba (sin red: se simula requests)."""
from unittest.mock import MagicMock

import requests

from scripts import deploy


def _respuesta(codigo):
    return MagicMock(status_code=codigo)


def test_staging_sano_promueve(monkeypatch):
    monkeypatch.setattr(deploy.requests, "get", lambda *a, **k: _respuesta(200))
    assert deploy.main() == 0


def test_staging_500_dispara_rollback(monkeypatch):
    monkeypatch.setattr(deploy.requests, "get", lambda *a, **k: _respuesta(500))
    assert deploy.main() == 1


def test_staging_caido_dispara_rollback(monkeypatch):
    def caido(*a, **k):
        raise requests.ConnectionError("sin conexión")
    monkeypatch.setattr(deploy.requests, "get", caido)
    assert deploy.main() == 1


def test_telegram_usa_secretos_de_entorno(monkeypatch):
    enviado = {}
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "c")
    monkeypatch.setattr(deploy.requests, "post", lambda url, **k: enviado.update(url=url, **k))
    deploy.notificar_telegram("hola")
    assert enviado["json"]["chat_id"] == "c" and "bott/" in enviado["url"]
