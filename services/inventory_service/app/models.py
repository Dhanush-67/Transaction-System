from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    available_quantity: Mapped[int]
    reserved_quantity: Mapped[int]


class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int]
    order_id: Mapped[int]
    quantity: Mapped[int]
    status: Mapped[str]