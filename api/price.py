import logging
import re
from typing import Optional, List

from pydantic import BaseModel, validator, ValidationError

logger = logging.getLogger(__name__)


class RecipeServingPrice(BaseModel):
    recipe_name: str
    serving_size: int
    price: float

    @validator('serving_size')
    def validate_serving_size(cls, serving_size: int) -> int:
        valid_serving_sizes = [2, 4, 6]
        if serving_size not in valid_serving_sizes:
            raise ValidationError("Invalid serving size.")
        return serving_size


class ReferredEmails(BaseModel):
    referred_emails: List[str]

    @validator('referred_emails')
    def validate_referred_emails(cls, referred_emails: List[str]) -> List[str]:
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        clean_emails: List[str] = []
        for email in referred_emails:
            if bool(re.match(pattern, email)):
                clean_email = email.lower()
                clean_email = clean_email.strip()
                clean_emails.append(clean_email)
            else:
                logger.error("Malformed email address: %s", email)
                raise ValidationError("Malformed email address.")
        return clean_emails


class Invitation(BaseModel):
    referred_emails: ReferredEmails
    referrer_email: str
    referrer_verification_code: Optional[str]

    @validator('referrer_email')
    def validate_referrer_email(cls, referrer_email: str) -> str:
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if bool(re.match(pattern, referrer_email)):
            clean_email = referrer_email.lower()
            clean_email = clean_email.strip()
            return clean_email
        logger.error("Malformed email address: %s", referrer_email)
        raise ValidationError("Malformed email address.")
