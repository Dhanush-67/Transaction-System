import time
import logging

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
    logger.info("Recovery worker started")

    while True:
        try:
            # Discover unfinished orders
            with SessionLocal() as db:
                stmt = select(Order.id).where(
                    Order.status.in_([
                        "PAYMENT_UNKNOWN",
                        "PENDING_COMPENSATION"
                    ])
                )

                order_ids = db.scalars(stmt).all()

            logger.info("Found %d unfinished orders", len(order_ids))

            # Recover orders individually
            for order_id in order_ids:
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

        except Exception:
            logger.exception("Failed to query unfinished orders")

        time.sleep(10)

if __name__ == "__main__":
    run_worker()
