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
async def test_execute_quote_success(client: AsyncClient, db: AsyncSession, funded_customer: Customer, pending_quote: Quote):
    """Test successful atomic two-leg execution."""
    idempotency_key = str(uuid.uuid4())
    
    response = await client.post(
        "/api/v1/executions",
        json={
            "quote_id": pending_quote.id,
            "customer_id": pending_quote.customer_id,
            "idempotency_key": idempotency_key
        }
    )
    assert response.status_code == 200
    
    # Verify balances updated atomically
    await db.refresh(funded_customer)
    usd_balance = (await db.execute(select(Balance).where(Balance.customer_id == funded_customer.id, Balance.currency == Currency.USD))).scalar_one()
    kes_balance = (await db.execute(select(Balance).where(Balance.customer_id == funded_customer.id, Balance.currency == Currency.KES))).scalar_one()
    
    # 1_000_000 minor original - 1_000 minor quote
    assert usd_balance.amount_minor == 999_000
    # 10_000_000 minor original + 130_000 minor quote
    assert kes_balance.amount_minor == 10_130_000
    
    await db.refresh(pending_quote)
    assert pending_quote.status == QuoteStatus.EXECUTED

@pytest.mark.asyncio
async def test_execute_quote_idempotency(client: AsyncClient, funded_customer: Customer, pending_quote: Quote):
    """Test idempotent retry returns same response, no double execution."""
    idempotency_key = str(uuid.uuid4())
    
    # First execution
    resp1 = await client.post("/api/v1/executions", json={"quote_id": pending_quote.id, "customer_id": pending_quote.customer_id, "idempotency_key": idempotency_key})
    assert resp1.status_code == 200
    
    # Second execution (retry)
    resp2 = await client.post("/api/v1/executions", json={"quote_id": pending_quote.id, "customer_id": pending_quote.customer_id, "idempotency_key": idempotency_key})
    assert resp2.status_code == 200
    
    # Must be exact same response
    assert resp1.json() == resp2.json()

@pytest.mark.asyncio
async def test_execute_quote_insufficient_funds(client: AsyncClient, db: AsyncSession, customer: Customer):
    """Test mid-execute failure due to negative balance."""
    # `customer` has 0 balance.
    now = datetime.now(UTC)
    q = Quote(
        id=str(uuid.uuid4()),
        customer_id=customer.id,
        from_currency=Currency.USD,
        to_currency=Currency.KES,
        from_amount_minor=1000, 
        to_amount_minor=130000, 
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
    
    response = await client.post(
        "/api/v1/executions",
        json={
            "quote_id": q.id,
            "customer_id": customer.id,
            "idempotency_key": str(uuid.uuid4())
        }
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INSUFFICIENT_FUNDS"
    
    # Verify quote marked as failed
    await db.refresh(q)
    assert q.status == QuoteStatus.FAILED
    
    # Verify no balance change
    usd_balance = (await db.execute(select(Balance).where(Balance.customer_id == customer.id, Balance.currency == Currency.USD))).scalar_one()
    assert usd_balance.amount_minor == 0

@pytest.mark.asyncio
async def test_execute_quote_expired(client: AsyncClient, db: AsyncSession, funded_customer: Customer):
    """Test executing an expired quote."""
    now = datetime.now(UTC)
    q = Quote(
        id=str(uuid.uuid4()),
        customer_id=funded_customer.id,
        from_currency=Currency.USD,
        to_currency=Currency.KES,
        from_amount_minor=1000,
        to_amount_minor=130000,
        effective_rate="130.00",
        rate_age_seconds=10,
        correlation_id=str(uuid.uuid4()),
        created_at=now - timedelta(seconds=120), # created 2 minutes ago
        expires_at=now - timedelta(seconds=60),  # expired 1 minute ago
        status=QuoteStatus.PENDING
    )
    db.add(q)
    await db.commit()
    await db.refresh(q)
    
    response = await client.post(
        "/api/v1/executions",
        json={
            "quote_id": q.id,
            "customer_id": funded_customer.id,
            "idempotency_key": str(uuid.uuid4())
        }
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "QUOTE_EXPIRED"
