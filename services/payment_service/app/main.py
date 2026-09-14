from fastapi import FastAPI

app = FastAPI(title="Payment Service")

class paymentResponse(BaseModel):
    payment_id: int
    status: str
    order_id: int
    amount: float

class paymentRequest(BaseModel):
    order_id: int
    amount: float

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.get("/payments/{payment_id}")
def get_payment(payment_id: int):
    return {"payment_id": payment_id, "status": "retrieved"}



@app.post("/payments", response_model=paymentResponse, status_code=status.HTTP_201_CREATED)
def create_payment(payment: paymentRequest):
    return paymentResponse(payment_id=1, status="created")




