from fastapi import FastAPI, status, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from services.order_service.app.database import get_db
from services.order_service.app.models import Order

import httpx

app = FastAPI(title="Order Service")

class OrderResponse(BaseModel):
    order_id: int
    status: str
    customer_id: int
    amount: float

class OrderItem(BaseModel):
    product_id: int
    quantity: int

class OrderRequest(BaseModel):
    customer_id: int
    amount: float
    item: OrderItem


@app.get("/health")
def health():
    return {"status": "healthy"}

@app.get("/orders/{order_id}")
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)

    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    return {"order_id": order.id, "status": order.status, "customer_id": order.customer_id, "amount": order.amount}

@app.post("/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(order: OrderRequest, db: Session = Depends(get_db)):
    new_order = Order(customer_id=order.customer_id, amount=order.amount, status="PENDING")
    db.add(new_order)
    db.commit()
    db.refresh(new_order)

    try:
        inventory_response = httpx.post(
        "http://localhost:8002/reservations",
        json={
            "product_id": order.item.product_id,
            "quantity": order.item.quantity,
            "order_id": new_order.id,
        },
        )
    except httpx.RequestError as e:
        new_order.status = "FAILED"
        db.commit()
        db.refresh(new_order)

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Inventory service unavailable"
        )

    if inventory_response.status_code != status.HTTP_201_CREATED:
        new_order.status = "FAILED"
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not reserve inventory"
        )

    reservation_data = inventory_response.json()
    reservation_id = reservation_data["reservation_id"]

    new_order.reservation_id = reservation_id
    db.commit()

    try:
        payment_response = httpx.post(
            "http://localhost:8003/payments",
            json={
                "order_id": new_order.id,
                "amount": new_order.amount,
            }
        )

    except httpx.RequestError:
        new_order.status = "PAYMENT_UNKNOWN"
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment outcome unknown; order is awaiting recovery",
        )

    if not 200 <= payment_response.status_code < 300:
        new_order.status = "PAYMENT_UNKNOWN"
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Payment outcome unresolved; order is awaiting recovery",
        )

    payment_data = payment_response.json()
    payment_id = payment_data["payment_id"]

    new_order.payment_id = payment_id
    db.commit()

    if payment_data["status"] == "SUCCEEDED":

        if commit_reservations(reservation_id):
            new_order.status = "COMPLETED"
            db.commit()
            db.refresh(new_order)

        else:
            # Save the cleanup plan before making either request.
            new_order.status = "PENDING_COMPENSATION"
            new_order.refund_pending = True
            new_order.release_pending = True
            db.commit()

            recover_compensation(new_order, db)
            db.refresh(new_order)


    elif payment_data["status"] == "FAILED":
        new_order.status = "PENDING_COMPENSATION"
        new_order.refund_pending = False
        new_order.release_pending = True
        db.commit()

        recover_compensation(new_order, db)
        db.refresh(new_order)

    else:
        new_order.status = "PAYMENT_UNKNOWN"
        db.commit() 
    

    return OrderResponse(order_id=new_order.id, status=new_order.status, customer_id=order.customer_id, amount=order.amount)



def release_reservation(reservation_id: int) -> bool:
    try:
        response = httpx.post(
            f"http://localhost:8002/reservations/{reservation_id}/release"
        )
    except httpx.RequestError:
        return False

    return 200 <= response.status_code < 300


def commit_reservations(reservation_id: int) -> bool:
    try:
        response = httpx.post(
            f"http://localhost:8002/reservations/{reservation_id}/commit"
        )
    except httpx.RequestError:
        return False

    return 200 <= response.status_code < 300


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


@app.post("/orders/{order_id}/recover", response_model=OrderResponse)
def recover_order(order_id: int, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)

    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    if order.status == "PAYMENT_UNKNOWN":
        resolve_unknown_payment(order, db)

    if order.status == "PENDING_COMPENSATION":
        recover_compensation(order, db)

    db.refresh(order)

    return OrderResponse(
        order_id=order.id,
        status=order.status,
        customer_id=order.customer_id,
        amount=order.amount,
    )
