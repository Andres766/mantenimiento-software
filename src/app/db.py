"""Persistencia con SQLAlchemy 2.0: PostgreSQL en Docker/producción, SQLite en pruebas rápidas."""
import os
import time
from collections.abc import AsyncIterator

from sqlalchemy import ForeignKey, String, create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


class Usuario(Base):
    __tablename__ = "usuarios"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario: Mapped[str] = mapped_column(String(50), unique=True)
    clave_hash: Mapped[str] = mapped_column(String(200))
    rol: Mapped[str] = mapped_column(String(20))           # "docente" | "estudiante"
    estudiante_id: Mapped[int | None] = mapped_column(nullable=True)


class Calificacion(Base):
    __tablename__ = "calificaciones"
    id: Mapped[int] = mapped_column(primary_key=True)
    estudiante_id: Mapped[int] = mapped_column(index=True)
    asignatura: Mapped[str] = mapped_column(String(100))
    creditos: Mapped[int]
    corte1: Mapped[float]
    corte2: Mapped[float]
    corte3: Mapped[float]
    definitiva: Mapped[float]
    estado: Mapped[str] = mapped_column(String(20))
    habilitacion: Mapped[float | None] = mapped_column(nullable=True)
    registrada_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)

    def a_dict(self) -> dict:
        return {
            "id": self.id, "estudiante_id": self.estudiante_id, "asignatura": self.asignatura,
            "creditos": self.creditos, "corte1": self.corte1, "corte2": self.corte2,
            "corte3": self.corte3, "definitiva": self.definitiva, "estado": self.estado,
            "habilitacion": self.habilitacion,
        }


def crear_motor(url: str):
    if url.startswith("sqlite"):
        opciones = {"connect_args": {"check_same_thread": False}}
        if ":memory:" in url:
            opciones["poolclass"] = StaticPool    # una sola BD en memoria compartida por hilos
        return create_engine(url, **opciones)
    # 20 + 30 = 50 conexiones > 40 hilos del threadpool de FastAPI: ningún hilo queda bloqueado
    # esperando una conexión que otro hilo no puede devolver (con 5 + 10 colapsaba a 200 usuarios)
    return create_engine(url, pool_pre_ping=True, pool_size=20, max_overflow=30)


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./notasqa.db")
motor = crear_motor(DATABASE_URL)
SesionLocal = sessionmaker(bind=motor, expire_on_commit=False)


async def get_db() -> AsyncIterator[Session]:
    """async a propósito: FastAPI cierra la sesión en el event loop, sin esperar un hilo libre.

    Con un generador síncrono, bajo carga la conexión quedaba retenida mientras la petición
    esperaba turno en el threadpool para cerrarla, y el pool se agotaba (QueuePool timeout)."""
    with SesionLocal() as sesion:
        yield sesion


def inicializar(semilla, intentos: int = 10, espera: float = 1.0) -> None:
    """Crea las tablas (migración inicial) y siembra usuarios de demostración.

    Reintenta si la BD aún no responde: en compose, el DNS de "db" puede tardar unos segundos."""
    for intento in range(1, intentos + 1):
        try:
            Base.metadata.create_all(motor)
            break
        except OperationalError:
            if intento == intentos:
                raise
            time.sleep(espera)
    with SesionLocal() as sesion:
        semilla(sesion)
        sesion.commit()
