"""Frente 4: pruebas E2E de la interfaz con Playwright (la punta de la pirámide).

Levantan un servidor Uvicorn real con BD temporal y manejan un navegador de verdad.
Correr:  python -m pytest -m e2e --no-cov tests/e2e            (en CI: playwright install chromium)
         python -m pytest -m e2e --no-cov --browser-channel chrome tests/e2e   (usar Chrome instalado)
"""
import os
import socket
import subprocess
import sys
import time
import urllib.request

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e

CLAVE_DOCENTE = "docente-e2e"
CLAVE_ESTUDIANTE = "estudiante-e2e"


def _puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def servidor(tmp_path_factory):
    puerto = _puerto_libre()
    entorno = {**os.environ,
               "DATABASE_URL": f"sqlite:///{tmp_path_factory.mktemp('e2e') / 'e2e.db'}",
               "JWT_SECRET": "secreto-solo-para-pruebas-e2e-0123456789",
               "DOCENTE_CLAVE": CLAVE_DOCENTE, "ESTUDIANTE_CLAVE": CLAVE_ESTUDIANTE, "ESTUDIANTE_ID": "1001"}
    proceso = subprocess.Popen([sys.executable, "-m", "uvicorn", "src.app.main:app", "--port", str(puerto)],
                               env=entorno, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{puerto}"
    for _ in range(50):
        try:
            urllib.request.urlopen(f"{base}/health", timeout=1)
            break
        except OSError:
            time.sleep(0.2)
    yield base
    proceso.terminate()
    proceso.wait(timeout=10)


def _ingresar(page: Page, base: str, usuario: str, clave: str) -> None:
    page.goto(f"{base}/ui/")
    page.get_by_label("Usuario").fill(usuario)
    page.get_by_label("Clave").fill(clave)
    page.get_by_role("button", name="Ingresar").click()


def test_docente_registra_nota_y_la_ve_en_la_tabla(page: Page, servidor):
    _ingresar(page, servidor, "docente", CLAVE_DOCENTE)
    expect(page.get_by_text("Docente", exact=True)).to_be_visible()

    page.get_by_label("Estudiante").fill("1001")
    page.get_by_label("Asignatura").fill("Pruebas E2E")
    page.get_by_label("Corte 1").fill("4.0")
    page.get_by_label("Corte 2").fill("4.5")
    page.get_by_label("Corte 3").fill("5.0")
    page.get_by_role("button", name="Registrar nota").click()

    expect(page.get_by_role("status")).to_have_text("Nota registrada: 4.6 EXCELENTE")
    fila = page.get_by_role("row").filter(has_text="Pruebas E2E")
    expect(fila).to_contain_text("EXCELENTE")


def test_nota_invalida_muestra_error(page: Page, servidor):
    _ingresar(page, servidor, "docente", CLAVE_DOCENTE)
    page.get_by_label("Estudiante").fill("1001")
    page.get_by_label("Asignatura").fill("Fuera de rango")
    page.get_by_label("Corte 1").fill("5.1")
    page.get_by_label("Corte 2").fill("3")
    page.get_by_label("Corte 3").fill("3")
    page.get_by_role("button", name="Registrar nota").click()
    expect(page.get_by_role("status")).to_have_text("La nota debe estar entre 0.0 y 5.0.")


def test_clave_incorrecta_no_entra(page: Page, servidor):
    _ingresar(page, servidor, "docente", "clave-equivocada")
    expect(page.get_by_role("status")).to_have_text("Usuario o clave incorrectos")
    expect(page.get_by_role("button", name="Registrar nota")).to_be_hidden()


def test_estudiante_no_ve_el_formulario_de_registro(page: Page, servidor):
    _ingresar(page, servidor, "estudiante", CLAVE_ESTUDIANTE)
    expect(page.get_by_text("Estudiante 1001")).to_be_visible()
    expect(page.get_by_role("heading", name="Calificaciones")).to_be_visible()
    expect(page.get_by_role("button", name="Registrar nota")).to_be_hidden()


def test_contenido_malicioso_no_se_ejecuta(page: Page, servidor):
    """Seguridad en la interfaz: un nombre de asignatura con HTML se muestra como texto (sin XSS)."""
    alertas = []
    page.on("dialog", lambda dialogo: (alertas.append(dialogo.message), dialogo.dismiss()))
    _ingresar(page, servidor, "docente", CLAVE_DOCENTE)
    page.get_by_label("Estudiante").fill("1001")
    page.get_by_label("Asignatura").fill("<img src=x onerror=alert(1)>")
    page.get_by_label("Corte 1").fill("3")
    page.get_by_label("Corte 2").fill("3")
    page.get_by_label("Corte 3").fill("3")
    page.get_by_role("button", name="Registrar nota").click()
    expect(page.get_by_role("cell", name="<img src=x onerror=alert(1)>")).to_be_visible()
    assert alertas == []


def test_salir_cierra_la_sesion(page: Page, servidor):
    _ingresar(page, servidor, "docente", CLAVE_DOCENTE)
    page.get_by_role("button", name="Salir").click()
    expect(page.get_by_role("status")).to_have_text("Sesión cerrada")
    expect(page.get_by_role("button", name="Ingresar")).to_be_visible()
