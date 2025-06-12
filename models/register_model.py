from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime

class RegisterUser(BaseModel):
    email: EmailStr
    fName: str = Field(alias='fname')
    lName: str = Field(alias='lname')
    password: str
    created_at: Optional[datetime] = None
    
    class Config:
        populate_by_name = True
