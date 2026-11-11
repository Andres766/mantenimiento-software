"""API REST de NotasQA."""
import json
import logging
import os
import time

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import FastAPI, HTTPException, Request, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel

from src.app import storage
from src.notas.reglas import calcular_definitiva, clasificar_nota

APP_VERSION = os.getenv("APP_VERSION", "1.0.0")

app = FastAPI(title="NotasQA", version=APP_VERSION)
log = logging.getLogger("notasqa")
logging.basicConfig(level=logging.INFO, format="%(message)s")

PETICIONES = Counter("notasqa_http_requests_total", "Peticiones HTTP", ["metodo", "ruta", "estado"])
LATENCIA = Histogram("notasqa_http_request_seconds", "Latencia HTTP", ["ruta"])

CALIFICACIONES: dict[int, dict] = {}  # repositorio en memoria


class CalificacionIn(BaseModel):
    estudiante_id: int
    asignatura: str
    corte1: float
    corte2: float
    corte3: float


@app.middleware("http")
async def observabilidad(request: Request, call_next):
    inicio = time.perf_counter()
    respuesta = await call_next(request)
    ruta = request.scope.get("route").path if request.scope.get("route") else request.url.path
    duracion = time.perf_counter() - inicio
    PETICIONES.labels(request.method, ruta, respuesta.status_code).inc()
    LATENCIA.labels(ruta).observe(duracion)
    log.info(json.dumps({"metodo": request.method, "ruta": ruta,
                         "estado": respuesta.status_code, "ms": round(duracion * 1000, 2)}))
    return respuesta


@app.get("/health")
def health(response: Response):
    # FORZAR_FALLO=1 simula un despliegue defectuoso (demo de rollback, semana 9)
    if os.getenv("FORZAR_FALLO") == "1":
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"status": "unhealthy", "version": APP_VERSION}
    return {"status": "ok", "service": "notasqa-api", "version": APP_VERSION}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/api/v1/calificaciones", status_code=status.HTTP_201_CREATED)
def crear_calificacion(datos: CalificacionIn):
    try:
        definitiva = calcular_definitiva(datos.corte1, datos.corte2, datos.corte3)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    nuevo_id = len(CALIFICACIONES) + 1
    registro = {"id": nuevo_id, **datos.model_dump(), "definitiva": definitiva,
                "estado": clasificar_nota(definitiva)}
    CALIFICACIONES[nuevo_id] = registro
    return registro


@app.get("/api/v1/calificaciones")
def listar_calificaciones():
    return list(CALIFICACIONES.values())


@app.get("/api/v1/calificaciones/{calificacion_id}")
def obtener_calificacion(calificacion_id: int):
    registro = CALIFICACIONES.get(calificacion_id)
    if registro is None:
        raise HTTPException(status_code=404, detail="Calificación no encontrada")
    return registro


@app.post("/api/v1/calificaciones/{calificacion_id}/boletin", status_code=status.HTTP_201_CREATED)
def generar_boletin(calificacion_id: int):
    registro = obtener_calificacion(calificacion_id)
    try:
        return {"s3_key": storage.publicar_boletin(registro)}
    except (BotoCoreError, ClientError) as error:
        log.error(json.dumps({"evento": "fallo_almacenamiento", "detalle": str(error)}))
        raise HTTPException(status_code=503, detail="Almacenamiento no disponible") from error
