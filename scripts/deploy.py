"""CD: smoke test en Staging -> promoción o rollback + alerta en Telegram (semana 9)."""
import os
import sys

import requests

STAGING_URL = os.getenv("STAGING_URL", "http://localhost:8001")
VERSION = os.getenv("APP_VERSION", "dev")


def notificar_telegram(mensaje: str) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")  # siempre desde GitHub Secrets, nunca en el código
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("(Telegram no configurado, se omite la notificación)")
        return
    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat_id, "text": mensaje}, timeout=5)
    except requests.RequestException as error:
        print(f"No se pudo notificar: {error}")


def smoke_test(base_url: str) -> bool:
    try:
        salud = requests.get(f"{base_url}/health", timeout=3)
        lista = requests.get(f"{base_url}/api/v1/calificaciones", timeout=3)
    except requests.RequestException as error:
        print(f"[ERROR DE CONEXIÓN] {error}")
        return False
    return salud.status_code == 200 and lista.status_code == 200


def main() -> int:
    print(f"=== CD NotasQA v{VERSION} === Smoke test en {STAGING_URL}")
    if smoke_test(STAGING_URL):
        print("[OK] Staging sano -> PROMOVER a producción")
        notificar_telegram(f"DESPLIEGUE EXITOSO: NotasQA v{VERSION} en producción")
        return 0
    print("[FALLO] Staging no sano -> ROLLBACK: producción se queda en la versión estable")
    notificar_telegram(f"ROLLBACK AUTOMÁTICO: NotasQA v{VERSION} falló en Staging")
    return 1


if __name__ == "__main__":
    sys.exit(main())
