import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDMixin
from app.utils.enums import QuoteStatus

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.execution import Execution


def _uuid() -> str:
    return str(uuid.uuid4())


class Quote(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "quotes"

    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customers.id"), nullable=False
    )
    from_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    to_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    from_amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    to_amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # Effective rate as Decimal string
    effective_rate: Mapped[str] = mapped_column(String(40), nullable=False)
    rate_age_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    correlation_id: Mapped[str] = mapped_column(
        String(36), nullable=False, default=_uuid
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=QuoteStatus.PENDING
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    # relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="quotes")
    execution: Mapped["Execution | None"] = relationship(
        "Execution", back_populates="quote"
    )

    __table_args__ = (Index("ix_quotes_customer_status", "customer_id", "status"),)

    def __repr__(self) -> str:
        return (
            f"<Quote customer_id={self.customer_id} from_currency={self.from_currency}>"
        )
