from pydantic import BaseModel

class ExecuteRequest(BaseModel):
    quote_id: str
    customer_id: str
    idempotency_key: str
