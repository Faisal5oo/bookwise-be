from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from enum import Enum

class InteractionType(str, Enum):
    VIEW = "view"
    FAVORITE = "favorite"
    EXCHANGE_REQUEST = "exchange_request"
    SHARE = "share"

class ReadingStats(BaseModel):
    user_id: str
    books_read: int = 0
    pages_read: int = 0
    authors_explored: int = 0
    top_genres: List[str] = []
    reading_habits: dict = {}
    updated_at: datetime = datetime.utcnow()

class BookInteraction(BaseModel):
    user_id: str
    book_id: str
    interaction_type: InteractionType
    timestamp: datetime = datetime.utcnow()
    metadata: Optional[dict] = None

class ReadingHabits(BaseModel):
    user_id: str
    average_books_per_month: float
    favorite_reading_time: Optional[str]
    preferred_genres: List[str]
    reading_streak: int
    total_reading_time: int  # in minutes
    last_updated: datetime = datetime.utcnow() 