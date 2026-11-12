"""CD (semana 9): smoke test en Staging -> listo para producción o rollback + alertas en Telegram.

Uso:
  python scripts/deploy.py                      # smoke test contra STAGING_URL
  python scripts/deploy.py --notificar "texto"  # solo enviar un mensaje (lo usan los jobs de CD)
"""
import os
import sys

import requests

STAGING_URL = os.getenv("STAGING_URL", "http://localhost:8001")
VERSION = os.getenv("APP_VERSION", "dev")[:7]


def notificar_telegram(mensaje: str) -> None:
    """Nunca rompe el despliegue, pero deja un ::warning:: visible en Actions si el aviso no sale."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()  # siempre desde GitHub Secrets, nunca en el código
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print(f"::warning::Telegram no configurado (faltan secretos). Mensaje: {mensaje}")
        return
    try:
        respuesta = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                                  json={"chat_id": chat_id, "text": mensaje}, timeout=5)
    except requests.RequestException as error:
        print(f"::warning::No se pudo notificar a Telegram: {error}")
        return
    if respuesta.ok:
        print(f"Telegram: mensaje enviado ({mensaje})")
    else:                                   # 401 = token inválido, 400 = chat_id inválido
        print(f"::warning::Telegram rechazó el mensaje ({respuesta.status_code}): {respuesta.text[:200]}")


def smoke_test(base_url: str) -> bool:
    """Rutas públicas: salud del servicio, interfaz web y rechazo correcto sin token."""
    try:
        salud = requests.get(f"{base_url}/health", timeout=3)
        interfaz = requests.get(f"{base_url}/ui/", timeout=3)
        protegida = requests.get(f"{base_url}/api/v1/calificaciones", timeout=3)
    except requests.RequestException as error:
        print(f"[ERROR DE CONEXIÓN] {error}")
        return False
    print(f"  /health={salud.status_code}  /ui/={interfaz.status_code}  "
          f"/api/v1/calificaciones sin token={protegida.status_code} (se espera 401)")
    return salud.status_code == 200 and interfaz.status_code == 200 and protegida.status_code == 401


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[0] == "--notificar":
        notificar_telegram(argv[1])
        return 0
    print(f"=== CD NotasQA {VERSION} === Smoke test en {STAGING_URL}")
    if smoke_test(STAGING_URL):
        print("[OK] Staging sano -> la versión queda lista para aprobación a producción")
        notificar_telegram(f"STAGING OK: NotasQA {VERSION} espera aprobación para producción")
        return 0
    print("[FALLO] Staging no sano -> ROLLBACK: producción se queda en la versión estable")
    notificar_telegram(f"ROLLBACK AUTOMÁTICO: NotasQA {VERSION} falló en Staging")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
