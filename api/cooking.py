from datetime import datetime

from pydantic import BaseModel


class FinishCookingPayload(BaseModel):
    order_id: str
    recipe_id: int
    cook_date: datetime
