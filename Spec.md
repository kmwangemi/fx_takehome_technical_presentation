# SPEC.md — FX Engine

## 1. Scope

In scope: quote generation, quote execution, rate ingestion, customer
balance management (create, view, manual credit). Out of scope: auth/authz,
multi-tenant isolation, KYC/AML, fees/commission beyond spread, FX limits
per customer, webhooks/notifications, multi-currency wallets beyond the
four listed currencies.

Currencies: USD, EUR, KES, NGN.

## 2. Currency precision

| Currency | Minor unit (decimal places) | Smallest unit |
|---|---|---|
| USD | 2 | 0.01 |
| EUR | 2 | 0.01 |
| KES | 2 | 0.01 |
| NGN | 2 | 0.01 |

All amounts stored as integer minor units (e.g. cents/kobo) in the
database — never as floats. All arithmetic performed using `Decimal`
with a context precision of 28 significant digits.

**Rounding mode:** `ROUND_HALF_EVEN` (banker's rounding), applied once,
at the final step of each conversion, when converting the computed
Decimal result to integer minor units. Intermediate calculations
(rate composition for cross pairs) retain full Decimal precision and
are not rounded until the final amount is produced.

## 3. Exchange rates and spreads

Rates are fetched from a public source (exchangeratesapi.io free tier or
equivalent) as **mid-market rates**, refreshed on a polling interval
(default: every 5 minutes, configurable). Each rate fetch is stored with
a `fetched_at` timestamp.

Buy/sell spread is applied at quote time, not at rate-fetch time:

- `sell_rate = mid_rate * (1 - spread_bps / 10000)` — rate the engine
  gives the customer when the customer is selling the source currency
  (i.e. converting *from* it).
- `buy_rate = mid_rate * (1 + spread_bps / 10000)` — reserved for the
  inverse direction; for this engine, a single spread is applied
  per-leg in the direction of conversion (we do not maintain separate
  customer-buy/customer-sell books).

Default spread: **50 bps (0.50%)** per leg, configurable per currency
pair via config. This is a simplification — a real desk would have
asymmetric, pair-specific spreads; documented as out of scope for this
exercise.

### Routing for cross pairs

Direct mid-market rates are only assumed available for pairs involving
USD or EUR as one side (i.e. USD/EUR, USD/KES, USD/NGN, EUR/KES, EUR/NGN,
and inverses). For pairs with neither leg being USD or EUR (i.e.
KES/NGN, NGN/KES), the engine routes through **USD**:

```
KES -> USD -> NGN
```

**Spread compounding:** each leg of a routed conversion applies its own
spread independently. For a two-leg route A→USD→B, the effective rate
is:

```
effective_rate = rate(A→USD) * (1 - spread_bps/10000)
                * rate(USD→B) * (1 - spread_bps/10000)
```

This means a routed cross pair has roughly double the effective spread
of a direct pair (≈100 bps vs ≈50 bps at default config). This is
documented and intentional — it reflects the real cost of a synthetic
cross. No rounding occurs between legs; only the final output amount is
rounded per §2.

## 4. Quotes

`POST /quotes` — input: `customer_id`, `from_currency`, `to_currency`,
`amount` (in minor units of `from_currency`).

Output: `quote_id` (UUID), `from_currency`, `to_currency`, `from_amount`,
`to_amount`, `rate` (effective rate used, as Decimal string),
`created_at`, `expires_at` (`created_at + 60s`), `correlation_id`.

Quotes are persisted (status: `pending`). A quote does **not** reserve or
lock balance — balance is checked at execute time. This means a quote can
become unexecutable if the customer's balance changes between quote and
execute; this is an accepted race, surfaced as an `INSUFFICIENT_FUNDS`
error at execute time, not a quote-time guarantee.

Quotes expire 60 seconds after creation. An expired quote cannot be
executed (`QUOTE_EXPIRED`).

## 5. Execute

`POST /executions` — input: `quote_id`, `idempotency_key`.

### Invariants

- A quote can be executed **at most once**, regardless of how many
  execute requests reference it (concurrently or sequentially).
- Both balance legs (debit `from_currency`, credit `to_currency`) for the
  same customer are updated atomically: both succeed or neither is
  applied.
- The source balance must not go negative as a result of execution. If
  it would, the execution fails with `INSUFFICIENT_FUNDS` and no balance
  changes are applied.
- A given `idempotency_key` maps to exactly one execution outcome. Repeat
  requests with the same key return the original result (same HTTP
  status + body) without re-applying balance changes, even if the
  original request is still in-flight or the process crashed
  mid-execution.

### Concurrency model

- Quote status transition (`pending` → `executed`) is performed via a
  single atomic, conditional database update:
  `UPDATE quotes SET status='executed' WHERE id=? AND status='pending'`.
  Exactly one concurrent caller will see `rows_affected == 1`; all others
  see `0` and are rejected with `QUOTE_ALREADY_EXECUTED` (or
  `QUOTE_EXPIRED` if also past expiry).
- The winning caller performs both balance updates and the idempotency
  record write inside a single DB transaction (`BEGIN ... COMMIT`). If
  any step fails (including the negative-balance check), the entire
  transaction is rolled back, and the quote status reverts to `pending`
  is **not** attempted — instead the quote is marked `failed` (terminal),
  since a quote that failed balance validation should not be retried
  silently with stale rates.
- Balance rows use `SELECT ... FOR UPDATE` (Postgres) / `BEGIN
  IMMEDIATE` (SQLite) to serialize concurrent writers to the same
  customer's balance rows.

### Idempotency

- `idempotency_key` is unique per `(customer_id, idempotency_key)` in an
  `idempotency_records` table, storing the request hash, response status,
  and response body.
- On receiving a request: if a record exists for that key, return the
  stored response verbatim (do not re-execute). If no record exists,
  proceed and write the record as part of the same transaction that
  applies balance changes — guaranteeing the record only exists if the
  execution committed.
- If a process crashes after the balance transaction commits but before
  the response is sent, the client retry will find the idempotency record
  (already committed) and return the stored result — no double-execution.

### Mid-execute interruption

If the process is killed between the quote-status update and the balance
transaction commit, the DB transaction is rolled back automatically (not
yet committed), so no balance change is applied — but the quote-status
update, if it was in the *same* transaction, also rolls back, leaving the
quote `pending` and re-executable. **Decision: the quote-status update,
balance debit/credit, and idempotency record write all occur inside one
single DB transaction.** This guarantees true all-or-nothing semantics
across the entire execute operation.

## 6. Rate-source failure handling

- Rates are cached in the DB with `fetched_at`. A background refresh job
  polls the upstream API every 5 minutes.
- **API down or erroring:** quote generation continues using the last
  successfully cached rate, provided it is not older than
  `MAX_RATE_STALENESS` (default: 60 minutes). The quote response includes
  a `rate_age_seconds` field so callers can see staleness.
- **Cached rate older than `MAX_RATE_STALENESS`:** quote generation fails
  with `RATES_UNAVAILABLE` (HTTP 503). No quote is issued on stale-beyond-
  threshold data.
- **API slow:** rate fetch has a 5-second timeout; on timeout, treated as
  a failed fetch (falls back to cache per above).
- **API returns malformed/partial data:** the fetch is rejected and
  logged; the previous cached rate set remains in effect.

## 7. Customer balances

- `POST /customers` creates a customer with zero balances in all four
  currencies.
- `GET /customers/{id}/balances` returns balances per currency in minor
  units (and a human-readable decimal string).
- `POST /customers/{id}/balances/credit` is a test-only fixture endpoint
  to manually set/increase a balance; not part of the "production" API
  surface but included for testability. Clearly marked as such in the
  README.

## 8. Observability

- `GET /healthz` — returns 200 + DB connectivity check + last successful
  rate-fetch timestamp.
- `GET /metrics` — Prometheus-format counters/histograms: quote count,
  execute count (success/failure by error code), execute latency, rate-
  fetch success/failure count, rate staleness gauge.
- Every quote and execution carries a `correlation_id` (generated at
  quote time, propagated to the execution record), logged in structured
  (JSON) log lines for both the quote-creation and execute events, so the
  two can be joined in logs.

## 9. Error semantics (summary)

| Error code | HTTP | Meaning |
|---|---|---|
| `QUOTE_EXPIRED` | 409 | Quote past its 60s expiry |
| `QUOTE_ALREADY_EXECUTED` | 409 | Quote already consumed |
| `QUOTE_NOT_FOUND` | 404 | Unknown quote_id |
| `INSUFFICIENT_FUNDS` | 422 | Source balance insufficient at execute time |
| `RATES_UNAVAILABLE` | 503 | No sufficiently fresh rate available |
| `IDEMPOTENCY_KEY_REUSED` | 200/original | Returns original response |

## 10. Out of scope (explicit)

- Auth/authz, multi-tenancy, rate limiting per customer.
- Fees/commission beyond the configured spread.
- Per-customer or per-pair transaction limits.
- Asymmetric buy/sell books (we use a single mid-rate + symmetric spread).
- Reconciliation/settlement with external ledgers.
- Currencies beyond USD/EUR/KES/NGN.