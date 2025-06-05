from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class RegisterUser(BaseModel):
    email:EmailStr
    fName : str
    lName : str
    password : str
    created_at: Optional[datetime] = None
