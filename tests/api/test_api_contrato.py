"""Semana 5: estado HTTP, cabeceras y contrato JSON Schema."""
from jsonschema import validate

CALIFICACION_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "integer"},
        "estudiante_id": {"type": "integer"},
        "asignatura": {"type": "string"},
        "creditos": {"type": "integer", "minimum": 1, "maximum": 10},
        "corte1": {"type": "number"},
        "corte2": {"type": "number"},
        "corte3": {"type": "number"},
        "definitiva": {"type": "number", "minimum": 0, "maximum": 5},
        "estado": {"enum": ["REPROBADO", "APROBADO", "EXCELENTE"]},
        "habilitacion": {"type": ["number", "null"]},
    },
    "required": ["id", "estudiante_id", "asignatura", "creditos", "definitiva", "estado", "habilitacion"],
    "additionalProperties": False,
}

VALIDA = {"estudiante_id": 1001, "asignatura": "Pruebas", "corte1": 2.0, "corte2": 2.5, "corte3": 4.0,
          "creditos": 3}


def test_health_200_y_json(client):
    respuesta = client.get("/health")
    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("application/json")
    assert respuesta.json()["status"] == "ok"


def test_crear_calificacion_201_cumple_contrato(client, docente):
    respuesta = client.post("/api/v1/calificaciones", json=VALIDA, headers=docente)
    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    validate(instance=cuerpo, schema=CALIFICACION_SCHEMA)
    assert cuerpo["definitiva"] == 3.0 and cuerpo["estado"] == "APROBADO"


def test_listar_cumple_contrato(client, docente):
    client.post("/api/v1/calificaciones", json=VALIDA, headers=docente)
    respuesta = client.get("/api/v1/calificaciones", headers=docente)
    assert respuesta.status_code == 200
    assert len(respuesta.json()) >= 1
    for item in respuesta.json():
        validate(instance=item, schema=CALIFICACION_SCHEMA)


def test_listar_esta_paginado(client, docente):
    for _ in range(3):
        client.post("/api/v1/calificaciones", json=VALIDA, headers=docente)
    pagina1 = client.get("/api/v1/calificaciones?limite=2", headers=docente).json()
    pagina2 = client.get("/api/v1/calificaciones?limite=2&desde=1", headers=docente).json()
    assert len(pagina1) == 2 and len(pagina2) == 2
    assert pagina1[1]["id"] == pagina2[0]["id"]              # desde=1 empieza en el segundo


def test_listar_muestra_primero_la_mas_reciente(client, docente):
    creada = client.post("/api/v1/calificaciones", json=VALIDA, headers=docente).json()
    primera = client.get("/api/v1/calificaciones?limite=1", headers=docente).json()
    assert primera[0]["id"] == creada["id"]


def test_limite_fuera_de_rango_422(client, docente):
    assert client.get("/api/v1/calificaciones?limite=0", headers=docente).status_code == 422
    assert client.get("/api/v1/calificaciones?limite=501", headers=docente).status_code == 422


def test_obtener_por_id_200(client, docente):
    creada = client.post("/api/v1/calificaciones", json=VALIDA, headers=docente).json()
    respuesta = client.get(f"/api/v1/calificaciones/{creada['id']}", headers=docente)
    assert respuesta.status_code == 200
    assert respuesta.json() == creada


def test_nota_fuera_de_rango_400(client, docente):
    respuesta = client.post("/api/v1/calificaciones", json={**VALIDA, "corte3": 5.1}, headers=docente)
    assert respuesta.status_code == 400


def test_creditos_fuera_de_rango_400(client, docente):
    respuesta = client.post("/api/v1/calificaciones", json={**VALIDA, "creditos": 11}, headers=docente)
    assert respuesta.status_code == 400


def test_calificacion_inexistente_404(client, docente):
    assert client.get("/api/v1/calificaciones/999999", headers=docente).status_code == 404


def test_metrics_expone_contadores(client):
    client.get("/health")
    assert "notasqa_http_requests_total" in client.get("/metrics").text


def test_interfaz_web_se_sirve(client):
    respuesta = client.get("/ui/")
    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("text/html")
