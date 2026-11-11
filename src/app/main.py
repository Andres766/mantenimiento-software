"""API REST de NotasQA."""
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.app import db as base_datos
from src.app import storage
from src.app.db import Calificacion, Usuario, get_db
from src.app.seguridad import autenticar, emitir_token, sembrar_usuarios, solo_docente, usuario_actual
from src.notas.reglas import (aplicar_habilitacion, calcular_definitiva, clasificar_nota,
                              promedio_ponderado, validar_creditos)

APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
log = logging.getLogger("notasqa")
logging.basicConfig(level=logging.INFO, format="%(message)s")


@asynccontextmanager
async def ciclo_de_vida(_app: FastAPI):
    base_datos.inicializar(sembrar_usuarios)
    yield


app = FastAPI(title="NotasQA", version=APP_VERSION, lifespan=ciclo_de_vida)
app.mount("/ui", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="ui")

PETICIONES = Counter("notasqa_http_requests_total", "Peticiones HTTP", ["metodo", "ruta", "estado"])
LATENCIA = Histogram("notasqa_http_request_seconds", "Latencia HTTP", ["ruta"])


class Credenciales(BaseModel):
    usuario: str
    clave: str


class CalificacionIn(BaseModel):
    estudiante_id: int
    asignatura: str
    corte1: float
    corte2: float
    corte3: float
    creditos: int = 3


class HabilitacionIn(BaseModel):
    nota: float


@app.middleware("http")
async def observabilidad(request: Request, call_next):
    inicio = time.perf_counter()
    respuesta = await call_next(request)
    ruta = request.scope.get("route").path if request.scope.get("route") else "otra"
    duracion = time.perf_counter() - inicio
    PETICIONES.labels(request.method, ruta, respuesta.status_code).inc()
    LATENCIA.labels(ruta).observe(duracion)
    log.info(json.dumps({"metodo": request.method, "ruta": ruta,
                         "estado": respuesta.status_code, "ms": round(duracion * 1000, 2)}))
    return respuesta


# ---------- Sistema ----------
@app.get("/", include_in_schema=False)
def inicio():
    return RedirectResponse("/ui/")


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


# ---------- Autenticación ----------
@app.post("/api/v1/auth/token")
def login(credenciales: Credenciales, db: Session = Depends(get_db)):
    usuario = autenticar(db, credenciales.usuario, credenciales.clave)
    if usuario is None:
        raise HTTPException(status_code=401, detail="Usuario o clave incorrectos")
    return {"access_token": emitir_token(usuario), "token_type": "bearer", "rol": usuario.rol,
            "estudiante_id": usuario.estudiante_id}


# ---------- Calificaciones ----------
def _buscar(db: Session, calificacion_id: int, usuario: Usuario) -> Calificacion:
    registro = db.get(Calificacion, calificacion_id)
    if registro is None:
        raise HTTPException(status_code=404, detail="Calificación no encontrada")
    if usuario.rol == "estudiante" and registro.estudiante_id != usuario.estudiante_id:
        raise HTTPException(status_code=403, detail="Solo puede ver sus propias notas")
    return registro


@app.post("/api/v1/calificaciones", status_code=status.HTTP_201_CREATED)
def crear_calificacion(datos: CalificacionIn, db: Session = Depends(get_db),
                       docente: Usuario = Depends(solo_docente)):
    try:
        validar_creditos(datos.creditos)
        definitiva = calcular_definitiva(datos.corte1, datos.corte2, datos.corte3)
    except (ValueError, TypeError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    registro = Calificacion(**datos.model_dump(), definitiva=definitiva,
                            estado=clasificar_nota(definitiva), registrada_por=docente.id)
    db.add(registro)
    db.commit()
    return registro.a_dict()


@app.get("/api/v1/calificaciones")
def listar_calificaciones(db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_actual)):
    consulta = select(Calificacion).order_by(Calificacion.id)
    if usuario.rol == "estudiante":
        consulta = consulta.where(Calificacion.estudiante_id == usuario.estudiante_id)
    return [c.a_dict() for c in db.scalars(consulta)]


@app.get("/api/v1/calificaciones/{calificacion_id}")
def obtener_calificacion(calificacion_id: int, db: Session = Depends(get_db),
                         usuario: Usuario = Depends(usuario_actual)):
    return _buscar(db, calificacion_id, usuario).a_dict()


@app.post("/api/v1/calificaciones/{calificacion_id}/habilitacion")
def habilitar(calificacion_id: int, datos: HabilitacionIn, db: Session = Depends(get_db),
              docente: Usuario = Depends(solo_docente)):
    registro = _buscar(db, calificacion_id, docente)
    if registro.habilitacion is not None:
        raise HTTPException(status_code=409, detail="La materia ya fue habilitada")
    try:
        final = aplicar_habilitacion(registro.definitiva, datos.nota)
    except PermissionError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except (ValueError, TypeError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    registro.habilitacion = datos.nota
    registro.definitiva = final
    registro.estado = clasificar_nota(final)
    db.commit()
    return registro.a_dict()


@app.get("/api/v1/estudiantes/{estudiante_id}/promedio")
def promedio(estudiante_id: int, db: Session = Depends(get_db),
             usuario: Usuario = Depends(usuario_actual)):
    if usuario.rol == "estudiante" and usuario.estudiante_id != estudiante_id:
        raise HTTPException(status_code=403, detail="Solo puede ver su propio promedio")
    notas = db.scalars(select(Calificacion).where(Calificacion.estudiante_id == estudiante_id)).all()
    if not notas:
        raise HTTPException(status_code=404, detail="El estudiante no tiene calificaciones")
    return {"estudiante_id": estudiante_id, "materias": len(notas),
            "creditos": sum(n.creditos for n in notas),
            "promedio": promedio_ponderado([(n.definitiva, n.creditos) for n in notas])}


@app.post("/api/v1/calificaciones/{calificacion_id}/boletin", status_code=status.HTTP_201_CREATED)
def generar_boletin(calificacion_id: int, db: Session = Depends(get_db),
                    docente: Usuario = Depends(solo_docente)):
    registro = _buscar(db, calificacion_id, docente)
    try:
        return {"s3_key": storage.publicar_boletin(registro.a_dict())}
    except (BotoCoreError, ClientError) as error:
        log.error(json.dumps({"evento": "fallo_almacenamiento", "detalle": str(error)}))
        raise HTTPException(status_code=503, detail="Almacenamiento no disponible") from error
