from enum import StrEnum

class QuoteStatus(StrEnum):
    PENDING = "pending"
    EXECUTED = "executed"
    EXPIRED = "expired"
    FAILED = "failed"
