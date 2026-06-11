import asyncio
import uuid
import pytest
from datetime import datetime, timedelta, UTC
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient
from sqlalchemy import select

from app.models.customer import Customer
from app.models.quote import Quote
from app.models.balance import Balance
from app.utils.currencies import Currency
from app.utils.enums import QuoteStatus

@pytest.fixture
async def pending_quote(db: AsyncSession, funded_customer: Customer) -> Quote:
    now = datetime.now(UTC)
    q = Quote(
        id=str(uuid.uuid4()),
        customer_id=funded_customer.id,
        from_currency=Currency.USD,
        to_currency=Currency.KES,
        from_amount_minor=1000, # $10.00
        to_amount_minor=130000, # 1300.00 KES
        effective_rate="130.00",
        rate_age_seconds=10,
        correlation_id=str(uuid.uuid4()),
        created_at=now,
        expires_at=now + timedelta(seconds=60),
        status=QuoteStatus.PENDING
    )
    db.add(q)
    await db.commit()
    await db.refresh(q)
    return q

@pytest.mark.asyncio
async def test_concurrent_execution(client: AsyncClient, db: AsyncSession, funded_customer: Customer, pending_quote: Quote):
    """
    Test concurrency safety on execute.
    Fires N parallel executions of the same quote ID (with DIFFERENT idempotency keys 
    to bypass the idempotency cache layer) and asserts exactly one succeeds.
    """
    N = 10
    # We use N different idempotency keys to ensure they all hit the DB transaction logic
    # instead of just returning the cached response from IdempotencyRecord
    requests = []
    for _ in range(N):
        req = client.post(
            "/api/v1/executions",
            json={
                "quote_id": pending_quote.id,
                "customer_id": pending_quote.customer_id,
                "idempotency_key": str(uuid.uuid4())
            }
        )
        requests.append(req)
    
    # Fire all concurrently
    responses = await asyncio.gather(*requests, return_exceptions=True)
    
    success_count = 0
    conflict_count = 0
    
    for resp in responses:
        if isinstance(resp, Exception):
            continue
        if resp.status_code == 200:
            success_count += 1
        elif resp.status_code == 409: # QUOTE_ALREADY_EXECUTED
            conflict_count += 1
            
    assert success_count == 1, f"Expected exactly 1 success, got {success_count}"
    assert conflict_count == N - 1, f"Expected exactly {N-1} conflicts, got {conflict_count}"
    
    # Verify balances updated exactly ONCE
    await db.refresh(funded_customer)
    usd_balance = (await db.execute(select(Balance).where(Balance.customer_id == funded_customer.id, Balance.currency == Currency.USD))).scalar_one()
    kes_balance = (await db.execute(select(Balance).where(Balance.customer_id == funded_customer.id, Balance.currency == Currency.KES))).scalar_one()
    
    assert usd_balance.amount_minor == 999_000
    assert kes_balance.amount_minor == 10_130_000
    
    await db.refresh(pending_quote)
    assert pending_quote.status == QuoteStatus.EXECUTED
