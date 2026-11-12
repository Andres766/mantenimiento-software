# NotasQA — Plataforma de calificaciones con pipeline DevTestOps

Proyecto integrador de **Pruebas y Mantenimiento de Software** (Universidad Cooperativa de Colombia, 2026-2) · equipo de 4 integrantes.

NotasQA registra las notas de cada corte (30 % / 30 % / 40 %, escala 0.0–5.0), calcula la definitiva con redondeo
institucional, gestiona habilitaciones y el promedio del semestre por créditos, y publica boletines en S3 que un
worker notifica de forma asíncrona. Docentes y estudiantes entran con JWT y solo ven lo que les corresponde.

Ningún cambio llega a producción sin cruzar **siete puertas automáticas** y una aprobación humana:

| # | Puerta | Herramienta | Falla si… |
|---|---|---|---|
| 1 | Pruebas + cobertura sobre PostgreSQL | Pytest + pytest-cov | una prueba falla o la cobertura < 80 % |
| 2 | Análisis estático | SonarCloud | el Quality Gate queda en *Failed* |
| 3 | Seguridad | pip-audit + Trivy | hay CVE HIGH/CRITICAL con parche disponible |
| 4 | Interfaz | Playwright | un flujo de usuario se rompe (incluye prueba de XSS) |
| 5 | Contenedores | Docker Compose + LocalStack | el `test-runner` o el flujo asíncrono fallan |
| 6 | Carga | Locust por roles | p95 > 500 ms o fallos > 1 % |
| 7 | Smoke test en Staging | `scripts/deploy.py` | `/health`, `/ui/` o la protección 401 fallan → **rollback** |
| ✋ | Aprobación | GitHub Environment `production` | un revisor no aprueba |

Además, `mutacion.yml` corre **pruebas de mutación** sobre las reglas de negocio (62/62 mutantes eliminados).

## Arquitectura

```
                 ┌──────────── docker compose ────────────────────────────────┐
 navegador ──►   │  api :8000  (FastAPI + /ui + /metrics)  ──►  db (PostgreSQL)│
 (/ui, JWT)      │     │ boletín                                               │
                 │     ▼                                                       │
                 │  localstack: S3 (boletines) + SQS (eventos) ──► DLQ          │
                 │                       │                                     │
                 │                       ▼                                     │
                 │                 notificador (worker) ──► Telegram / log     │
                 │  prometheus ◄── /metrics      grafana (tablero + alertas)   │
                 └─────────────────────────────────────────────────────────────┘

 push ─► CI: pruebas(PostgreSQL) ─┬─ sonarcloud          seguridad (pip-audit + Trivy)
                                  └─ contenedores ── carga        e2e (Playwright)
        CI verde ─► CD: imagen:SHA ─► Staging ─► ¿smoke OK? ─ sí ─► ✋ aprobación ─► imagen:stable
                                                         └ no ─► rollback (stable no cambia) + Telegram
```

## Equipo y frentes

| Frente | Qué construye | Evidencia clave |
|---|---|---|
| 1. Lógica y datos | Reglas (definitiva, habilitación, créditos), SQLAlchemy + PostgreSQL, mutación | Tabla BVA, 62/62 mutantes, misma suite en SQLite y PostgreSQL |
| 2. API y seguridad | JWT con roles, propiedad de datos, contrato JSON Schema, pip-audit, Trivy | 401/403 probados, token expirado/alterado, imagen sin CVE críticos |
| 3. DevOps y nube | IaC con DLQ, worker SQS, CD con Staging → aprobación → producción, rollback manual | Mensaje corrupto termina en la DLQ; run de rollback |
| 4. Rendimiento y E2E | Interfaz `/ui`, Playwright, Locust por roles, Grafana + alertas | 6 E2E en navegador real, prueba de XSS, tablero en vivo |

Reglas de trabajo, ramas y revisiones: [CONTRIBUTING.md](CONTRIBUTING.md).

## Requisitos

- Python 3.11+ · Docker Desktop con Compose v2 (Windows: WSL 2) · cuentas de GitHub, SonarCloud y Telegram.

## 1. Pruebas en local

```bash
python -m venv venv
# Windows: .\venv\Scripts\activate      Linux/Mac: source venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest                                  # 101 pruebas (unit 56 · api 32 · integración 13), cobertura ≈ 95 %
python -m pytest --cov-report=html                # abrir htmlcov/index.html
python -m playwright install chromium             # una sola vez
python -m pytest -m e2e --no-cov tests/e2e        # 6 pruebas E2E (agregar --headed para ver el navegador)
pip install "mutmut<3" && mutmut run              # pruebas de mutación de las reglas
```

> En Windows usa siempre `python -m pytest` (evita el error de PATH *"pytest no se reconoce"*).
> Para correr las pruebas contra PostgreSQL: `TEST_DATABASE_URL=postgresql+psycopg://usuario:clave@localhost:5432/bd`.

## 2. Todo el sistema en contenedores

```bash
cp .env.example .env                                       # opcional: cambiar claves locales
docker compose run --rm --build test-runner                # pruebas de API contra el contenedor (exit code = pytest)
docker compose up -d --build --wait api notificador        # dejar el sistema arriba
python scripts/smoke_boletin.py http://localhost:8000      # login -> nota -> boletín en S3 + evento SQS
docker compose logs notificador                            # "Boletín listo — estudiante 2026 ..."
docker compose down -v                                     # destruir todo (BD y "nube")
```

- Interfaz: http://localhost:8000 → usuario `docente` / `docente-local` o `estudiante` / `estudiante-local`.
- Documentación interactiva: http://localhost:8000/docs (botón *Authorize* con el token).

| Método y ruta | Rol | Respuesta |
|---|---|---|
| `POST /api/v1/auth/token` | público | 200 con token · 401 |
| `GET /health` · `GET /metrics` · `GET /ui/` | público | 200 (`/health` 500 si `FORZAR_FALLO=1`) |
| `POST /api/v1/calificaciones` | docente | 201 · 400 (nota o créditos fuera de rango) · 401 · 403 |
| `GET /api/v1/calificaciones?limite=100&desde=0` | ambos | 200, paginado (el estudiante solo ve las suyas) · 422 si `limite` no está entre 1 y 500 |
| `GET /api/v1/calificaciones/{id}` | ambos | 200 · 403 (ajena) · 404 |
| `POST /api/v1/calificaciones/{id}/habilitacion` | docente | 200 · 400 · 409 (no habilitable o ya habilitada) |
| `GET /api/v1/estudiantes/{id}/promedio` | ambos | 200 · 403 (ajeno) · 404 |
| `POST /api/v1/calificaciones/{id}/boletin` | docente | 201 · 503 si S3/SQS no responden |

## 3. Carga

```bash
# DOCENTE_CLAVE y ESTUDIANTE_CLAVE deben coincidir con las del servidor
python -m locust -f load/locustfile.py --host http://localhost:8000                     # interfaz en :8089
python -m locust -f load/locustfile.py --headless -u 100 -r 10 -t 60s --host http://localhost:8000 --csv carga
```

Proporción 1 docente : 4 estudiantes; cada usuario virtual hace login una vez y reutiliza su token.

## 4. Observabilidad

```bash
docker compose --profile observabilidad up -d --build
```

Prometheus en http://localhost:9090 (pestaña *Alerts*: p95 alto, errores 5xx, API caída, accesos rechazados) y
Grafana en http://localhost:3000 → carpeta **NotasQA** (tablero ya provisionado). Logs JSON: `docker compose logs -f api`.

## 5. CI/CD en GitHub

1. Crear el repositorio **vacío** y hacer push (`git remote add origin …` y `git push -u origin main`).
2. **SonarCloud:** *Analyze new project* → desactivar *Automatic Analysis* → copiar el token → editar `sonar-project.properties`.
3. **Telegram:** bot con @BotFather (`/newbot`) y chat id con @userinfobot.
4. **Secrets and variables → Actions:** secrets `SONAR_TOKEN`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`; variable `FORZAR_FALLO` vacía.
5. **Environments:** crear `staging` y `production`; en `production` activar *Required reviewers* con los 4 integrantes.
6. **Actions → General → Workflow permissions:** *Read and write* (publicar imágenes en GHCR).
7. **Branches:** proteger `main` como indica CONTRIBUTING.md y descomentar `.github/CODEOWNERS`.

| Workflow | Cuándo corre | Qué hace |
|---|---|---|
| `ci.yml` | push y PR a `main` | pruebas, sonarcloud, seguridad, e2e, contenedores, carga |
| `cd.yml` | CI en verde sobre `main` | imagen:SHA → Staging → smoke → aprobación → imagen:stable |
| `rollback.yml` | manual (pide un SHA) | repunta `stable` a una versión anterior, con aprobación |
| `mutacion.yml` | PR que toca reglas, lunes, manual | mutmut sobre `src/notas` |

Todas las acciones están fijadas por **SHA completo**. Caso real que lo justifica: en marzo de 2026 atacantes
reescribieron 76 de 77 etiquetas de `aquasecurity/trivy-action` para robar secretos de los pipelines que las usaban
por etiqueta (CVE-2026-33634); los pipelines fijados por SHA no ejecutaron el código malicioso.

## Matriz de trazabilidad: semana → proyecto

| Semana | Tema | Dónde se aplica | Evidencia |
|---|---|---|---|
| 1 | Error → defecto → fallo, pirámide, patrón AAA | `tests/unit/test_reglas.py::test_nota_aprobatoria_exacta_es_aprobado` | Cambiar `<` por `<=` y ver pruebas en rojo |
| 2 | Partición de equivalencia, BVA, `parametrize`, `pytest.raises` | `test_clasificar_nota_fronteras`, `test_clasificar_nota_entradas_destructivas`, `test_calcular_definitiva_redondeo` | `pytest -v` con cada tupla visible |
| 3 | Cobertura y Quality Gate `--cov-fail-under=80` | `pytest.ini` (ramas sobre `src`, `infra`, `scripts`) | 95 % en terminal + `htmlcov/index.html` |
| 4 | Docker, imagen, contenedor, compose, exit code | `Dockerfile`, `docker-compose.yml` | `docker images` + test-runner con exit 0 |
| 5 | Pruebas de API, JSON Schema, test-runner efímero | `tests/api/`, servicio `test-runner` (`API_URL=http://api:8000`) | 28 pruebas contra el contenedor |
| 6 | CI con GitHub Actions | `.github/workflows/ci.yml` | Pestaña Actions con runs verdes y rojos |
| 7 | SAST, SonarCloud, acciones fijadas por SHA | job `sonarcloud`, `sonar-project.properties` | Quality Gate en *Passed* |
| 8 | Carga con Locust, p95, RPS, punto de quiebre | `load/locustfile.py` (docente : estudiante = 1 : 4) | CSV en artifacts, Charts con 200 usuarios |
| 9 | CD, Staging, smoke test, rollback, Telegram | `cd.yml`, `rollback.yml`, `scripts/deploy.py` | CD verde, CD rojo y 3 mensajes en Telegram |
| 10 | IaC idempotente con LocalStack (S3 + SQS) | `infra/init_infra.py`, servicios `localstack` e `infra-init` | Boletín en S3; `docker compose down -v` borra la "nube" |
| 11–12 | Observabilidad | `/metrics`, logs JSON, `observabilidad/` (Prometheus + Grafana) | Tablero con RPS, p95 y 5xx durante Locust |

## Demos para la sustentación

| Frente / semana | Demo | Qué se ve |
|---|---|---|
| 1 · S1 | Cambiar `if valor < NOTA_APROBATORIA` por `<=` | pruebas en rojo |
| 1 · S2 | Reemplazar `Decimal` por `round(float, 1)` | fallan (0.4, 4.1, 4.0) y (4.0, 4.5, 5.0) |
| 1 · S3 | `python -m pytest --cov-fail-under=98` | *Required test coverage of 98% not reached* |
| 1 | Quitar `match=` de un `pytest.raises` y correr `mutmut run` | aparece un mutante sobreviviente |
| 2 · S5 | En `db.py` devolver `"estado": 1` en `a_dict` | `ValidationError` del JSON Schema |
| 2 | En crear calificación cambiar `Depends(solo_docente)` por `Depends(usuario_actual)` | falla `test_estudiante_no_puede_registrar_notas_403` |
| 2 · S7 | Commit con clave quemada + `if/else` idéntico | Quality Gate de Sonar en rojo |
| 3 · S10 | Enviar un mensaje corrupto a la cola | tras 3 intentos aparece en la DLQ |
| 3 · S9 | Variable `FORZAR_FALLO=1` | Staging 500 → rollback + alerta en Telegram |
| 3 | Ejecutar `rollback.yml` con un SHA anterior | producción vuelve a esa versión |
| 4 | Cambiar `textContent` por `innerHTML` en `index.html` | la prueba E2E de XSS falla |
| 4 · S8 | `time.sleep(0.6)` en el listado | p95 > 500 ms → Locust exit 1 y alerta en Prometheus |

## Estructura

```
src/notas/reglas.py           reglas de negocio (Decimal, habilitación, créditos)
src/app/main.py               API FastAPI + métricas + logs JSON
src/app/db.py                 modelos SQLAlchemy (PostgreSQL / SQLite)
src/app/seguridad.py          JWT, roles, hash PBKDF2
src/app/storage.py            S3 y SQS (boto3)
src/app/static/index.html     interfaz web
src/worker/notificador.py     worker asíncrono SQS -> notificación
infra/init_infra.py           IaC idempotente: bucket + cola + DLQ
scripts/deploy.py             CD: smoke test, rollback, Telegram
scripts/smoke_boletin.py      E2E del flujo asíncrono contra la API real
load/locustfile.py            carga por roles con umbrales
tests/unit · api · integration · e2e
observabilidad/               Prometheus (alertas) + Grafana provisionado
.github/workflows/            ci, cd, rollback, mutacion
```

## Problemas frecuentes

- **LocalStack no descarga:** no cambies `3.8.1` por `latest` (desde marzo de 2026 `latest` exige token).
- **Puerto 8000 ocupado:** `Test-NetConnection -ComputerName localhost -Port 8000` y cambia `"8000:8000"`.
- **`JWT_SECRET debe existir`:** define la variable (mínimo 32 caracteres) o usa `docker compose`, que trae una para desarrollo.
- **Trivy falla por una CVE de la imagen base:** actualiza `python:3.11-slim` o, si no hay parche, documenta la excepción en `.trivyignore` con su justificación.
