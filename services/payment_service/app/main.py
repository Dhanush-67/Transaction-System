from fastapi import FastAPI, status
from pydantic import BaseModel
from fastapi import Depends
from sqlalchemy.orm import Session
from fastapi import HTTPException

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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )
    return {"payment_id": payment.id, "status": payment.status}




@app.post("/payments", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
def create_payment(payment: PaymentRequest, db: Session = Depends(get_db)):
    new_payment = Payment(order_id=payment.order_id, amount=payment.amount, status="PROCESSING")
    db.add(new_payment)
    db.commit()
    db.refresh(new_payment)

    new_payment.status = "SUCCEEDED"
    db.commit()
    db.refresh(new_payment)

    

    return PaymentResponse(payment_id=new_payment.id, status=new_payment.status, order_id=payment.order_id, amount=payment.amount)


@app.post("/payments/{payment_id}/refund")
def refund_payment(payment_id: int, db: Session = Depends(get_db)):
    payment = db.get(Payment, payment_id)

    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )

    if payment.status != "SUCCEEDED":
        raise HTTPException(
            status_code = status.HTTP_400_BAD_REQUEST,
            detail = "Payment cannot be refunded"
        )

    payment.status = "REFUNDED"

    db.commit()
    db.refresh(payment)

    return {
        "payment_id": payment.id,
        "status": payment.status
    }
