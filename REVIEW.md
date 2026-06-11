# Code Review: FX Engine (`planted_bugs/`)

This review documents all critical issues found in the FX engine. Bugs are ranked by severity,
focusing on production impact, financial accuracy, and concurrency safety.

---

## Bug 1 — Missing Balance Updates and Insufficient-Funds Check
**Severity**: 🔴 Blocker  
**File**: `fx.py` — `execute_quote`

`execute_quote` updates the quote status to `executed` and inserts a transaction record, but
**never debits the source balance or credits the destination balance**, and never checks whether
the customer actually has sufficient funds. Conversions complete out of thin air without touching
real accounts.

**Production impact**: Every execution is a "free money glitch". Customers receive converted funds
without the source currency leaving their account. This violates the atomic two-leg execution
requirement and will cause the ledger to be unreconcilable from day one.

**Fix**: Inside the database transaction in `execute_quote`, after the concurrency gate passes:

```python
# 1. Check sufficient funds
source_row = conn.execute(
    "SELECT amount_minor FROM balances WHERE customer_id=? AND currency=?",
    (customer_id, row["from_currency"])
).fetchone()
if source_row is None or source_row["amount_minor"] < from_amount_minor:
    raise InsufficientFunds(row["from_currency"])

# 2. Debit source, credit destination (both in the same transaction)
conn.execute(
    "UPDATE balances SET amount_minor = amount_minor - ? WHERE customer_id=? AND currency=?",
    (from_amount_minor, customer_id, row["from_currency"])
)
conn.execute(
    "UPDATE balances SET amount_minor = amount_minor + ? WHERE customer_id=? AND currency=?",
    (to_amount_minor, customer_id, row["to_currency"])
)
```

---

## Bug 2 — Ineffective Concurrency Control (`threading.Lock`)
**Severity**: 🔴 Blocker  
**File**: `fx.py` — `execute_quote`, `_execute_lock`

The engine uses a Python `threading.Lock()` to protect the execution section. Two problems:

1. **Multi-process deployments (Gunicorn, uWSGI)**: the lock only applies within a single process.
   Concurrent requests handled by different workers bypass it entirely.
2. **TOCTOU race**: the `SELECT * FROM quotes` (which reads `executed = 0`) happens *before*
   the lock is acquired. Two threads can both read `executed = 0`, both pass the check, and both
   proceed to execute the same quote.

**Production impact**: A quote can be executed twice. Both executions create transaction records
and (once Bug 1 is fixed) apply two balance debit/credits for the same quote — a financial
double-spend.

**Fix**: Remove the Python-level lock entirely. Use the database as the sole concurrency gate via
a conditional `UPDATE`:

```python
result = conn.execute(
    "UPDATE quotes SET executed=1, executed_at=? WHERE id=? AND executed=0",
    (now.isoformat(), quote_id)
)
if result.rowcount == 0:
    raise ValueError("quote already executed or not found")
# Only if rowcount == 1 do we proceed with the transaction insert
```

This is atomic at the DB level and works correctly across multiple processes.

---

## Bug 3 — `float` Conversion Precision Loss in `generate_quote`
**Severity**: 🔴 Blocker  
**File**: `fx.py:56`

```python
# Buggy
final = float(amount) * float(rate)
final_decimal = Decimal(str(final)).quantize(QUANTUM, rounding=ROUND_HALF_UP)
```

`float` has only 53 bits of precision (~15 significant digits). Converting `Decimal → float → Decimal`
introduces binary approximation errors before `quantize` runs. The module docstring explicitly
states "all financial calculations use Decimal" — this violates that contract.

**Production impact**: Silent rounding errors on every quote. They're small per-transaction but
compound across high volume into material accounting discrepancies and failed reconciliation.

**Fix**:
```python
# Correct — stay in Decimal the whole way
final_decimal = (amount * rate).quantize(QUANTUM, rounding=ROUND_HALF_UP)
```

---

## Bug 4 — `execute_quote` Re-fetches Live Rate Instead of Using the Locked Quote Rate
**Severity**: 🔴 Critical  
**File**: `fx.py:103–107`

```python
# Buggy — re-prices at execution time
current_rate = self._effective_rate(row["from_currency"], row["to_currency"])
final = (amount * current_rate).quantize(...)
```

The transaction record is written with the *live rate at execution time*, not the rate the customer
was shown and agreed to. The quote rate is already persisted in `row["rate"]` — it is never read
back.

**Production impact**: Customer is quoted one rate, clicks confirm, and the executed amount
reflects a different rate. This is a material misrepresentation and a breach of the quote contract.
In regulated FX markets this is a compliance violation.

**Fix**:
```python
# Use the rate the customer was quoted
rate = Decimal(row["rate"])
final = (amount * rate).quantize(QUANTUM, rounding=ROUND_HALF_UP)
# Delete the current_rate fetch
```

---

## Bug 5 — Incorrect Inverse Rate Calculation (Bank Loses Spread)
**Severity**: 🟠 Major  
**File**: `fx.py:114–117`

```python
# Buggy
mid = (inverse["buy"] + inverse["sell"]) / 2
return Decimal("1") / mid
```

When a customer sells KES to receive USD, the bank is *buying* KES and *selling* USD. The correct
rate to invert is the **sell** side of the base pair (`USD/KES sell`), not the arithmetic midpoint.
Using the midpoint strips out the spread and gives the customer a better-than-market rate.

**Production impact**: On USD/KES with buy=129, sell=130:
- `1/mid = 1/129.5 = 0.007722` (what the buggy code returns — too generous)
- `1/sell = 1/130 = 0.007692` (correct — bank retains its margin)

The bank silently subsidises every inverted-pair trade. At volume this is a significant P&L leak
and opens an arbitrage window (buy USD/KES directly, sell via the inverse, repeat).

**Fix**:
```python
inverse = self.rates.get(f"{to_ccy}/{from_ccy}")
if inverse is not None:
    return Decimal("1") / inverse["sell"]
```

---

## Bug 6 — Broken Cross-Pair Rate Resolution
**Severity**: 🟠 Major  
**File**: `fx.py:120–124`

```python
# Buggy
leg1 = self.rates.get(f"{from_ccy}/USD") or self.rates.get(f"USD/{from_ccy}")
leg2 = self.rates.get(f"USD/{to_ccy}") or self.rates.get(f"{to_ccy}/USD")
if leg1 and leg2:
    return leg1["sell"] * leg2["sell"]
```

If a leg resolves via its fallback (e.g. `USD/KES` instead of `KES/USD`), the raw `sell` rate
is mathematically wrong for cross-multiplication. `USD/KES sell ≈ 130` — multiplying that into
the cross produces a rate that is orders of magnitude too large.

**Production impact**: Cross pairs (e.g. KES→NGN) produce wildly incorrect rates. A customer
converting KES 1,000 to NGN could receive NGN 190,000,000 instead of NGN 11,400.

**Fix**: Delegate each leg to `_effective_rate` so that direction and spread are handled
consistently, including inversion when needed:

```python
return self._effective_rate(from_ccy, "USD") * self._effective_rate("USD", to_ccy)
```

---

## Bug 7 — Idempotency Keys Not Scoped to Customer (Cross-Customer Data Leak)
**Severity**: 🟠 Major  
**File**: `fx.py:88`, `db.py` schema

```python
# Buggy — no customer_id filter
row = conn.execute("SELECT response FROM idempotency WHERE key = ?", (idempotency_key,))
```

The `idempotency` table has no `customer_id` column. If Customer A uses key `"pay-001"` and
Customer B later uses the same key, Customer B receives Customer A's transaction response —
including amounts, currencies, and transaction IDs — and their own exchange never executes.

**Production impact**: Data leak between customers. Customer B's request silently returns stale
data; their funds are never actually moved.

**Fix**:
```sql
-- Schema change
CREATE TABLE idempotency (
    key         TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    response    TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (key, customer_id)
);
```
```python
# Lookup
conn.execute("SELECT response FROM idempotency WHERE key=? AND customer_id=?",
             (idempotency_key, customer_id))
```

---

## Bug 8 — `get_db()` Has No Rollback on Exception
**Severity**: 🟠 Major  
**File**: `db.py:13–20`

```python
# Buggy
@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:          # ← no except + rollback
        conn.close()
```

If an exception is raised mid-transaction (e.g. between `UPDATE quotes SET executed=1` and
`INSERT INTO transactions`), `commit()` is skipped and the connection is closed. SQLite's Python
driver has a subtle implicit transaction model: DDL statements auto-commit, so depending on
execution order, partial writes can land in the database before the exception is raised.

**Production impact**: Under certain failure modes `quotes.executed` is set to 1 with no
corresponding transaction record. The quote appears consumed but no exchange occurred. Manual
intervention is required to detect and remediate.

**Fix**:
```python
@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

---

## Bug 9 — Default SQLite Configuration (Locking Under Concurrent Writes)
**Severity**: 🟡 Minor / Major (load-dependent)  
**File**: `db.py` — `get_db()`, `init_db()`

SQLite's default rollback-journal mode takes a full write lock for the duration of every write
transaction. Under concurrent request load, this causes `OperationalError: database is locked`
for any connection that cannot acquire the lock within the (default zero-millisecond) timeout.

**Production impact**: Valid execution requests fail with 500 errors under load. At low traffic
this may not surface, but any burst (e.g. end-of-day FX conversions) will trigger it. Grows
worse as Bug 1 is fixed and writes become heavier.

**Fix**: Enable WAL mode and set a busy timeout in `init_db()`:

```python
def init_db():
    with get_db() as conn:
        conn.executescript("PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS quotes ( ... );
            ...
        """)
```

---

## Summary

| # | File | Description | Severity |
|---|------|-------------|----------|
| 1 | `fx.py` | No balance debit/credit or funds check on execution | 🔴 Blocker |
| 2 | `fx.py` | `threading.Lock` ineffective; TOCTOU race → double-spend | 🔴 Blocker |
| 3 | `fx.py:56` | `float` intermediate in financial arithmetic | 🔴 Blocker |
| 4 | `fx.py:103` | Execution re-prices at live rate instead of quote rate | 🔴 Critical |
| 5 | `fx.py:114` | Inverse rate uses mid instead of sell (bank loses spread) | 🟠 Major |
| 6 | `fx.py:120` | Cross-rate fallback uses wrong-direction rate | 🟠 Major |
| 7 | `fx.py:88` + schema | Idempotency keys not scoped to customer | 🟠 Major |
| 8 | `db.py:13` | No rollback on exception in `get_db()` | 🟠 Major |
| 9 | `db.py` | Default SQLite journal mode → locks under concurrent writes | 🟡 Minor/Major |