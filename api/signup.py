import logging
import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ValidationError, validator

logger = logging.getLogger(__name__)


class SignUpViaEmail(BaseModel):
    email: str
    zipcode: str
    signup_date: datetime
    verification_code: str
    referrer: Optional[str]

    class Config:
        orm_mode = True

    @validator('email')
    def validate_email(cls, email_address: str) -> str:
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if bool(re.match(pattern, email_address)):
            return email_address
        logger.error("Malformed email address: %s", email_address)
        raise ValidationError("Malformed email address.")

    @validator('zipcode')
    def validate_zipcode(cls, zipcode: str) -> str:
        pattern = r"^\d{5}$"
        if bool(re.match(pattern, zipcode)):
            return zipcode
        logger.error("Invalid zip code: %d", zipcode)
        raise ValidationError("Invalid zip code.")