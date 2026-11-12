"""Prueba end-to-end del flujo completo contra la API real en Docker:
login docente -> registrar nota -> generar boletín (S3 + evento SQS en LocalStack).
Solo usa la librería estándar para poder correr en cualquier runner.
La clave del docente se lee de DOCENTE_CLAVE."""
import json
import os
import sys
import urllib.request
from urllib.parse import urlsplit

# Solo los destinos del proyecto: evita que el script se use para pedir URLs arbitrarias (SSRF)
HOSTS_PERMITIDOS = {"localhost": "localhost", "127.0.0.1": "127.0.0.1", "api": "api"}


def validar_base(base: str) -> str:
    partes = urlsplit(base)
    if partes.scheme not in ("http", "https") or partes.hostname not in HOSTS_PERMITIDOS:
        raise ValueError(f"URL no permitida: {base} (hosts válidos: {', '.join(HOSTS_PERMITIDOS)})")
    esquema = "https" if partes.scheme == "https" else "http"
    puerto = int(partes.port or (443 if esquema == "https" else 80))
    return f"{esquema}://{HOSTS_PERMITIDOS[partes.hostname]}:{puerto}"


def post(url: str, cuerpo: dict | None = None, token: str | None = None) -> tuple[int, dict]:
    cabeceras = {"Content-Type": "application/json"}
    if token:
        cabeceras["Authorization"] = f"Bearer {token}"
    peticion = urllib.request.Request(url, data=json.dumps(cuerpo or {}).encode(), method="POST",
                                      headers=cabeceras)
    with urllib.request.urlopen(peticion, timeout=10) as respuesta:
        return respuesta.status, json.loads(respuesta.read())


def main(base: str) -> int:
    try:
        base = validar_base(base)
    except ValueError as error:
        print(f"[ERROR] {error}")
        return 2
    estado, sesion = post(f"{base}/api/v1/auth/token",
                          {"usuario": "docente", "clave": os.environ.get("DOCENTE_CLAVE", "")})
    print(f"[1/3] Login docente -> {estado}")
    token = sesion.get("access_token")
    if estado != 200 or not token:
        return 1
    estado, nota = post(f"{base}/api/v1/calificaciones", {
        "estudiante_id": 2026, "asignatura": "Pruebas y Mantenimiento",
        "corte1": 4.0, "corte2": 4.5, "corte3": 5.0, "creditos": 3}, token)
    print(f"[2/3] POST calificación -> {estado} definitiva={nota.get('definitiva')} estado={nota.get('estado')}")
    if estado != 201 or nota.get("estado") != "EXCELENTE":
        return 1
    estado, boletin = post(f"{base}/api/v1/calificaciones/{nota['id']}/boletin", token=token)
    print(f"[3/3] POST boletín -> {estado} s3_key={boletin.get('s3_key')}")
    return 0 if estado == 201 and boletin.get("s3_key") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"))
