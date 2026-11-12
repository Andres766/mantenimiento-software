"""Worker asíncrono: consume eventos de SQS y notifica que el boletín está listo.

Si un mensaje no se puede procesar NO se borra: SQS lo vuelve a entregar y, tras MAX_REINTENTOS,
lo mueve a la DLQ (notasqa-eventos-dlq) para revisarlo sin bloquear la cola."""
import json
import logging
import os
import signal
import time

import requests
from botocore.exceptions import BotoCoreError, ClientError

from src.app import storage

log = logging.getLogger("notasqa.worker")
logging.basicConfig(level=logging.INFO, format="%(message)s")


def construir_mensaje(evento: dict) -> str:
    if evento.get("evento") != "boletin_generado":
        raise ValueError(f"Evento desconocido: {evento.get('evento')}")
    b = storage.leer_boletin(evento["s3_key"])
    return (f"Boletín listo — estudiante {b['estudiante_id']}, {b['asignatura']}: "
            f"{b['definitiva']:.1f} ({b['estado']})")


def notificar(texto: str) -> None:
    """Telegram si hay credenciales en el entorno; si no, solo log (modo local)."""
    token, chat_id = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if token and chat_id:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat_id, "text": texto}, timeout=5).raise_for_status()
    log.info(json.dumps({"evento": "notificacion", "texto": texto}))


def procesar_lote(enviar=notificar, espera: int = 10) -> dict:
    sqs = storage.cliente("sqs")
    url = storage.url_cola()
    mensajes = sqs.receive_message(QueueUrl=url, MaxNumberOfMessages=10,
                                   WaitTimeSeconds=espera).get("Messages", [])
    resultado = {"procesados": 0, "fallidos": 0}
    for mensaje in mensajes:
        try:
            enviar(construir_mensaje(json.loads(mensaje["Body"])))
        except (ValueError, KeyError, ClientError, BotoCoreError, requests.RequestException) as error:
            resultado["fallidos"] += 1
            log.warning(json.dumps({"evento": "mensaje_fallido", "detalle": str(error)}))
            continue                           # sin borrar: se reintenta y luego va a la DLQ
        sqs.delete_message(QueueUrl=url, ReceiptHandle=mensaje["ReceiptHandle"])
        resultado["procesados"] += 1
    return resultado


def main() -> None:  # pragma: no cover - bucle infinito, se prueba procesar_lote
    activo = {"si": True}
    signal.signal(signal.SIGTERM, lambda *_: activo.update(si=False))
    log.info(json.dumps({"evento": "worker_iniciado", "cola": storage.COLA}))
    while activo["si"]:
        try:
            procesar_lote()
        except (BotoCoreError, ClientError) as error:   # cola caída o aún arrancando: esperar, no morir
            log.warning(json.dumps({"evento": "cola_no_disponible", "detalle": str(error)}))
            time.sleep(2)


if __name__ == "__main__":  # pragma: no cover
    main()
