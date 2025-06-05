from pydantic import BaseModel, EmailStr, HttpUrl, Field
from typing import List, Optional, Dict
from datetime import datetime


class UserProfile(BaseModel):
    fName: Optional[str]
    lName: Optional[str]
    email: Optional[EmailStr]
    profile_picture_url: Optional[HttpUrl] = None
    member_since: Optional[datetime] = None
    bookListed: Optional[int] = 0
    exchangeBook: Optional[int] = 0
    book_collection: Optional[List[Dict]] = []
    activity: Optional[List[Dict]] = []
