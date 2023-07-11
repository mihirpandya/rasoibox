import logging
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


class Invitation(BaseModel):
    referred_emails: ReferredEmails
    referrer_email: str
    referrer_verification_code: Optional[str]
