from pydantic import BaseModel, Field

from app.utils.currencies import Currency


class QuoteRequest(BaseModel):
    customer_id: str
    from_currency: Currency
    to_currency: Currency
    from_amount_minor: int = Field(
        ..., gt=0, description="Amount in minor units (e.g. cents)"
    )


class QuoteResponse(BaseModel):
    quote_id: str
    customer_id: str
    from_currency: str
    to_currency: str
    from_amount_minor: int
    to_amount_minor: int
    effective_rate: str
    rate_age_seconds: int
    correlation_id: str
    created_at: str
    expires_at: str
    status: str
