from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class UserPreferences(BaseModel):
    user_id: str
    favorite_genres: List[str] = []
    favorite_authors: List[str] = []
    reading_preferences: dict = {}
    updated_at: datetime = datetime.utcnow()

class AIRecommendation(BaseModel):
    user_id: str
    book_id: str
    match_percentage: float
    reason: str
    created_at: datetime = datetime.utcnow()

class BookTrending(BaseModel):
    book_id: str
    trend_score: float
    views_count: int
    exchange_requests_count: int
    updated_at: datetime = datetime.utcnow() 