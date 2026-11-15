import logging
import json
import pika

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

    channel.queue_declare(
        queue="order_recovery_retry",
        durable=True,
        arguments={
            "x-message-ttl": 10000,
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": "order_recovery",
        }
    )

    channel.basic_qos(prefetch_count=1)

    channel.basic_consume(
        queue="order_recovery",
        on_message_callback=process_message,
        auto_ack=False
    )

    channel.confirm_delivery()
    channel.start_consuming()


def process_message(ch, method, properties, body):
    message = json.loads(body)
    order_id = message["order_id"]

    recovery_complete = False

    try:
        with SessionLocal() as db:
            order = db.get(Order, order_id)

            if order is None:
                recovery_complete = True

            else:
                if order.status == "PAYMENT_UNKNOWN":
                    resolve_unknown_payment(order, db)

                if order.status == "PENDING_COMPENSATION":
                    recover_compensation(order, db)

                if order.status in ("COMPLETED", "FAILED"):
                    recovery_complete = True

    except Exception:
        logger.exception("Failed to recover order %s", order_id)

    if recovery_complete:
        ch.basic_ack(delivery_tag=method.delivery_tag)
        logger.info("Recovery complete for order %s", order_id)
    else:
        ch.basic_publish(
                exchange="",
                routing_key="order_recovery_retry",
                body=json.dumps({"order_id": order_id}),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                ),
                mandatory=True,
            )
        ch.basic_ack(delivery_tag=method.delivery_tag)

if __name__ == "__main__":
    run_worker()
