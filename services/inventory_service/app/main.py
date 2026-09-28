from fastapi import FastAPI, status
from pydantic import BaseModel

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from services.inventory_service.app.database import get_db
from services.inventory_service.app.models import InventoryItem, Reservation

app = FastAPI(title="Inventory Service")

class InventoryItemResponse(BaseModel):
    product_id: int
    available_quantity: int
    reserved_quantity: int

class InventoryItemRequest(BaseModel):
    product_id: int
    quantity: int

class ReservationRequest(BaseModel):
    product_id: int
    quantity: int
    order_id: int

class ReservationResponse(BaseModel):
    reservation_id: int
    status: str
    product_id: int
    quantity: int
    order_id: int

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.get("/items/{product_id}", response_model=InventoryItemResponse)
def get_item(product_id: int, db: Session = Depends(get_db)):

    item = db.get(InventoryItem, product_id)

    if item is None:
        raise HTTPException(
            status_code=404,
            detail="Inventory item not found"
        )
    
    return InventoryItemResponse(
        product_id=product_id,
        available_quantity=item.available_quantity,
        reserved_quantity=item.reserved_quantity
    )

@app.post("/reservations", response_model=ReservationResponse, status_code=status.HTTP_201_CREATED)
def create_reservation(reservation: ReservationRequest, db: Session = Depends(get_db)):

    item = db.get(InventoryItem, reservation.product_id)

    if item is None:
        raise HTTPException(
            status_code=404,
            detail="Inventory item not found"
        )

    remaining_stock = item.available_quantity - item.reserved_quantity

    if reservation.quantity > remaining_stock:
        raise HTTPException(
            status_code=400,
            detail="Not enough inventory available"
        )

    item.reserved_quantity += reservation.quantity

    new_reservation = Reservation(
        product_id=reservation.product_id,
        quantity=reservation.quantity,
        order_id=reservation.order_id,
        status="RESERVED"
    )
    db.add(new_reservation)
    db.commit()
    db.refresh(new_reservation)

    return ReservationResponse(
        reservation_id=new_reservation.id,
        status=new_reservation.status,
        product_id=new_reservation.product_id,
        quantity=new_reservation.quantity,
        order_id=new_reservation.order_id
    )

@app.post("/reservations/{reservation_id}/commit")
def commit_reservation(reservation_id: int, db: Session = Depends(get_db)):
    reservation = db.get(Reservation, reservation_id)

    if reservation is None:
        raise HTTPException(
            status_code=404,
            detail="Reservation not found"
        )

    if reservation.status != "RESERVED":
        raise HTTPException(
            status_code=400,
            detail="Reservation is not active"
        )

    item = db.get(InventoryItem, reservation.product_id)

    if item is None:
        raise HTTPException(
            status_code=404,
            detail="Inventory item not found"
        )

    if reservation.quantity > item.reserved_quantity:
        raise HTTPException(
            status_code=400,
            detail="Not enough reserved inventory to commit"
        )

    item.reserved_quantity -= reservation.quantity
    item.available_quantity -= reservation.quantity
    reservation.status = "COMMITTED"

    db.commit()
    db.refresh(reservation)

    return {
        "reservation_id": reservation.id,
        "status": reservation.status
    }


@app.post("/reservations/{reservation_id}/release")
def release_reservation(reservation_id: int, db: Session = Depends(get_db)):
    reservation = db.get(Reservation, reservation_id)

    if reservation is None:
        raise HTTPException(
            status_code=404,
            detail="Reservation not found"
        )

    if reservation.status != "RESERVED":
        raise HTTPException(
            status_code=400,
            detail="Reservation is not active"
        )

    item = db.get(InventoryItem, reservation.product_id)

    if item is None:
        raise HTTPException(
            status_code=404,
            detail="Inventory item not found"
        )

    item.reserved_quantity -= reservation.quantity
    reservation.status = "RELEASED"

    db.commit()
    db.refresh(reservation)

    return {
        "reservation_id": reservation.id,
        "status": reservation.status
    }



