"""Semana 5: estado HTTP, cabeceras y contrato JSON Schema."""
from jsonschema import validate

CALIFICACION_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "integer"},
        "estudiante_id": {"type": "integer"},
        "asignatura": {"type": "string"},
        "corte1": {"type": "number"},
        "corte2": {"type": "number"},
        "corte3": {"type": "number"},
        "definitiva": {"type": "number", "minimum": 0, "maximum": 5},
        "estado": {"enum": ["REPROBADO", "APROBADO", "EXCELENTE"]},
    },
    "required": ["id", "estudiante_id", "asignatura", "definitiva", "estado"],
}

VALIDA = {"estudiante_id": 1001, "asignatura": "Pruebas", "corte1": 2.0, "corte2": 2.5, "corte3": 4.0}


def test_health_200_y_json(client):
    respuesta = client.get("/health")
    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("application/json")
    assert respuesta.json()["status"] == "ok"


def test_crear_calificacion_201_cumple_contrato(client):
    respuesta = client.post("/api/v1/calificaciones", json=VALIDA)
    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    validate(instance=cuerpo, schema=CALIFICACION_SCHEMA)
    assert cuerpo["definitiva"] == 3.0 and cuerpo["estado"] == "APROBADO"


def test_listar_cumple_contrato(client):
    client.post("/api/v1/calificaciones", json=VALIDA)
    respuesta = client.get("/api/v1/calificaciones")
    assert respuesta.status_code == 200
    for item in respuesta.json():
        validate(instance=item, schema=CALIFICACION_SCHEMA)


def test_obtener_por_id_200(client):
    creada = client.post("/api/v1/calificaciones", json=VALIDA).json()
    assert client.get(f"/api/v1/calificaciones/{creada['id']}").status_code == 200


def test_nota_fuera_de_rango_400(client):
    respuesta = client.post("/api/v1/calificaciones", json={**VALIDA, "corte3": 5.1})
    assert respuesta.status_code == 400


def test_calificacion_inexistente_404(client):
    assert client.get("/api/v1/calificaciones/999999").status_code == 404


def test_metrics_expone_contadores(client):
    client.get("/health")
    assert "notasqa_http_requests_total" in client.get("/metrics").text
