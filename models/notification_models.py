from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

class NotificationType(str, Enum):
    EXCHANGE_REQUEST = "exchange_request"
    EXCHANGE_RESPONSE = "exchange_response"
    EXCHANGE_COMPLETED = "exchange_completed"
    BOOK_AVAILABLE = "book_available"
    SYSTEM_UPDATE = "system_update"
    NEW_RECOMMENDATION = "new_recommendation"

class Notification(BaseModel):
    user_id: str
    type: NotificationType
    title: str
    message: str
    data: Optional[Dict[str, Any]] = None
    read: bool = False
    created_at: datetime = datetime.utcnow()

class NotificationPreferences(BaseModel):
    user_id: str
    email_notifications: bool = True
    push_notifications: bool = True
    notification_types: Dict[NotificationType, bool] = {} 