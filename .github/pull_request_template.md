## ¿Qué cambia?

<!-- Una o dos frases. Enlaza el issue si existe (Closes #N). -->

## Frente

- [ ] 1. Lógica y datos
- [ ] 2. API y seguridad
- [ ] 3. DevOps y nube
- [ ] 4. Rendimiento y E2E

## Lista de verificación

- [ ] Agregué o actualicé pruebas (BVA si hay fronteras) y `python -m pytest` pasa en local.
- [ ] La cobertura sigue ≥ 80 % y no aparecen code smells nuevos en SonarCloud.
- [ ] No hay claves, tokens ni contraseñas en el código.
- [ ] Si cambié la interfaz, corrí `python -m pytest -m e2e --no-cov tests/e2e`.
- [ ] Si cambié reglas de negocio, corrí `mutmut run` sin mutantes sobrevivientes.
- [ ] Actualicé el README si cambia cómo se ejecuta algo.

## Evidencia

<!-- Captura, salida de terminal o enlace al run de Actions. -->
