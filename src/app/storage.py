"""Acceso a S3 y SQS (LocalStack en local, moto en pruebas, AWS real si se quisiera)."""
import json
import os

import boto3

BUCKET = os.getenv("BUCKET_BOLETINES", "notasqa-boletines")
COLA = os.getenv("COLA_EVENTOS", "notasqa-eventos")
COLA_DLQ = os.getenv("COLA_EVENTOS_DLQ", "notasqa-eventos-dlq")


def cliente(servicio: str):
    return boto3.client(
        servicio,
        endpoint_url=os.getenv("AWS_ENDPOINT_URL"),  # http://localstack:4566 en Docker
        region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "test"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "test"),
    )


def url_cola(nombre: str = COLA) -> str:
    return cliente("sqs").get_queue_url(QueueName=nombre)["QueueUrl"]


def publicar_boletin(calificacion: dict) -> str:
    """Guarda el boletín en S3 y emite un evento en SQS. Devuelve la llave S3."""
    llave = f"boletines/{calificacion['estudiante_id']}/{calificacion['id']}.json"
    cliente("s3").put_object(
        Bucket=BUCKET, Key=llave, Body=json.dumps(calificacion).encode("utf-8"),
        ContentType="application/json",
    )
    cliente("sqs").send_message(QueueUrl=url_cola(),
                                MessageBody=json.dumps({"evento": "boletin_generado", "s3_key": llave}))
    return llave


def leer_boletin(llave: str) -> dict:
    return json.loads(cliente("s3").get_object(Bucket=BUCKET, Key=llave)["Body"].read())
