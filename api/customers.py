import logging
from datetime import datetime

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class CustomerPayload(BaseModel):
    email: str
    password: str
    first_name: str
    last_name: str
    zipcode: str
    join_date: datetime
    verification_code: str

    class Config:
        orm_mode = True


class ChangePasswordPayload(BaseModel):
    old_password: str
    new_password: str

    class Config:
        orm_mode = True


class ResetPasswordPayload(BaseModel):
    reset_code: str
    new_password: str

    class Config:
        orm_mode = True
