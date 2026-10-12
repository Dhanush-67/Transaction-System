from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int]
    amount: Mapped[float]
    status: Mapped[str] = mapped_column(default="created")
    reservation_id: Mapped[int | None] = mapped_column(nullable=True)
    payment_id: Mapped[int | None] = mapped_column(nullable=True)

    refund_pending: Mapped[bool] = mapped_column(default=False)
    release_pending: Mapped[bool] = mapped_column(default=False)