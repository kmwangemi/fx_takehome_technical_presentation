from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.execution_schema import ExecuteRequest
from app.services.execution_service import execute_quote

router = APIRouter(prefix="/executions", tags=["executions"])


@router.post("", status_code=200)
async def post_execution(
    body: ExecuteRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await execute_quote(
        db=db,
        quote_id=body.quote_id,
        customer_id=body.customer_id,
        idempotency_key=body.idempotency_key,
    )
