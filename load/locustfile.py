"""Semana 8: carga concurrente con umbrales que hacen fallar el pipeline si se superan."""
import random

from locust import HttpUser, between, events, task

MAX_FALLOS = 0.01   # 1 % de peticiones fallidas
MAX_P95_MS = 500    # percentil 95 en milisegundos


class Docente(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def consultar(self):
        self.client.get("/api/v1/calificaciones")

    @task(1)
    def registrar(self):
        self.client.post("/api/v1/calificaciones", json={
            "estudiante_id": random.randint(1, 500), "asignatura": "Pruebas",
            "corte1": round(random.uniform(0, 5), 1), "corte2": round(random.uniform(0, 5), 1),
            "corte3": round(random.uniform(0, 5), 1)})


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
