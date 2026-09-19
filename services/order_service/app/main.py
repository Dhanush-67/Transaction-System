from fastapi import FastAPI, status, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from services.order_service.app.database import get_db
from services.order_service.app.models import Order

app = FastAPI(title="Order Service")

class OrderResponse(BaseModel):
    order_id: int
    status: str
    customer_id: int
    amount: float

class OrderRequest(BaseModel):
    customer_id: int
    amount: float


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
    new_order = Order(customer_id=order.customer_id, amount=order.amount, status="Pending")
    db.add(new_order)
    db.commit()
    db.refresh(new_order)
    return OrderResponse(order_id=new_order.id, status=new_order.status, customer_id=order.customer_id, amount=order.amount)