from sqlalchemy import Column, Integer, String, DateTime

from models.base import Base


class UnverifiedUser(Base):
    __tablename__ = "unverified_users"
    id = Column(Integer, primary_key=True)
    first_name = Column(String)
    last_name = Column(String)
    email = Column(String)
    signup_date = Column(DateTime)
    signup_from = Column(String)
    zipcode = Column(Integer)
    verification_code = Column(String)


class VerifiedUser(Base):
    __tablename__ = "verified_users"

    id = Column(Integer, primary_key=True)
    first_name = Column(String)
    last_name = Column(String)
    email = Column(String)
    signup_date = Column(DateTime)
    signup_from = Column(String)
    join_date = Column(DateTime)
    zipcode = Column(Integer)
