# Cómo trabajamos (4 integrantes)

## Frentes y responsables

| Frente | Responsable | Carpetas que cuida | Lo que defiende en la sustentación |
|---|---|---|---|
| 1. Lógica y datos | Integrante 1 | `src/notas/`, `src/app/db.py`, `tests/unit/test_reglas*`, `tests/integration/test_persistencia.py`, `setup.cfg` | EP + BVA, redondeo con `Decimal`, habilitación, promedio por créditos, PostgreSQL, pruebas de mutación |
| 2. API y seguridad | Integrante 2 | `src/app/main.py`, `src/app/seguridad.py`, `tests/api/`, job `seguridad` | Contrato JSON Schema, JWT, 401/403, propiedad de datos, pip-audit, Trivy, SonarCloud |
| 3. DevOps y nube | Integrante 3 | `infra/`, `src/worker/`, `docker-compose.yml`, `Dockerfile*`, `.github/workflows/cd.yml`, `rollback.yml` | IaC idempotente, DLQ, worker asíncrono, Staging → aprobación → producción, rollback |
| 4. Rendimiento y E2E | Integrante 4 | `src/app/static/`, `tests/e2e/`, `load/`, `observabilidad/` | Playwright, XSS, Locust por roles, Grafana y alertas |

Todos deben poder explicar el pipeline completo (`ci.yml`) y la matriz de trazabilidad del README.

## Flujo de trabajo

1. Nadie hace push directo a `main`. Se protege la rama en *Settings → Branches → Add rule*:
   *Require a pull request before merging* (1 aprobación) y *Require status checks to pass*
   (marcar `pruebas`, `seguridad`, `e2e` y `contenedores`).
2. Cada cambio sale de una rama propia:
   ```bash
   git switch -c frente1/habilitacion-supletorio
   # ... cambios + pruebas ...
   python -m pytest
   git push -u origin frente1/habilitacion-supletorio
   ```
3. Se abre un Pull Request con la plantilla. **Otro integrante** lo revisa y aprueba.
4. El CI corre sobre el PR: si algo queda en rojo no se puede fusionar.
5. Al fusionar a `main`, el CD despliega a Staging y espera la aprobación para producción.

## Convenciones

- Ramas: `frenteN/descripcion-corta`.
- Commits en español e imperativo: `Agrega prueba BVA para créditos = 10`.
- Toda regla nueva llega con su prueba **en el mismo PR** (BVA si tiene fronteras).
- Nunca se suben claves: van en `.env` (local) o en GitHub Secrets (CI/CD).

## Ideas para seguir ampliando cada frente

- **Frente 1:** supletorios, cancelación de materias, migraciones con Alembic, historial de cambios de nota.
- **Frente 2:** límite de intentos de login (429), roles de administrador, auditoría de quién cambió cada nota.
- **Frente 3:** despliegue real en un servicio gratuito (Render/Railway) como producción, alarmas del worker.
- **Frente 4:** pruebas de accesibilidad con `axe-core`, prueba de estrés hasta encontrar el punto de quiebre.
