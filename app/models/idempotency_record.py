from sqlalchemy import (
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin, UUIDMixin


class IdempotencyRecord(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "idempotency_records"

    customer_id: Mapped[str] = mapped_column(String(36), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        Index(
            "ix_idempotency_customer_key",
            "customer_id",
            "idempotency_key",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        return f"<IdempotencyRecord id={self.customer_id} key={self.idempotency_key}>"
