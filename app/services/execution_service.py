"""
Execution service.

Implements SPEC §5 exactly:
- Quote status → executed is a single conditional UPDATE (concurrency gate).
- Balance debit + credit + idempotency record are in the SAME transaction.
- SELECT ... FOR UPDATE serialises concurrent writers to balance rows.
- Idempotency: repeated calls with same key return stored result.
"""

import json
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.balance import Balance
from app.models.execution import Execution
from app.models.idempotency_record import IdempotencyRecord
from app.models.quote import Quote
from app.utils.enums import QuoteStatus
from app.utils.exceptions import (
    InsufficientFunds,
    QuoteAlreadyExecuted,
    QuoteExpired,
    QuoteNotFound,
)


async def execute_quote(
    db: AsyncSession,
    quote_id: str,
    customer_id: str,
    idempotency_key: str,
) -> dict:
    """
    Execute a quote atomically. Returns a dict suitable for JSON serialisation.

    Steps (all in one DB transaction):
    1. Check idempotency cache.
    2. Load + validate quote (exists, belongs to customer, not expired).
    3. Conditional UPDATE quote status pending → executed (concurrency gate).
    4. SELECT ... FOR UPDATE on both balance rows.
    5. Check sufficient funds.
    6. Debit source, credit destination.
    7. Write Execution record + idempotency record.
    8. COMMIT.
    """
    # --- Idempotency check (outside main transaction — fast path) -----------
    existing = await _get_idempotency_record(db, customer_id, idempotency_key)
    if existing:
        logger.info(
            "execute.idempotent_replay",
            idempotency_key=idempotency_key,
            customer_id=customer_id,
        )
        return json.loads(existing.response_body)
    # --- Load quote ---------------------------------------------------------
    quote = await _load_quote(db, quote_id, customer_id)
    now = datetime.now(UTC)
    if quote.expires_at.replace(tzinfo=UTC) < now:
        raise QuoteExpired(quote_id)
    # --- Main atomic transaction --------------------------------------------
    async with db.begin():
        # 1. Conditional status transition (concurrency gate)
        result = await db.execute(
            update(Quote)
            .where(Quote.id == quote_id, Quote.status == QuoteStatus.PENDING)
            .values(status=QuoteStatus.EXECUTED)
        )
        if result.rowcount == 0:
            # Somebody else won the race or quote already executed/failed
            refreshed = await db.get(Quote, quote_id)
            if refreshed and refreshed.status == QuoteStatus.EXECUTED:
                raise QuoteAlreadyExecuted(quote_id)
            raise QuoteAlreadyExecuted(quote_id)
        # 2. Lock balance rows (FOR UPDATE)
        from_balance = await _get_balance_for_update(
            db, customer_id, quote.from_currency
        )
        to_balance = await _get_balance_for_update(db, customer_id, quote.to_currency)
        # 3. Sufficient funds check
        if from_balance.amount_minor < quote.from_amount_minor:
            # Mark quote as failed (terminal — do not silently retry)
            await db.execute(
                update(Quote)
                .where(Quote.id == quote_id)
                .values(status=QuoteStatus.FAILED)
            )
            raise InsufficientFunds(
                quote.from_currency,
                from_balance.amount_minor,
                quote.from_amount_minor,
            )
        # 4. Apply balance changes
        from_balance.amount_minor -= quote.from_amount_minor
        to_balance.amount_minor += quote.to_amount_minor
        # 5. Execution record
        execution = Execution(
            quote_id=quote_id,
            customer_id=customer_id,
            correlation_id=quote.correlation_id,
        )
        db.add(execution)
        # 6. Idempotency record (committed in same txn)
        response_payload = _build_response(quote, execution)
        idempotency_record = IdempotencyRecord(
            customer_id=customer_id,
            idempotency_key=idempotency_key,
            response_status=200,
            response_body=json.dumps(response_payload),
        )
        db.add(idempotency_record)
        # db.begin() context manager commits on exit
    logger.info(
        "execute.success",
        quote_id=quote_id,
        customer_id=customer_id,
        correlation_id=quote.correlation_id,
        from_currency=quote.from_currency,
        to_currency=quote.to_currency,
        from_amount_minor=quote.from_amount_minor,
        to_amount_minor=quote.to_amount_minor,
    )
    return response_payload


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _load_quote(db: AsyncSession, quote_id: str, customer_id: str) -> Quote:
    quote = await db.get(Quote, quote_id)
    if quote is None:
        raise QuoteNotFound(quote_id)
    # Ownership check — a customer cannot execute another customer's quote
    if quote.customer_id != customer_id:
        raise QuoteNotFound(quote_id)
    return quote


async def _get_balance_for_update(
    db: AsyncSession, customer_id: str, currency: str
) -> Balance:
    result = await db.execute(
        select(Balance)
        .where(
            Balance.customer_id == customer_id,
            Balance.currency == currency,
        )
        .with_for_update()
    )
    balance = result.scalar_one_or_none()
    if balance is None:
        # Auto-create zero balance if missing (customers start with all 4 balances
        # but guard here for safety)
        balance = Balance(customer_id=customer_id, currency=currency, amount_minor=0)
        db.add(balance)
        await db.flush()
    return balance


async def _get_idempotency_record(
    db: AsyncSession, customer_id: str, idempotency_key: str
) -> IdempotencyRecord | None:
    result = await db.execute(
        select(IdempotencyRecord).where(
            IdempotencyRecord.customer_id == customer_id,
            IdempotencyRecord.idempotency_key == idempotency_key,
        )
    )
    return result.scalar_one_or_none()


def _build_response(quote: Quote, execution: Execution) -> dict:
    return {
        "execution_id": execution.id,
        "quote_id": quote.id,
        "customer_id": quote.customer_id,
        "from_currency": quote.from_currency,
        "to_currency": quote.to_currency,
        "from_amount_minor": quote.from_amount_minor,
        "to_amount_minor": quote.to_amount_minor,
        "effective_rate": quote.effective_rate,
        "correlation_id": quote.correlation_id,
        "executed_at": execution.executed_at.isoformat(),
    }
