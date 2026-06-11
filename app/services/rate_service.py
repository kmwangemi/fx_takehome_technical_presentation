"""
Rate fetching service.

Polls the upstream API and persists rates to the exchange_rates table.
Quote generation reads from that table (never hits API directly).

Staleness policy (per SPEC §6):
- API down/error  → fall back to last cached rate if age < MAX_RATE_STALENESS_SECONDS
- Age ≥ threshold → raise RatesUnavailable (503)
- API timeout     → treated as failed fetch; fall back to cache
- Malformed data  → log, reject, keep previous cache
"""

from datetime import UTC, datetime
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.utils.currencies import SUPPORTED_PAIRS, Currency
from app.utils.exceptions import RatesUnavailable
from app.core.logging import logger
from app.models.exchange_rate import ExchangeRate


async def fetch_and_store_rates(db: AsyncSession) -> None:
    """Called by the background scheduler every RATE_POLL_INTERVAL_SECONDS."""
    try:
        async with httpx.AsyncClient(
            timeout=settings.RATE_FETCH_TIMEOUT_SECONDS
        ) as client:
            resp = await client.get(
                settings.EXCHANGE_RATES_API_URL,
                params={
                    "access_key": settings.EXCHANGE_RATES_API_KEY,
                    "symbols": ",".join([c.value for c in Currency])
                },
            )
            resp.raise_for_status()
            data = resp.json()
        rates_raw: dict[str, float] = data.get("rates", {})
        if not rates_raw:
            logger.error(
                "rate_fetch.empty_response", url=settings.EXCHANGE_RATES_API_URL
            )
            return
        fetched_at = datetime.now(UTC)
        # Build a {currency: Decimal} map of rates relative to the API's base currency
        base_ccy = data.get("base", "USD")
        base_rates: dict[str, Decimal] = {k: Decimal(str(v)) for k, v in rates_raw.items()}
        base_rates[base_ccy] = Decimal("1")
        # Derive all supported pair rates and persist
        records = []
        for from_ccy, to_ccy in SUPPORTED_PAIRS:
            try:
                mid = _derive_rate(base_rates, from_ccy, to_ccy)
            except KeyError:
                logger.warning(
                    "rate_fetch.missing_pair",
                    from_currency=from_ccy,
                    to_currency=to_ccy,
                )
                continue
            records.append(
                ExchangeRate(
                    from_currency=from_ccy,
                    to_currency=to_ccy,
                    mid_rate=str(mid),
                    fetched_at=fetched_at,
                )
            )
        db.add_all(records)
        await db.commit()
        logger.info("rate_fetch.success", num_pairs=len(records), fetched_at=fetched_at.isoformat())
    except httpx.TimeoutException:
        logger.warning("rate_fetch.timeout", url=settings.EXCHANGE_RATES_API_URL)
    except httpx.HTTPStatusError as exc:
        logger.error("rate_fetch.http_error", status=exc.response.status_code)
    except Exception as exc:  # noqa: BLE001
        logger.error("rate_fetch.unexpected_error", error=str(exc))


def _derive_rate(
    base_rates: dict[str, Decimal], from_ccy: Currency, to_ccy: Currency
) -> Decimal:
    """Cross via Base: rate(A→B) = rate(Base→B) / rate(Base→A)."""
    return base_rates[to_ccy.value] / base_rates[from_ccy.value]


async def get_latest_rate(
    db: AsyncSession, from_ccy: Currency, to_ccy: Currency
) -> tuple[Decimal, int]:
    """
    Return (mid_rate, age_seconds) for the freshest cached rate for a pair.
    Raises RatesUnavailable if no rate or too stale.
    """
    stmt = (
        select(ExchangeRate)
        .where(
            ExchangeRate.from_currency == from_ccy,
            ExchangeRate.to_currency == to_ccy,
        )
        .order_by(ExchangeRate.fetched_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        raise RatesUnavailable("No rate data available for pair")
    age_seconds = int((datetime.now(UTC) - row.fetched_at.replace(tzinfo=UTC)).total_seconds())
    if age_seconds > settings.MAX_RATE_STALENESS_SECONDS:
        raise RatesUnavailable(
            f"Cached rate is {age_seconds}s old (threshold: {settings.MAX_RATE_STALENESS_SECONDS}s)"
        )
    return Decimal(row.mid_rate), age_seconds
