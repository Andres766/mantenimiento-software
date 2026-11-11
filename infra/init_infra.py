"""IaC: aprovisiona el bucket S3 y la cola SQS (idempotente: correrlo 1 o 100 veces da lo mismo)."""
from src.app import storage


def aprovisionar() -> dict:
    s3 = storage._cliente("s3")
    sqs = storage._cliente("sqs")
    existentes = [b["Name"] for b in s3.list_buckets().get("Buckets", [])]
    if storage.BUCKET not in existentes:
        s3.create_bucket(Bucket=storage.BUCKET)
    url = sqs.create_queue(QueueName=storage.COLA)["QueueUrl"]
    return {"bucket": storage.BUCKET, "cola": url}


if __name__ == "__main__":
    print("=== APROVISIONANDO INFRAESTRUCTURA (IaC) ===")
    print(aprovisionar())
