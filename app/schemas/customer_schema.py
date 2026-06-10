from pydantic import BaseModel

from app.utils.currencies import Currency


class CreateCustomerRequest(BaseModel):
    name: str


class CreditRequest(BaseModel):
    currency: Currency
    amount_minor: int
