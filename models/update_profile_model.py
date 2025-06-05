from pydantic import BaseModel, HttpUrl
from typing import List, Optional, Dict
from datetime import datetime

class UpdateUserProfile(BaseModel):
    fName: Optional[str] = None
    lName: Optional[str] = None
    profile_picture_url: Optional[HttpUrl] = None