import time
import logging
import json
import pika

from sqlalchemy import select

from services.order_service.app.database import SessionLocal
from services.order_service.app.models import Order
from services.order_service.app.recovery import (
    resolve_unknown_payment,
    recover_compensation,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_worker():
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host="localhost")
    )

    channel = connection.channel()

    channel.queue_declare(
        queue="order_recovery",
        durable=True
    )

    channel.basic_qos(prefetch_count=1)

    channel.basic_consume(
        queue="order_recovery",
        on_message_callback=process_message,
        auto_ack=False
    )

    channel.start_consuming()


def process_message(ch, method, properties, body):
    message = json.loads(body)
    order_id = message["order_id"]
    logger.info("Recovery worker started")

    # 1. Query PostgreSQL for this order
    try:
        with SessionLocal() as db:
            order = db.get(Order, order_id)

            if order is None:
                continue

            if order.status == "PAYMENT_UNKNOWN":
                resolve_unknown_payment(order, db)

            if order.status == "PENDING_COMPENSATION":
                recover_compensation(order, db)
    
    except Exception:
        logger.exception(
            "Failed to recover order %s",
            order_id
        )

    # 2. Run the appropriate recovery functions

    # 3. Check whether the order is terminal

    # 4. ACK if terminal, otherwise schedule retry

if __name__ == "__main__":
    run_worker()
