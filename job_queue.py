import json
import time
import pika
from datetime import datetime
from config import (
    RABBITMQ_HOST, RABBITMQ_PORT, RABBITMQ_USER, RABBITMQ_PASSWORD,
    RABBITMQ_QUEUE, DEAD_LETTER_EXCHANGE, DEAD_LETTER_QUEUE
)


def get_rabbitmq_connection():
    """
    Creates and returns a new RabbitMQ connection using the configuration settings.
    """
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
    parameters = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        port=RABBITMQ_PORT,
        credentials=credentials,
    )
    return pika.BlockingConnection(parameters)


def setup_queue(channel):
    """
    Declare the primary job queue with dead-letter exchange settings.
    For a production system, the dead-letter settings should be refined.
    """
    # Declare dead-letter exchange and queue for persistent failures.
    channel.exchange_declare(exchange=DEAD_LETTER_EXCHANGE, exchange_type='fanout', durable=True)
    channel.queue_declare(queue=DEAD_LETTER_QUEUE, durable=True)
    channel.queue_bind(exchange=DEAD_LETTER_EXCHANGE, queue=DEAD_LETTER_QUEUE)

    # Declare our primary queue and set dead-letter exchange properties.
    queue_arguments = {
        "x-dead-letter-exchange": DEAD_LETTER_EXCHANGE,
    }
    channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True, arguments=queue_arguments)


def enqueue_job(job_payload: dict, max_retries: int = 5):
    """
    Attempts to enqueue the job payload into RabbitMQ.
    Implements a basic exponential backoff mechanism.
    Raises an exception if all retries fail.
    """
    message = json.dumps(job_payload)
    attempt = 0
    while attempt < max_retries:
        try:
            connection = get_rabbitmq_connection()
            channel = connection.channel()
            setup_queue(channel)  # Ensure the queue is set up with proper arguments

            # Publish the message to the specified queue.
            channel.basic_publish(
                exchange='',  # Direct publishing to the queue
                routing_key=RABBITMQ_QUEUE,
                body=message,
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Make message persistent
                )
            )
            connection.close()
            return  # Successfully enqueued the message
        except Exception as e:
            attempt += 1
            wait_time = 2 ** attempt  # Exponential backoff
            print(f"Enqueue attempt {attempt} failed: {e}. Retrying in {wait_time}s...")
            time.sleep(wait_time)
    # After max retries, raise an exception to be handled upstream.
    raise Exception("Failed to enqueue job after multiple attempts")
