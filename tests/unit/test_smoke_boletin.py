"""El script E2E del CI también se prueba: simula las respuestas HTTP con un doble de prueba."""
import io
import json

from scripts import smoke_boletin


class RespuestaFalsa(io.BytesIO):
    def __init__(self, status, cuerpo):
        super().__init__(json.dumps(cuerpo).encode())
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _servidor(respuestas):
    cola = list(respuestas)
    return lambda peticion, timeout: cola.pop(0)


def test_flujo_completo_exitoso(monkeypatch):
    monkeypatch.setattr(smoke_boletin.urllib.request, "urlopen", _servidor([
        RespuestaFalsa(201, {"id": 1, "definitiva": 4.6, "estado": "EXCELENTE"}),
        RespuestaFalsa(201, {"s3_key": "boletines/2026/1.json"}),
    ]))
    assert smoke_boletin.main("http://api") == 0


def test_estado_incorrecto_falla(monkeypatch):
    monkeypatch.setattr(smoke_boletin.urllib.request, "urlopen", _servidor([
        RespuestaFalsa(201, {"id": 1, "definitiva": 4.5, "estado": "APROBADO"}),
    ]))
    assert smoke_boletin.main("http://api") == 1


def test_boletin_sin_llave_falla(monkeypatch):
    monkeypatch.setattr(smoke_boletin.urllib.request, "urlopen", _servidor([
        RespuestaFalsa(201, {"id": 1, "definitiva": 4.6, "estado": "EXCELENTE"}),
        RespuestaFalsa(201, {}),
    ]))
    assert smoke_boletin.main("http://api") == 1
