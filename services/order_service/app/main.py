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

    try:
        payment_response = httpx.post(
            "http://localhost:8003/payments",
            json={
                "order_id": new_order.id,
                "amount": new_order.amount,
            }
        )

    except httpx.RequestError:
        release_succeeded = release_reservation(reservation_id)
        new_order.status = (
            "FAILED" if release_succeeded else "PENDING_COMPENSATION"
        )

        db.commit()
        db.refresh(new_order)

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment service unavailable"
        )

    if not 200 <= payment_response.status_code < 300:
        release_succeeded = release_reservation(reservation_id)

        new_order.status = (
            "FAILED" if release_succeeded else "PENDING_COMPENSATION"
        )
        db.commit()
        db.refresh(new_order)

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Payment service returned an unsuccessful response",
        )

    payment_data = payment_response.json()

    if payment_data["status"] == "SUCCEEDED":
        payment_id = payment_data["payment_id"]

        if commit_reservations(reservation_id):
            new_order.status = "COMPLETED"
            db.commit()
            db.refresh(new_order)

        else:
            refund_succeeded = False
            release_succeeded = False
            #the inventory service failed to commit the reservation, we need to refund the payment
            try:
                refund_response = httpx.post(
                    f"http://localhost:8003/payments/{payment_id}/refund"
                )

                if refund_response.status_code == status.HTTP_200_OK:
                    refund_succeeded = True

            except httpx.RequestError:
                pass

            release_succeeded = release_reservation(reservation_id)

            if refund_succeeded and release_succeeded:
                new_order.status = "FAILED"
            else:
                new_order.status = "PENDING_COMPENSATION"

            db.commit()
            db.refresh(new_order)


    else:

        release_succeeded = release_reservation(reservation_id)

        if release_succeeded:
            new_order.status = "FAILED"
        else:
            new_order.status = "PENDING_COMPENSATION"

        db.commit()
        db.refresh(new_order)
    

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
