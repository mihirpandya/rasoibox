import logging
import re

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


class Invitation(BaseModel):
    email: str
    zipcode: str

    @validator('zipcode')
    def validate_zipcode(cls, zipcode: str) -> str:
        pattern = r"^\d{5}$"
        if bool(re.match(pattern, zipcode)):
            return zipcode
        logger.error("Invalid zip code: %d", zipcode)
        raise ValidationError("Invalid zip code.")
