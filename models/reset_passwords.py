from sqlalchemy import Column, Integer, String, Boolean, DateTime

from models.base import Base


class ResetPassword(Base):
    __tablename__ = "reset_passwords"

    id = Column(Integer, primary_key=True)
    email = Column(String(100))
    reset_code = Column(String(100))
    reset_date = Column(DateTime)
    reset_complete = Column(Boolean)
