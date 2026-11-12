"""Autenticación JWT con roles (docente / estudiante). Sin secretos en el código: todo viene del entorno."""
import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.app.db import Usuario, get_db

ALGORITMO = "HS256"
ITERACIONES = 120_000
_bearer = HTTPBearer(auto_error=False)


def _secreto() -> str:
    secreto = os.getenv("JWT_SECRET")
    if not secreto or len(secreto) < 32:
        raise RuntimeError("JWT_SECRET debe existir y tener al menos 32 caracteres.")
    return secreto


def hashear_clave(clave: str) -> str:
    sal = secrets.token_bytes(16)
    derivada = hashlib.pbkdf2_hmac("sha256", clave.encode(), sal, ITERACIONES)
    return f"{base64.b64encode(sal).decode()}${base64.b64encode(derivada).decode()}"


def verificar_clave(clave: str, guardada: str) -> bool:
    sal_b64, derivada_b64 = guardada.split("$")
    derivada = hashlib.pbkdf2_hmac("sha256", clave.encode(), base64.b64decode(sal_b64), ITERACIONES)
    return hmac.compare_digest(derivada, base64.b64decode(derivada_b64))


def emitir_token(usuario: Usuario) -> str:
    ahora = datetime.now(timezone.utc)
    minutos = int(os.getenv("JWT_MINUTOS", "30"))
    datos = {"sub": str(usuario.id), "rol": usuario.rol, "est": usuario.estudiante_id,
             "iat": ahora, "exp": ahora + timedelta(minutes=minutos)}
    return jwt.encode(datos, _secreto(), algorithm=ALGORITMO)


def _no_autorizado(detalle: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detalle,
                         headers={"WWW-Authenticate": "Bearer"})


def usuario_actual(credenciales: HTTPAuthorizationCredentials | None = Depends(_bearer),
                   db: Session = Depends(get_db)) -> Usuario:
    if credenciales is None:
        raise _no_autorizado("Falta el token de acceso")
    try:
        datos = jwt.decode(credenciales.credentials, _secreto(), algorithms=[ALGORITMO])
    except jwt.ExpiredSignatureError as error:
        raise _no_autorizado("Token expirado") from error
    except jwt.InvalidTokenError as error:
        raise _no_autorizado("Token inválido") from error
    usuario = db.get(Usuario, int(datos["sub"]))
    db.commit()   # devuelve la conexión al pool mientras la petición espera hilo para el endpoint
    if usuario is None:
        raise _no_autorizado("Usuario no existe")
    return usuario


def solo_docente(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
    if usuario.rol != "docente":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requiere rol docente")
    return usuario


def autenticar(db: Session, usuario: str, clave: str) -> Usuario | None:
    encontrado = db.scalar(select(Usuario).where(Usuario.usuario == usuario))
    db.commit()   # no retener la conexión durante el hash PBKDF2 (~20 ms de CPU)
    if encontrado and verificar_clave(clave, encontrado.clave_hash):
        return encontrado
    return None


def sembrar_usuarios(db: Session) -> None:
    """Crea los usuarios de demostración solo si sus claves vienen en el entorno."""
    semillas = [
        ("docente", os.getenv("DOCENTE_CLAVE"), "docente", None),
        ("estudiante", os.getenv("ESTUDIANTE_CLAVE"), "estudiante",
         int(os.getenv("ESTUDIANTE_ID", "1001"))),
    ]
    for nombre, clave, rol, estudiante_id in semillas:
        if clave and db.scalar(select(Usuario).where(Usuario.usuario == nombre)) is None:
            db.add(Usuario(usuario=nombre, clave_hash=hashear_clave(clave), rol=rol,
                           estudiante_id=estudiante_id))
