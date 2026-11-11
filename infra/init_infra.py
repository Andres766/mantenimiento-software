"""IaC: aprovisiona el bucket S3, la cola de eventos y su cola de mensajes fallidos (DLQ).
Idempotente: correrlo 1 o 100 veces deja el mismo estado."""
import json

from src.app import storage

MAX_REINTENTOS = 3   # tras 3 entregas fallidas el mensaje pasa a la DLQ


def aprovisionar() -> dict:
    s3 = storage.cliente("s3")
    sqs = storage.cliente("sqs")
    existentes = [b["Name"] for b in s3.list_buckets().get("Buckets", [])]
    if storage.BUCKET not in existentes:
        s3.create_bucket(Bucket=storage.BUCKET)
    url_dlq = sqs.create_queue(QueueName=storage.COLA_DLQ)["QueueUrl"]
    arn_dlq = sqs.get_queue_attributes(QueueUrl=url_dlq, AttributeNames=["QueueArn"])["Attributes"]["QueueArn"]
    politica = json.dumps({"deadLetterTargetArn": arn_dlq, "maxReceiveCount": str(MAX_REINTENTOS)})
    url = sqs.create_queue(QueueName=storage.COLA,
                           Attributes={"RedrivePolicy": politica, "VisibilityTimeout": "30"})["QueueUrl"]
    return {"bucket": storage.BUCKET, "cola": url, "dlq": url_dlq}


if __name__ == "__main__":
    print("=== APROVISIONANDO INFRAESTRUCTURA (IaC) ===")
    print(aprovisionar())
