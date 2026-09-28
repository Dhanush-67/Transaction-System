from fastapi import FastAPI, status
from pydantic import BaseModel
from fastapi import Depends
from sqlalchemy.orm import Session

from services.payment_service.app.database import get_db
from services.payment_service.app.models import Payment

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
def get_payment(payment_id: int, db: Session = Depends(get_db)):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        return {"error": "Payment not found"}
    return {"payment_id": payment.id, "status": "retrieved"}




@app.post("/payments", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
def create_payment(payment: PaymentRequest, db: Session = Depends(get_db)):
    new_payment = Payment(order_id=payment.order_id, amount=payment.amount, status="pending")
    db.add(new_payment)
    db.commit()
    db.refresh(new_payment)
    return PaymentResponse(payment_id=new_payment.id, status="created", order_id=payment.order_id, amount=payment.amount)




