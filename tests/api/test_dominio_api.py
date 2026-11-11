"""Frente 1 a través de la API: habilitación y promedio del semestre."""
import random

NOTA_BAJA = {"estudiante_id": 3003, "asignatura": "Física", "corte1": 2.5, "corte2": 2.5, "corte3": 2.5, "creditos": 4}


def _crear(client, docente, **cambios):
    return client.post("/api/v1/calificaciones", json={**NOTA_BAJA, **cambios}, headers=docente).json()


def test_habilitacion_aprobada_deja_tres(client, docente):
    nota = _crear(client, docente)
    respuesta = client.post(f"/api/v1/calificaciones/{nota['id']}/habilitacion", json={"nota": 4.2}, headers=docente)
    assert respuesta.status_code == 200
    assert respuesta.json()["definitiva"] == 3.0
    assert respuesta.json()["estado"] == "APROBADO"
    assert respuesta.json()["habilitacion"] == 4.2


def test_habilitacion_reprobada_conserva_la_mayor(client, docente):
    nota = _crear(client, docente)
    respuesta = client.post(f"/api/v1/calificaciones/{nota['id']}/habilitacion", json={"nota": 2.7}, headers=docente)
    assert respuesta.json()["definitiva"] == 2.7
    assert respuesta.json()["estado"] == "REPROBADO"


def test_no_se_habilita_dos_veces_409(client, docente):
    nota = _crear(client, docente)
    ruta = f"/api/v1/calificaciones/{nota['id']}/habilitacion"
    client.post(ruta, json={"nota": 2.6}, headers=docente)
    assert client.post(ruta, json={"nota": 4.0}, headers=docente).status_code == 409


def test_no_habilita_si_ya_aprobo_409(client, docente):
    nota = _crear(client, docente, corte1=4.0, corte2=4.0, corte3=4.0)
    respuesta = client.post(f"/api/v1/calificaciones/{nota['id']}/habilitacion", json={"nota": 5.0}, headers=docente)
    assert respuesta.status_code == 409


def test_habilitacion_con_nota_invalida_400(client, docente):
    nota = _crear(client, docente)
    respuesta = client.post(f"/api/v1/calificaciones/{nota['id']}/habilitacion", json={"nota": 6}, headers=docente)
    assert respuesta.status_code == 400


def test_promedio_ponderado_por_creditos(client, docente):
    est = random.randint(100_000, 899_999)  # id único: la prueba es repetible contra una BD compartida
    _crear(client, docente, estudiante_id=est, corte1=4.0, corte2=4.0, corte3=4.0, creditos=4)
    _crear(client, docente, estudiante_id=est, corte1=3.0, corte2=3.0, corte3=3.0, creditos=3)
    _crear(client, docente, estudiante_id=est, corte1=2.0, corte2=2.0, corte3=2.0, creditos=1)
    respuesta = client.get(f"/api/v1/estudiantes/{est}/promedio", headers=docente)
    assert respuesta.status_code == 200
    # (4.0*4 + 3.0*3 + 2.0*1) / 8 = 3.375 -> 3.38
    assert respuesta.json() == {"estudiante_id": est, "materias": 3, "creditos": 8, "promedio": 3.38}


def test_promedio_sin_notas_404(client, docente):
    assert client.get("/api/v1/estudiantes/999999/promedio", headers=docente).status_code == 404
