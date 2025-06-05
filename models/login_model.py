from pydantic import BaseModel, EmailStr
from typing import Optional

class LoginUser(BaseModel):
    email:EmailStr
    password:str
