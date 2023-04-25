from sqlalchemy import Column, Integer, String, DateTime

from models.base import Base


class UnverifiedUser(Base):
    __tablename__ = "unverified_users"
    id = Column(Integer, primary_key=True)
    first_name = Column(String(100))
    last_name = Column(String(100))
    email = Column(String(100))
    signup_date = Column(DateTime)
    signup_from = Column(String(100))
    zipcode = Column(Integer)
    verification_code = Column(String(100))


class VerifiedUser(Base):
    __tablename__ = "verified_users"

    id = Column(Integer, primary_key=True)
    first_name = Column(String(100))
    last_name = Column(String(100))
    email = Column(String(100))
    signup_date = Column(DateTime)
    signup_from = Column(String(100))
    join_date = Column(DateTime)
    zipcode = Column(Integer)
    verification_code = Column(String(100))
