import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from models.event import Event

logger = logging.getLogger("rasoibox")


def emit_event(db: Session, event_type: str, event_timestamp: datetime, code: str, referrer_opt: Optional[str]):
    try:
        referrer = referrer_opt if referrer_opt is not None else "NONE"
        event = Event(event_type=event_type, event_timestamp=event_timestamp, code=code, referrer=referrer)
        db.add(event)
        db.commit()
    except Exception as e:
        logger.error("Failed to save event.")
        logger.error(e)
        return
