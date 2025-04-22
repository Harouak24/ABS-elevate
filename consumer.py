import pika, json
from config import RABBITMQ_HOST, RABBITMQ_PORT, RABBITMQ_USER, RABBITMQ_PASSWORD, RABBITMQ_QUEUE
from worker import process_job

def on_message(ch, method, properties, body):
    job = json.loads(body)
    try:
        process_job(job)
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception:
        # on fatal error, dead-letter
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

if __name__ == "__main__":
    creds = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
    params = pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=creds)
    conn = pika.BlockingConnection(params)
    ch = conn.channel()
    ch.queue_declare(queue=RABBITMQ_QUEUE, durable=True)
    ch.basic_qos(prefetch_count=1)
    ch.basic_consume(RABBITMQ_QUEUE, on_message)
    print(" [*] Waiting for jobs. To exit press CTRL+C")
    ch.start_consuming()