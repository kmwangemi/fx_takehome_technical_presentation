from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Index,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin, UUIDMixin


class ExchangeRate(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "exchange_rates"

    from_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    to_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    # Mid-market rate stored as string to preserve Decimal precision
    mid_rate: Mapped[str] = mapped_column(String(40), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index(
            "ix_exchange_rates_pair_fetched",
            "from_currency",
            "to_currency",
            "fetched_at",
        ),
    )

    def __repr__(self) -> str:
        return f"<ExchangeRate from_currency={self.from_currency} to_currency={self.to_currency}>"
