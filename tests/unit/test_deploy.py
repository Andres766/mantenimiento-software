"""Semana 9: la lógica de promoción/rollback también se prueba (sin red: se simula requests)."""
from unittest.mock import MagicMock

import requests

from scripts import deploy


def _servidor(health=200, ui=200, protegida=401):
    codigos = {"/health": health, "/ui/": ui, "/api/v1/calificaciones": protegida}

    def get(url, **_):
        ruta = "/" + url.split("/", 3)[3]
        return MagicMock(status_code=codigos[ruta])
    return get


def test_staging_sano_queda_listo(monkeypatch):
    monkeypatch.setattr(deploy.requests, "get", _servidor())
    assert deploy.main([]) == 0


def test_staging_500_dispara_rollback(monkeypatch):
    monkeypatch.setattr(deploy.requests, "get", _servidor(health=500))
    assert deploy.main([]) == 1


def test_api_sin_seguridad_dispara_rollback(monkeypatch):
    # Si la ruta protegida responde 200 sin token, el despliegue rompió la autenticación
    monkeypatch.setattr(deploy.requests, "get", _servidor(protegida=200))
    assert deploy.main([]) == 1


def test_staging_caido_dispara_rollback(monkeypatch):
    def caido(*a, **k):
        raise requests.ConnectionError("sin conexión")
    monkeypatch.setattr(deploy.requests, "get", caido)
    assert deploy.main([]) == 1


def test_telegram_usa_secretos_de_entorno(monkeypatch):
    enviado = {}
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "c")
    monkeypatch.setattr(deploy.requests, "post", lambda url, **k: enviado.update(url=url, **k))
    assert deploy.main(["--notificar", "hola"]) == 0
    assert enviado["json"] == {"chat_id": "c", "text": "hola"} and "bott/" in enviado["url"]


def test_telegram_caido_no_rompe_el_despliegue(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "c")

    def falla(*a, **k):
        raise requests.Timeout("lento")
    monkeypatch.setattr(deploy.requests, "post", falla)
    deploy.notificar_telegram("hola")      # no lanza excepción
