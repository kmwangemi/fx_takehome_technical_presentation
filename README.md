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

Make sure your `.env` contains the `DATABASE_URL` pointing to your PostgreSQL instance, as well as any other necessary configuration settings.
```
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/fx_engine
```

### 3. Setup Database

Create the database in your PostgreSQL instance:
```sql
CREATE DATABASE fx_engine;
```

Run Alembic migrations to set up the schema:
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
- `GET /healthz` — Health check
- `GET /metrics` — Prometheus metrics (or structured logs)

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
