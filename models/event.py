from sqlalchemy import Column, Integer, String, DateTime

from models.base import Base


class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True)
    event_type = Column(String(100))
    event_timestamp = Column(DateTime)
    referrer = Column(String(100))
    code = Column(String(100))


class RecipeEvent(Base):
    __tablename__ = "recipe_events"
    id = Column(Integer, primary_key=True)
    event_type = Column(String(100))
    event_timestamp = Column(DateTime)
    referrer = Column(String(100))
    code = Column(String(100))
