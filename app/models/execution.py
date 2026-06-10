from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.quote import Quote


class Execution(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "executions"

    quote_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("quotes.id"), nullable=False, unique=True
    )
    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customers.id"), nullable=False
    )
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    # relationships
    quote: Mapped["Quote"] = relationship("Quote", back_populates="execution")

    def __repr__(self) -> str:
        return f"<Execution quote_id={self.quote_id} customer_id={self.customer_id}>"
