import pytest
from decimal import Decimal, getcontext, ROUND_HALF_EVEN
from hypothesis import given, settings
from hypothesis.strategies import integers, decimals, floats

from app.utils.decimal import to_minor_units, from_minor_units, apply_spread, compose_cross_rate
from app.utils.currencies import Currency

getcontext().prec = 28

@given(decimals(min_value=Decimal("0.01"), max_value=Decimal("1000000000.0"), places=4))
def test_to_minor_units_rounding(amount: Decimal):
    """
    Test that to_minor_units applies ROUND_HALF_EVEN correctly.
    """
    # e.g., 100.005 EUR -> 10000 minor units
    # e.g., 100.015 EUR -> 10002 minor units (banker's rounding)
    
    # We'll just test that it returns an integer and the calculation matches standard Decimal quantize
    minor = to_minor_units(amount, Currency.USD)
    
    expected = amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN) * 100
    assert minor == int(expected)

@given(integers(min_value=1, max_value=1_000_000_000))
def test_from_minor_units(amount_minor: int):
    """
    Test conversion from minor units to Decimal is exact.
    """
    result = from_minor_units(amount_minor, Currency.USD)
    assert result == Decimal(amount_minor) / Decimal('100')
    
@given(
    decimals(min_value=Decimal("0.0001"), max_value=Decimal("10000.0"), places=6),
    integers(min_value=0, max_value=1000)
)
def test_apply_spread(mid_rate: Decimal, spread_bps: int):
    """
    Test spread application is mathematically sound and doesn't lose precision.
    """
    spread_factor = Decimal(1) - (Decimal(spread_bps) / Decimal(10_000))
    expected = mid_rate * spread_factor
    
    result = apply_spread(mid_rate, spread_bps)
    assert result == expected

@given(
    decimals(min_value=Decimal("0.0001"), max_value=Decimal("10000.0"), places=6),
    decimals(min_value=Decimal("0.0001"), max_value=Decimal("10000.0"), places=6),
    integers(min_value=0, max_value=1000)
)
def test_compose_cross_rate(rate_a_usd: Decimal, rate_usd_b: Decimal, spread_bps: int):
    """
    Test compounding of cross rates with spread.
    """
    result = compose_cross_rate(rate_a_usd, rate_usd_b, spread_bps)
    
    spread_factor = Decimal(1) - (Decimal(spread_bps) / Decimal(10_000))
    expected_leg1 = rate_a_usd * spread_factor
    expected_leg2 = rate_usd_b * spread_factor
    expected_total = expected_leg1 * expected_leg2
    
    assert result == expected_total

def test_bankers_rounding_edge_cases():
    """Explicitly test the edge cases of Banker's rounding for minor units."""
    # .005 -> rounds down to even .00 (0 cents)
    assert to_minor_units(Decimal("0.005"), Currency.USD) == 0
    
    # .015 -> rounds up to even .02 (2 cents)
    assert to_minor_units(Decimal("0.015"), Currency.USD) == 2
    
    # .025 -> rounds down to even .02 (2 cents)
    assert to_minor_units(Decimal("0.025"), Currency.USD) == 2
    
    # .035 -> rounds up to even .04 (4 cents)
    assert to_minor_units(Decimal("0.035"), Currency.USD) == 4
