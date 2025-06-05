from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum

class ExchangeStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class ExchangeRequest(BaseModel):
    requester_id: str
    book_id: str
    owner_id: str
    message: Optional[str]
    status: ExchangeStatus = ExchangeStatus.PENDING
    created_at: datetime = datetime.utcnow()

class ExchangeResponse(BaseModel):
    exchange_id: str
    response_type: ExchangeStatus
    message: Optional[str]
    created_at: datetime = datetime.utcnow()

class ExchangeDetails(BaseModel):
    id: str
    requester_id: str
    book_id: str
    owner_id: str
    message: Optional[str]
    status: ExchangeStatus
    created_at: datetime
    response: Optional[ExchangeResponse] = None 