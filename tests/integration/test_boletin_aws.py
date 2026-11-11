"""Semana 10 + Frente 3: S3/SQS con moto (sin Docker ni cuentas), DLQ y worker asíncrono."""
import json

import pytest
from moto import mock_aws

from infra.init_infra import aprovisionar
from src.app import storage
from src.worker.notificador import procesar_lote

pytestmark = pytest.mark.skipif(__import__("tests.conftest").conftest.REMOTO,
                                reason="usa moto en proceso")

NOTA = {"estudiante_id": 7, "asignatura": "Pruebas", "corte1": 4.0, "corte2": 4.0, "corte3": 4.0, "creditos": 3}


@pytest.fixture
def aws(monkeypatch):
    monkeypatch.delenv("AWS_ENDPOINT_URL", raising=False)
    with mock_aws():
        aprovisionar()
        yield storage.cliente("sqs")


def _sin_espera(sqs):
    """Visibilidad 0 para que los reintentos ocurran de inmediato en la prueba."""
    sqs.set_queue_attributes(QueueUrl=storage.url_cola(), Attributes={"VisibilityTimeout": "0"})


def test_aprovisionar_es_idempotente(aws):
    assert aprovisionar() == aprovisionar()


def test_cola_tiene_politica_de_dlq(aws):
    atributos = aws.get_queue_attributes(QueueUrl=storage.url_cola(), AttributeNames=["RedrivePolicy"])
    politica = json.loads(atributos["Attributes"]["RedrivePolicy"])
    assert politica["maxReceiveCount"] in (3, "3")
    assert politica["deadLetterTargetArn"].endswith(storage.COLA_DLQ)


def test_boletin_se_guarda_en_s3_y_el_worker_lo_notifica(aws, client, docente):
    creada = client.post("/api/v1/calificaciones", json=NOTA, headers=docente).json()

    respuesta = client.post(f"/api/v1/calificaciones/{creada['id']}/boletin", headers=docente)

    assert respuesta.status_code == 201
    assert storage.leer_boletin(respuesta.json()["s3_key"])["definitiva"] == 4.0
    enviados = []
    assert procesar_lote(enviar=enviados.append, espera=0) == {"procesados": 1, "fallidos": 0}
    assert "APROBADO" in enviados[0]
    assert aws.receive_message(QueueUrl=storage.url_cola()).get("Messages") is None   # se borró


def test_mensaje_corrupto_termina_en_dlq(aws):
    _sin_espera(aws)
    aws.send_message(QueueUrl=storage.url_cola(), MessageBody="esto-no-es-json")
    for _ in range(4):                                  # 3 intentos fallidos + 1 que ya no lo ve
        procesar_lote(enviar=lambda texto: None, espera=0)
    en_dlq = aws.receive_message(QueueUrl=storage.url_cola(storage.COLA_DLQ))["Messages"]
    assert en_dlq[0]["Body"] == "esto-no-es-json"


def test_evento_desconocido_no_se_borra(aws):
    aws.send_message(QueueUrl=storage.url_cola(), MessageBody=json.dumps({"evento": "otro"}))
    assert procesar_lote(enviar=lambda texto: None, espera=0) == {"procesados": 0, "fallidos": 1}


def test_fallo_de_notificacion_se_reintenta(aws, client, docente):
    import requests

    creada = client.post("/api/v1/calificaciones", json=NOTA, headers=docente).json()
    client.post(f"/api/v1/calificaciones/{creada['id']}/boletin", headers=docente)

    def telegram_caido(texto):
        raise requests.ConnectionError("Telegram no responde")

    assert procesar_lote(enviar=telegram_caido, espera=0) == {"procesados": 0, "fallidos": 1}


def test_boletin_sin_infraestructura_responde_503(monkeypatch, client, docente):
    monkeypatch.delenv("AWS_ENDPOINT_URL", raising=False)
    with mock_aws():                                    # nube vacía: sin bucket ni cola
        creada = client.post("/api/v1/calificaciones", json=NOTA, headers=docente).json()
        respuesta = client.post(f"/api/v1/calificaciones/{creada['id']}/boletin", headers=docente)
    assert respuesta.status_code == 503
