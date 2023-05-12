from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SiteEvent(BaseModel):
    event_date: datetime
    verification_code: str
    event_type: str
    referrer: Optional[str]

    class Config:
        orm_mode = True
