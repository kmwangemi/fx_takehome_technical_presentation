# Architectural & Process Decisions (DECISIONS.md)

This document outlines the core trade-offs made during the development of the FX Engine and details the collaborative process between myself (the engineer) and the AI assistant.

---

## 1. Main Trade-offs (Architecture, Scope, Libraries)

* **Architecture (Async vs. Sync):** Chose an entirely asynchronous stack (`FastAPI`, `httpx`, `asyncpg/aiosqlite`). While this introduces complexity regarding session management and thread safety, it was a necessary trade-off to ensure the FX engine can handle high-throughput concurrent executions without blocking the event loop.
* **Database (Postgres via Neon):** Opted for serverless Neon Postgres with `asyncpg` to ensure the FX engine runs on a robust, production-grade RDBMS. This guarantees that advanced concurrency mechanisms, like `SELECT ... FOR UPDATE` row-level locking, operate flawlessly under heavy transactional load, avoiding the limitations of lightweight alternatives.
* **Database Migrations (Alembic):** Integrated Alembic alongside SQLAlchemy to enforce robust schema version control. This decision ensures that as the financial engine scales and data models evolve, database schema changes are tracked natively, reviewed programmatically, and rolled out safely in production without relying on manual SQL scripts or `create_all()` shortcuts.
* **Rate Polling (Async Background vs. Synchronous Lookup):** I chose to implement a background `asyncio` scheduler that fetches rates on an interval rather than fetching rates dynamically when the user hits `/quotes`. **Trade-off:** Data might be slightly stale (up to the interval duration), but it guarantees **100% API uptime** for quote generation even if the external `exchangeratesapi` goes down, and completely eliminates the risk of hitting external rate limits.

## 2. Human vs. AI Delegation

* **What I Owned (Self):** I established the rigid boundaries. I defined the database schemas (specifically enforcing `BigInteger` minor units), dictated the strict usage of `ROUND_HALF_EVEN` for financial rounding, designed the transaction boundary logic (Two-leg atomic rollbacks), and mandated the usage of `SELECT ... FOR UPDATE` for concurrency control.
* **What I Delegated (AI):** I delegated the boilerplate. The AI wrote the FastAPI router files, the Pydantic validation schemas, the foundational `pytest` scaffolding, and the implementation of the `asyncio` background loop for the rate scheduler.

## 3. Accepting, Rejecting, and Overriding AI Suggestions

* **Accepted:** I accepted the AI's usage of `httpx.AsyncClient` for the rate fetching service. It integrates natively with FastAPI's async environment and handled timeouts cleanly.
* **Overrode:** When integrating the `exchangeratesapi.io` service, the AI initially attempted to use an `apikey` header and force the base currency to `base=USD`. I knew this would cause 401 and 105 (Restricted Plan) errors on the legacy free tier. I explicitly overrode the AI, instructing it to revert to the `access_key` query parameter and dynamically extract the base currency (usually `EUR`) from the API payload to use in the cross-pair math logic.

## 4. One Thing the AI Got Wrong (and How I Caught It)

* **The Bug:** During test generation, the AI assumed the `balances` table used a composite primary key consisting of `(customer_id, currency)`. It subsequently wrote balance validation tests using `await db.get(Balance, (customer_id, Currency.USD))`. 
* **How I Caught It:** I ran the test suite, which immediately exploded with an `InvalidRequestError`. I realized the AI had hallucinated the schema design (the table actually used an auto-incrementing UUID as the primary key, with a unique index on the customer/currency pair). I instructed the AI to rewrite its test assertions to use standard `select(Balance).where(...)` ORM queries instead.

## 5. What I Refused to Trust Without Verifying

* **Financial Mathematics:** I did not trust the AI to accurately perform base-10 financial math using standard unit tests. AI models are notoriously bad at catching floating-point precision boundaries. To verify its logic, I forced it to write a **Property-Based Testing suite using `Hypothesis`**, which fuzzed the application with thousands of arbitrary, multi-decimal floats to explicitly prove the `to_minor_units` logic handled Banker's Rounding perfectly across edge cases.
* **Concurrency Locking:** I didn't take the AI's word that its `execute_quote` method was race-condition safe. I explicitly had it write `test_execution_concurrency.py`, leveraging `asyncio.gather` to fire 10 simultaneous HTTP requests against a single quote to physically verify that Postgres locked the row and successfully rejected exactly 9 of the requests with HTTP 409 Conflicts.
