"""
Decimal arithmetic helpers.

All arithmetic uses Decimal with 28 sig-fig precision.
Rounding mode: ROUND_HALF_EVEN (banker's rounding), applied ONCE at the final
step when converting a Decimal result to integer minor units.
"""

from decimal import ROUND_HALF_EVEN, Decimal, getcontext

from app.utils.currencies import CURRENCY_DECIMALS, Currency

getcontext().prec = 28


def to_minor_units(amount: Decimal, currency: Currency) -> int:
    """Convert a Decimal amount to integer minor units (e.g. 1.005 USD → 101 cents)."""
    decimals = CURRENCY_DECIMALS[currency]
    quantize_str = Decimal(10) ** -decimals  # e.g. Decimal("0.01") for 2 dp
    rounded = amount.quantize(quantize_str, rounding=ROUND_HALF_EVEN)
    return int(rounded * (10**decimals))


def from_minor_units(amount_minor: int, currency: Currency) -> Decimal:
    """Convert integer minor units back to a Decimal."""
    decimals = CURRENCY_DECIMALS[currency]
    return Decimal(amount_minor) / Decimal(10**decimals)


def apply_spread(mid_rate: Decimal, spread_bps: int) -> Decimal:
    """
    Return the sell rate (customer sells source currency):
        sell_rate = mid_rate * (1 - spread_bps / 10000)
    """
    return mid_rate * (Decimal(1) - Decimal(spread_bps) / Decimal(10_000))


def compose_cross_rate(
    rate_a_to_usd: Decimal,
    rate_usd_to_b: Decimal,
    spread_bps: int,
) -> Decimal:
    """
    Compound two-leg rate for A→USD→B, each leg with its own spread.
    No rounding between legs; caller rounds the final output amount once.
    """
    leg1 = rate_a_to_usd * (Decimal(1) - Decimal(spread_bps) / Decimal(10_000))
    leg2 = rate_usd_to_b * (Decimal(1) - Decimal(spread_bps) / Decimal(10_000))
    return leg1 * leg2
