from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.quote_schema import QuoteRequest, QuoteResponse
from app.services.quote_service import create_quote

router = APIRouter(prefix="/quotes", tags=["quotes"])


@router.post("", response_model=QuoteResponse, status_code=201)
async def post_quote(
    body: QuoteRequest, db: AsyncSession = Depends(get_db)
) -> QuoteResponse:
    quote = await create_quote(
        db=db,
        customer_id=body.customer_id,
        from_currency=body.from_currency,
        to_currency=body.to_currency,
        from_amount_minor=body.from_amount_minor,
    )
    return QuoteResponse(
        quote_id=quote.id,
        customer_id=quote.customer_id,
        from_currency=quote.from_currency,
        to_currency=quote.to_currency,
        from_amount_minor=quote.from_amount_minor,
        to_amount_minor=quote.to_amount_minor,
        effective_rate=quote.effective_rate,
        rate_age_seconds=quote.rate_age_seconds,
        correlation_id=quote.correlation_id,
        created_at=quote.created_at.isoformat(),
        expires_at=quote.expires_at.isoformat(),
        status=quote.status,
    )
