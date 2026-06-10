from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.customer import Customer


class Balance(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "balances"

    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    # Stored in minor units (e.g. cents). Never floats.
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    # relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="balances")

    __table_args__ = (
        Index("ix_balances_customer_currency", "customer_id", "currency", unique=True),
    )

    def __repr__(self) -> str:
        return f"<Balance id={self.customer_id} currency={self.currency}>"
