import uuid
import pytest
from datetime import datetime, timedelta, UTC
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient

from app.models.customer import Customer
from app.models.exchange_rate import ExchangeRate
from app.utils.currencies import Currency
from app.core.config import settings

@pytest.fixture
async def seed_rates(db: AsyncSession):
    """Seed dummy exchange rates."""
    now = datetime.now(UTC)
    rates = [
        ExchangeRate(from_currency=Currency.USD, to_currency=Currency.KES, mid_rate="130.50", fetched_at=now),
        ExchangeRate(from_currency=Currency.KES, to_currency=Currency.USD, mid_rate="0.00766", fetched_at=now),
        ExchangeRate(from_currency=Currency.USD, to_currency=Currency.NGN, mid_rate="1500.00", fetched_at=now),
        ExchangeRate(from_currency=Currency.NGN, to_currency=Currency.USD, mid_rate="0.00066", fetched_at=now),
    ]
    db.add_all(rates)
    await db.commit()

@pytest.mark.asyncio
async def test_create_quote_direct(client: AsyncClient, customer: Customer, seed_rates):
    """Test creating a quote for a direct pair (USD to KES)."""
    response = await client.post(
        "/api/v1/quotes",
        json={
            "customer_id": customer.id,
            "from_currency": "USD",
            "to_currency": "KES",
            "from_amount_minor": 1000  # $10.00
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["from_currency"] == "USD"
    assert data["to_currency"] == "KES"
    assert data["from_amount_minor"] == 1000
    # spread applies: mid = 130.50, spread = 0.5%. sell rate = 130.50 * 0.995 = 129.8475
    # 10.00 * 129.8475 = 1298.475 KES -> minor = 129848
    assert data["to_amount_minor"] == 129848
    assert "quote_id" in data
    assert "expires_at" in data

@pytest.mark.asyncio
async def test_create_quote_cross(client: AsyncClient, customer: Customer, seed_rates):
    """Test creating a quote for a cross pair (KES to NGN routed via USD)."""
    response = await client.post(
        "/api/v1/quotes",
        json={
            "customer_id": customer.id,
            "from_currency": "KES",
            "to_currency": "NGN",
            "from_amount_minor": 13050  # 130.50 KES
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["from_currency"] == "KES"
    assert data["to_currency"] == "NGN"
    # rate KES->USD = 0.00766 * 0.995
    # rate USD->NGN = 1500.00 * 0.995
    # compounded = ...
    assert data["to_amount_minor"] > 0

@pytest.mark.asyncio
async def test_rate_unavailable_stale(client: AsyncClient, customer: Customer, db: AsyncSession):
    """Test generating quote when rates are older than MAX_RATE_STALENESS_SECONDS."""
    stale_time = datetime.now(UTC) - timedelta(seconds=settings.MAX_RATE_STALENESS_SECONDS + 10)
    stale_rate = ExchangeRate(
        from_currency=Currency.USD, 
        to_currency=Currency.EUR, 
        mid_rate="0.92", 
        fetched_at=stale_time
    )
    db.add(stale_rate)
    await db.commit()
    
    response = await client.post(
        "/api/v1/quotes",
        json={
            "customer_id": customer.id,
            "from_currency": "USD",
            "to_currency": "EUR",
            "from_amount_minor": 1000
        }
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "RATES_UNAVAILABLE"

@pytest.mark.asyncio
async def test_unsupported_pair(client: AsyncClient, customer: Customer):
    """Test quoting an unsupported currency pair."""
    response = await client.post(
        "/api/v1/quotes",
        json={
            "customer_id": customer.id,
            "from_currency": "USD",
            "to_currency": "GBP",
            "from_amount_minor": 1000
        }
    )
    assert response.status_code == 422
