from fastapi import HTTPException


class FXError(HTTPException):
    """Base FX engine error."""


class QuoteExpired(FXError):
    def __init__(self, quote_id: str) -> None:
        super().__init__(
            status_code=409, detail={"code": "QUOTE_EXPIRED", "quote_id": quote_id}
        )


class QuoteAlreadyExecuted(FXError):
    def __init__(self, quote_id: str) -> None:
        super().__init__(
            status_code=409,
            detail={"code": "QUOTE_ALREADY_EXECUTED", "quote_id": quote_id},
        )


class QuoteNotFound(FXError):
    def __init__(self, quote_id: str) -> None:
        super().__init__(
            status_code=404, detail={"code": "QUOTE_NOT_FOUND", "quote_id": quote_id}
        )


class InsufficientFunds(FXError):
    def __init__(self, currency: str, available: int, required: int) -> None:
        super().__init__(
            status_code=422,
            detail={
                "code": "INSUFFICIENT_FUNDS",
                "currency": currency,
                "available_minor": available,
                "required_minor": required,
            },
        )


class RatesUnavailable(FXError):
    def __init__(self, reason: str = "No sufficiently fresh rate available") -> None:
        super().__init__(
            status_code=503, detail={"code": "RATES_UNAVAILABLE", "reason": reason}
        )


class UnsupportedPair(FXError):
    def __init__(self, from_ccy: str, to_ccy: str) -> None:
        super().__init__(
            status_code=422,
            detail={
                "code": "UNSUPPORTED_PAIR",
                "from_currency": from_ccy,
                "to_currency": to_ccy,
            },
        )
