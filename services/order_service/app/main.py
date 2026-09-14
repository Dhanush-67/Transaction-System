from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Order Service")

class orderResponse(BaseModel):
    order_id: int
    status: str
    cutomer_id: int
    amount: float

class orderRequest(BaseModel):
    customer_id: int
    amount: float


@app.get("/health")
def health():
    return {"status": "healthy"}

@app.get("/orders/{order_id}")
def get_order(order_id: int):
    return {"order_id": order_id, "status": "retrieved"}

@app.post("/orders", response_model=orderResponse, status_code=status.HTTP_201_CREATED)
def create_order(order: orderRequest):
    return orderResponse(order_id=1, status="created", cutomer_id=order.customer_id, amount=order.amount)