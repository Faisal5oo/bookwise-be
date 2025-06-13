from pydantic import BaseModel, HttpUrl
from typing import List, Optional
from datetime import datetime

class PostBookModel(BaseModel):
    user_id: str 
    bookName: str
    authorName: str
    genre: str  # Added genre field
    description: Optional[str] = None
    bookCondition: str
    bookImages: List[HttpUrl] = []
    is_taken: Optional[bool] = False  
    created_at: Optional[datetime] = None 
