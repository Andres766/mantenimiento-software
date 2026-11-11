"""Prueba end-to-end del flujo completo contra la API real en Docker:
registrar nota -> generar boletín -> queda en S3 (LocalStack) y se emite evento SQS.
Solo usa la librería estándar para poder correr en cualquier runner."""
import json
import sys
import urllib.request


def post(url: str, cuerpo: dict | None = None) -> tuple[int, dict]:
    datos = json.dumps(cuerpo or {}).encode()
    peticion = urllib.request.Request(url, data=datos, method="POST",
                                      headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(peticion, timeout=10) as respuesta:
        return respuesta.status, json.loads(respuesta.read())


def main(base: str) -> int:
    estado, nota = post(f"{base}/api/v1/calificaciones", {
        "estudiante_id": 2026, "asignatura": "Pruebas y Mantenimiento",
        "corte1": 4.0, "corte2": 4.5, "corte3": 5.0})
    print(f"[1/2] POST calificación -> {estado} definitiva={nota['definitiva']} estado={nota['estado']}")
    if estado != 201 or nota["estado"] != "EXCELENTE":
        return 1
    estado, boletin = post(f"{base}/api/v1/calificaciones/{nota['id']}/boletin")
    print(f"[2/2] POST boletín -> {estado} s3_key={boletin.get('s3_key')}")
    return 0 if estado == 201 and boletin.get("s3_key") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"))
