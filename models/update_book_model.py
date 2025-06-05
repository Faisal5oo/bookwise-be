from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict

class UpdateBookModel(BaseModel):
    bookName: Optional[str]
    authorName: Optional[str]
    description: Optional[str] = None
    bookCondition: Optional[str]
    bookImages: Optional[List[HttpUrl]] = []
    is_taken: Optional[bool] = False 