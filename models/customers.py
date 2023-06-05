from sqlalchemy import Column, Integer, String, DateTime, Boolean

from models.base import Base


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True)
    first_name = Column(String(100))
    last_name = Column(String(100))
    email = Column(String(100))
    hashed_password = Column(String(1000))
    verified = Column(Boolean)
    join_date = Column(DateTime)
