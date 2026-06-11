import asyncio
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base_class import Base
from app.db.database import get_db
from app.main import app
from app.models.balance import Balance
from app.models.customer import Customer
from app.utils.currencies import Currency

# Use SQLite in-memory file for tests, but one that supports cross-connection updates
# We use a file-backed sqlite database because the app requires real locks/concurrency checks.
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_fx.db"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)

TestingSessionLocal = async_sessionmaker(
    autocommit=False, autoflush=False, expire_on_commit=False, bind=test_engine, class_=AsyncSession
)

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database():
    """Create all tables in the test database before the test session, drop them after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture
async def db():
    """Provide a database session for a test."""
    async with TestingSessionLocal() as session:
        yield session
        # Rollback any uncommitted changes
        await session.rollback()

@pytest_asyncio.fixture
async def client():
    """Provide an HTTP client connected to the FastAPI app with test db override."""
    async def override_get_db():
        async with TestingSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
        
    app.dependency_overrides.clear()

@pytest_asyncio.fixture
async def customer(db: AsyncSession) -> Customer:
    """Fixture that provides a fresh customer."""
    import uuid
    from datetime import UTC, datetime
    cust = Customer(
        id=str(uuid.uuid4()),
        name="Test Customer",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC)
    )
    db.add(cust)
    # Give them 0 balances for all supported currencies
    for curr in Currency:
        db.add(Balance(customer_id=cust.id, currency=curr, amount_minor=0))
    await db.commit()
    await db.refresh(cust)
    return cust

@pytest_asyncio.fixture
async def funded_customer(db: AsyncSession) -> Customer:
    """Fixture that provides a customer funded with various currencies."""
    import uuid
    from datetime import UTC, datetime
    cust = Customer(
        id=str(uuid.uuid4()),
        name="Funded Customer",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC)
    )
    db.add(cust)
    
    # Give them funds (e.g. 10,000 USD = 1,000,000 minor units)
    db.add(Balance(customer_id=cust.id, currency=Currency.USD, amount_minor=1_000_000))
    db.add(Balance(customer_id=cust.id, currency=Currency.EUR, amount_minor=1_000_000))
    db.add(Balance(customer_id=cust.id, currency=Currency.KES, amount_minor=100_000_00))
    db.add(Balance(customer_id=cust.id, currency=Currency.NGN, amount_minor=100_000_00))
    
    await db.commit()
    await db.refresh(cust)
    return cust
