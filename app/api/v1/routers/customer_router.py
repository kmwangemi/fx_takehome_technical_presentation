from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.customer_schema import CreateCustomerRequest, CreditRequest
from app.services.customer_service import create_customer, credit_balance, get_balances

router = APIRouter(prefix="/customers", tags=["customers"])


@router.post("", status_code=201)
async def post_customer(
    body: CreateCustomerRequest, db: AsyncSession = Depends(get_db)
) -> dict:
    customer = await create_customer(db, body.name)
    return {
        "customer_id": customer.id,
        "name": customer.name,
        "created_at": customer.created_at.isoformat(),
    }


@router.get("/{customer_id}/balances")
async def get_customer_balances(
    customer_id: str, db: AsyncSession = Depends(get_db)
) -> dict:
    balances = await get_balances(db, customer_id)
    return {"customer_id": customer_id, "balances": balances}


@router.post("/{customer_id}/balances/credit")
async def post_credit(
    customer_id: str, body: CreditRequest, db: AsyncSession = Depends(get_db)
) -> dict:
    """TEST-ONLY fixture — manually credit a customer balance. Not for production use."""
    result = await credit_balance(db, customer_id, body.currency, body.amount_minor)
    return result
