from fastapi import FastAPI, status
from pydantic import BaseModel

app = FastAPI(title="Inventory Service")

class InventoryItemResponse(BaseModel):
    product_id: int
    available_quantity: int
    reserved_quantity: int

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
def get_item(product_id: int):
    return InventoryItemResponse(
        product_id=product_id,
        available_quantity=100,
        reserved_quantity=10
    )

@app.post("/reservations", response_model=ReservationResponse, status_code=status.HTTP_201_CREATED)
def create_reservation(reservation: ReservationRequest):
    return ReservationResponse(reservation_id=1, status="RESERVED", product_id=reservation.product_id, quantity=reservation.quantity, order_id=reservation.order_id)

@app.post("/reservations/{reservation_id}/commit")
def commit_reservation(reservation_id: int):
    return {
        "reservation_id": reservation_id,
        "status": "COMMITTED"
    }


@app.post("/reservations/{reservation_id}/release")
def release_reservation(reservation_id: int):
    return {
        "reservation_id": reservation_id,
        "status": "RELEASED"
    }


