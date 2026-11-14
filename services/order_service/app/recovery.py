import httpx

from fastapi import status
from sqlalchemy.orm import Session

from services.order_service.app.models import Order



def resolve_unknown_payment(order: Order, db: Session) -> None:
    try:
        response = httpx.get(
            f"http://localhost:8003/payments/by-order/{order.id}"
        )
    except httpx.RequestError:
        return  # Payment unavailable. Check again later.

    if response.status_code != status.HTTP_200_OK:
        return  # Includes 404: no payment visible yet.

    payment_data = response.json()
    payment_status = payment_data["status"]

    order.payment_id = payment_data["payment_id"]

    if payment_status == "SUCCEEDED":
        order.refund_pending = True
        order.release_pending = True
        order.status = "PENDING_COMPENSATION"

    elif payment_status in ("FAILED", "REFUNDED"):
        order.refund_pending = False
        order.release_pending = True
        order.status = "PENDING_COMPENSATION"

    # PROCESSING leaves the order as PAYMENT_UNKNOWN.
    db.commit()



def recover_compensation(order: Order, db: Session) -> None:
    if order.status != "PENDING_COMPENSATION":
        return

    # Finish release before attempting any refund.
    if order.release_pending:
        if order.reservation_id is None:
            return

        if not release_reservation(order.reservation_id):
            try:
                reservation_response = httpx.get(
                    f"http://localhost:8002/reservations/{order.reservation_id}"
                )
            except httpx.RequestError:
                return
            if reservation_response.status_code != status.HTTP_200_OK:
                return

            reservation_data = reservation_response.json()

            if reservation_data["order_id"] != order.id:
                return

            if reservation_data["status"] == "COMMITTED":
                if order.payment_id is None:
                    return

                try:
                    payment_response = httpx.get(
                        f"http://localhost:8003/payments/{order.payment_id}"
                    )
                except httpx.RequestError:
                    return

                if payment_response.status_code != status.HTTP_200_OK:
                    return

                if payment_response.json()["status"] != "SUCCEEDED":
                    return

                order.release_pending = False
                order.refund_pending = False
                order.status = "COMPLETED"
                db.commit()
                return

            if reservation_data["status"] != "RELEASED":
                return

        order.release_pending = False
        db.commit()

    if order.refund_pending:
        if order.payment_id is None:
            return

        try:
            response = httpx.post(
                f"http://localhost:8003/payments/{order.payment_id}/refund"
            )
        except httpx.RequestError:
            return

        if response.status_code != status.HTTP_200_OK:
            return

        order.refund_pending = False
        db.commit()

    order.status = "FAILED"
    db.commit()


def release_reservation(reservation_id: int) -> bool:
    try:
        response = httpx.post(
            f"http://localhost:8002/reservations/{reservation_id}/release"
        )
    except httpx.RequestError:
        return False

    return 200 <= response.status_code < 300

def commit_reservations(reservation_id: int) -> bool:
    return False
    try:
        response = httpx.post(
            f"http://localhost:8002/reservations/{reservation_id}/commit"
        )
    except httpx.RequestError:
        return False

    return 200 <= response.status_code < 300