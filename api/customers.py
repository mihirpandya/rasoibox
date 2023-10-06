import logging
import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, validator, ValidationError

logger = logging.getLogger(__name__)


class CustomerPayload(BaseModel):
    email: str
    password: str
    first_name: str
    last_name: str
    zipcode: str
    join_date: datetime
    verification_code: str

    @validator('email')
    def validate_email(cls, email_address: str) -> str:
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if bool(re.match(pattern, email_address)):
            clean_email = email_address.lower()
            clean_email = clean_email.strip()
            return clean_email
        logger.error("Malformed email address: %s", email_address)
        raise ValidationError("Malformed email address.")

    @validator('first_name')
    def validate_first_name(cls, first_name: str) -> str:
        clean_name = first_name.strip()
        clean_name = clean_name.capitalize()
        return clean_name

    @validator('last_name')
    def validate_last_name(cls, last_name: str) -> str:
        clean_name = last_name.strip()
        clean_name = clean_name.capitalize()
        return clean_name

    class Config:
        orm_mode = True


class UpdateCustomerPayload(BaseModel):
    email: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]

    @validator('email')
    def validate_email(cls, email_address: str) -> str:
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if bool(re.match(pattern, email_address)):
            clean_email = email_address.lower()
            clean_email = clean_email.strip()
            return clean_email
        logger.error("Malformed email address: %s", email_address)
        raise ValidationError("Malformed email address.")

    @validator('first_name')
    def validate_first_name(cls, first_name: str) -> str:
        clean_name = first_name.strip()
        clean_name = clean_name.capitalize()
        return clean_name

    @validator('last_name')
    def validate_last_name(cls, last_name: str) -> str:
        clean_name = last_name.strip()
        clean_name = clean_name.capitalize()
        return clean_name

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


class CreateAccountFromIntentPayload(BaseModel):
    create_id: int
    payment_intent: str
    password: str
