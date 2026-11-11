# NotasQA — API de calificaciones con pipeline DevTestOps

Proyecto integrador de **Pruebas y Mantenimiento de Software** (Universidad Cooperativa de Colombia, 2026-2).

NotasQA calcula la nota definitiva de un estudiante (cortes 30 % / 30 % / 40 %, escala 0.0–5.0),
la clasifica (REPROBADO / APROBADO / EXCELENTE) y genera su boletín en S3 con un evento en SQS.
Sobre la API corre un pipeline que impide que un cambio llegue a producción sin pasar **cinco puertas automáticas**:

| # | Puerta | Herramienta | Falla si… |
|---|--------|-------------|-----------|
| 1 | Pruebas + cobertura | Pytest + pytest-cov | una prueba falla o la cobertura < 80 % |
| 2 | Análisis estático | SonarCloud | el Quality Gate queda en *Failed* |
| 3 | Pruebas en contenedores | Docker Compose + LocalStack | el `test-runner` sale con código ≠ 0 |
| 4 | Carga | Locust | p95 > 500 ms o fallos > 1 % |
| 5 | Smoke test en Staging | `scripts/deploy.py` | `/health` o el listado no responden 200 → **rollback** |

## Arquitectura

```
push a main ──► CI (ci.yml)
                 ├─ pruebas ─┬─ sonarcloud
                 │           └─ contenedores ── carga
                 └─ todo verde ──► CD (cd.yml)
                                   build imagen:SHA → Staging → ¿smoke 200?
                                     ├─ sí → push imagen:stable (producción) + Telegram ✅
                                     └─ no → stable no cambia (rollback) + Telegram 🚨

docker compose:  localstack (S3+SQS) ◄── infra-init (IaC)
                       ▲
                      api :8000 ◄── test-runner (pruebas de API)
                       ▲
                 prometheus :9090 ◄── grafana :3000   (perfil "observabilidad")
```

## Requisitos

- Python 3.11+ (probado también con 3.13)
- Docker Desktop con Docker Compose v2 (en Windows, con WSL 2)
- Cuenta de GitHub, SonarCloud y Telegram (para CI/CD y alertas)

## 1. Ejecutar las pruebas en local (semanas 1–3)

```bash
python -m venv venv
# Windows: .\venv\Scripts\activate      Linux/Mac: source venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest                          # 35 pruebas, cobertura ≈ 94 %, Quality Gate 80 %
python -m pytest --cov-report=html        # abrir htmlcov/index.html
```

> En Windows usa siempre `python -m pytest` (evita el error de PATH *"pytest no se reconoce"*).

## 2. Todo el sistema en contenedores (semanas 4, 5 y 10)

```bash
docker compose up --build --exit-code-from test-runner    # pruebas de API contra el contenedor
docker compose up -d --build --wait api                    # dejar la API arriba
python scripts/smoke_boletin.py http://localhost:8000      # nota -> boletín en S3 + evento SQS
docker compose down -v                                     # destruir la "nube" local
```

Orden de arranque: `localstack` (healthy) → `infra-init` crea bucket y cola y termina → `api` (healthy) → `test-runner`.
La documentación interactiva de la API queda en http://localhost:8000/docs.

| Método y ruta | Respuesta |
|---|---|
| `GET /health` | 200 (500 si `FORZAR_FALLO=1`) |
| `GET /metrics` | métricas Prometheus |
| `POST /api/v1/calificaciones` | 201 · 400 si una nota está fuera de 0.0–5.0 |
| `GET /api/v1/calificaciones` | 200 |
| `GET /api/v1/calificaciones/{id}` | 200 · 404 |
| `POST /api/v1/calificaciones/{id}/boletin` | 201 con `s3_key` · 503 si S3/SQS no responden |

## 3. Pruebas de carga (semana 8)

```bash
# Con interfaz (captura de Charts): abrir http://localhost:8089
python -m locust -f load/locustfile.py --host http://localhost:8000
# Sin interfaz, igual que el CI (exit code 1 si se rompe el umbral)
python -m locust -f load/locustfile.py --headless -u 100 -r 10 -t 60s --host http://localhost:8000 --csv carga
```

## 4. Observabilidad (semanas 11–12)

```bash
docker compose --profile observabilidad up -d --build
```

- Prometheus: http://localhost:9090 (lee `/metrics` cada 5 s)
- Grafana: http://localhost:3000 → carpeta **NotasQA** → tablero *NotasQA — Observabilidad*
  (RPS, latencia p95 con umbral de 500 ms, errores 5xx y respuestas por código). Ya viene provisionado.
- Logs JSON por petición: `docker compose logs -f api`

## 5. CI/CD en GitHub (semanas 6, 7 y 9)

1. Crear el repositorio **vacío** en GitHub (sin README, sin .gitignore, sin licencia) y hacer push:
   ```bash
   git remote add origin https://github.com/<usuario>/notasqa.git
   git push -u origin main
   ```
2. SonarCloud: *Analyze new project* → elegir el repo → *With GitHub Actions*. Copiar el token.
   Editar `sonar-project.properties` y reemplazar `TU_ORGANIZACION`.
   En SonarCloud, desactivar *Automatic Analysis* (el análisis lo hace el pipeline).
3. Telegram: crear el bot con **@BotFather** (`/newbot`) y obtener el chat id con **@userinfobot**.
4. En GitHub → *Settings → Secrets and variables → Actions*:

   | Tipo | Nombre | Valor |
   |---|---|---|
   | Secret | `SONAR_TOKEN` | token de SonarCloud |
   | Secret | `TELEGRAM_BOT_TOKEN` | token del bot |
   | Secret | `TELEGRAM_CHAT_ID` | id numérico del chat |
   | Variable | `FORZAR_FALLO` | vacío (poner `1` para la demo de rollback) |

5. *Settings → Actions → General → Workflow permissions*: **Read and write** (para publicar la imagen en GHCR).

Todas las acciones están fijadas por **SHA completo** (regla de Sonar *"Use full commit SHA hash"*).
Ningún secreto vive en el código: `deploy.py` los lee de variables de entorno.

## Demos para la sustentación

| Semana | Demo | Qué se ve |
|---|---|---|
| 1 | En `src/notas/reglas.py` cambiar `if valor < NOTA_APROBATORIA` por `<=` | 3 pruebas en rojo |
| 2 | Reemplazar `Decimal` por `round(float, 1)` | fallan (0.4, 4.1, 4.0) y (4.0, 4.5, 5.0) |
| 3 | `python -m pytest --cov-fail-under=98` (o borrar `tests/unit/test_deploy.py`) | *Required test coverage of 98% not reached* → build en rojo |
| 5 | En `main.py` poner `"estado": 1` | `ValidationError` del JSON Schema en el test-runner |
| 7 | Commit con variable sin uso + `if/else` idéntico + clave quemada | Quality Gate de Sonar en rojo |
| 8 | `time.sleep(0.6)` en el listado | p95 > 500 ms → Locust exit 1 |
| 9 | Variable `FORZAR_FALLO=1` en GitHub | Staging 500 → rollback + alerta en Telegram |
| 10 | `docker compose down -v` | la infraestructura desaparece y se recrea igual |

## Estructura

```
src/notas/reglas.py        lógica de negocio (Decimal, redondeo ROUND_HALF_UP)
src/app/main.py            API FastAPI + métricas + logs JSON
src/app/storage.py         S3 y SQS (boto3)
infra/init_infra.py        IaC idempotente: bucket + cola
scripts/deploy.py          CD: smoke test, promoción/rollback, Telegram
scripts/smoke_boletin.py   prueba E2E del boletín contra la API real
load/locustfile.py         carga con umbrales
tests/unit · tests/api · tests/integration
observabilidad/            Prometheus + Grafana provisionado
.github/workflows/         ci.yml y cd.yml
```

## Problemas frecuentes

- **`docker compose` falla al descargar LocalStack**: no cambies la etiqueta `3.8.1` a `latest`;
  desde marzo de 2026 `latest` exige cuenta y `LOCALSTACK_AUTH_TOKEN`.
- **Puerto 8000 ocupado**: `Test-NetConnection -ComputerName localhost -Port 8000` (PowerShell) y cambia `"8000:8000"` por `"8080:8000"`.
- **El CD no publica la imagen**: revisa el paso 5 de la sección de CI/CD (permisos de escritura).
