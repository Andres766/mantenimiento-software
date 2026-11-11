"""Semana 10: la integración con S3/SQS se prueba con moto en CI (sin Docker ni cuentas)
y con LocalStack en docker compose."""
import json

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

from infra.init_infra import aprovisionar
from src.app import storage
from src.app.main import CALIFICACIONES, app


@pytest.fixture
def aws(monkeypatch):
    monkeypatch.delenv("AWS_ENDPOINT_URL", raising=False)
    with mock_aws():
        aprovisionar()
        yield


def test_aprovisionar_es_idempotente(aws):
    primera = aprovisionar()
    segunda = aprovisionar()
    assert primera == segunda


def test_boletin_se_guarda_en_s3_y_emite_evento(aws):
    CALIFICACIONES.clear()
    cliente = TestClient(app)
    creada = cliente.post("/api/v1/calificaciones", json={
        "estudiante_id": 7, "asignatura": "Pruebas", "corte1": 4.0, "corte2": 4.0, "corte3": 4.0}).json()

    respuesta = cliente.post(f"/api/v1/calificaciones/{creada['id']}/boletin")

    assert respuesta.status_code == 201
    llave = respuesta.json()["s3_key"]
    s3 = boto3.client("s3", region_name="us-east-1")
    assert json.loads(s3.get_object(Bucket=storage.BUCKET, Key=llave)["Body"].read())["definitiva"] == 4.0
    sqs = boto3.client("sqs", region_name="us-east-1")
    url = sqs.get_queue_url(QueueName=storage.COLA)["QueueUrl"]
    mensaje = sqs.receive_message(QueueUrl=url)["Messages"][0]
    assert json.loads(mensaje["Body"])["evento"] == "boletin_generado"


def test_boletin_sin_infraestructura_responde_503(monkeypatch):
    # Arrange: la "nube" no existe (bucket y cola sin aprovisionar)
    monkeypatch.delenv("AWS_ENDPOINT_URL", raising=False)
    with mock_aws():
        CALIFICACIONES.clear()
        cliente = TestClient(app)
        creada = cliente.post("/api/v1/calificaciones", json={
            "estudiante_id": 8, "asignatura": "Pruebas", "corte1": 3.0, "corte2": 3.0, "corte3": 3.0}).json()
        # Act
        respuesta = cliente.post(f"/api/v1/calificaciones/{creada['id']}/boletin")
    # Assert: error controlado, no un 500 sin manejar
    assert respuesta.status_code == 503
