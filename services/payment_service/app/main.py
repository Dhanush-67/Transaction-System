from fastapi import FastAPI, status
from pydantic import BaseModel

app = FastAPI(title="Payment Service")

class PaymentResponse(BaseModel):
    payment_id: int
    status: str
    order_id: int
    amount: float

class PaymentRequest(BaseModel):
    order_id: int
    amount: float

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.get("/payments/{payment_id}")
def get_payment(payment_id: int):
    return {"payment_id": payment_id, "status": "retrieved"}




@app.post("/payments", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
def create_payment(payment: PaymentRequest):
    return PaymentResponse(payment_id=1, status="created", order_id=payment.order_id, amount=payment.amount)




