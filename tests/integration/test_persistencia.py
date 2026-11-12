"""Frente 1: los datos sobreviven fuera de la petición (SQLite en local, PostgreSQL en CI)."""
import pytest
from sqlalchemy import select

from src.app import db
from src.app.seguridad import hashear_clave, verificar_clave
from tests.conftest import REMOTO

pytestmark = pytest.mark.skipif(REMOTO, reason="consulta la BD directamente")


def test_calificacion_queda_persistida(client, docente):
    creada = client.post("/api/v1/calificaciones", json={
        "estudiante_id": 55, "asignatura": "Bases de datos", "corte1": 3.5, "corte2": 4.0,
        "corte3": 4.5, "creditos": 2}, headers=docente).json()

    with db.SesionLocal() as sesion:                     # sesión nueva, independiente de la API
        guardada = sesion.get(db.Calificacion, creada["id"])

    assert guardada.a_dict() == creada


def test_claves_se_guardan_con_hash(client):
    with db.SesionLocal() as sesion:
        usuarios = sesion.scalars(select(db.Usuario)).all()
    assert {u.usuario for u in usuarios} == {"docente", "estudiante"}
    for usuario in usuarios:
        assert "pruebas" not in usuario.clave_hash          # nunca en texto plano


def test_hash_con_sal_distinta_cada_vez():
    primero, segundo = hashear_clave("misma-clave"), hashear_clave("misma-clave")
    assert primero != segundo
    assert verificar_clave("misma-clave", primero) and not verificar_clave("otra", primero)


def test_motor_en_uso():
    print(f"\nBase de datos de la prueba: {db.motor.dialect.name}")
    assert db.motor.dialect.name in {"sqlite", "postgresql"}


def test_inicializar_reintenta_si_la_bd_no_responde(monkeypatch):
    llamadas = []

    def create_all_inestable(motor):
        llamadas.append(motor)
        if len(llamadas) < 3:
            raise db.OperationalError("SELECT 1", {}, Exception("failed to resolve host 'db'"))

    monkeypatch.setattr(db.Base.metadata, "create_all", create_all_inestable)
    db.inicializar(lambda sesion: None, espera=0)
    assert len(llamadas) == 3


def test_inicializar_se_rinde_tras_agotar_intentos(monkeypatch):
    def create_all_caido(motor):
        raise db.OperationalError("SELECT 1", {}, Exception("BD caída"))

    monkeypatch.setattr(db.Base.metadata, "create_all", create_all_caido)
    with pytest.raises(db.OperationalError):
        db.inicializar(lambda sesion: None, intentos=2, espera=0)
