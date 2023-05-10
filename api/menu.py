from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class MenuEvent(BaseModel):
    menu_date: datetime
    verification_code: str
    referrer: Optional[str]

    class Config:
        orm_mode = True
