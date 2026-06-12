from prometheus_client import Counter, Gauge, Histogram

# Quotes
quotes_created_total = Counter(
    "fx_quotes_created_total",
    "Total number of quotes generated",
    ["from_currency", "to_currency"],
)

# Executions
executions_total = Counter(
    "fx_executions_total",
    "Total number of execute attempts",
    ["status", "error_code"],  # status: success|failure ; error_code: "" if none
)

execution_latency_seconds = Histogram(
    "fx_execution_latency_seconds",
    "Latency of /executions requests",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)

# Rates
rate_fetch_total = Counter(
    "fx_rate_fetch_total",
    "Total rate-fetch attempts to upstream provider",
    ["status"],  # success|failure|timeout
)

rate_staleness_seconds = Gauge(
    "fx_rate_staleness_seconds",
    "Age of the most recently cached exchange rate, in seconds",
)
