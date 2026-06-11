"""
Quote service.

Generates a quote (rate + amounts) for a given currency pair and amount.
Does NOT lock or reserve balance — balance check happens at execute time.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.quote import Quote
from app.services.rate_service import get_latest_rate
from app.utils.currencies import CROSS_PAIRS_VIA_USD, SUPPORTED_PAIRS, Currency
from app.utils.decimal import (
    apply_spread,
    compose_cross_rate,
    from_minor_units,
    to_minor_units,
)
from app.utils.exceptions import UnsupportedPair


async def create_quote(
    db: AsyncSession,
    customer_id: str,
    from_currency: Currency,
    to_currency: Currency,
    from_amount_minor: int,
) -> Quote:
    """
    Create and persist a quote. Returns the Quote ORM object.

    Rate routing:
    - Direct pair: apply single spread to mid-rate.
    - Cross pair (KES/NGN or NGN/KES): route through USD, compound two spreads.
    """
    if (from_currency, to_currency) not in SUPPORTED_PAIRS:
        raise UnsupportedPair(from_currency, to_currency)
    spread_bps = settings.DEFAULT_SPREAD_BPS
    if (from_currency, to_currency) in CROSS_PAIRS_VIA_USD:
        # Two-leg: A → USD → B
        mid_a_to_usd, age1 = await get_latest_rate(db, from_currency, Currency.USD)
        mid_usd_to_b, age2 = await get_latest_rate(db, Currency.USD, to_currency)
        effective_rate = compose_cross_rate(mid_a_to_usd, mid_usd_to_b, spread_bps)
        rate_age_seconds = max(age1, age2)
    else:
        mid_rate, rate_age_seconds = await get_latest_rate(
            db, from_currency, to_currency
        )
        effective_rate = apply_spread(mid_rate, spread_bps)
    from_amount_decimal = from_minor_units(from_amount_minor, from_currency)
    to_amount_decimal = from_amount_decimal * effective_rate
    to_amount_minor = to_minor_units(to_amount_decimal, to_currency)
    now = datetime.now(UTC)
    quote = Quote(
        id=str(uuid.uuid4()),
        customer_id=customer_id,
        from_currency=from_currency,
        to_currency=to_currency,
        from_amount_minor=from_amount_minor,
        to_amount_minor=to_amount_minor,
        effective_rate=str(effective_rate),
        rate_age_seconds=rate_age_seconds,
        correlation_id=str(uuid.uuid4()),
        created_at=now,
        expires_at=now + timedelta(seconds=settings.QUOTE_TTL_SECONDS),
    )
    db.add(quote)
    await db.commit()
    await db.refresh(quote)
    return quote
