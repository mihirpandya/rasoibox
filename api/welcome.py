from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class WelcomeEvent(BaseModel):
    welcome_date: datetime
    verification_code: str
    referrer: Optional[str]

    class Config:
        orm_mode = True
