from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from enum import Enum

class GenreEnum(str, Enum):
    FANTASY = "Fantasy"
    SCIENCE_FICTION = "Science Fiction"
    MYSTERY = "Mystery"
    THRILLER = "Thriller"
    CLASSIC = "Classic"
    ROMANCE = "Romance"
    BIOGRAPHY = "Biography"
    HISTORY = "History"
    PHILOSOPHY = "Philosophy"
    ADVENTURE = "Adventure"

class BookLengthEnum(str, Enum):
    SHORT = "Short"
    MEDIUM = "Medium"
    LONG = "Long"

class WritingStyleEnum(str, Enum):
    SIMPLE = "Simple"
    MODERATE = "Moderate"
    COMPLEX = "Complex"

class PublicationEraEnum(str, Enum):
    CLASSIC = "Classic"
    MODERN = "Modern"
    CONTEMPORARY = "Contemporary"

class ReadingPreferences(BaseModel):
    book_length: Optional[BookLengthEnum] = None
    writing_style: Optional[WritingStyleEnum] = None
    publication_era: Optional[PublicationEraEnum] = None

class UserPreferences(BaseModel):
    user_id: str
    favorite_genres: List[GenreEnum] = []
    favorite_authors: List[str] = []
    reading_preferences: ReadingPreferences = ReadingPreferences()
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