from typing import TYPE_CHECKING, List

from sqlalchemy import (
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.balance import Balance
    from app.models.quote import Quote


class Customer(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "customers"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # relationships
    balances: Mapped[List["Balance"]] = relationship(
        "Balance", back_populates="customer", lazy="selectin"
    )
    quotes: Mapped[List["Quote"]] = relationship("Quote", back_populates="customer")

    def __repr__(self) -> str:
        return f"<Customer name={self.name}>"
