import logging
import re
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, validator, ValidationError

logger = logging.getLogger(__name__)


class Address(BaseModel):
    street_name: str
    street_number: int
    apartment_number: Optional[int]
    city: str
    state: str
    zipcode: str

    class Config:
        orm_mode = True

    @validator('zipcode')
    def validate_zipcode(cls, zipcode: str) -> str:
        pattern = r"^\d{5}$"
        if bool(re.match(pattern, zipcode)):
            return zipcode
        logger.error("Invalid zip code: %d", zipcode)
        raise ValidationError("Invalid zip code.")


class Order(BaseModel):
    order_date: datetime
    recipe_names: List[str]
    recipient_first_name: str
    recipient_last_name: str
    delivery_address: Address
    phone_number: str
    coupons: List[str]

    class Config:
        orm_mode = True

    @validator('phone_number')
    def validate_phone_number(cls, phone_number: str) -> str:
        pattern = r"^\d{10}$"
        if bool(re.match(pattern, phone_number)):
            return phone_number
        logger.error("Invalid phone number: %d", phone_number)
        raise ValidationError("Invalid phone number.")


class CartItem(BaseModel):
    recipe_name: str
    serving_size: int

    @validator('serving_size')
    def validate_serving_size(cls, serving_size: int) -> int:
        valid_serving_sizes = [0, 2, 4, 6]
        if serving_size not in valid_serving_sizes:
            raise ValidationError("Invalid serving size.")
        return serving_size


class PricedCartItem(BaseModel):
    recipe_name: str
    image_url: str
    serving_size: int
    price: float

    @validator('serving_size')
    def validate_serving_size(cls, serving_size: int) -> int:
        valid_serving_sizes = [0, 2, 4, 6]
        if serving_size not in valid_serving_sizes:
            raise ValidationError("Invalid serving size.")
        return serving_size
