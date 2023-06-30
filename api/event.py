from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SiteEvent(BaseModel):
    event_date: datetime
    verification_code: Optional[str]
    event_type: str
    referrer: Optional[str]

    class Config:
        orm_mode = True


class RecipeEvent(BaseModel):
    event_date: datetime
    verification_code: Optional[str]
    event_type: str
    recipe_id: int
    serving_size: int
    step_number: int
    referrer: Optional[str]

    class Config:
        orm_mode = True
