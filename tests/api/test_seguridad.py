"""Frente 2: autenticación (401), autorización por rol (403) y propiedad de los datos."""
import os
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from tests.conftest import REMOTO

NOTA = {"estudiante_id": 1001, "asignatura": "Pruebas", "corte1": 4.0, "corte2": 4.0, "corte3": 4.0, "creditos": 3}
AJENA = {**NOTA, "estudiante_id": 2002, "asignatura": "Cálculo"}


def test_login_correcto_devuelve_token_y_rol(client):
    respuesta = client.post("/api/v1/auth/token",
                            json={"usuario": "docente", "clave": os.environ["DOCENTE_CLAVE"]})
    assert respuesta.status_code == 200
    assert respuesta.json()["rol"] == "docente"
    assert respuesta.json()["token_type"] == "bearer"


@pytest.mark.parametrize("usuario, clave", [("docente", "clave-mala"), ("nadie", "x"), ("", "")])
def test_login_incorrecto_401(client, usuario, clave):
    assert client.post("/api/v1/auth/token", json={"usuario": usuario, "clave": clave}).status_code == 401


def test_sin_token_401(client):
    respuesta = client.get("/api/v1/calificaciones")
    assert respuesta.status_code == 401
    assert respuesta.headers["www-authenticate"] == "Bearer"


def test_token_alterado_401(client, docente):
    alterado = {"Authorization": docente["Authorization"][:-2] + "xx"}
    assert client.get("/api/v1/calificaciones", headers=alterado).status_code == 401


@pytest.mark.skipif(REMOTO, reason="requiere conocer el secreto del servidor")
def test_token_expirado_401(client):
    vencido = jwt.encode({"sub": "1", "rol": "docente", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
                         os.environ["JWT_SECRET"], algorithm="HS256")
    respuesta = client.get("/api/v1/calificaciones", headers={"Authorization": f"Bearer {vencido}"})
    assert respuesta.status_code == 401
    assert respuesta.json()["detail"] == "Token expirado"


@pytest.mark.skipif(REMOTO, reason="requiere conocer el secreto del servidor")
def test_token_firmado_con_otro_secreto_401(client):
    falso = jwt.encode({"sub": "1", "rol": "docente"}, "secreto-del-atacante-0123456789abcdef", algorithm="HS256")
    assert client.get("/api/v1/calificaciones", headers={"Authorization": f"Bearer {falso}"}).status_code == 401


def test_estudiante_no_puede_registrar_notas_403(client, estudiante):
    assert client.post("/api/v1/calificaciones", json=NOTA, headers=estudiante).status_code == 403


def test_estudiante_no_puede_generar_boletin_403(client, docente, estudiante):
    creada = client.post("/api/v1/calificaciones", json=NOTA, headers=docente).json()
    assert client.post(f"/api/v1/calificaciones/{creada['id']}/boletin", headers=estudiante).status_code == 403


def test_estudiante_solo_ve_sus_notas(client, docente, estudiante, estudiante_id):
    client.post("/api/v1/calificaciones", json=NOTA, headers=docente)
    client.post("/api/v1/calificaciones", json=AJENA, headers=docente)
    notas = client.get("/api/v1/calificaciones", headers=estudiante).json()
    assert notas and all(n["estudiante_id"] == estudiante_id for n in notas)


def test_estudiante_no_ve_nota_ajena_403(client, docente, estudiante):
    ajena = client.post("/api/v1/calificaciones", json=AJENA, headers=docente).json()
    assert client.get(f"/api/v1/calificaciones/{ajena['id']}", headers=estudiante).status_code == 403


def test_estudiante_no_ve_promedio_ajeno_403(client, estudiante):
    assert client.get("/api/v1/estudiantes/2002/promedio", headers=estudiante).status_code == 403


def test_estudiante_ve_su_promedio(client, docente, estudiante, estudiante_id):
    client.post("/api/v1/calificaciones", json=NOTA, headers=docente)
    respuesta = client.get(f"/api/v1/estudiantes/{estudiante_id}/promedio", headers=estudiante)
    assert respuesta.status_code == 200
