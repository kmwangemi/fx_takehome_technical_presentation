import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.balance import Balance
from app.models.customer import Customer
from app.utils.currencies import Currency
from app.utils.decimal import from_minor_units


async def create_customer(db: AsyncSession, name: str) -> Customer:
    customer = Customer(id=str(uuid.uuid4()), name=name)
    db.add(customer)
    # Seed zero balances for all four currencies
    for currency in Currency:
        db.add(Balance(customer_id=customer.id, currency=currency, amount_minor=0))
    await db.commit()
    await db.refresh(customer)
    return customer


async def get_balances(db: AsyncSession, customer_id: str) -> list[dict]:
    result = await db.execute(select(Balance).where(Balance.customer_id == customer_id))
    balances = result.scalars().all()
    return [
        {
            "currency": b.currency,
            "amount_minor": b.amount_minor,
            "amount_decimal": str(
                from_minor_units(b.amount_minor, Currency(b.currency))
            ),
        }
        for b in balances
    ]


async def credit_balance(
    db: AsyncSession, customer_id: str, currency: Currency, amount_minor: int
) -> dict:
    """Test-only fixture: manually credit a balance."""
    result = await db.execute(
        select(Balance)
        .where(Balance.customer_id == customer_id, Balance.currency == currency)
        .with_for_update()
    )
    balance = result.scalar_one_or_none()
    if balance is None:
        balance = Balance(customer_id=customer_id, currency=currency, amount_minor=0)
        db.add(balance)

    balance.amount_minor += amount_minor
    await db.commit()
    await db.refresh(balance)
    return {
        "currency": balance.currency,
        "amount_minor": balance.amount_minor,
        "amount_decimal": str(from_minor_units(balance.amount_minor, currency)),
    }
