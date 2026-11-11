"""Persistencia con SQLAlchemy 2.0: PostgreSQL en Docker/producción, SQLite en pruebas rápidas."""
import os
from collections.abc import Iterator

from sqlalchemy import ForeignKey, String, create_engine
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
    return create_engine(url, pool_pre_ping=True)


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./notasqa.db")
motor = crear_motor(DATABASE_URL)
SesionLocal = sessionmaker(bind=motor, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    with SesionLocal() as sesion:
        yield sesion


def inicializar(semilla) -> None:
    """Crea las tablas (migración inicial) y siembra usuarios de demostración."""
    Base.metadata.create_all(motor)
    with SesionLocal() as sesion:
        semilla(sesion)
        sesion.commit()
