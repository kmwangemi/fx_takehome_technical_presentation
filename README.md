# FX Engine — Take-Home Assignment

## Overview

This project is a foreign exchange (FX) engine that handles currency conversions between USD, EUR, KES, and NGN, with per-customer balance accounts. It is built using Python, FastAPI, and PostgreSQL.

## Tech Stack

- **FastAPI** — Web framework
- **SQLAlchemy 2.0** — ORM (async)
- **Alembic** — Database migrations
- **PostgreSQL** — Database
- **asyncpg** — Async PostgreSQL driver
- **uv** — Package manager

---

## Setup

### 1. Clone and install dependencies

Ensure you have [uv](https://docs.astral.sh/uv/) installed.

```bash
uv sync
```

### 2. Configure environment

This project uses [Neon](https://neon.tech/) as the PostgreSQL database provider. You can quickly set up a free serverless Postgres database on Neon.

Make sure your `.env` contains the following environment variables. You can copy these examples and replace them with your actual values:

```env
# Database (Neon PostgreSQL examples)
# Note: SYNC_DATABASE_URL is used specifically by Alembic for synchronous database migrations (see alembic/env.py)
DATABASE_URL="postgresql+asyncpg://user:password@ep-example-host.aws.neon.tech/dbname?ssl=require"
SYNC_DATABASE_URL="postgresql+psycopg2://user:password@ep-example-host.aws.neon.tech/dbname?sslmode=require"

# App
APP_ENV="development"
APP_NAME="FX Engine System API"
APP_VERSION="1.0.0"

# Rates API
EXCHANGE_RATES_API_KEY="your_api_key_here"
EXCHANGE_RATES_API_URL="https://api.exchangeratesapi.io/v1/latest"

# Spread & rates config
DEFAULT_SPREAD_BPS=50
RATE_POLL_INTERVAL_SECONDS=3600
MAX_RATE_STALENESS_SECONDS=7200
RATE_FETCH_TIMEOUT_SECONDS=5

# Quote TTL
QUOTE_TTL_SECONDS=60
```

### 3. Setup Database

Once your Neon database is created and your `.env` is configured with the correct connection strings, run Alembic migrations to set up the schema:
```bash
uv run alembic upgrade head
```

### 4. Run the Server

```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
API docs will be available at: http://localhost:8000/docs

---

## Running Tests

Run the test suite using `pytest`:

```bash
uv run pytest -v
```
*Tests validate core requirements, including atomic two-leg execution, idempotent retry protection, concurrent execution safety, and correct decimal rounding operations.*

---

## API Endpoints Summary

### Customers
- `POST /api/v1/customers` — Create a customer
- `GET /api/v1/customers/{id}/balances` — View balances per currency
- `POST /api/v1/customers/{id}/balances/credit` — Manually credit a balance (Test fixture only)

### Quotes & Executions
- `POST /api/v1/quotes` — Generate an FX quote
- `POST /api/v1/executions` — Execute an FX transaction using a quote ID and idempotency key

### Observability

- **Health Checks**: `GET /healthz` — Basic health check endpoint.
- **Metrics**: `GET /metrics` — Prometheus metrics tracking quote generations, execution latencies, and rate staleness.
- **Structured Logging**: The application uses `structlog` for JSON-formatted logs.
- **Correlation IDs**: Every quote generates a `correlation_id` which is carried forward into the execution phase, allowing distributed tracing of a single customer's transaction flow from quote to execution.

**Example Structured Log Output**:
```json
{
  "event": "execute.success",
  "quote_id": "550e8400-e29b-41d4-a716-446655440000",
  "customer_id": "cust_12345",
  "correlation_id": "8755b76b-967f-4318-874e-030a5fb291fc",
  "from_currency": "USD",
  "to_currency": "KES",
  "from_amount_minor": 10000,
  "to_amount_minor": 1300000,
  "level": "info",
  "timestamp": "2026-06-12T03:55:00.000Z"
}
```

---

## Known Limitations

- **Authentication/Authorization**: Omitted per the assignment's constraints.
- **Fees**: Fixed spread percentage applies; there are no dynamic or asymmetric spreads based on customer tiers.
- **Rate Source Polling**: Poller might be centralized; a production environment would prefer distributed task queues (e.g. Celery).

## What I'd Do With More Time

1. **Load Testing**: Use tools like Locust or k6 to robustly test concurrency limits and transaction isolation behavior under peak load.
2. **Distributed Task Queue**: Move rate ingestion into a more robust background worker system like Celery or Temporal.
3. **Advanced Tracing**: Integrate OpenTelemetry fully for detailed trace contexts linking `quote` and `execution` flows, and a Grafana dashboard.
4. **Enhanced Rate Features**: Introduce multi-tier spreads, more dynamic currency routing rules, and real-time WebSocket feeds for quotes.
5. **Database Partitioning**: As `idempotency_records` and `executions` tables grow, implement time-based partitioning for optimal lookup performance.
