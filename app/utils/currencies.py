from enum import StrEnum


class Currency(StrEnum):
    USD = "USD"
    EUR = "EUR"
    KES = "KES"
    NGN = "NGN"


# Minor units (decimal places) per currency
CURRENCY_DECIMALS: dict[Currency, int] = {
    Currency.USD: 2,
    Currency.EUR: 2,
    Currency.KES: 2,
    Currency.NGN: 2,
}

# Pairs that require USD routing (no direct market rate available)
CROSS_PAIRS_VIA_USD: set[tuple[Currency, Currency]] = {
    (Currency.KES, Currency.NGN),
    (Currency.NGN, Currency.KES),
}

# All supported pairs (direct + inverses + cross)
SUPPORTED_PAIRS: set[tuple[Currency, Currency]] = {
    (Currency.USD, Currency.EUR),
    (Currency.EUR, Currency.USD),
    (Currency.USD, Currency.KES),
    (Currency.KES, Currency.USD),
    (Currency.USD, Currency.NGN),
    (Currency.NGN, Currency.USD),
    (Currency.EUR, Currency.KES),
    (Currency.KES, Currency.EUR),
    (Currency.EUR, Currency.NGN),
    (Currency.NGN, Currency.EUR),
    (Currency.KES, Currency.NGN),
    (Currency.NGN, Currency.KES),
}
