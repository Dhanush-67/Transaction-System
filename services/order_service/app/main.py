from fastapi import FastAPI, status
from pydantic import BaseModel

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
def get_order(order_id: int):
    return {"order_id": order_id, "status": "retrieved"}

@app.post("/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(order: OrderRequest):
    return OrderResponse(order_id=1, status="created", customer_id=order.customer_id, amount=order.amount)