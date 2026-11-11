"""Semana 8 + Frente 4: carga realista por roles, con umbrales que fallan el pipeline.

Proporción 1 docente : 4 estudiantes. Cada usuario virtual hace login una vez (on_start)
y reutiliza su token, como un navegador real. Claves desde DOCENTE_CLAVE / ESTUDIANTE_CLAVE."""
import os
import random

from locust import HttpUser, between, events, task

MAX_FALLOS = 0.01   # 1 % de peticiones fallidas
MAX_P95_MS = 500    # percentil 95 en milisegundos


class UsuarioAutenticado(HttpUser):
    abstract = True
    usuario = ""
    variable_clave = ""

    def on_start(self):
        respuesta = self.client.post("/api/v1/auth/token", name="login", json={
            "usuario": self.usuario, "clave": os.getenv(self.variable_clave, "")})
        datos = respuesta.json() if respuesta.ok else {}
        self.client.headers["Authorization"] = f"Bearer {datos.get('access_token', '')}"
        self.estudiante_id = datos.get("estudiante_id")


class Docente(UsuarioAutenticado):
    weight = 1
    wait_time = between(1, 3)
    usuario = "docente"
    variable_clave = "DOCENTE_CLAVE"

    @task(3)
    def registrar(self):
        self.client.post("/api/v1/calificaciones", json={
            "estudiante_id": random.choice([1001, random.randint(2000, 2500)]), "asignatura": "Pruebas",
            "corte1": round(random.uniform(0, 5), 1), "corte2": round(random.uniform(0, 5), 1),
            "corte3": round(random.uniform(0, 5), 1), "creditos": random.randint(1, 4)})

    @task(1)
    def listar_todo(self):
        self.client.get("/api/v1/calificaciones")


class Estudiante(UsuarioAutenticado):
    weight = 4
    wait_time = between(2, 5)
    usuario = "estudiante"
    variable_clave = "ESTUDIANTE_CLAVE"

    @task(3)
    def mis_notas(self):
        self.client.get("/api/v1/calificaciones")

    @task(1)
    def mi_promedio(self):
        # 404 es válido si aún no tiene notas: no se cuenta como fallo
        with self.client.get(f"/api/v1/estudiantes/{self.estudiante_id}/promedio",
                             name="/api/v1/estudiantes/[id]/promedio", catch_response=True) as r:
            if r.status_code in (200, 404):
                r.success()


@events.quitting.add_listener
def quality_gate(environment, **_):
    total = environment.stats.total
    p95 = total.get_response_time_percentile(0.95) or 0
    if total.fail_ratio > MAX_FALLOS or p95 > MAX_P95_MS:
        print(f"QUALITY GATE DE CARGA FALLIDO: fallos={total.fail_ratio:.2%} p95={p95} ms")
        environment.process_exit_code = 1
    else:
        print(f"Quality gate de carga OK: fallos={total.fail_ratio:.2%} p95={p95} ms")
        environment.process_exit_code = 0
